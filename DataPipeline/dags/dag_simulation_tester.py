# DAG 파일: 시뮬레이션용 통합 테스트
"""
TradeSmartAI 시뮬레이션 테스트 DAG

이 DAG는 실제 시간이 아닌 '가짜 시간'을 사용하여 데이터 수집 파이프라인을
빠르게 테스트합니다. Airflow Variable의 simulation_base_time을 5분씩 증가시키며
각 타임프레임별 데이터 수집 로직을 검증합니다.

필요한 Airflow Variables:
- system_mode: 'SIMULATION' 또는 'LIVE'
- simulation_base_time: YYYYMMDDHHMMSS 형식의 시뮬레이션 현재 시간
- simulation_end_time: YYYYMMDDHHMMSS 형식의 시뮬레이션 종료 시간
"""

import pendulum
from datetime import datetime, timedelta
from airflow.models.dag import DAG
from airflow.models import Variable
from airflow.operators.python import PythonOperator, BranchPythonOperator, ShortCircuitOperator
from airflow.utils.trigger_rule import TriggerRule

# --- 공통 모듈 및 변수 로드 ---
from src.data_collector import collect_and_store_candles

# 시뮬레이션용 테스트 종목 (2-3개 대표 종목)
TEST_STOCKS = [
    '005930',  # 삼성전자 (KOSPI 대표)
]

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,  # 시뮬레이션은 재시도 최소화
    'retry_delay': pendulum.duration(minutes=1),
}
# ---------------------------------------------

def check_simulation_mode(**context):
    """
    system_mode Variable을 확인하여 SIMULATION 모드일 때만 True 반환
    LIVE 모드일 경우 False를 반환하여 후속 Task 실행 중단
    """
    system_mode = Variable.get('system_mode', default_var='LIVE')
    
    if system_mode == 'SIMULATION':
        print(f"✅ 시뮬레이션 모드 확인: {system_mode}")
        print(f"시뮬레이션 테스트를 계속 진행합니다.")
        return True
    else:
        print(f"❌ 현재 모드: {system_mode}")
        print(f"시뮬레이션 DAG는 SIMULATION 모드에서만 실행됩니다.")
        print(f"DAG 실행을 중단합니다.")
        return False

def determine_tasks_to_run(**context):
    """
    현재 시뮬레이션 시간을 기준으로 실행할 Task들을 결정
    BranchPythonOperator에서 사용
    """
    # 시뮬레이션 현재 시간 가져오기
    sim_time_str = Variable.get('simulation_base_time')
    sim_time = datetime.strptime(sim_time_str[:14], '%Y%m%d%H%M%S')
    
    # 시간 정보 추출
    weekday = sim_time.weekday()  # 0=월요일, 4=금요일
    hour = sim_time.hour
    minute = sim_time.minute
    
    print(f"🕐 현재 시뮬레이션 시간: {sim_time.strftime('%Y-%m-%d %H:%M:%S')} ({['월','화','수','목','금','토','일'][weekday]}요일)")
    
    # 실행할 Task ID 리스트
    tasks_to_run = []
    
    # 주말이면 아무것도 실행하지 않음
    if weekday >= 5:  # 토요일(5) 또는 일요일(6)
        print("📅 주말이므로 데이터 수집을 건너뜁니다.")
        # 시간 업데이트 Task는 항상 실행
        return ['update_simulation_time']
    
    # 장 시간 확인 (09:00 ~ 15:30)
    if not (9 <= hour < 15 or (hour == 15 and minute <= 30)):
        print("🌙 장외 시간이므로 데이터 수집을 건너뜁니다.")
        return ['update_simulation_time']
    
    # 5분봉: 5분마다
    if minute % 5 == 0:
        tasks_to_run.append('run_5min_simulation')
        print("  → 5분봉 수집 시점")
    
    # 30분봉: 30분마다
    if minute % 30 == 0:
        tasks_to_run.append('run_30min_simulation')
        print("  → 30분봉 수집 시점")
    
    # 1시간봉: 정시마다
    if minute == 0:
        tasks_to_run.append('run_1h_simulation')
        print("  → 1시간봉 수집 시점")
    
    # 일봉: 15:30 (장 마감)
    if hour == 15 and minute == 30:
        tasks_to_run.append('run_daily_simulation')
        print("  → 일봉 수집 시점 (장 마감)")
    
    # 주봉: 금요일 15:30
    if weekday == 4 and hour == 15 and minute == 30:
        tasks_to_run.append('run_weekly_simulation')
        print("  → 주봉 수집 시점 (주 마감)")
    
    # 시간 업데이트 Task는 항상 추가
    tasks_to_run.append('update_simulation_time')
    
    print(f"🎯 실행할 Task: {tasks_to_run}")
    return tasks_to_run

