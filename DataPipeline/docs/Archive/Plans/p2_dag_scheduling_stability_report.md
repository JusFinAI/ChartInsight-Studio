
# P2 과제: Airflow DAG 실행 정책 안정화 보고서

**문서 버전: 1.0**

**작성자: Gemini (Project Supervisor)**

---

### 1. 과제 ID 및 요약

- **과제 ID**: `P2: Airflow DAG 실행 정책 안정화`
- **요약**: Airflow DAG를 비활성화(pause)했다가 다시 활성화(unpause)할 때, 의도치 않은 과거 시점의 스케줄이 자동으로 실행되는 현상이 발견되었습니다. 이 보고서는 해당 현상의 원인을 분석하고, 향후 적용할 수 있는 근본적인 해결 방안을 기술하는 것을 목적으로 합니다.

### 2. 상세 현상

1.  **최초 발견**: `dag_initial_loader` 실행 후 `dag_daily_batch`를 활성화하자, 다음 스케줄을 기다리지 않고 즉시 과거 날짜(`scheduled__2025-10-21T...`)의 DAG 실행(Run)이 트리거되었습니다.

2.  **확장된 현상 (실제 운영 경험 기반)**:
    - **다중 DAG 상호작용**: 한 DAG의 unpause가 다른 DAG의 실행에 영향을 미칩니다. 예를 들어, `dag_daily_batch`를 unpause하면 `dag_financials_update`도 자동으로 과거 스케줄 실행을 시도합니다.
    - **Pause 상태 무시**: DAG가 pause 상태임에도 불구하고, unpause 과정에서 또는 다른 DAG의 영향으로 인해 과거 스케줄 실행이 트리거될 수 있습니다.
    - **CLI vs Web UI 실행 차이**: 
        - **CLI 수동 트리거**: `airflow dags trigger` 명령어로 실행하면 DAG가 pause 상태이거나 다른 조건이 불안정할 경우 `queued` 상태에서 실행이 멈추는 경우가 빈번합니다.
        - **Web UI 수동 트리거**: UI에서 "Trigger DAG w/ config"를 사용하면 대부분 즉시 실행되어 더 안정적인 결과를 제공합니다.
    - **데이터 무결성 문제**: 의도치 않은 다중 실행으로 인해 동일한 분석이 여러 번 수행되어 데이터베이스에 중복 데이터가 저장되거나, UPSERT 전략(`on_conflict_do_nothing`)에 의해 최신 결과가 저장되지 않는 문제가 발생합니다.
    - **리소스 낭비**: 예기치 않은 API 호출(예: DART API, Kiwoom API)이 발생하여 일일 호출 한계를 초과하거나 불필요한 비용이 발생할 수 있습니다.

3.  **재현 조건**: 이 현상은 주로 아래와 같은 특정 조건에서 발생합니다.
    - DAG의 `start_date`가 현재보다 과거로 설정되어 있음
    - 해당 DAG의 성공/실패 기록이 전무한 상태(신규 배포 등)에서 처음 활성화될 때
    - 운영자가 수동으로 DAG의 실행 기록을 모두 삭제(Clear)하고 다시 활성화할 때
    - **다중 DAG 환경**: 여러 DAG가 서로 연관되어 있는 환경에서 한 DAG의 상태 변화가 다른 DAG에 영향을 미칠 때
    - **Pause/Unpause 작업**: DAG를 pause했다가 unpause하는 과정에서 스케줄러의 상태 불일치가 발생할 때

### 3. 근본 원인 분석

이 현상은 우리 코드의 버그가 아닌, **Airflow 스케줄러의 고유한 설계 특징**과 관련이 있습니다.

- **`catchup` 파라미터의 한계**: 우리 DAG에는 이미 `catchup=False`가 설정되어 있습니다. 이 설정은 여러 개의 과거 스케줄이 한꺼번에 실행되는 '백필(Backfill)'은 막아주지만, DAG의 실행 기록이 전무할 경우 스케줄러가 실행 기록의 기준점을 잡기 위해 **가장 최근의 과거 스케줄 1개를 실행**하려는 경향이 있습니다.

- **동적 `start_date`의 위험성**: `start_date`를 현재 시간(`pendulum.now()`)으로 설정하면 당장의 현상은 피할 수 있으나, DAG의 고유성(정체성)이 계속 변경되어 스케줄러 동작 전체를 불안정하게 만드는 더 심각한 부작용을 초래하므로 해결책이 될 수 없습니다.

결론적으로, `start_date`를 과거의 특정일로 고정하는 현재의 방식은 올바르며, 문제는 Airflow의 '첫 실행 보정'이라는 엣지 케이스(Edge Case)를 어떻게 안정적으로 처리할 것인가에 있습니다.

### 4. 제안된 해결 방안: 실행 시간 검증 가드 (Guard)

향후 이 문제를 근본적으로 해결하기 위한 최적의 방안은 **"DAG 내부 가드"** 를 추가하는 것입니다.

