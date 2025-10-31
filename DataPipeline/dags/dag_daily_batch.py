# /home/jscho/ChartInsight-Studio/DataPipeline/dags/dag_daily_batch.py

import pendulum
import json
import logging
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from airflow.models.dag import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import BranchPythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.exceptions import AirflowException

# import master_data_manager
from src.master_data_manager import sync_stock_master_to_db, update_analysis_target_flags
from src.data_collector import collect_and_store_candles, load_initial_history
from src.analysis.rs_calculator import calculate_rs_for_stocks
from src.analysis.financial_analyzer import analyze_financials_for_stocks
from src.analysis.technical_analyzer import analyze_technical_for_stocks
from sqlalchemy.dialects.postgresql import insert
from src.database import SessionLocal, DailyAnalysisResult, FinancialAnalysisResult, Stock, Sector
import time

def _calculate_default_target_datetime() -> str:
    """
    LIVE 모드의 target_datetime 기본값을 동적으로 계산합니다.
    - 장 마감 후: 오늘 날짜의 16:00
    - 장 중/전: 직전 거래일의 16:00
    """
    kst = ZoneInfo('Asia/Seoul')
    now_kst = datetime.now(kst)
    trading_end_time = dt_time(15, 30)

    target_date = now_kst.date()

    # 장 마감 시간 이전이면, 날짜를 하루 전으로 설정
    if now_kst.time() < trading_end_time:
        target_date -= timedelta(days=1)

    # 주말 처리: 토요일(5)이면 금요일로, 일요일(6)이면 금요일로 이동
    if target_date.weekday() == 5:  # Saturday
        target_date -= timedelta(days=1)
    elif target_date.weekday() == 6:  # Sunday
        target_date -= timedelta(days=2)

    # 최종 기준 시점을 오후 4시로 설정
    default_dt = datetime.combine(target_date, dt_time(16, 0), tzinfo=kst)
    return default_dt.strftime('%Y-%m-%d %H:%M:%S')


# --- 검증 함수 추가 ---
def _validate_simulation_snapshot(**kwargs):
    """
    SIMULATION 모드에서, 파라미터가 없으면 Variable에서 기준 시점을 자동 감지하고,
    파라미터가 있으면 Variable의 시점과 일치하는지 검증합니다.
    """
    logger = logging.getLogger(__name__)
    params = kwargs.get('params', {})
    execution_mode = params.get('execution_mode', 'LIVE')

    if execution_mode != 'SIMULATION':
        logger.info("✅ LIVE 모드: 스냅샷 검증 건너뛰고 계속 진행")
        return 'continue_live_mode'

    logger.info("SIMULATION 모드: 스냅샷 유효성 검증을 시작합니다.")

    target_datetime = params.get('target_datetime')

    try:
        snapshot_json = Variable.get("simulation_snapshot_info")
        snapshot_info = json.loads(snapshot_json)
        snapshot_time = snapshot_info.get('snapshot_time')
    except KeyError:
        raise AirflowException(
            "SIMULATION 데이터 스냅샷이 준비되지 않았습니다. "
            "먼저 dag_initial_loader를 SIMULATION 모드로 실행하여 스냅샷을 생성해야 합니다."
        )

    # target_datetime이 없으면 Variable에서 자동 감지
    if not target_datetime:
        logger.info(f"target_datetime 파라미터가 비어있어, 스냅샷의 시간 '{snapshot_time}'로 자동 설정합니다.")
        target_datetime = snapshot_time
    else:
        # target_datetime이 있으면 Variable과 일치하는지 검증
        if target_datetime != snapshot_time:
            raise AirflowException(
                f"시점 불일치 오류! 분석하려는 시점({target_datetime})과 "
                f"준비된 데이터 스냅샷의 시점({snapshot_time})이 다릅니다. "
                f"dag_initial_loader를 올바른 execution_time으로 다시 실행하거나, "
                f"현재 DAG의 execution_time을 스냅샷 시점으로 변경하십시오."
            )

    logger.info(f"✅ 스냅샷 검증 통과 (시점: {target_datetime}). 'continue_simulation_mode' 경로로 진행합니다.")
    return 'continue_simulation_mode'

