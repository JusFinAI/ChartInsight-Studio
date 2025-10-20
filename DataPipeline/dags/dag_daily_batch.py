# /home/jscho/ChartInsight-Studio/DataPipeline/dags/dag_daily_batch.py

import pendulum
from airflow.models.dag import DAG
from airflow.models.param import Param
from airflow.operators.python import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.models import Variable
from airflow.exceptions import AirflowException
import logging

# import master_data_manager
from src.master_data_manager import sync_stock_master_to_db, update_analysis_target_flags
from src.data_collector import collect_and_store_candles
from src.analysis.rs_calculator import calculate_rs_for_stocks
from src.analysis.financial_analyzer import analyze_financials_for_stocks
from src.analysis.technical_analyzer import analyze_technical_for_stocks
from sqlalchemy.dialects.postgresql import insert
from src.database import SessionLocal, DailyAnalysisResult, FinancialAnalysisResult, Stock

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
    """Task 2: 저빈도(일/주/월) 캔들 최신 데이터 수집
    
    키움 API로부터 일/주/월봉의 최신 데이터를 증분 수집합니다.
    API가 제공하는 완성된 캔들 데이터를 신뢰하여 저장합니다.
    """
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)
    if execution_mode == 'SIMULATION':
        logger.info("SIMULATION 모드: 저빈도 캔들 수집을 건너뜁니다.")
        return

    # [수정] XCom 조회 대신 DB에서 직접 분석 대상 조회
    db = SessionLocal()
    try:
        target_codes_tuples = db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()
        stock_codes = [code for code, in target_codes_tuples]
    finally:
        db.close()

    if not stock_codes:
        logger.warning("DB에서 분석 대상 종목 리스트를 찾지 못했습니다. Task를 건너뜁니다.")
        return

    logger.info(f"총 {len(stock_codes)}개 종목에 대한 저빈도(일/주/월) 최신 캔들 데이터 수집을 시작합니다.")

    # 업데이트할 타임프레임 목록에 'mon' 추가
    timeframes_to_update = ['d', 'w', 'mon']

    success_count = 0
    fail_count = 0

    # get_managed_stocks_from_db는 항상 문자열 리스트를 반환합니다
    for i, stock_code in enumerate(stock_codes):
        for timeframe in timeframes_to_update:
            try:
                logger.info(f"[{i+1}/{len(stock_codes)}] {stock_code} ({timeframe}) 업데이트 중...")
                collect_and_store_candles(
                    stock_code=stock_code,
                    timeframe=timeframe,
                    execution_mode='LIVE'
                )
                success_count += 1
            except Exception as e:
                logger.error(f"'{stock_code}' ({timeframe}) 업데이트 중 오류 발생: {e}")
                fail_count += 1

    logger.info(f"저빈도 캔들 데이터 수집 완료. 성공: {success_count}, 실패: {fail_count}")

    if fail_count > len(stock_codes) * len(timeframes_to_update) * 0.5:
        raise ValueError("너무 많은 캔들 데이터 수집 작업에 실패했습니다.")