- **핵심 아이디어**: 스케줄러가 의도치 않은 과거 실행을 생성하는 것을 막을 수는 없지만, 생성된 실행이 실제 작업을 수행하기 전에 **스스로 실행을 중단(Skip)하도록** 만들 수 있습니다.

- **구현 방식**: `BranchPythonOperator`를 사용하여 DAG의 가장 첫 단계에 '문지기(Guard)' 역할을 하는 Task를 배치합니다.

**[핵심 로직 의사코드]**
```python
# 1. DAG 파일 상단에 실행 시간 검증 함수 정의

def _check_execution_date(**kwargs):
    logical_date = kwargs.get('logical_date')
    allowed_delay = pendulum.duration(days=2) # 최대 2일 지연까지만 허용
    
    # 현재 시간이 DAG의 기준 시간(logical_date)보다 너무 미래이면
    if pendulum.now('Asia/Seoul') > logical_date + allowed_delay:
        # 'skip_downstream' 신호를 보내 후속 Task들을 모두 건너뛰게 함
        return 'skip_downstream'
    else:
        # 정상 범위일 경우, 다음 Task의 ID를 리턴하여 실행을 계속함
        return 'continue_downstream_task_id'

# 2. DAG 정의부에서 BranchPythonOperator로 가드 Task 생성

with DAG(...) as dag:
    
    check_execution_date_task = BranchPythonOperator(
        task_id='check_execution_date',
        python_callable=_check_execution_date,
    )

    # 정상 경로의 첫 Task
    continue_downstream_task = ...

    # 스킵 경로를 위한 더미 Task
    skip_task = DummyOperator(task_id='skip_downstream')

    # 의존성 설정
    check_execution_date_task >> [continue_downstream_task, skip_task]
```

### 5. 기대 효과

- **완전한 예측 가능성**: 위 가드 로직을 적용하면, 향후 어떤 상황(신규 배포, 이력 삭제)에서도 DAG가 활성화될 때 의도치 않은 작업이 수행되지 않음을 100% 보장할 수 있습니다.
- **안정성**: 스케줄러의 동작에 영향을 주지 않고 DAG 내부에서 안전하게 처리가 가능합니다.
- **표준화**: 이 가드 패턴을 모든 신규 DAG에 적용하여 프로젝트 전체의 스케줄링 정책을 일관되게 유지할 수 있습니다.

### 6. 현 상태 및 결정

- **결정 사항**: 현재 해당 현상의 발생 빈도가 낮고, 다른 우선순위의 작업을 위해 위 해결 방안의 **즉각적인 코드 구현은 보류**합니다.
- **목적**: 이 문서는 해당 이슈의 원인과 가장 합리적인 해결 방안을 명확히 기록하여, 향후 언제든 다시 논의하고 구현을 진행할 수 있도록 **기술 부채(Technical Debt)로서 관리**하는 것을 목적으로 합니다.


### 7. 구체적 지침 

