# DAG 파일: 운영용 초기 데이터 적재 (수동 실행 전용)
"""
TradeSmartAI 초기 데이터 적재 DAG

이 DAG는 운영자가 필요할 때 수동으로 과거 데이터를 대량 적재하기 위한 용도입니다.
Airflow UI의 "Trigger DAG with config" 기능을 통해 파라미터를 받아 실행됩니다.

Task 구조:
1. stock_info_load_task: 종목 정보 수집 (전제조건)
2. initial_load_task: 차트 데이터 수집 (메인 작업)

지원 모드:
1. 단일 작업 모드: 특정 종목의 특정 타임프레임만 적재
2. 특정 종목 전체 모드: 특정 종목의 모든 타임프레임 적재
3. 일괄 작업 모드: 모든 타겟 종목의 모든 타임프레임 적재 (총 150개 작업)

사용 예시:
- 단일 작업: {"stock_code": "005930", "timeframe": "d", "period": "2y"}
- 특정 종목 전체: {"stock_code": "005930", "period": "2y"}
- 일괄 작업: {"run_all_targets": true, "period": "2y"}
"""

import time
import pendulum
import json
import logging
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
from airflow.models.param import Param
from airflow.models import Variable

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import load_initial_history, create_simulation_snapshot
from src.database import SessionLocal, Stock, Sector
from src.kiwoom_api.services.master import get_sector_list
from sqlalchemy.dialects.postgresql import insert

            

# 지원하는 타임프레임 목록
TARGET_TIMEFRAMES = ['5m', '30m', '1h', 'd', 'w', 'mon']

# 타임프레임별 조회 기간 설정
TIMEFRAME_PERIOD_MAP = {
    '5m': '3M',   # 5분봉은 최근 3개월
    '30m': '6M',  # 30분봉은 최근 6개월
    '1h': '1y',   # 1시간봉은 최근 1년
    'd': '5y',    # 일봉은 5년
    'w': '10y',   # 주봉은 10년
    'mon': '10y', # 월봉은 10년 (RS 계산에 필수)
}
# ---------------------------------------------

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,  # 초기 적재는 재시도 최소화
    'retry_delay': pendulum.duration(minutes=5),  # 재시도 간 5분 대기
}

# dags/dag_initial_loader.py

def _run_stock_info_load_task(**kwargs):
    """
    (통합 로직) 외부 API와 DB의 전체 종목 마스터를 동기화합니다.
    dag_daily_batch와 동일한 표준 함수를 호출하여 데이터 정책의 일관성을 보장합니다.
    """
    import logging
    from src.database import SessionLocal
    # sync_stock_master_to_db를 직접 임포트하여 사용
    from src.master_data_manager import sync_stock_master_to_db

    logger = logging.getLogger(__name__)
    logger.info("표준 동기화 함수(sync_stock_master_to_db)를 호출하여 종목 마스터를 동기화합니다.")

    db_session = SessionLocal()
    try:
        # 이 Task는 DB 상태를 변경하는 것이 유일한 목적이므로, 반환값은 사용하지 않습니다.
        sync_stock_master_to_db(db_session)
        logger.info("종목 마스터 동기화가 성공적으로 완료되었습니다.")
    except Exception as e:
        logger.error(f"종목 마스터 동기화 중 오류 발생: {e}", exc_info=True)
        raise
    finally:
        db_session.close()


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


def _determine_target_stocks_task(**kwargs):
    """
    초기 적재 대상을 결정하고 '제로 필터'를 적용하여 XCom으로 전달합니다.
    """
    from src.master_data_manager import get_filtered_initial_load_targets

    config = kwargs.get('dag_run').conf if kwargs.get('dag_run') else {}
    test_stock_codes_param = config.get('test_stock_codes')

    db_session = SessionLocal()
    try:
        # 수정 제안: 수동 모드에서도 제로 필터링 적용
        if test_stock_codes_param:
            user_codes = [code.strip() for code in test_stock_codes_param.split(',') if code.strip()]
            # ✅ get_filtered_initial_load_targets에 사용자 지정 종목 전달
            target_codes = get_filtered_initial_load_targets(db_session, user_codes)
            logging.info(f"사용자 지정 종목 {len(user_codes)}개 중 {len(target_codes)}개가 필터링 후 처리됩니다.")
        else:
            # 자동 모드: DB 조회 및 제로 필터 적용
            target_codes = get_filtered_initial_load_targets(db_session)
            logging.info(f"자동 필터링된 최종 대상 종목: {len(target_codes)}개")

        return target_codes
    finally:
        db_session.close()


