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
from src.utils.common_helpers import get_target_stocks

DEFAULT_ARGS = {
    'owner': 'tradesmart_ai',
    'retries': 1,  # 초기 적재는 재시도 최소화
    'retry_delay': pendulum.duration(minutes=5),  # 재시도 간 5분 대기
}

# 지원하는 타임프레임 목록
TARGET_TIMEFRAMES = ['5m', '30m', '1h', 'd', 'w']
# ---------------------------------------------

# dags/dag_initial_loader.py

def _run_stock_info_load_task(**kwargs):
    """
    종목 정보를 DB의 'live.stocks' 테이블에 적재하는 Task
    """
    from src.database import SessionLocal, Stock
    from src.utils.common_helpers import load_stock_data_from_json_files
    from sqlalchemy.dialects.postgresql import insert
    from airflow.exceptions import AirflowException
    import os

    print("📊 'live.stocks' 테이블에 종목 정보 적재 시작")
    # Stock 모델의 기본 스키마는 'live'이므로, 별도 설정이 필요 없습니다.

    db = SessionLocal()
    try:
        existing_count = db.query(Stock).count()
        if existing_count > 0:
            print(f"✅ 'live.stocks'에 종목 정보가 이미 존재합니다: {existing_count}개")
            return

        base_dir = "/opt/airflow"
        kospi_path = os.path.join(base_dir, "data/kospi_code.json")
        kosdaq_path = os.path.join(base_dir, "data/kosdaq_code.json")
        all_stocks = load_stock_data_from_json_files(kospi_path, kosdaq_path)

        if not all_stocks:
            raise AirflowException("JSON 파일에서 로드할 종목 정보가 없습니다.")
        print(f"📊 로드된 종목 수: 총 {len(all_stocks)}개")

        stmt = insert(Stock).values(all_stocks)
        update_columns = {
            col.name: getattr(stmt.excluded, col.name)
            for col in Stock.__table__.columns
            if col.name != 'stock_code'
        }
        stmt = stmt.on_conflict_do_update(
            index_elements=['stock_code'],
            set_=update_columns
        )
        
        db.execute(stmt)
        db.commit()
        
        print(f"✅ 종목 정보 적재 완료: {len(all_stocks)}개 레코드가 'live.stocks'에 저장되었습니다.")

    except Exception as e:
        print(f"❌ 종목 정보 적재 실패: {e}")
        db.rollback()
        raise AirflowException(f"종목 정보 적재 실패: {e}")
    finally:
        db.close()
        print("DB 세션이 종료되었습니다.")
        