# --- 1. 기본 설정 ---
DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 2,
    'retry_delay': pendulum.duration(minutes=10),
}


# --- 2. 개별 Task 함수 정의 (플레이스홀더: 추후 실제 로직으로 교체) ---
def _sync_stock_master(**kwargs):
    """종목 마스터 정보 동기화 및 활성 종목 리스트 반환 Task
    
    DB의 live.stocks 테이블을 외부 API와 동기화하여 메타데이터를 최신 상태로 유지하고,
    후속 Task에서 사용할 활성 종목 리스트를 XCom으로 반환합니다.
    
    Returns:
        List[str]: 활성 종목 코드 리스트 (XCom으로 전달)
    """
    # params 컨텍스트에서 execution_mode 값 읽기
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)

    if execution_mode == 'SIMULATION':
        logger.info("SIMULATION 모드: `sync_stock_master`를 건너뜁니다 (독립 유지보수 Task).")
        return None  # 명시적으로 None 반환

    logger.info("LIVE 모드: `sync_stock_master`를 실행합니다.")
    # DB 세션 주입을 통해 메타데이터 동기화를 수행하고, 활성 종목 리스트를 XCom으로 반환합니다.
    db = SessionLocal()
    try:
        active_codes = sync_stock_master_to_db(db)
        logger.info(f"sync_stock_master_to_db 반환된 활성 종목 개수: {len(active_codes) if active_codes else 0}")
        # XCom으로 활성 종목 리스트를 반환
        return active_codes
    finally:
        db.close()


def _fetch_latest_low_frequency_candles(**kwargs):
    """Task 3: 저빈도(일/주/월) 캔들 데이터 증분 수집"""
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)
    
    # SIMULATION 모드에서는 데이터 수집을 건너뜁니다.
    if execution_mode == 'SIMULATION':
        logger.info("✅ SIMULATION 모드: 데이터 수집을 건너뜁니다 (dag_initial_loader가 이미 준비).")
        return
    
    ti = kwargs['ti']
    # Step 1: '게이트키퍼' Task로부터 최종 대상 목록을 XCom으로 받습니다.
    _xcom_result = ti.xcom_pull(task_ids='update_analysis_target_flags', key='return_value') or {}
    if isinstance(_xcom_result, dict):
        stock_codes_from_xcom = _xcom_result.get('codes', [])
    elif isinstance(_xcom_result, list):
        stock_codes_from_xcom = _xcom_result
    else:
        stock_codes_from_xcom = []

    db = SessionLocal()
    try:
        # 2. 전체 '업종' 코드 조회
        sector_codes = {s.sector_code for s in db.query(Sector.sector_code).all()}
        # 3. '시장 지수' 코드 추가
        market_index_codes = {'001', '101'}
        # 4. XCom으로 받은 종목 리스트와 업종/지수 코드를 통합
        try:
            stock_set = set(stock_codes_from_xcom)
        except Exception:
            stock_set = set()

        all_codes_to_update = list(stock_set | sector_codes | market_index_codes)
    finally:
        db.close()

    if not all_codes_to_update:
        logger.warning("캔들 증분 업데이트 대상이 없습니다.")
        return

    logger.info(f"총 {len(all_codes_to_update)}개 대상에 대한 증분 캔들 수집을 시작합니다.")
    timeframes_to_update = ['d', 'w', 'mon']

    success_count = 0
    fail_count = 0

    for i, code in enumerate(all_codes_to_update):
        for timeframe in timeframes_to_update:
            try:
                logger.info(f"[{i+1}/{len(all_codes_to_update)}] {code} ({timeframe}) 증분 업데이트 중...")
                collect_and_store_candles(
                    stock_code=code,
                    timeframe=timeframe,
                    execution_mode=execution_mode
                )
                success_count += 1
            except Exception as e:
                logger.error(f"'{code}' ({timeframe}) 업데이트 중 오류 발생: {e}")
                fail_count += 1

    logger.info(f"저빈도 캔들 증분 수집 완료. 성공: {success_count}, 실패: {fail_count}")

    if fail_count > len(all_codes_to_update) * len(timeframes_to_update) * 0.5:
        raise ValueError("너무 많은 캔들 데이터 수집 작업에 실패했습니다.")