지침: DAG 안정성 확보를 위한 '실행 시간 검증 가드' 구현

  TO: cursor.ai 개발자
  FROM: 프로젝트 총감독관 (Gemini)
  DATE: 2025-10-30
  SUBJECT: 모든 주요 DAG에 '실행 시간 검증 가드'를 구현하여 스케줄링 안정성을 100% 확보하라.

  1. 목적 (Objective)

  Airflow 스케줄러의 특성으로 인해 발생하는 의도치 않은 과거 스케줄 자동 실행 현상을 원천 차단하여, 모든 DAG가 예측 가능하고 안정적으로 동작하도록 보장하는 것을 목표로 한다.

  2. 배경 (Background)

  현재 dag_daily_batch 등 주요 DAG들은 비활성화(pause) 후 다시 활성화(unpause)할 때, 가장 최근의 과거 스케줄 1개가 자동으로 실행되는 문제가 있다. 이는 불필요한 API 호출과 데이터 중복 처리 등 리소스 낭비와 데이터 무결성 문제를 야기하는 심각한
  이슈이다.

  우리는 이 문제를 해결하기 위해, 스케줄러의 동작 자체를 바꾸는 대신, DAG가 실행될 때 스스로 실행 시점의 유효성을 검사하여, 너무 오래된 실행일 경우 후속 작업을 모두 건너뛰게(Skip) 만드는 '가드(Guard)' 패턴을 도입하기로 결정했다.

  3. 구현 계획 (Implementation Plan)

  ##### 1단계: `start_date` 원상 복구

  가장 먼저, 임시방편으로 적용했던 동적 start_date를 원래의 고정된 날짜로 되돌린다. 이는 DAG의 정체성을 안정적으로 유지하기 위해 필수적이다.

   - 대상 파일:
       - DataPipeline/dags/dag_daily_batch.py
       - DataPipeline/dags/dag_financials_update.py
   - 수정 내용:

   1     # 변경 전
   2     start_date=pendulum.now('Asia/Seoul').subtract(hours=1)
   3
   4     # 변경 후 (예시)
   5     start_date=pendulum.datetime(2025, 1, 1, tz="Asia/Seoul")

  ##### 2단계: 공통 가드 함수 생성

  여러 DAG에서 재사용할 수 있도록, 가드 로직을 별도의 유틸리티 파일로 분리한다.

   - 신규 파일 생성: DataPipeline/src/utils/dag_guards.py
   - 작성 내용:

    1     # DataPipeline/src/utils/dag_guards.py
    2     import pendulum
    3     import logging
    4
    5     logger = logging.getLogger(__name__)
    6
    7     def check_execution_is_recent(**kwargs):
    8         """
    9         DAG의 실행 시점(logical_date)이 현재로부터 너무 오래되었는지 검사합니다.
   10         오래된 스케줄일 경우, 후속 작업을 건너뛰도록 분기합니다.
   11
   12         Returns:
   13             str: 다음 Task의 ID 또는 스킵을 위한 Task ID
   14         """
   15         logical_date = kwargs.get('logical_date')
   16
   17         # 허용 지연 시간 (예: 2일). 이 시간보다 오래된 스케줄은 비정상으로 간주.
   18         allowed_delay = pendulum.duration(days=2)
   19
   20         logger.info(f"가드 검사 시작: 실행 시점 = {logical_date}")
   21
   22         if pendulum.now('Asia/Seoul') > logical_date + allowed_delay:
   23             logger.warning(f"오래된 스케줄 감지. 실행을 건너뜁니다. (허용 지연: {allowed_delay.in_days()}일)")
   24             return 'skip_downstream_tasks'  # 스킵 경로로 분기
   25         else:
   26             logger.info("정상적인 최신 실행입니다. 작업을 계속 진행합니다.")
   27             return 'continue_dag_execution' # 정상 경로로 분기

  ##### 3단계: `dag_daily_batch.py`에 가드 적용

  가장 복잡한 dag_daily_batch.py에 가드 패턴을 적용하는 예시이다.

   1     # dag_daily_batch.py 상단
   2     from airflow.operators.python import BranchPythonOperator
   3     from airflow.operators.empty import EmptyOperator
   4     from src.utils.dag_guards import check_execution_is_recent # 2단계에서 만든 함수

   2. 가드 Task 정의: DAG 정의부(with DAG(...) as dag:) 내에 아래 Task들을 추가한다.

    1     # with DAG(...) as dag:
    2
    3     # 가드 Task: 실행 여부를 분기
    4     check_execution_date_task = BranchPythonOperator(
    5         task_id='check_execution_date',
    6         python_callable=check_execution_is_recent,
    7         doc_md="""
    8         ### 실행 시간 검증 가드
    9         - **목적**: DAG의 실행 시점이 너무 오래된 과거일 경우, 모든 후속 작업을 건너뛰게 하여 불필요한 실행을 방지합니다.
   10         - **분기**:
   11             - `continue_dag_execution`: 정상 실행
   12             - `skip_downstream_tasks`: 모든 작업 건너뛰기
   13         """,
   14     )
   15
   16     # 정상 실행 경로를 시작하는 더미 Task
   17     continue_dag_task = EmptyOperator(
   18         task_id='continue_dag_execution'
   19     )
   20
   21     # 스킵 경로의 종착점이 될 더미 Task
   22     skip_dag_task = EmptyOperator(
   23         task_id='skip_downstream_tasks'
   24     )

    1     # 기존 의존성 코드 전체를 아래 내용으로 교체
    2
    3     # 1. 가드 Task가 가장 먼저 실행되어 두 경로(계속/스킵)로 분기
    4     check_execution_date_task >> [continue_dag_task, skip_dag_task]
    5
    6     # 2. '계속' 경로가 원래의 첫 Task였던 'validate_snapshot_task'를 호출
    7     continue_dag_task >> validate_snapshot_task
    8
    9     # 3. 이후 모든 기존 의존성은 그대로 유지
   10     validate_snapshot_task >> [continue_live_mode_task, continue_simulation_mode_task]
   11     continue_live_mode_task >> sync_stock_master_task
   12     sync_stock_master_task >> update_analysis_target_flags_task
   13     continue_simulation_mode_task >> update_analysis_target_flags_task
   14     update_analysis_target_flags_task >> fetch_latest_low_frequency_candles_task
   15     fetch_latest_low_frequency_candles_task >> [calculate_core_metrics_group, run_technical_analysis_task]
   16     [calculate_core_metrics_group, run_technical_analysis_task] >> load_final_results_task

  ##### 4단계: `dag_financials_update.py`에 가드 적용

  dag_financials_update.py 에도 위와 동일한 패턴을 적용한다. 이 DAG는 구조가 더 단순하므로 적용하기 쉬울 것이다.

   - check_execution_date_task를 추가하고, 기존의 첫 Task였던 run_financials_update_task가 continue_dag_task에 의존하도록 수정한다.

   - unpause 시 의도치 않은 과거 스케줄이 생성되더라도, check_execution_date Task 이후의 모든 Task들이 'skipped' 상태가 되어야 한다.
   - 정상적인 스케줄 시간이나 수동 실행 시에는 모든 Task가 정상 실행되어야 한다.

  ---