def _run_initial_load_task(**kwargs):
    """
    Airflow UI의 "Trigger DAG with config" 기능을 통해 전달된 파라미터를 읽어
    load_initial_history 함수를 호출하는 어댑터 함수
    
    3가지 모드 지원:
    1. 일괄 작업 모드: run_all_targets=true인 경우
    2. 특정 종목 전체 모드: stock_code만 있고 timeframe이 없는 경우
    3. 단일 작업 모드: stock_code와 timeframe 둘 다 있는 경우
    """
    # DAG 실행 설정에서 파라미터 추출
    dag_run = kwargs.get('dag_run')
    if not dag_run or not dag_run.conf:
        raise AirflowException(
            "DAG 실행 설정이 없습니다. "
            "Airflow UI에서 'Trigger DAG w/ Config' 버튼을 사용하여 "
            "JSON 형식으로 파라미터를 입력해주세요."
        )
    
    config = dag_run.conf
    print(f"📋 입력받은 설정: {config}")
    
    # 공통 파라미터 추출
    period = config.get('period', '2y')
    base_date = config.get('base_date')
    execution_mode = config.get('execution_mode', 'LIVE')
    
    # 모드 판별 및 실행
    if config.get('run_all_targets', False):
        # === 모드 1: 일괄 작업 모드 ===
        print(f"\n{'='*60}")
        print(f"🚀 일괄 초기 적재 작업을 시작합니다")
        print(f"📊 전체 타겟 종목 수: 30개")
        print(f"⏰ 타임프레임: {TARGET_TIMEFRAMES}")
        print(f"📅 기준일: {base_date or '현재 날짜'}")
        print(f"📆 기간: {period}")
        print(f"🔧 실행 모드: {execution_mode}")
        print(f"{'='*60}\n")
        
        # 타겟 종목 가져오기
        target_stocks = get_target_stocks()
        if not target_stocks:
            raise AirflowException("타겟 종목 목록을 가져올 수 없습니다")
        
        success_count = 0
        fail_count = 0
        total_tasks = len(target_stocks) * len(TARGET_TIMEFRAMES)
        current_task = 0
        
        # 이중 반복문으로 모든 조합 처리
        for stock_code in target_stocks:
            for timeframe in TARGET_TIMEFRAMES:
                current_task += 1
                print(f"\n[{current_task}/{total_tasks}] 처리 중: {stock_code} - {timeframe}")
                
                try:
                    success = load_initial_history(
                        stock_code=stock_code,
                        timeframe=timeframe,
                        base_date=base_date,
                        period=period,
                        execution_mode=execution_mode
                    )
                    
                    if success:
                        success_count += 1
                        print(f"✅ 성공: {stock_code} - {timeframe}")
                    else:
                        fail_count += 1
                        print(f"⚠️ 데이터 없음: {stock_code} - {timeframe}")
                        
                except Exception as e:
                    fail_count += 1
                    print(f"❌ 실패: {stock_code} - {timeframe}: {str(e)}")
                
                # API 서버 보호를 위한 대기
                time.sleep(0.3)
        
        # 최종 결과 출력
        print(f"\n{'='*60}")
        print(f"🎯 일괄 초기 적재 완료")
        print(f"✅ 성공: {success_count}개")
        print(f"❌ 실패: {fail_count}개")
        print(f"📊 전체: {total_tasks}개")
        print(f"{'='*60}\n")
        
        if fail_count > total_tasks * 0.3:  # 30% 이상 실패 시 에러
            raise AirflowException(f"너무 많은 작업이 실패했습니다: {fail_count}/{total_tasks}")
            
    elif 'stock_code' in config:
        stock_code = config['stock_code']
        timeframe = config.get('timeframe')
        
        # 빈 문자열이나 'None' 문자열을 None으로 처리
        if timeframe in ['', 'None', 'null']:
            timeframe = None
        
        if not timeframe:
            # === 모드 2: 특정 종목 전체 타임프레임 모드 ===
            print(f"\n{'='*60}")
            print(f"🚀 특정 종목 전체 타임프레임 적재 시작")
            print(f"📊 종목 코드: {stock_code}")
            print(f"⏰ 타임프레임: {TARGET_TIMEFRAMES}")
            print(f"📅 기준일: {base_date or '현재 날짜'}")
            print(f"📆 기간: {period}")
            print(f"🔧 실행 모드: {execution_mode}")
            print(f"{'='*60}\n")
            
            success_count = 0
            fail_count = 0
            
            for timeframe in TARGET_TIMEFRAMES:
                print(f"\n처리 중: {stock_code} - {timeframe}")
                
                try:
                    success = load_initial_history(
                        stock_code=stock_code,
                        timeframe=timeframe,
                        base_date=base_date,
                        period=period,
                        execution_mode=execution_mode
                    )
                    
                    if success:
                        success_count += 1
                        print(f"✅ 성공: {stock_code} - {timeframe}")
                    else:
                        fail_count += 1
                        print(f"⚠️ 데이터 없음: {stock_code} - {timeframe}")
                        
                except Exception as e:
                    fail_count += 1
                    print(f"❌ 실패: {stock_code} - {timeframe}: {str(e)}")
                
                # API 서버 보호를 위한 대기
                time.sleep(0.3)
            
            # 결과 출력
            print(f"\n{'='*60}")
            print(f"🎯 종목 전체 타임프레임 적재 완료")
            print(f"✅ 성공: {success_count}개")
            print(f"❌ 실패: {fail_count}개")
            print(f"📊 전체: {len(TARGET_TIMEFRAMES)}개")
            print(f"{'='*60}\n")
            
            if fail_count > len(TARGET_TIMEFRAMES) * 0.3:
                raise AirflowException(f"너무 많은 작업이 실패했습니다: {fail_count}/{len(TARGET_TIMEFRAMES)}")
                
        else:
            # === 모드 3: 단일 작업 모드 ===
            # 타임프레임 유효성 검사
            if timeframe not in TARGET_TIMEFRAMES:
                raise AirflowException(
                    f"지원하지 않는 타임프레임: {timeframe}\n"
                    f"지원되는 타임프레임: {TARGET_TIMEFRAMES}"
                )
            
            print(f"\n{'='*60}")
            print(f"🚀 단일 초기 데이터 적재 시작")
            print(f"📊 종목 코드: {stock_code}")
            print(f"⏰ 타임프레임: {timeframe}")
            print(f"📅 기준일: {base_date or '현재 날짜'}")
            print(f"📆 기간: {period}")
            print(f"🔧 실행 모드: {execution_mode}")
            print(f"{'='*60}\n")
            
            try:
                success = load_initial_history(
                    stock_code=stock_code,
                    timeframe=timeframe,
                    base_date=base_date,
                    period=period,
                    execution_mode=execution_mode
                )
                
                if success:
                    print(f"\n🎉 초기 데이터 적재가 성공적으로 완료되었습니다!")
                    print(f"종목: {stock_code}, 타임프레임: {timeframe}")
                    return f"SUCCESS: {stock_code}_{timeframe}"
                else:
                    error_msg = f"초기 데이터 적재가 실패했습니다: {stock_code}_{timeframe}"
                    print(f"\n❌ {error_msg}")
                    raise AirflowException(error_msg)
                    
            except Exception as e:
                error_msg = f"초기 데이터 적재 중 예외 발생: {str(e)}"
                print(f"\n💥 {error_msg}")
                raise AirflowException(error_msg)
    else:
        # 잘못된 설정
        raise AirflowException(
            "유효하지 않은 설정입니다.\n"
            "다음 중 하나의 형식으로 입력해주세요:\n"
            "1. 일괄 작업: {\"run_all_targets\": true, \"period\": \"2y\"}\n"
            "2. 특정 종목 전체: {\"stock_code\": \"005930\", \"period\": \"2y\"}\n"
            "3. 단일 작업: {\"stock_code\": \"005930\", \"timeframe\": \"d\", \"period\": \"2y\"}"
        )
    
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

        parquet_path = Path(f"/opt/airflow/data/simulation/{stock_for_endtime}_5m_full.parquet")
        
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
    tags=['production', 'initial_load', 'manual'],
    description='운영자가 필요할 때 수동으로 과거 데이터를 대량 적재하는 DAG',
    params={
        "run_all_targets": Param(
            type="boolean", 
            default=True, 
            title="✅ 전체 타겟 종목 실행",
            description="이 옵션을 True로 설정하면 30개 전체 종목의 모든 타임프레임을 적재합니다"
        ),
        "stock_code": Param(
            type=["null", "string"], 
            default=None, 
            title="종목 코드",
            description="특정 종목만 처리할 경우 입력 (예: 005930)"
        ),

        "timeframe": Param(
            type=["null", "string"], 
            default="",  # 기본값은 빈 문자열
            title="타임프레임 (직접 입력)",
            description="5m, 30m, 1h, d, w 중 하나 입력. 비워두면 모든 타임프레임 처리"
            # enum 옵션을 완전히 제거합니다.
        ),
        "period": Param(
            type=["null", "string"], 
            default=None, 
            title="조회 기간",
            description="기준일로부터의 과거 기간. 비워두면 타임프레임별 최적화된 기간 자동 적용 (5분봉:30일, 30분봉:6개월, 1시간봉:1년, 일봉:5년, 주봉:10년)"
        ),
        "base_date": Param(
            type=["null", "string"], 
            default=None, 
            title="기준일 (YYYYMMDD)",
            description="데이터 조회의 기준일. 비워두면 현재 날짜 사용"
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
    ## 초기 데이터 적재 DAG
    
    이 DAG는 운영자가 필요할 때 수동으로 과거 데이터를 대량 적재하기 위한 용도입니다.
    
    ### 지원 모드
    1. **일괄 작업 모드**: 모든 타겟 종목의 모든 타임프레임 적재
    2. **특정 종목 전체 모드**: 특정 종목의 모든 타임프레임 적재
    3. **단일 작업 모드**: 특정 종목의 특정 타임프레임만 적재
    
    ### 사용 방법
    1. Airflow UI에서 `dag_initial_loader` DAG 선택
    2. "Trigger DAG w/ Config" 버튼 클릭
    3. JSON 형식으로 파라미터 입력
    
    ### 파라미터 예시
    
    **일괄 작업 모드** (30개 종목 × 5개 타임프레임 = 150개 작업):
    ```json
    {
        "run_all_targets": true,
        "period": "2y",
        "execution_mode": "LIVE"
    }
    ```
    
    **특정 종목 전체 모드** (1개 종목 × 5개 타임프레임):
    ```json
    {
        "stock_code": "005930",
        "period": "2y"
    }
    ```
    
    **단일 작업 모드** (1개 종목 × 1개 타임프레임):
    ```json
    {
        "stock_code": "005930",
        "timeframe": "d",
        "period": "1y",
        "base_date": "20250701"
    }
    ```
    
    ### 파라미터 설명
    - `run_all_targets`: 전체 타겟 종목 실행 여부 (boolean)
    - `stock_code`: 특정 종목 코드 (string)
    - `timeframe`: 타임프레임 ("5m", "30m", "1h", "d", "w")
    - `period`: 조회 기간 ("2y", "6m", "30d" 등)
    - `base_date`: 기준일 (YYYYMMDD 형식, 생략 시 현재 날짜)
    - `execution_mode`: 실행 모드 ("LIVE" 또는 "SIMULATION")
    
    ### 주의사항
    - 대량 데이터 적재 시 API 호출 제한에 주의하세요
    - 각 API 호출 사이에 0.3초 대기 시간이 자동으로 적용됩니다
    - 실행 전 해당 종목이 DB에 등록되어 있는지 확인하세요
    - 일괄 작업 모드는 완료까지 상당한 시간이 소요됩니다
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