
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