def run_simulation_collection(timeframe: str, **context):
    """
    시뮬레이션 모드로 데이터 수집 실행
    """
    sim_time_str = Variable.get('simulation_base_time')
    print(f"\n{'='*60}")
    print(f"📊 {timeframe} 시뮬레이션 데이터 수집 시작")
    print(f"🕐 시뮬레이션 시간: {sim_time_str}")
    print(f"🏢 테스트 종목: {TEST_STOCKS}")
    print(f"{'='*60}\n")
    
    success_count = 0
    fail_count = 0
    
    for stock_code in TEST_STOCKS:
        try:
            print(f"\n[{stock_code}] {timeframe} 데이터 수집 중...")
            result = collect_and_store_candles(
                stock_code=stock_code,
                timeframe=timeframe,
                execution_mode='SIMULATION',
                execution_time=sim_time_str
            )
            
            if result:
                success_count += 1
                print(f"[{stock_code}] ✅ 성공")
            else:
                print(f"[{stock_code}] ⚠️ 신규 데이터 없음")
                
        except Exception as e:
            fail_count += 1
            print(f"[{stock_code}] ❌ 실패: {str(e)}")
    
    print(f"\n{'='*60}")
    print(f"📊 {timeframe} 수집 완료: 성공 {success_count}개, 실패 {fail_count}개")
    print(f"{'='*60}\n")