def _run_initial_load_task(db_session=None, **kwargs):
    """
    파라미터를 읽어 LIVE 모드에서는 초기 적재를,
    SIMULATION 모드에서는 DB 스냅샷 생성을 수행합니다.
    """
    config = kwargs.get('dag_run').conf if kwargs.get('dag_run') else {}
    execution_mode = config.get('execution_mode', 'LIVE')
    logger = logging.getLogger(__name__)
    logger.info(f"🎯 _run_initial_load_task 시작: mode={execution_mode}")

    # 1. 'target_datetime' 결정 (지능형 기본값 로직 추가)
    target_datetime_str = config.get('target_datetime')
    if not target_datetime_str and execution_mode == 'LIVE':
        target_datetime_str = _calculate_default_target_datetime()
        logger.info(f"LIVE 모드에서 기준 시점이 지정되지 않아, '{target_datetime_str}'로 자동 설정합니다.")

    # --- DB Session Management ---
    session_owner = False
    if execution_mode != 'SIMULATION':
        if db_session is None:
            db_session = SessionLocal()
            session_owner = True

    try:
        if execution_mode == 'SIMULATION':
            # --- SIMULATION 모드: 데이터 스냅샷 준비 ---

            test_stock_codes_str = config.get('test_stock_codes', '')
            target_datetime_str = config.get('target_datetime')

            if not test_stock_codes_str or not target_datetime_str:
                raise AirflowException(
                    "SIMULATION 모드에서는 'test_stock_codes'와 'target_datetime' 파라미터가 반드시 필요합니다."
                )

            user_stock_codes = [code.strip() for code in test_stock_codes_str.split(',') if code.strip()]

            # 1. [신규] RS 계산에 필요한 모든 코드를 자동으로 추가합니다.
            db = SessionLocal()
            try:
                # [변경] 모든 업종 대신 필요한 업종만 조회
                from src.utils.sector_mapper import get_necessary_sector_codes
                user_sector_codes = get_necessary_sector_codes(db, user_stock_codes)
                market_index_codes = {'001', '101'}
                all_necessary_codes = list(set(user_stock_codes) | user_sector_codes | market_index_codes)
                logger.info(f"RS 계산 및 테스트를 위해 {len(all_necessary_codes)}개 관련 코드만 처리합니다.")
            finally:
                db.close()

            # 2. 데이터 스냅샷 생성 함수 호출 (통합된 코드 리스트 사용)
            snapshot_result = create_simulation_snapshot(
                stock_codes=all_necessary_codes,
                execution_time=target_datetime_str
            )

            if snapshot_result.get('status') != 'completed':
                raise AirflowException(f"❌ SIMULATION 스냅샷 생성 실패: {snapshot_result.get('error')}")

            # 3. Airflow Variable 저장 (사용자 입력 종목 기준)
            snapshot_meta = {
                "snapshot_time": target_datetime_str,
                "stock_codes": user_stock_codes, # Variable에는 사용자가 명시한 종목만 기록
                "timeframes": snapshot_result["timeframes"],
                "prepared_at": datetime.now().isoformat(),
                "total_rows": snapshot_result["total_rows"],
                "status": snapshot_result["status"]
            }
            Variable.set("simulation_snapshot_info", json.dumps(snapshot_meta))
            logger.info(f"✅ SIMULATION 스냅샷 생성 완료: {target_datetime_str} ({snapshot_result['total_rows']}행)")
            return

        else:
            # --- LIVE 모드: 기존 초기 적재 로직 (수정) ---
            logger.info("Starting LIVE mode initial loading process.")

            # 'target_datetime'을 'base_date' (YYYYMMDD) 형식으로 변환
            base_date = None
            if target_datetime_str:
                try:
                    base_date = datetime.strptime(target_datetime_str, '%Y-%m-%d %H:%M:%S').strftime('%Y%m%d')
                except ValueError:
                    raise AirflowException(f"target_datetime 형식이 잘못되었습니다. 'YYYY-MM-DD HH:MM:SS' 형식을 사용해주세요.")

            # --- LIVE 모드: 대상 선정 로직을 XCom PULL로 대체 ---
            logger.info("LIVE 모드: XCom에서 대상 종목 리스트를 가져옵니다.")
            ti = kwargs['ti']
            target_stocks = ti.xcom_pull(task_ids='determine_target_stocks_task')

            if not target_stocks:
                print("처리할 대상 종목이 없습니다. 작업을 종료합니다.")
                return

            # [기존 로직 유지] 공통 파라미터 추출
            timeframes_to_process = config.get('timeframes', ['5m', '30m', '1h', 'd', 'w', 'mon'])

            # 3. 작업 실행 로직
            print(f'\n{'='*60}')
            print(f'🚀 LIVE 모드로 초기 적재 작업을 시작합니다.')
            print(f'📊 대상 종목 수: {len(target_stocks)}개')
            print(f'⏰ 타임프레임: {timeframes_to_process}')
            print(f'📅 기준 시점: {target_datetime_str or '자동 계산됨'}')
            print(f'📆 기간: 타임프레임별 최적화된 기간 사용')
            print(f'🔧 실행 모드: {execution_mode}')
            print(f'{'='*60}\n')

            success_count = 0
            fail_count = 0
            total_tasks = len(target_stocks) * len(timeframes_to_process)
            current_task = 0

            logger = logging.getLogger(__name__)
            logger.info("업종 마스터 데이터 준비를 시작합니다.")
            all_sectors = get_sector_list()
            if all_sectors:
                stmt = insert(Sector).values(all_sectors)
                update_stmt = stmt.on_conflict_do_update(
                    index_elements=['sector_code'],
                    set_={'sector_name': stmt.excluded.sector_name, 'market_name': stmt.excluded.market_name}
                )
                db_session.execute(update_stmt)
                db_session.commit()
                logger.info(f"{len(all_sectors)}개 업종 마스터 데이터 준비 완료.")
            else:
                logger.warning("API로부터 업종 데이터를 가져오지 못했습니다.")

            # --- [수정] 기준 데이터(지수, 업종) 적재 로직 ---
            logger.info("기준 데이터(지수, 업종)의 과거 일/주/월봉 적재를 시작합니다.")
            index_codes = ['001', '101']

            # [핵심 수정] target_stocks (XCom으로 받은 최종 대상) 유무에 따라 분기
            if target_stocks:
                # 수동 모드(test_stock_codes 지정)로 실행된 경우, 해당 종목의 업종만 조회
                from src.utils.sector_mapper import get_necessary_sector_codes
                sector_codes = list(get_necessary_sector_codes(db_session, target_stocks))
                logger.info(f"LIVE(수동 모드): 지정된 종목과 관련된 {len(sector_codes)}개 업종 데이터만 수집합니다.")
            else:
                # 자동 모드(test_stock_codes 미지정)인 경우, 전체 업종 조회
                sector_codes = [s.sector_code for s in db_session.query(Sector.sector_code).all()]
                logger.info(f"LIVE(자동 모드): 전체 {len(sector_codes)}개 업종 데이터를 수집합니다.")

            baseline_codes = index_codes + sector_codes

            # 기준 데이터 레코드가 stocks 테이블에 존재하도록 보장
            baseline_stock_info = [{'stock_code': code, 'stock_name': 'BASELINE_DATA', 'is_active': True, 'backfill_needed': False} for code in baseline_codes]
            stmt = insert(Stock).values(baseline_stock_info)
            db_session.execute(stmt.on_conflict_do_nothing(index_elements=['stock_code']))
            db_session.commit()

            # 처리할 타임프레임 목록 정의
            baseline_timeframes = ['d', 'w', 'mon']

            # [개선] 에러 카운팅을 통한 안정성 확보
            error_count = 0
            total_baseline_tasks = len(baseline_codes) * len(baseline_timeframes)

            for code in baseline_codes:
                for timeframe in baseline_timeframes:
                    try:
                        # [개선] TIMEFRAME_PERIOD_MAP 변수의 존재 여부를 확인하는 방어적 코드
                        if 'TIMEFRAME_PERIOD_MAP' in globals():
                            period = TIMEFRAME_PERIOD_MAP.get(timeframe, '10y')
                        else:
                            # TIMEFRAME_PERIOD_MAP이 없는 경우를 대비한 안전장치
                            period = '10y' if timeframe == 'mon' else '5y'

                        load_initial_history(
                            stock_code=code,
                            timeframe=timeframe,
                            period=period,
                            execution_mode=execution_mode
                        )
                        # [개선] API Rate Limiting 강화
                        time.sleep(0.5)
                    except Exception as e:
                        error_count += 1
                        # [개선] 에러 로그에 timeframe 정보 추가
                        logger.error(f"기준 데이터 적재 중 오류: {code} ({timeframe}) - {e}", exc_info=True)
                        continue

            # [개선] 에러율이 30%를 초과하면 DAG 실패 처리
            if total_baseline_tasks > 0 and (error_count / total_baseline_tasks) > 0.3:
                raise AirflowException(f"너무 많은 기준 데이터 적재에 실패했습니다. (총 {total_baseline_tasks}개 중 {error_count}개 실패)")

            logger.info("기준 데이터 과거 일/주/월봉 적재 완료.")

            for stock_code in target_stocks:
                all_success = True
                for timeframe in timeframes_to_process:
                    current_task += 1
                    # 타임프레임별 최적화된 기간 조회
                    period_for_timeframe = TIMEFRAME_PERIOD_MAP.get(timeframe, '1y')
                    print(f"\n[{current_task}/{total_tasks}] 처리 중: {stock_code} - {timeframe} (기간: {period_for_timeframe})")
                    try:
                        success = load_initial_history(
                            stock_code=stock_code, timeframe=timeframe, base_date=base_date, period=period_for_timeframe, execution_mode=execution_mode
                        )
                        if success:
                            success_count += 1
                            print(f"✅ 성공: {stock_code} - {timeframe}")
                        else:
                            fail_count += 1
                            all_success = False
                            print(f"⚠️ 데이터 없음:{stock_code} - {timeframe}")
                    except Exception as e:
                        fail_count += 1
                        all_success = False
                        print(f"❌ 실패: {stock_code} - {timeframe}: {str(e)}")
                    time.sleep(0.3) # API 서버 보호
                
                if all_success:
                    db_session.query(Stock).filter(Stock.stock_code == stock_code).update({"backfill_needed": False})
                    db_session.commit()
                    print(f"'{stock_code}' 백필 완료. backfill_needed=False로 업데이트.")

            # --- [신규 최종 단계] 4. 적재된 종목에 대한 업종 코드 백필 ---
            try:
                from src.master_data_manager import backfill_sector_codes
                logger.info("초기 적재된 종목에 대한 업종 코드 매핑(백필)을 시작합니다.")
                backfill_sector_codes()
                logger.info("업종 코드 매핑(백필) 완료.")
            except Exception as e:
                logger.error(f"초기 적재 후 업종 코드 백필 중 오류 발생: {e}", exc_info=True)

            # 4. 최종 결과 출력 (이하 생략)

    finally:
        if execution_mode != 'SIMULATION' and session_owner:
            db_session.close()

    # 4. 최종 결과 출력
    print(f"\n{'='*60}")
    print(f"🎯 초기 적재 완료")
    print(f"✅ 성공: {success_count}개")
    print(f"❌ 실패/데이터 없음: {fail_count}개")
    print(f"📊 전체: {total_tasks}개")
    print(f"{'='*60}\n")

    if fail_count > total_tasks * 0.3:
        raise AirflowException(f"너무 많은 작업({fail_count}/{total_tasks})이 실패했습니다.")