def _calculate_rs_score(**kwargs):
    """Task 4a: RS 점수 계산"""
    logger = logging.getLogger(__name__)
   

    ti = kwargs['ti']
    # execution_mode 전달을 위해 kwargs에서 읽어옵니다.
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')

    # Step 1: '게이트키퍼' Task로부터 최종 대상 목록을 XCom으로 받습니다.
    ti = kwargs['ti']
    _xcom_result = ti.xcom_pull(task_ids='update_analysis_target_flags', key='return_value') or {}
    if isinstance(_xcom_result, dict):
        filtered_codes = _xcom_result.get('codes', [])
    elif isinstance(_xcom_result, list):
        filtered_codes = _xcom_result
    else:
        filtered_codes = []

    if not filtered_codes:
        logger.warning("DB에서 분석 대상 종목을 찾지 못했습니다. Task를 건너뜁니다.")
        return None

    logger.info(f"총 {len(filtered_codes)}개 종목에 대한 RS 점수 계산을 시작합니다.")

    # Step 2: 모듈화된 분석 함수 호출 (현재는 목업)
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')
    rs_results = calculate_rs_for_stocks(stock_codes=filtered_codes, execution_mode=execution_mode)

    logger.info(f"RS 점수 계산 완료. {len(rs_results)}개 종목의 결과를 XCom으로 전달합니다.")

    # Step 3: 결과를 XCom으로 전달하여 다음 Task가 사용하도록 함
    return rs_results


def _fetch_financial_grades_from_db(**kwargs):
    """Task 4b: 재무 등급 조회 (DB에서 최신 데이터 가져오기)
    
    dag_financials_update에서 주간 단위로 생성한 financial_analysis_results 테이블로부터
    각 종목의 가장 최신 재무 분석 결과를 조회합니다.
    
    Returns:
        Dict[str, Dict]: 종목코드별 재무 분석 결과
        {
            'stock_code': {
                'eps_growth_yoy': float,
                'eps_annual_growth_avg': float,
                'financial_grade': str
            }
        }
    """
    logger = logging.getLogger(__name__)
    ti = kwargs['ti']

    # 실행 모드 확인 (SIMULATION에서는 simulation 스키마를 조회)
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')

    # Step 1: '게이트키퍼' Task로부터 최종 대상 목록을 XCom으로 받습니다.
    ti = kwargs['ti']
    _xcom_result = ti.xcom_pull(task_ids='update_analysis_target_flags', key='return_value') or {}
    if isinstance(_xcom_result, dict):
        filtered_codes = _xcom_result.get('codes', [])
    elif isinstance(_xcom_result, list):
        filtered_codes = _xcom_result
    else:
        filtered_codes = []

    if not filtered_codes:
        logger.warning("XCom으로부터 분석 대상 종목 리스트를 찾지 못했습니다. Task를 건너뜁니다.")
        return {}

    logger.info(f"총 {len(filtered_codes)}개 종목의 재무 등급을 DB에서 조회합니다.")

    # Step 2: DB에서 각 종목의 가장 최신 재무 분석 결과 조회
    db = SessionLocal()
    try:
        from sqlalchemy import func
        from sqlalchemy.sql import and_

        # 스키마 전환: SIMULATION 모드면 simulation 스키마에서 조회
        target_table = FinancialAnalysisResult.__table__
        original_schema = target_table.schema
        if execution_mode == 'SIMULATION':
            target_table.schema = 'simulation'
        try:
            # 각 종목별로 가장 최신 analysis_date를 가진 레코드를 조회
            latest_dates_subq = (
                db.query(
                    FinancialAnalysisResult.stock_code,
                    func.max(FinancialAnalysisResult.analysis_date).label('latest_date')
                )
                .filter(FinancialAnalysisResult.stock_code.in_(filtered_codes))
                .group_by(FinancialAnalysisResult.stock_code)
                .subquery()
            )

            # 실제 데이터 조회: 종목코드와 최신 날짜가 일치하는 레코드
            results = (
                db.query(FinancialAnalysisResult)
                .join(
                    latest_dates_subq,
                    and_(
                        FinancialAnalysisResult.stock_code == latest_dates_subq.c.stock_code,
                        FinancialAnalysisResult.analysis_date == latest_dates_subq.c.latest_date
                    )
                )
                .all()
            )
        finally:
            # 스키마 복원
            target_table.schema = original_schema

        # Step 3: 결과를 XCom 전달 형식으로 변환
        financial_results = {}
        for result in results:
            financial_results[result.stock_code] = {
                'eps_growth_yoy': float(result.eps_growth_yoy) if result.eps_growth_yoy is not None else None,
                'eps_annual_growth_avg': float(result.eps_annual_growth_avg) if result.eps_annual_growth_avg is not None else None,
                'financial_grade': result.financial_grade
            }

        logger.info(
            f"재무 등급 조회 완료. {len(financial_results)}개 종목의 결과를 XCom으로 전달합니다. "
            f"(조회 대상: {len(filtered_codes)}개, 미조회: {len(filtered_codes) - len(financial_results)}개)"
        )

        return financial_results

    except Exception as e:
        logger.error(f"재무 등급 조회 중 오류 발생: {e}", exc_info=True)
        return {}
    finally:
        db.close()


