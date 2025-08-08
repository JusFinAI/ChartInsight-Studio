from __future__ import annotations

import pendulum
import logging

from airflow.models.dag import DAG

from airflow.operators.python import PythonOperator

from airflow.models import Variable
from airflow.exceptions import AirflowSkipException

# Airflow가 src 폴더를 인식하도록 PYTHONPATH 설정이 되어있거나,
# airflow.cfg 또는 DAG 정의 시 sys.path에 추가 필요
try:
    from src.data_collector_test import (
        fetch_and_store_initial_minute_data,
        fetch_and_store_next_minute_candle
    )
except ImportError as e:
    logging.error(f"Airflow DAG에서 src 모듈 임포트 실패: {e}")
    raise # ImportError가 발생하면 DAG 로딩을 여기서 강제로 중단하고 에러를 띄웁니다.
    fetch_and_store_initial_minute_data = None
    fetch_and_store_next_minute_candle = None

logger = logging.getLogger(__name__)

# Airflow Variable 키 정의
VAR_TEST_STOCK_CODE = "test_stock_code"
VAR_TEST_TIMEFRAME_MINUTES = "test_timeframe_minutes"
VAR_TEST_BASE_DATE_STR = "test_base_date_str"
VAR_TEST_NUM_INITIAL_CANDLES = "test_num_initial_candles"
VAR_LAST_COLLECTED_TIMESTAMP = "last_collected_timestamp_test_dag"

DEFAULT_ARGS = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': pendulum.duration(minutes=1),
}

def _get_variable(key, default_val=None):
    try:
        return Variable.get(key, default_var=default_val)
    except KeyError:
        logger.warning(f"Airflow Variable '{key}'를 찾을 수 없습니다. 기본값 '{default_val}'을 사용합니다.")
        return default_val

def _initial_load_callable(**kwargs):
    ti = kwargs['ti']
    
    # 마지막 수집된 타임스탬프 확인
    last_ts_from_var = _get_variable(VAR_LAST_COLLECTED_TIMESTAMP)
    
    # 이미 초기 적재가 완료되었다고 판단되면 스킵
    if last_ts_from_var:
        logger.info(f"'{VAR_LAST_COLLECTED_TIMESTAMP}' 변수에 이미 값({last_ts_from_var})이 존재합니다. 초기 적재를 건너뜁니다.")
        return None

    logger.info("초기 분봉 데이터 적재 태스크 시작...")
    if not fetch_and_store_initial_minute_data:
        logger.error("fetch_and_store_initial_minute_data 함수를 찾을 수 없습니다.")
        raise ImportError("src.data_collector_test 모듈 로드 실패")

    stock_code = _get_variable(VAR_TEST_STOCK_CODE, '005930')
    timeframe_minutes = int(_get_variable(VAR_TEST_TIMEFRAME_MINUTES, 5))
    base_date_str = _get_variable(VAR_TEST_BASE_DATE_STR, '20250529')
    num_candles = int(_get_variable(VAR_TEST_NUM_INITIAL_CANDLES, 77))

    logger.info(f"초기 적재 파라미터: stock_code={stock_code}, timeframe={timeframe_minutes}분, base_date={base_date_str}, num_candles={num_candles}")

    # 수정된 함수 시그니처에 맞게 호출 (start_time_str 제거)
    new_last_timestamp = fetch_and_store_initial_minute_data(
        stock_code=stock_code,
        timeframe_minutes=timeframe_minutes,
        base_date_str=base_date_str,
        num_candles=num_candles
    )

    if new_last_timestamp:
        logger.info(f"초기 적재 성공. 마지막 타임스탬프: {new_last_timestamp}")
        Variable.set(VAR_LAST_COLLECTED_TIMESTAMP, new_last_timestamp)
        ti.xcom_push(key="last_collected_timestamp", value=new_last_timestamp)
        return new_last_timestamp
    else:
        logger.error("초기 적재 실패.")
        return None

