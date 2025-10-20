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
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from airflow.exceptions import AirflowException
from airflow.models.param import Param

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import load_initial_history
from src.database import SessionLocal, Stock
from src.master_data_manager import sync_stock_master_to_db
from src.utils.common_helpers import get_target_stocks, get_all_filtered_stocks

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,  # 초기 적재는 재시도 최소화
    'retry_delay': pendulum.duration(minutes=5),  # 재시도 간 5분 대기
}

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
        
def _run_initial_load_task(db_session=None, **kwargs):
    """
    Airflow UI의 "Trigger DAG with config"를 통해 전달된 파라미터를 읽어,
    대상을 선정한 후 load_initial_history 함수를 호출하는 어댑터 함수.
    """
    dag_run = kwargs.get('dag_run')
    config = dag_run.conf if dag_run and dag_run.conf else {}
    print(f"📋 입력받은 설정: {config}")

    # --- DB Session Management ---
    session_owner = False
    if db_session is None:
        db_session = SessionLocal()
        session_owner = True
    # -----------------------------

    try:
        # 1. 대상 종목 선정 로직
        target_stocks = []
        mode_description = ""
        if config.get('stock_codes'):
            mode_description = "🎯 '특정 종목' 모드"
            target_stocks = [code.strip() for code in config['stock_codes'].split(',') if code.strip()]
            print(f"수동 모드로 특정 종목에 대해 실행합니다: {target_stocks}")
        else:
            rows = db_session.query(Stock.stock_code).filter(Stock.is_active == True, Stock.backfill_needed == True).all()
            target_stocks = [r.stock_code for r in rows]
            mode_description = "🔥 '자동 모드(백필 대상 조회)'"
            print(f"자동 모드로 DB에서 백필 대상 {len(target_stocks)}건을 조회하여 실행합니다.")

        if not target_stocks:
            print("처리할 대상 종목이 없습니다. 작업을 종료합니다.")
            return

        # 2. 공통 파라미터 추출
        base_date = config.get('base_date')
        execution_mode = config.get('execution_mode', 'LIVE')
        timeframes_to_process = config.get('timeframes', ['5m', '30m', '1h', 'd', 'w', 'mon'])

        # 3. 작업 실행 로직
        print(f'\n{'='*60}')
        print(f'🚀 {mode_description}으로 초기 적재 작업을 시작합니다.')
        print(f'📊 대상 종목 수: {len(target_stocks)}개')
        print(f'⏰ 타임프레임: {timeframes_to_process}')
        print(f'📅 기준일: {base_date or '현재 날짜'}')
        print(f'📆 기간: 타임프레임별 최적화된 기간 사용')
        print(f'🔧 실행 모드: {execution_mode}')
        print(f'{'='*60}\n')

        success_count = 0
        fail_count = 0
        total_tasks = len(target_stocks) * len(timeframes_to_process)
        current_task = 0

        # --- 시장 지수(인덱스) 고정 적재 (항상 수행, stock_limit 영향 없음) ---
        from sqlalchemy.dialects.postgresql import insert
        index_info = [
            {'stock_code': '001', 'stock_name': 'KOSPI', 'market_name': 'INDEX', 'is_active': True, 'backfill_needed': False},
            {'stock_code': '101', 'stock_name': 'KOSDAQ', 'market_name': 'INDEX', 'is_active': True, 'backfill_needed': False}
        ]
        print("🔔 시장 지수 정보를 'stocks' 테이블에 UPSERT 합니다.")
        stmt = insert(Stock).values(index_info)
        update_cols = {c.name: getattr(stmt.excluded, c.name) for c in Stock.__table__.columns if c.name != 'stock_code'}
        final_stmt = stmt.on_conflict_do_update(index_elements=['stock_code'], set_=update_cols)
        db_session.execute(final_stmt)
        db_session.commit()

        index_codes = ['001', '101']  # KOSPI, KOSDAQ
        index_timeframes = ['mon']
        print(f"🔔 시장 지수 데이터 고정 적재를 시작합니다: {index_codes} x {index_timeframes}")
        for idx_code in index_codes:
            for timeframe in index_timeframes:
                current_task += 1
                total_tasks += 1
                period_for_timeframe = TIMEFRAME_PERIOD_MAP.get(timeframe, '1y')
                print(f"\n[INDEX {current_task}] 처리 중: {idx_code} - {timeframe} (기간: {period_for_timeframe})")
                try:
                    success = load_initial_history(
                        stock_code=idx_code, timeframe=timeframe, base_date=base_date, period=period_for_timeframe, execution_mode=execution_mode
                    )
                    if success:
                        success_count += 1
                        print(f"✅ 성공: {idx_code} - {timeframe}")
                    else:
                        fail_count += 1
                        print(f"⚠️ 데이터 없음: {idx_code} - {timeframe}")
                except Exception as e:
                    fail_count += 1
                    print(f"❌ 실패: {idx_code} - {timeframe}: {str(e)}")
                time.sleep(0.3)
        print(f"🔔 시장 지수 데이터 고정 적재 완료. 성공: {success_count}, 실패: {fail_count}")

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

        # 4. 최종 결과 출력 (이하 생략)

    finally:
        if session_owner:
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
    if execution_mode == 'SIMULATION' and base_date:
        
        from airflow.models import Variable
        from datetime import datetime, timedelta
        from pathlib import Path
        import pandas as pd

        print("\n🚀 시뮬레이션 변수 자동 설정 시작...")

        # 1. simulation_base_time 설정 (기준일 다음 거래일 오전 9시)
        base_date_obj = datetime.strptime(base_date, '%Y%m%d')
        next_day_obj = base_date_obj + timedelta(days=1)
        
        # 다음날이 주말(토:5, 일:6)이면 월요일(0)으로 이동
        if next_day_obj.weekday() >= 5:
            next_day_obj += timedelta(days=7 - next_day_obj.weekday())
        
        start_time_str = next_day_obj.strftime('%Y%m%d') + '090000'
        Variable.set('simulation_base_time', start_time_str)
        print(f"  ✅ simulation_base_time 설정 완료: {start_time_str}")

        # 2. simulation_end_time 설정 (Parquet 파일의 마지막 시간 기준)
        stock_for_endtime = config.get('stock_code')
        if not stock_for_endtime:
             # 일괄 모드일 경우, 기준이 될 종목을 타겟 리스트의 첫 번째 종목으로 사용
            stock_for_endtime = get_target_stocks()[0]

        import os
        from pathlib import Path

        sim_base = os.getenv('SIMULATION_DATA_PATH')
        if not sim_base:
            raise AirflowException("환경변수 SIMULATION_DATA_PATH가 설정되어 있지 않습니다. 예: export SIMULATION_DATA_PATH=/opt/airflow/data/simulation")

        parquet_path = Path(sim_base) / f"{stock_for_endtime}_5m_full.parquet"
        
        end_time_str = None
        if parquet_path.exists():
            df = pd.read_parquet(parquet_path)
            if not df.empty:
                last_timestamp = df.index.max()
                end_time_str = last_timestamp.strftime('%Y%m%d%H%M%S')
                Variable.set('simulation_end_time', end_time_str)
                print(f"  ✅ simulation_end_time 설정 완료 (데이터 기준): {end_time_str}")
        
        if not end_time_str:
            # Parquet 파일을 찾지 못하거나 비어있는 경우, 안전하게 2일 뒤로 설정
            fallback_end_time_obj = next_day_obj + timedelta(days=2)
            fallback_end_time_str = fallback_end_time_obj.strftime('%Y%m%d') + '153000'
            Variable.set('simulation_end_time', fallback_end_time_str)
            print(f"  ⚠️ Parquet 파일을 찾을 수 없어 기본 종료 시간으로 설정: {fallback_end_time_str}")

        # 3. system_mode를 SIMULATION으로 자동 설정
        Variable.set('system_mode', 'SIMULATION')
        print(f"  ✅ system_mode 설정 완료: SIMULATION")
        print("="*60)

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
        "stock_codes": Param(
            type=["null", "string"],
            default=None,
            title="🎯 특정 종목 대상 실행",
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
        "base_date": Param(
            type=["null", "string"],
            default=None,
            title="기준일 (YYYYMMDD)",
            description="데이터 조회의 기준일. 비워두면 현재 날짜를 사용합니다."
        ),
        "execution_mode": Param(
            type="string",
            default="LIVE",
            title="실행 모드",
            description="LIVE: 실제 API 호출, SIMULATION: 테스트 데이터 사용",
            enum=["LIVE", "SIMULATION"]
        )
    },
    doc_md="""
    ### [유틸리티] 과거 데이터 대량 적재 DAG

    이 DAG는 시스템을 최초로 구축하거나, 특정 종목의 과거 데이터를 보강(백필)해야 할 때 **수동으로 실행**하는 관리용 도구입니다.

    #### 실행 모드
    - **자동 모드 (기본)**: `stock_codes` 파라미터를 비워두고 실행하면, DB에서 `backfill_needed=True`로 표시된 모든 종목을 자동으로 찾아 과거 데이터를 적재합니다.
    - **수동 모드**: `stock_codes`에 종목코드를 입력하여 특정 종목의 과거 데이터만 선별적으로 적재합니다. 신규 관심 종목 추가나 데이터 유실 시 복구 용도로 사용합니다.

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
    
    # 의존성 설정
    stock_info_load_task >> initial_load_task 