def _calculate_rs_score(**kwargs):
    """Task 4a: RS 점수 계산"""
    logger = logging.getLogger(__name__)
   

    ti = kwargs['ti']
    # execution_mode 전달을 위해 kwargs에서 읽어옵니다.
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')

    # Step 1: DB에서 직접 분석 대상 종목 리스트를 조회합니다.
    db = SessionLocal()
    try:
        target_codes_tuples = db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()
        filtered_codes = [code for code, in target_codes_tuples]
    finally:
        db.close()

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

    # Step 1: DB에서 직접 분석 대상 종목 리스트를 조회합니다.
    db = SessionLocal()
    try:
        target_codes_tuples = db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()
        filtered_codes = [code for code, in target_codes_tuples]
    finally:
        db.close()

    if not filtered_codes:
        logger.warning("DB에서 분석 대상 종목 리스트를 찾지 못했습니다. Task를 건너뜁니다.")
        return {}

    logger.info(f"총 {len(filtered_codes)}개 종목의 재무 등급을 DB에서 조회합니다.")

    # Step 2: DB에서 각 종목의 가장 최신 재무 분석 결과 조회
    db = SessionLocal()
    try:
        from sqlalchemy import func
        from sqlalchemy.sql import and_
        
        # 각 종목별로 가장 최신 analysis_date를 가진 레코드를 조회
        # Subquery: 종목별 최신 날짜
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

    # Step 1: DB에서 직접 분석 대상 종목 리스트를 조회합니다.
    db = SessionLocal()
    try:
        target_codes_tuples = db.query(Stock.stock_code).filter(Stock.is_analysis_target == True).all()
        filtered_codes = [code for code, in target_codes_tuples]
    finally:
        db.close()

    if not filtered_codes:
        logger.warning("DB에서 분석 대상 종목 리스트를 찾지 못했습니다. Task를 건너뜁니다.")
        return None

    logger.info(f"총 {len(filtered_codes)}개 종목에 대한 기술적 분석을 시작합니다.")

    # Step 2: 모듈화된 분석 함수 호출 (현재는 목업)
    technical_results = analyze_technical_for_stocks(stock_codes=filtered_codes, execution_mode=execution_mode)

    logger.info(f"기술적 분석 완료. {len(technical_results)}개 종목의 결과를 XCom으로 전달합니다.")

    # Step 3: 결과를 XCom으로 전달
    return technical_results


