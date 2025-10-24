# DAG 파일: Live 증분 업데이트 (동적 생성)
"""
⚠️ 사전 요구사항:
이 DAG가 정상적으로 실행되려면 Airflow UI에서 Pool을 수동으로 생성해야 합니다.
- Pool Name: kiwoom_api_pool
- Pool Slots: 1  (API 동시 호출 제한)
(CLI 명령어: airflow pools set kiwoom_api_pool 1 "Kiwoom API Rate Limiting")
"""
import pendulum
from airflow.models.dag import DAG
from airflow.operators.python import PythonOperator
from functools import lru_cache
from typing import List

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import collect_and_store_candles
from src.database import SessionLocal, Stock

# --- ⚙️ 설정: 모든 증분 DAG의 설정을 한 곳에서 관리 ---
DAG_CONFIGS = {
    '5m': {'schedule': '*/5 9-15 * * 1-5', 'tags': ['5min']},
    '30m': {'schedule': '*/30 9-15 * * 1-5', 'tags': ['30min']},
    '1h': {'schedule': '0 9-15 * * 1-5', 'tags': ['1h']},
}

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 2,
    'retry_delay': pendulum.duration(minutes=3),
}

# ---------------------------------------------
# 캐시된 장중 분봉 데이터 수집 대상 종목 리스트 조회 함수
# ---------------------------------------------

@lru_cache(maxsize=1)
def get_live_collector_targets() -> List[str]:
    """
    캐시된 장중 분봉 데이터 수집 대상 종목 리스트 반환 (DAG 파싱 시 1회만 DB 조회)

    live.stocks 테이블에서 is_active=True인 종목 코드를 조회합니다.
    @lru_cache 데코레이터를 통해 DAG 파일 파싱 시 단 한 번만 DB에 접근하며,
    이후 호출은 캐시된 결과를 반환하여 DB 부하를 최소화합니다.

    Returns:
        List[str]: 활성 상태인 종목 코드 리스트
    """
    db = SessionLocal()
    try:
        rows = db.query(Stock.stock_code).filter(Stock.is_active == True).all()
        codes = [r.stock_code for r in rows]
        return codes
    finally:
        db.close()

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
    dag_id = f'dag_{timeframe}_collector'

    with DAG(
        dag_id=dag_id,
        default_args=DEFAULT_ARGS,
        schedule_interval=config['schedule'],
        start_date=pendulum.datetime(2025, 7, 1, tz="Asia/Seoul"),
        catchup=False,
        tags=['production', 'incremental'] + config['tags'],
        max_active_runs=1,  # 동시에 여러 스케줄이 실행되지 않도록 방지
        description='[LIVE 모드 전용] 장중 분봉 데이터 증분 수집 DAG'
    ) as dag:
        
        # 캐시된 함수 호출로 활성 종목 리스트 조회
        target_stocks = get_live_collector_targets()
        
        for stock_code in target_stocks:
            PythonOperator(
                task_id=f'collect_{stock_code}_{timeframe}',  # 원본 timeframe 사용 (가독성 우선)
                python_callable=_run_live_task,
                op_kwargs={
                    'stock_code': stock_code,
                    'timeframe': timeframe
                },
                pool='kiwoom_api_pool'  # API 호출 제한을 위한 Pool 사용 (매우 중요!)
            )