def _run_technical_analysis(**kwargs):
    """Task 5: 기술적 지표 및 패턴 분석"""
    logger = logging.getLogger(__name__)
    ti = kwargs['ti']
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')

    # Step 1: '게이트키퍼' Task로부터 최종 대상 목록을 XCom으로 받습니다.
    _xcom_result = ti.xcom_pull(task_ids='update_analysis_target_flags', key='return_value') or {}
    if isinstance(_xcom_result, dict):
        filtered_codes = _xcom_result.get('codes', [])
    elif isinstance(_xcom_result, list):
        filtered_codes = _xcom_result
    else:
        filtered_codes = []

    if not filtered_codes:
        logger.warning("XCom으로부터 분석 대상 종목 리스트를 찾지 못했습니다. Task를 건너뜁니다.")
        return None

    logger.info(f"총 {len(filtered_codes)}개 종목에 대한 기술적 분석을 시작합니다.")

    # Step 2: 모듈화된 분석 함수 호출 (현재는 목업)
    technical_results = analyze_technical_for_stocks(stock_codes=filtered_codes, execution_mode=execution_mode)

    logger.info(f"기술적 분석 완료. {len(technical_results)}개 종목의 결과를 XCom으로 전달합니다.")

    # Step 3: 결과를 XCom으로 전달
    return technical_results