def _load_final_results(**kwargs):
    """Task 6: 모든 분석 결과를 `daily_analysis_results` 테이블에 적재"""
    execution_mode = kwargs.get('params', {}).get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)
    ti = kwargs['ti']
    # Airflow가 제공하는 논리적 실행일자 (logical_date)을 사용합니다.
    # 우선적으로 Airflow의 logical_date를 사용하되, 없으면 params.analysis_date를 사용합니다.
    logical_date = kwargs.get('logical_date') or kwargs.get('params', {}).get('analysis_date')
    
    # params.analysis_date가 빈 문자열이면 현재 시각을 사용
    if not logical_date:
        import pendulum
        logical_date = pendulum.now('UTC')
        logger.info(f"analysis_date 파라미터가 없어 현재 UTC 시각 사용: {logical_date}")
    
    # 문자열로 전달된 경우 pendulum으로 파싱
    if isinstance(logical_date, str):
        try:
            import pendulum
            logical_date = pendulum.parse(logical_date, tz='Asia/Seoul')
            logger.info(f"analysis_date 파싱 성공: {logical_date}")
        except Exception as e:
            # 파싱 실패 시 DAG 실행을 중단하여 데이터 오염 방지
            error_msg = f"analysis_date 파라미터 '{logical_date}' 파싱 실패: {e}. " \
                       f"올바른 날짜 형식(YYYY-MM-DD 또는 YYYYMMDD)을 사용하거나 비워두십시오."
            logger.error(error_msg)
            raise AirflowException(error_msg)

    # Step 1: 모든 병렬 Task로부터 분석 결과(딕셔너리)를 XCom으로 받기
    rs_results = ti.xcom_pull(task_ids='calculate_core_metrics.calculate_rs_score', key='return_value') or {}
    financial_results = ti.xcom_pull(task_ids='calculate_core_metrics.fetch_financial_grades_from_db', key='return_value') or {}
    technical_results = ti.xcom_pull(task_ids='run_technical_analysis', key='return_value') or {}

    if not (rs_results or financial_results or technical_results):
        logger.warning("모든 분석 결과를 XCom으로부터 받지 못했습니다. Task를 건너뜁니다.")
        return

    # Step 2: 분석 기준일을 Date로 정규화 (중복 적재 방지)
    # logical_date는 pendulum.DateTime 또는 datetime이 될 수 있으므로 날짜 부분만 사용합니다.
    try:
        if hasattr(logical_date, 'date'):
            analysis_date_only = logical_date.date()
        else:
            # fallback: parse string or use current date
            from datetime import datetime
            import pendulum
            if isinstance(logical_date, str):
                analysis_date_only = pendulum.parse(logical_date, tz='Asia/Seoul').date()
            elif isinstance(logical_date, datetime):
                analysis_date_only = logical_date.date()
            else:
                analysis_date_only = pendulum.now('Asia/Seoul').date()
    except Exception:
        import pendulum
        analysis_date_only = pendulum.now('Asia/Seoul').date()

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
    # analysis_date: 기본값을 비워 둡니다. 빈값일 경우 실제 실행 시 현재 UTC 시각을 분석 날짜로 사용합니다.
    # 사용자가 날짜를 특정하면 해당 날짜(Asia/Seoul 기준)로 파싱하여 사용합니다.
    "analysis_date": Param(
        type=["null", "string"],
        default="",
        title="분석 기준일 (YYYY-MM-DD)",
        description="분석의 기준이 될 날짜. 비워두면 Airflow의 논리적 실행일(logical_date)을 사용합니다."
    ),
        # execution_mode 파라미터를 UI에서 선택 가능하도록 정의
        "execution_mode": Param(
            type="string",
            default="LIVE",
            title="Execution Mode",
            description="파이프라인의 실행 모드를 선택합니다. (LIVE: 실제 API/DB, SIMULATION: 로컬 파일)",
            enum=["LIVE", "SIMULATION"],
        ),
        # 테스트용: 특정 종목만 빠르게 실행할 수 있는 파라미터
        "target_stock_codes": Param(
            type=["null", "array"],
            default=[],
            title="[테스트용] 특정 종목 대상 실행",
            description="여기에 종목 코드 리스트를 제공하면, 해당 종목들만 대상으로 분석을 실행합니다. (예: [\"005930\", \"000660\"])"
        ),
        # (Deprecated) 기존의 run_for_all_filtered_stocks, sample_stock_codes 파라미터 제거됨
    },
    # 스케줄을 Variable로 관리하면 운영 중 UI에서 변경 가능
    schedule_interval=Variable.get('daily_batch_schedule', default_var='0 17 * * 1-5'),
    start_date=pendulum.datetime(2025, 10, 1, tz="Asia/Seoul"),
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
        선행 Task로부터 XCom으로 활성 종목 리스트를 받아, '필터 제로'를 적용하여
        is_analysis_target 플래그를 업데이트합니다.
        """
        logger = logging.getLogger(__name__)
        ti = kwargs['ti']

        # 1. 선행 Task로부터 XCom으로 전체 활성 종목 코드 리스트를 받음
        all_active_codes = ti.xcom_pull(task_ids='sync_stock_master')
        if not all_active_codes:
            logger.warning("XCom으로부터 활성 종목 리스트를 받지 못했습니다. Task를 건너뜁니다.")
            return {"status": "skipped", "updated_count": 0}

        logger.info(f"XCom으로부터 {len(all_active_codes)}개의 활성 종목 리스트를 받았습니다.")

        db = SessionLocal()
        try:
            # 2. 받은 리스트를 인자로 전달하여 DB 플래그 업데이트
            update_count = update_analysis_target_flags(db, all_active_codes)
            logger.info(f"총 {update_count}개 종목의 플래그가 업데이트되었습니다.")
            return {"status": "completed", "updated_count": update_count}
        finally:
            db.close()

    update_analysis_target_flags_task = PythonOperator(
        task_id='update_analysis_target_flags',
        python_callable=_update_analysis_target_flags_task,
        doc_md="""
        #### Task: Update Analysis Target Flags
        - 목적: `Stock` 테이블의 모든 활성 종목에 '필터 제로'를 적용하여 `is_analysis_target` 플래그를 업데이트합니다.
        - 출력: XCom(작업 요약)
        """,
    )

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

    # --- 5. Task 의존성 설정 ---
    # 종목 마스터 동기화가 가장 먼저 실행되도록 의존성 설정
    run_technical_analysis_task = PythonOperator(
        task_id='run_technical_analysis',
        python_callable=_run_technical_analysis,
        doc_md="""
        #### Task: Run Technical Analysis
        - 목적: 기술적 지표/패턴 분석
        """,
    )
    sync_stock_master_task >> update_analysis_target_flags_task
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

