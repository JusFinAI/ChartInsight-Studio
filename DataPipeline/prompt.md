
### **`dag_initial_loader.py` 리팩토링 및 기능 확장을 위한 프롬프트 (for Cursor.ai)**

#### **컨텍스트 및 목표 (Context & Goal) - 수정된 버전**

목표: 현재 구현된 dags/dag_initial_loader.py를 'PRD Ver 3.2.md'의 모든 요구사항을 충족하도록 확장 및 리팩토링하는 것이 목표다.

현재 상태: 현재 코드는 PRD에 명시된 기능 중 '단일 작업 모드' (특정 종목, 특정 타임프레임만 적재)만 구현된 상태다.

추가 요구사항: 여기에 더해, PRD의 또 다른 핵심 요구사항인 '일괄 작업 모드' (모든 타겟 종목, 모든 타임프레임 동시 적재)와 '특정 종목 전체 타임프레임 적재 모드' 기능을 추가해야 한다.

최종 결과물: 하나의 DAG가 Airflow UI에서 받는 config 값에 따라 '단일 작업', '특정 종목 전체', '전체 일괄 작업'을 모두 지능적으로 처리할 수 있어야 한다.

#### **컨텍스트 및 현재 상태 (Context & As-Is)**

1.  **핵심 요구사항 문서:** 모든 개발의 기준은 **`PRD Ver 3.2.md`** 문서다. 이 문서를 최우선으로 참고해야 한다.
2.  **현재 `dag_initial_loader.py`의 한계:** 지금의 코드는 Airflow UI의 "Trigger DAG with config"를 통해 **단 하나의 종목, 단 하나의 타임프레임**에 대한 초기 적재만 수행할 수 있도록 구현되어 있다.
3.  **궁극적인 목표:** 이 DAG의 원래 목적은, 운영자가 단 한 번의 실행으로 **30개 타겟 종목 전체에 대한 모든 타임프레임(총 150개 작업)의 초기 데이터를 DB에 적재**하는 것이다.

#### **리팩토링 요청사항 (Requirements & To-Be)**

현재의 `dag_initial_loader.py`를 다음과 같이 수정하여, \*\*'단일 작업 모드'\*\*와 \*\*'일괄 작업 모드'\*\*를 모두 지원하는 지능적인 DAG로 만들어달라.

##### **1. 어댑터 함수 `_run_initial_load_task` 로직 수정**

`PythonOperator`가 호출하는 `python_callable` 함수(현재 `_run_initial_load_task` 또는 유사한 이름)의 내부 로직을 다음과 같이 수정해야 한다.

  * **`config` 기반 분기 처리:** 함수는 `kwargs['dag_run'].conf`를 통해 전달받은 `config` 딕셔너리를 분석하여 동작 모드를 결정한다.

      * **IF `config`에 `run_all_targets: true`가 포함된 경우 (일괄 작업 모드):**

        1.  `src.utils.common_helpers`에서 `get_target_stocks()`를 `import`하여 30개 종목 리스트를 가져온다.
        2.  `TARGET_TIMEFRAMES = ['5m', '30m', '1h', 'd', 'w']` 리스트를 정의한다.
        3.  "일괄 초기 적재 작업을 시작합니다..." 와 같은 정보성 로그를 남긴다.
        4.  **이중 `for` 반복문**을 사용하여 `TARGET_STOCKS`와 `TARGET_TIMEFRAMES`를 순회한다.
        5.  반복문 내부에서, 현재의 `stock_code`와 `timeframe`을 인자로 `load_initial_history()` 함수를 호출한다. `period`, `base_date`, `execution_mode` 등 다른 파라미터는 `config`에서 받아 전달한다.
        6.  `load_initial_history()` 호출 후, API 서버 보호를 위해 `time.sleep(0.3)`을 실행한다.

      * **ELIF `config`에 `stock_code`가 포함된 경우 (단일 작업 모드):**

        1.  기존 로직과 동일하게, `config`에서 받은 파라미터를 사용하여 `load_initial_history()` 함수를 **단 한 번** 호출한다.

      * **ELSE (잘못된 설정):**

        1.  유효하지 않은 `config`임을 알리는 에러 로그를 남기고 `ValueError`를 발생시켜 Task를 실패 처리한다.

##### **2. DAG `params` 정의 업데이트**

`DAG()` 객체에 전달하는 `params` 딕셔너리를 수정하여, 두 가지 모드를 모두 지원하고 UI에서 명확하게 보이도록 만들어야 한다.

```python
# params 수정 예시
params={
    "run_all_targets": Param(type="boolean", default=False, title="✅ 전체 타겟 종목 실행", description="이 옵션을 True로 설정하면 아래 stock_code와 timeframe은 무시되고, 30개 전체 종목/5개 타임프레임에 대한 일괄 적재를 수행합니다."),
    "stock_code": Param(type=["null", "string"], default=None, title="종목 코드 (단일 작업용)"),
    "timeframe": Param(type=["null", "string"], default=None, title="타임프레임 (단일 작업용)", enum=["5m", "30m", "1h", "d", "w", None]),
    "period": Param(type="string", default="2y", title="조회 기간", description="기준일로부터의 과거 기간 (예: '2y', '6m')"),
    "base_date": Param(type=["null", "string"], default=None, title="기준일 (YYYYMMDD)"),
    "execution_mode": Param(type="string", default="LIVE", title="실행 모드", enum=["LIVE", "SIMULATION"])
}
```

#### **최종 테스트 시나리오**

이 리팩토링이 완료되면, 다음과 같은 시나리오로 테스트할 수 있어야 한다.

  * **LIVE 모드 일괄 테스트:**

      * **실행:** Airflow UI에서 `dag_initial_loader`를 `{"run_all_targets": true, "period": "2y", "execution_mode": "LIVE"}` 설정으로 Trigger.
      * **검증:** 하나의 DAG Run이 생성되고, 그 안의 Task가 150개의 작업을 순차적으로 처리하며 DB에 실제 과거 데이터를 적재하는지 로그를 통해 확인.

  * **SIMULATION 모드 단일 테스트:**

      * **실행:** Airflow UI에서 `{"stock_code": "005930", "timeframe": "d", "period": "1y", "execution_mode": "SIMULATION"}` 설정으로 Trigger.
      * **검증:** Task가 `load_initial_history`를 `SIMULATION` 모드로 한 번만 호출하여, Parquet 파일로부터 데이터를 읽어와 DB에 저장하는지 확인.

#### **요청사항 요약**

위 요구사항을 모두 반영하여, **수정된 `dags/dag_initial_loader.py` 파일의 전체 코드를 작성**해달라.

-----

만약 이 요구사항을 완벽하게 구현하기 위해 추가적으로 필요한 정보나 명확히 해야 할 부분이 있다면, 주저하지 말고 질문해달라.