def _load_final_results(**kwargs):
    """Task 6: 모든 분석 결과를 `daily_analysis_results` 테이블에 적재"""
    params = kwargs.get('params', {})
    execution_mode = params.get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)
    ti = kwargs['ti']

    # 1. 'target_datetime' 결정 (지능형/자동감지 로직 통합)
    target_datetime_str = params.get('target_datetime')

    if not target_datetime_str:
        if execution_mode == 'LIVE':
            target_datetime_str = _calculate_default_target_datetime()
            logger.info(f"LIVE 모드에서 기준 시점이 지정되지 않아, '{target_datetime_str}'로 자동 설정합니다.")
        elif execution_mode == 'SIMULATION':
            try:
                snapshot_json = Variable.get("simulation_snapshot_info")
                snapshot_info = json.loads(snapshot_json)
                target_datetime_str = snapshot_info.get('snapshot_time')
                logger.info(f"SIMULATION 모드에서 기준 시점이 지정되지 않아, 스냅샷의 시간 '{target_datetime_str}'로 자동 설정합니다.")
            except (KeyError, json.JSONDecodeError):
                 raise AirflowException("SIMULATION 모드 자동 감지 실패: 'simulation_snapshot_info' Variable을 찾을 수 없거나 형식이 잘못되었습니다.")

    if not target_datetime_str:
        raise AirflowException(f"{execution_mode} 모드에서 기준 시점(target_datetime)을 결정할 수 없습니다.")

    # 2. 'analysis_date' 추출 (기존 로직과 동일)
    try:
        analysis_date_only = datetime.strptime(target_datetime_str, '%Y-%m-%d %H:%M:%S').date()
    except ValueError:
        raise AirflowException(f"target_datetime 형식이 잘못되었습니다. 'YYYY-MM-DD HH:MM:SS' 형식을 사용해주세요.")

    logger.info(f"분석 결과 저장을 위한 최종 analysis_date: {analysis_date_only}")

    # Step 1: 모든 병렬 Task로부터 분석 결과(딕셔너리)를 XCom으로 받기
    rs_results = ti.xcom_pull(task_ids='calculate_core_metrics.calculate_rs_score', key='return_value') or {}
    financial_results = ti.xcom_pull(task_ids='calculate_core_metrics.fetch_financial_grades_from_db', key='return_value') or {}
    technical_results = ti.xcom_pull(task_ids='run_technical_analysis', key='return_value') or {}

    if not (rs_results or financial_results or technical_results):
        logger.warning("모든 분석 결과를 XCom으로부터 받지 못했습니다. Task를 건너뜁니다.")
        return

    # Step 3: 데이터 취합 (Aggregation)
    all_codes = set(rs_results.keys()) | set(financial_results.keys()) | set(technical_results.keys())

    records_to_upsert = []
    for code in all_codes:
        rs_data = rs_results.get(code, {})
        fin_data = financial_results.get(code, {})
        tech_data = technical_results.get(code, {})

        record = {
            "analysis_date": analysis_date_only,
            "stock_code": code,
            # RS 결과 매핑
            "market_rs_score": rs_data.get('market_rs_score') or rs_data.get('market_rs') or None,
            "sector_rs_score": rs_data.get('sector_rs_score') or rs_data.get('sector_rs') or None,
            # 재무 결과 매핑
            "eps_growth_yoy": fin_data.get('eps_growth_yoy'),
            "eps_annual_growth_avg": fin_data.get('eps_annual_growth_avg'),
            "financial_grade": fin_data.get('financial_grade'),
            # 기술적 분석 결과 매핑
            "sma_20_val": tech_data.get('sma_20'),
            "rsi_14_val": tech_data.get('rsi_14'),
            "pattern_daily": tech_data.get('pattern'),
        }
        records_to_upsert.append(record)

    if not records_to_upsert:
        logger.info("DB에 저장할 최종 분석 데이터가 없습니다.")
        return

    # Step 3: 데이터베이스에 UPSERT (execution_mode에 따라 스키마 선택)
    target_schema = 'simulation' if execution_mode == 'SIMULATION' else 'live'
    db = SessionLocal()
    try:
        logger.info(f"총 {len(records_to_upsert)}개의 최종 분석 결과를 '{target_schema}' 스키마의 DB에 동기화(UPSERT)합니다.")

        # SQLAlchemy 모델의 테이블 객체에 동적으로 스키마 설정
        target_table = DailyAnalysisResult.__table__
        target_table.schema = target_schema

        stmt = insert(target_table).values(records_to_upsert)

        # 충돌 발생 시 업데이트할 컬럼들 지정 (PK 제외)
        update_columns = {
            c.name: getattr(stmt.excluded, c.name)
            for c in target_table.columns
            if c.name not in ["analysis_date", "stock_code", "id"]
        }

        stmt = stmt.on_conflict_do_update(
            index_elements=['analysis_date', 'stock_code'],
            set_=update_columns
        )

        db.execute(stmt)
        db.commit()
        logger.info(f"'{target_schema}' 스키마에 DB 동기화 완료.")
    except Exception as e:
        db.rollback()
        logger.error(f"최종 분석 결과 저장 중 DB 오류 발생: {e}")
        raise
    finally:
        # 다른 Task에 영향을 주지 않도록 스키마를 기본값으로 복원
        DailyAnalysisResult.__table__.schema = 'live'
        db.close()