def _periodic_update_callable(**kwargs):
    ti = kwargs['ti']
    logger.info("스마트 증분 업데이트 태스크 시작...")

    if not fetch_and_store_next_minute_candle:
        logger.error("fetch_and_store_next_minute_candle 함수를 찾을 수 없습니다.")
        raise ImportError("src.data_collector_test 모듈 로드 실패")

    # 이제 last_timestamp는 함수 내부에서 DB를 조회하므로 전달할 필요 없음
    stock_code = _get_variable(VAR_TEST_STOCK_CODE, '005930')
    timeframe_minutes = int(_get_variable(VAR_TEST_TIMEFRAME_MINUTES, 5))

    logger.info(f"스마트 증분 업데이트 파라미터: stock_code={stock_code}, timeframe={timeframe_minutes}분")

    # last_timestamp_str은 이제 선택적 매개변수이므로 전달하지 않음
    new_last_timestamp = fetch_and_store_next_minute_candle(
        stock_code=stock_code,
        timeframe_minutes=timeframe_minutes
    )

    if new_last_timestamp:
        logger.info(f"스마트 증분 업데이트 성공. 최신 타임스탬프: {new_last_timestamp}")
        Variable.set(VAR_LAST_COLLECTED_TIMESTAMP, new_last_timestamp)
        ti.xcom_push(key="last_collected_timestamp", value=new_last_timestamp)
        return new_last_timestamp
    else:
        logger.info("스마트 증분 업데이트: 신규 데이터 없음 또는 실패")
        return None


with DAG(
    dag_id='data_collector_test_dag',
    default_args=DEFAULT_ARGS,
    start_date=pendulum.datetime(2025, 5, 30, tz="Asia/Seoul"),
    schedule_interval='*/5 * * * *', # 매 1분마다 (학습용)
    catchup=False,
    tags=['test', 'data_collector', 'smart_update'],
    doc_md="""
    ### 스마트 증분 업데이트 DAG
    - `src.data_collector_test` 모듈의 개선된 함수를 사용하여 분봉 데이터를 효율적으로 수집합니다.
    - 매 1분마다 실행되지만, 실제로는 DB의 최신 캔들 이후의 신규 데이터만 배치로 저장합니다.
    - 초기 적재 태스크와 스마트 증분 업데이트 태스크로 구성됩니다.
    - **Airflow 학습 목적**: Scheduler, Worker, Task 실행 주기 등을 관찰할 수 있습니다.
    - **필수 Airflow Variables** (미리 Airflow UI에서 설정 필요):
        - `test_stock_code` (str, 예: '005930')
        - `test_timeframe_minutes` (int, 예: 5)
        - `test_base_date_str` (str, YYYYMMDD, 예: '20250529') - 초기 적재 기준일
        - `test_num_initial_candles` (int, 예: 77) - 초기 적재 캔들 수
        - `last_collected_timestamp_test_dag` (str) - DAG 실행에 따라 자동 관리됨
    """
) as dag:
    
    initial_load_task = PythonOperator(
        task_id='initial_load_minute_data_task',
        python_callable=_initial_load_callable,
        doc_md="""
        #### 초기 분봉 데이터 적재
        지정된 종목의 과거 분봉 데이터를 DB에 초기 적재합니다.
        `last_collected_timestamp_test_dag` Variable이 비어있을 때만 실행됩니다.
        성공 시, 마지막으로 수집된 캔들의 타임스탬프를 XCom으로 push하고, 
        `last_collected_timestamp_test_dag` Variable에 업데이트합니다.
        """
    )

    periodic_update_task = PythonOperator(
        task_id='smart_incremental_update_task',
        python_callable=_periodic_update_callable,
        doc_md="""
        #### 스마트 증분 업데이트
        DB의 최신 캔들 이후의 모든 신규 데이터를 배치로 가져와 저장합니다.
        API로부터 최신 데이터를 받아와서 DB와 비교하여 신규분만 선별적으로 저장합니다.
        성공 시, 새로 수집된 가장 최신 캔들의 타임스탬프를 XCom으로 push하고, 
        `last_collected_timestamp_test_dag` Variable에 업데이트합니다.
        신규 데이터가 없는 경우에도 정상적으로 완료됩니다.
        """
    )


