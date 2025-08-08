# DAG 파일: Live 증분 업데이트 (동적 생성)
import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import collect_and_store_candles
from src.utils.common_helpers import get_target_stocks

# --- ⚙️ 설정: 모든 증분 DAG의 설정을 한 곳에서 관리 ---
DAG_CONFIGS = {
    '5m': {'schedule': '*/5 9-15 * * 1-5', 'tags': ['5min']},
    '30m': {'schedule': '*/30 9-15 * * 1-5', 'tags': ['30min']},
    '1h': {'schedule': '0 9-15 * * 1-5', 'tags': ['1h']},
    'daily': {'schedule': '0 16 * * 1-5', 'tags': ['daily']},
    'weekly': {'schedule': '0 17 * * 5', 'tags': ['weekly']}, # 금요일 17시
}

TARGET_STOCKS = get_target_stocks() 

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 2,
    'retry_delay': pendulum.duration(minutes=3),
}
# ---------------------------------------------

# Airflow Task에서 호출될 공통 함수
def _run_live_task(stock_code: str, timeframe: str):
    """모든 Live 증분 업데이트 Task가 공유하는 실행 함수"""
    print(f"Executing incremental update for {stock_code} ({timeframe})")
    collect_and_store_candles(
        stock_code=stock_code,
        timeframe=timeframe,
        execution_mode='LIVE'
        # LIVE 모드에서는 execution_time이 필요 없음 (자동으로 현재 시간 기준)
    )

# --- 🏭 동적 DAG 생성 공장 ---
for timeframe, config in DAG_CONFIGS.items():
    
    # timeframe 변수에서 'm', 'h' 등을 제거하여 DB 포맷('d', 'w')과 일치시킴
    db_timeframe = timeframe.replace('m','').replace('h','') if 'm' in timeframe or 'h' in timeframe else timeframe

    dag_id = f'dag_{timeframe}_collector'

    with DAG(
        dag_id=dag_id,
        default_args=DEFAULT_ARGS,
        schedule_interval=config['schedule'],
        start_date=pendulum.datetime(2025, 7, 1, tz="Asia/Seoul"),
        catchup=False,
        tags=['production', 'incremental'] + config['tags'],
        max_active_runs=1 # 동시에 여러 스케줄이 실행되지 않도록 방지
    ) as dag:
        
        for stock_code in TARGET_STOCKS:
            PythonOperator(
                task_id=f'collect_{stock_code}_{db_timeframe}',
                python_callable=_run_live_task,
                op_kwargs={
                    'stock_code': stock_code,
                    'timeframe': timeframe # data_collector는 '5m', '1h' 형식 사용
                },
                pool='kiwoom_api_pool' # API 호출 제한을 위한 Pool 사용 (매우 중요!)
            )