# DAG 정의
with DAG(
    dag_id='dag_initial_loader',
    default_args=DEFAULT_ARGS,
    schedule_interval=None,  # 수동 실행 전용 (매우 중요!)
    start_date=pendulum.datetime(2025, 7, 1, tz="Asia/Seoul"),
    catchup=False,
    tags=['Utility', 'Backfill', 'Manual'],
    description='[유틸리티] 과거 데이터 대량 적재 (초기 구축 및 데이터 백필용)',
    params={
        "test_stock_codes": Param(
            type=["null", "string"],
            default=None,
            title="[테스트용] 특정 종목 대상 실행",
            description="종목코드를 입력하세요. 여러 종목은 쉼표(,)로 구분합니다. (예: 005930,000660)"
        ),
        "stock_limit": Param(
            type="integer",
            default=0,
            title="종목 수 제한 (0=제한 없음)",
            description="테스트 목적으로 처리할 종목 수를 제한합니다. 0 또는 음수이면 필터링된 전체 종목을 처리합니다."
        ),
        "timeframes": Param(
            type=["null", "array"],
            default=['5m', '30m', '1h', 'd', 'w', 'mon'],
            title="타임프레임 목록",
            description="수집할 타임프레임 목록을 지정합니다. 비워두면 기본 6개 타임프레임(5m, 30m, 1h, d, w, mon)을 모두 수집합니다."
        ),
        "execution_mode": Param(
            type="string",
            default="LIVE",
            title="실행 모드",
            description="LIVE: API로 초기 적재, SIMULATION: DB 스냅샷 생성",
            enum=["LIVE", "SIMULATION"]
        ),
        "target_datetime": Param(
            type=["null", "string"],
            default="",
            title="기준 시점 (YYYY-MM-DD HH:MM:SS)",
            description="[LIVE 모드] 초기 적재의 종료 시점. 비워두면 가장 최근 거래일 기준으로 자동 설정됩니다. [SIMULATION 모드] 스냅샷 생성의 기준 시점 (필수 입력)."
        )
    },
    doc_md="""
    ### [유틸리티] 과거 데이터 대량 적재 DAG

    이 DAG는 시스템을 최초로 구축하거나, 특정 종목의 과거 데이터를 보강(백필)해야 할 때 **수동으로 실행**하는 관리용 도구입니다.

    #### 실행 모드
    - **자동 모드 (기본)**: `test_stock_codes` 파라미터를 비워두고 실행하면, DB에서 `backfill_needed=True`로 표시된 모든 종목을 자동으로 찾아 과거 데이터를 적재합니다.
    - **수동 모드**: `test_stock_codes`에 종목코드를 입력하여 특정 종목의 과거 데이터만 선별적으로 적재합니다. 신규 관심 종목 추가나 데이터 유실 시 복구 용도로 사용합니다.

    **주의**: 이 DAG는 대량의 API 호출을 유발할 수 있으므로, 신중하게 사용해야 합니다.
    """
) as dag:
    
    # 단일 Task: 종목 정보 적재
    stock_info_load_task = PythonOperator(
        task_id='stock_info_load_task',
        python_callable=_run_stock_info_load_task,
        provide_context=True,
        # Pool 제거: 종목 정보 적재는 API 호출이 아니므로 Pool 불필요
        doc_md="""
        ### 종목 정보 적재 Task
        
        이 Task는 종목 정보를 DB에 적재하는 작업입니다.
        이는 차트 데이터 수집의 전제조건이며, 대량 데이터 적재 작업을 시작하기 전에 반드시 실행되어야 합니다.
        
        **주의**: 이 Task는 대량 데이터 적재 작업보다 훨씬 빠르게 완료됩니다.
        """
    )
    
    # 대상 종목 선정 Task 추가
    determine_target_stocks_task = PythonOperator(
        task_id='determine_target_stocks_task',
        python_callable=_determine_target_stocks_task,
        doc_md="""
        ### 대상 종목 선정 및 필터링 Task
        - **자동 모드**: `backfill_needed=True`인 종목을 조회하여 '제로 필터'를 적용합니다.
        - **수동 모드**: `test_stock_codes` 파라미터로 지정된 종목을 그대로 사용합니다.
        - **출력**: 최종 대상 종목 리스트를 XCom으로 전달합니다.
        """
    )
    
    # 단일 Task: 초기 데이터 적재
    initial_load_task = PythonOperator(
        task_id='initial_load_task',
        python_callable=_run_initial_load_task,
        provide_context=True,
        # Pool 제거: 순차 실행(for 문)이므로 Pool 불필요, 증분 업데이트 DAG에서 Pool 사용 예정
        doc_md="""
        ### 초기 데이터 적재 Task
        
        이 Task는 전달된 파라미터에 따라 세 가지 모드로 동작합니다:
        
        **1. 일괄 작업 모드 (run_all_targets=true)**
        - 30개 타겟 종목 × 5개 타임프레임 = 총 150개 작업 수행
        - 각 작업 사이에 0.3초 대기 (순차 실행으로 자연스러운 Rate Limiting)
        - 예상 소요 시간: 약 1시간
        
        **2. 특정 종목 전체 모드 (stock_code만 지정)**
        - 1개 종목 × 5개 타임프레임 = 총 5개 작업 수행
        - 각 작업 사이에 0.3초 대기
        
        **3. 단일 작업 모드 (stock_code + timeframe 지정)**
        - 1개 종목 × 1개 타임프레임 = 1개 작업 수행
        
        **공통 기능:**
        - 파라미터 검증
        - load_initial_history 함수 호출
        - 진행 상황 및 결과 로깅
        - 실패율이 30% 초과 시 DAG 실패 처리
        
        **Pool 사용 안 함**: 순차 실행이므로 Pool 불필요 (증분 업데이트 DAG에서 Pool 사용 예정)
        """
    )
    
    # 최종 의존성 설정
    stock_info_load_task >> determine_target_stocks_task >> initial_load_task 