def update_simulation_time(**context):
    """
    시뮬레이션 시간을 5분 증가시키고, 주말/장외시간 처리
    종료 조건 확인
    """
    # 현재 시뮬레이션 시간
    sim_time_str = Variable.get('simulation_base_time')
    sim_time = datetime.strptime(sim_time_str[:14], '%Y%m%d%H%M%S')
    
    # 종료 시간
    end_time_str = Variable.get('simulation_end_time')
    end_time = datetime.strptime(end_time_str[:14], '%Y%m%d%H%M%S')
    
    print(f"\n{'='*60}")
    print(f"⏰ 시뮬레이션 시간 업데이트")
    print(f"현재: {sim_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 5분 증가
    new_time = sim_time + timedelta(minutes=5)
    
    # 주말/장외시간 건너뛰기 로직
    weekday = new_time.weekday()
    hour = new_time.hour
    minute = new_time.minute
    
    # 금요일 15:30 이후라면 다음 월요일 09:00으로
    if weekday == 4 and (hour > 15 or (hour == 15 and minute > 30)):
        days_to_monday = 3  # 금 -> 월
        new_time = new_time.replace(hour=9, minute=0, second=0)
        new_time += timedelta(days=days_to_monday)
        print(f"📅 주말 건너뛰기: 다음 월요일 오전으로 이동")
    
    # 토요일이나 일요일이면 다음 월요일 09:00으로
    elif weekday >= 5:
        days_to_monday = 8 - weekday  # 토(6)->월(1), 일(7)->월(1)
        new_time = new_time.replace(hour=9, minute=0, second=0)
        new_time += timedelta(days=days_to_monday)
        print(f"📅 주말 건너뛰기: 다음 월요일 오전으로 이동")
    
    # 15:30 이후라면 다음날 09:00으로
    elif hour > 15 or (hour == 15 and minute > 30):
        new_time = new_time.replace(hour=9, minute=0, second=0)
        new_time += timedelta(days=1)
        # 다음날이 주말이면 월요일로
        if new_time.weekday() >= 5:
            days_to_monday = 8 - new_time.weekday()
            new_time += timedelta(days=days_to_monday)
        print(f"🌙 장외시간 건너뛰기: 다음 거래일 오전으로 이동")
    
    # 09:00 이전이면 09:00으로
    elif hour < 9:
        new_time = new_time.replace(hour=9, minute=0, second=0)
        print(f"🌅 장 시작 전: 09:00으로 이동")
    
    print(f"다음: {new_time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 종료 조건 확인
    if new_time > end_time:
        print(f"\n🏁 시뮬레이션 종료 시간에 도달했습니다!")
        print(f"종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"시뮬레이션을 종료합니다.")
        print(f"{'='*60}\n")
        
        # 시간을 업데이트하지 않음으로써 사실상 정지
        return
    
    # 새로운 시간으로 Variable 업데이트
    new_time_str = new_time.strftime('%Y%m%d%H%M%S')
    Variable.set('simulation_base_time', new_time_str)
    
    print(f"✅ 시뮬레이션 시간이 업데이트되었습니다.")
    print(f"{'='*60}\n")

# DAG 정의
with DAG(
    dag_id='dag_simulation_tester',
    default_args=DEFAULT_ARGS,
    schedule_interval='* * * * *',  # 매 1분마다 실행 (빠른 시뮬레이션)
    start_date=pendulum.datetime(2025, 7, 1, tz="Asia/Seoul"),
    catchup=False,
    tags=['test', 'simulation'],
    description='시뮬레이션 모드에서 데이터 수집 파이프라인을 빠르게 테스트'
) as dag:
    
    # Task 1: 시스템 모드 확인 (ShortCircuitOperator)
    check_mode = ShortCircuitOperator(
        task_id='check_system_mode',
        python_callable=check_simulation_mode,
        provide_context=True
    )
    
    # Task 2: 실행할 Task 결정 (BranchPythonOperator)
    branch = BranchPythonOperator(
        task_id='determine_tasks',
        python_callable=determine_tasks_to_run,
        provide_context=True
    )
    
    # Task 3-7: 각 타임프레임별 시뮬레이션 실행
    sim_5min = PythonOperator(
        task_id='run_5min_simulation',
        python_callable=run_simulation_collection,
        op_kwargs={'timeframe': '5m'},
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    sim_30min = PythonOperator(
        task_id='run_30min_simulation',
        python_callable=run_simulation_collection,
        op_kwargs={'timeframe': '30m'},
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    sim_1h = PythonOperator(
        task_id='run_1h_simulation',
        python_callable=run_simulation_collection,
        op_kwargs={'timeframe': '1h'},
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    sim_daily = PythonOperator(
        task_id='run_daily_simulation',
        python_callable=run_simulation_collection,
        op_kwargs={'timeframe': 'd'},
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    sim_weekly = PythonOperator(
        task_id='run_weekly_simulation',
        python_callable=run_simulation_collection,
        op_kwargs={'timeframe': 'w'},
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    # Task 8: 시뮬레이션 시간 업데이트
    update_time = PythonOperator(
        task_id='update_simulation_time',
        python_callable=update_simulation_time,
        provide_context=True,
        trigger_rule=TriggerRule.NONE_FAILED_MIN_ONE_SUCCESS
    )
    
    # Task 의존성 설정
    check_mode >> branch
    
    # 분기된 Task들은 모두 update_time으로 수렴
    branch >> [sim_5min, sim_30min, sim_1h, sim_daily, sim_weekly, update_time]
    [sim_5min, sim_30min, sim_1h, sim_daily, sim_weekly] >> update_time 