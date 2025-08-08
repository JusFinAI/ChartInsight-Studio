# DAG 파일: 5분봉 증분 업데이트
import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import collect_and_store_candles
from src.utils.common_helpers import get_target_stocks # 중앙에서 타겟 종목 로드

TARGET_STOCKS = get_target_stocks() 

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 2, # 실패 시 2번 더 재시도
    'retry_delay': pendulum.duration(minutes=3), # 재시도 간 3분 대기
}
# ---------------------------------------------

# Airflow Task에서 호출될 어댑터 함수
def _run_live_task(stock_code: str, timeframe: str):
    print(f"Executing incremental update for {stock_code} ({timeframe})")
    collect_and_store_candles(
        stock_code=stock_code,
        timeframe=timeframe,
        execution_mode='LIVE'
    )

# --- 5분봉 DAG 설정 ---
with DAG(
    dag_id='dag_5min_collector',
    default_args=DEFAULT_ARGS,
    schedule_interval='*/5 9-15 * * 1-5', # 주중 9-15시 5분마다
    start_date=pendulum.datetime(2025, 7, 1, tz="Asia/Seoul"),
    catchup=False,
    tags=['production', 'incremental', '5min']
) as dag:
    for stock_code in TARGET_STOCKS:
        PythonOperator(
            task_id=f'collect_{stock_code}_5m',
            python_callable=_run_live_task,
            op_kwargs={
                'stock_code': stock_code,
                'timeframe': '5m'
            },
            pool='kiwoom_api_pool'
        ) 