# --- 3. DAG 정의 ---
with DAG(
    dag_id='dag_daily_batch',
    default_args=DEFAULT_ARGS,
    params={
        "execution_mode": Param(
            type="string",
            default="LIVE",
            title="Execution Mode",
            description="실행 모드를 선택합니다. (LIVE: 실제 DB, SIMULATION: 스냅샷 DB)",
            enum=["LIVE", "SIMULATION"],
        ),
        "target_datetime": Param(
            type=["null", "string"],
            default="",
            title="기준 시점 (YYYY-MM-DD HH:MM:SS)",
            description="[LIVE 모드] 분석 기준 시점. 비워두면 가장 최근 거래일 기준으로 자동 설정됩니다. [SIMULATION 모드] 스냅샷의 기준 시점 (필수 입력)."
        ),
        "test_stock_codes": Param(
            type=["null", "string"],
            default="",
            title="[테스트용] 특정 종목 대상 실행",
            description="쉼표로 구분된 종목 코드를 입력하세요. (예: 005930,000660)"
        ),
    },
    # 스케줄을 Variable로 관리하면 운영 중 UI에서 변경 가능
    schedule_interval=Variable.get('daily_batch_schedule', default_var='0 17 * * 1-5'),
    #start_date=pendulum.datetime(2025, 10, 1, tz="Asia/Seoul"),
    start_date=pendulum.now('Asia/Seoul').subtract(hours=1),
    catchup=False,
    tags=['production', 'batch', 'daily'],
    description='매일 장 마감 후, 시장의 모든 핵심 데이터를 분석하고 집계하는 일일 배치 DAG',
    doc_md="""
    ### Daily Batch Analysis DAG

    이 DAG는 TRADING LAB 서비스의 핵심 데이터를 생성하는 일일 배치 파이프라인입니다.
    장 마감 후 실행되며, Task 단위로 모듈화된 분석 로직을 순차/병렬로 실행합니다.
    """,
) as dag:

    # --- 4. Task 생성 (전용 함수 연결, UI용 doc_md 포함) ---
    sync_stock_master_task = PythonOperator(
        task_id='sync_stock_master',
        python_callable=_sync_stock_master,
        doc_md="""
        #### Task: Master Data Synchronization
        - 목적: 전체 종목 마스터 정보를 동기화합니다.
        - 출력: XCom으로 전체 종목 코드 리스트 반환
        """,
    )

    fetch_latest_low_frequency_candles_task = PythonOperator(
        task_id='fetch_latest_low_frequency_candles',
        python_callable=_fetch_latest_low_frequency_candles,
        doc_md="""
        #### Task: Fetch Latest Low-frequency Candles
        - 목적: 키움 API로부터 일/주/월봉 최신 데이터를 증분 수집합니다.
        - 입력: XCom(get_managed_stocks_from_db)
        - 참고: API가 제공하는 완성된 캔들 데이터를 신뢰하여 저장합니다.
        """,
    )


    # (Removed) get_managed_stocks_task: no longer used after refactor

    # 기존 apply_analysis_filters_task는 제거되고, 대신 DB에 플래그를 업데이트하고 XCom을 반환하는 Task를 사용합니다.
    def _update_analysis_target_flags_task(**kwargs):
        """
        실행 대상 종목을 결정하고, '필터 제로'를 적용하여 is_analysis_target 플래그를 업데이트합니다.
        SIMULATION 모드에서는 Airflow Variable에서 대상 종목을 자동으로 감지할 수 있습니다.
        """
        logger = logging.getLogger(__name__)
        ti = kwargs['ti']
        params = kwargs.get('params', {})
        execution_mode = params.get('execution_mode', 'LIVE')
        test_stock_codes_param = params.get('test_stock_codes', "")

        db = SessionLocal()
        try:
            codes_to_process = []
            if test_stock_codes_param:
                # 1. 사용자가 test_stock_codes를 직접 입력한 경우: 제로 필터링 적용
                if isinstance(test_stock_codes_param, str):
                    user_codes = [c.strip() for c in test_stock_codes_param.split(',') if c.strip()]
                elif isinstance(test_stock_codes_param, (list, tuple)):
                    user_codes = [str(c).strip() for c in test_stock_codes_param if str(c).strip()]
                
                # ✅ 제로 필터링 적용하여 최종 대상 결정
                codes_to_process = user_codes  # 필터링은 update_analysis_target_flags 함수 내에서 수행
                logger.info(f"사용자 지정 종목 {len(user_codes)}개에 대해 제로 필터링을 적용합니다.")
            else:
                # 2. 사용자가 test_stock_codes를 비워둔 경우: 모드에 따라 동작 분기
                if execution_mode == 'SIMULATION':
                    # 2-A. SIMULATION 모드: Airflow Variable에서 자동 감지
                    logger.info("SIMULATION 모드에서 test_stock_codes가 비어있어, Airflow Variable에서 분석 대상을 자동 감지합니다.")
                    try:
                        snapshot_json = Variable.get("simulation_snapshot_info")
                        snapshot_info = json.loads(snapshot_json)
                        codes_to_process = snapshot_info.get('stock_codes', [])
                        if not codes_to_process:
                             raise AirflowException("Variable 'simulation_snapshot_info'에 'stock_codes'가 비어있습니다.")
                        logger.info(f"스냅샷에서 {len(codes_to_process)}개 종목을 분석 대상으로 설정합니다.")
                    except KeyError:
                        raise AirflowException("SIMULATION 데이터 스냅샷 정보(Variable 'simulation_snapshot_info')를 찾을 수 없습니다.")
                else:
                    # 2-B. LIVE 모드: 기존 방식대로 선행 Task(sync_stock_master)의 결과(XCom)를 사용
                    all_active_codes = ti.xcom_pull(task_ids='sync_stock_master')
                    if not all_active_codes:
                        logger.warning("XCom으로부터 활성 종목 리스트를 받지 못했습니다. Task를 건너뜁니다.")
                        return {"status": "skipped", "codes": [], "processed_count": 0}
                    codes_to_process = all_active_codes
                    logger.info(f"XCom으로부터 {len(codes_to_process)}개의 활성 종목 리스트를 받았습니다.")

            if not codes_to_process:
                logger.warning("처리할 대상 종목이 없습니다.")
                return {"status": "skipped", "codes": [], "processed_count": 0}

            # (이하 '필터 제로' 적용 및 최종 대상 확정 로직은 기존과 동일)
            # 3. 입력 검증: DB에 실제 존재하는 종목만 선별
            valid_codes = []
            missing_codes = []
            batch_size = 500
            for i in range(0, len(codes_to_process), batch_size):
                batch = codes_to_process[i:i+batch_size]
                existing = db.query(Stock.stock_code).filter(Stock.stock_code.in_(batch)).all()
                existing_set = {c for c, in existing}
                valid_codes.extend(list(existing_set))
                missing = [c for c in batch if c not in existing_set]
                missing_codes.extend(missing)

            if missing_codes:
                logger.warning(f"입력된 종목 중 DB에 존재하지 않는 코드 {len(missing_codes)}개: {missing_codes[:10]}{'...' if len(missing_codes)>10 else ''}")

            if not valid_codes:
                logger.warning("검증된 유효한 종목 코드가 없어 종료합니다.")
                return {"status": "skipped", "codes": [], "processed_count": 0, "missing": missing_codes}

            # 4. '필터 제로' 로직을 통해 is_analysis_target 플래그 업데이트 수행
            update_count = update_analysis_target_flags(db, valid_codes)

            # 5. 최종적으로 필터 제로를 통과한 종목만 다시 조회하여 XCom에 전달
            final_target_codes = []
            for i in range(0, len(valid_codes), batch_size):
                batch = valid_codes[i:i+batch_size]
                rows = db.query(Stock.stock_code).filter(Stock.stock_code.in_(batch), Stock.is_analysis_target == True).all()
                final_target_codes.extend([c for c, in rows])

            logger.info(f"플래그 업데이트: 입력 {len(codes_to_process)}개 → 필터 제로 통과 {len(final_target_codes)}개 (업데이트된 플래그 수: {update_count})")
            return {"status": "completed", "codes": final_target_codes, "processed_count": len(final_target_codes), "missing": missing_codes, "input_count": len(codes_to_process)}
        finally:
            db.close()

    update_analysis_target_flags_task = PythonOperator(
        task_id='update_analysis_target_flags',
        python_callable=_update_analysis_target_flags_task,
        trigger_rule='one_success',  # SIMULATION/LIVE 모드 분기에서 Task가 올바르게 실행되도록 설정
        doc_md="""
        #### Task: Update Analysis Target Flags
        - 목적: `Stock` 테이블의 모든 활성 종목에 '필터 제로'를 적용하여 `is_analysis_target` 플래그를 업데이트합니다.
        - 출력: XCom(작업 요약)
        """,
    )

    # NOTE: 기준 데이터 새로고침 Task는 초기 로더(dag_initial_loader)에 의해 처리되므로 삭제됨.

    with TaskGroup(group_id='calculate_core_metrics') as calculate_core_metrics_group:
        calculate_rs_task = PythonOperator(
            task_id='calculate_rs_score',
            python_callable=_calculate_rs_score,
            doc_md="""
            #### Sub-Task: Calculate RS Score
            - 목적: 시장/업종 상대강도 점수 계산
            """,
        )

        fetch_financial_grades_task = PythonOperator(
            task_id='fetch_financial_grades_from_db',
            python_callable=_fetch_financial_grades_from_db,
            doc_md="""
            #### Sub-Task: Fetch Financial Grades from DB
            - 목적: financial_analysis_results 테이블에서 최신 재무 등급 조회
            - 참고: 실제 재무 분석은 dag_financials_update에서 주간 단위로 수행
            """,
        )

    run_technical_analysis_task = PythonOperator(
        task_id='run_technical_analysis',
        python_callable=_run_technical_analysis,
        doc_md="""
        #### Sub-Task: Run Technical Analysis
        - 목적: 기술적 지표 및 패턴 분석
        """,
    )

    # --- 5. Task 의존성 설정 ---
    # 검증 Task 및 분기 Operator 추가
    validate_snapshot_task = BranchPythonOperator(
        task_id='validate_simulation_snapshot',
        python_callable=_validate_simulation_snapshot,
        doc_md="""
        #### Task: Validate Simulation Snapshot
        - 목적: SIMULATION 모드 실행 시, Airflow Variable에 저장된 스냅샷 정보와
          현재 DAG의 실행 파라미터가 일치하는지 검증합니다.
        - 출력: 분기 경로 (continue_simulation_mode 또는 continue_live_mode)
        """,
    )

    # 분기 처리를 위한 Empty Operators
    continue_live_mode_task = EmptyOperator(task_id='continue_live_mode')
    continue_simulation_mode_task = EmptyOperator(task_id='continue_simulation_mode')

    # 1. 검증 Task가 가장 먼저 실행된 후, 두 경로로 분기합니다.
    validate_snapshot_task >> [continue_live_mode_task, continue_simulation_mode_task]

    # 2. LIVE 모드 경로는 기존처럼 sync_stock_master_task를 실행합니다.
    continue_live_mode_task >> sync_stock_master_task
    sync_stock_master_task >> update_analysis_target_flags_task

    # 3. SIMULATION 모드 경로는 sync_stock_master_task를 건너뛰고,
    #    바로 update_analysis_target_flags_task로 연결됩니다.
    continue_simulation_mode_task >> update_analysis_target_flags_task

    # refresh_baseline_candles_task와 fetch_latest_low_frequency_candles_task는 서로 의존성이 없으므로 병렬 실행 가능
    update_analysis_target_flags_task >> fetch_latest_low_frequency_candles_task

    fetch_latest_low_frequency_candles_task >> [calculate_core_metrics_group, run_technical_analysis_task]
    # ensure load_final_results_task is defined before referencing it
    load_final_results_task = PythonOperator(
        task_id='load_final_results',
        python_callable=_load_final_results,
        doc_md="""
        #### Task: Load Final Results
        - 목적: 모든 분석 결과를 적재합니다.
        """,
    )

    [calculate_core_metrics_group, run_technical_analysis_task] >> load_final_results_task

