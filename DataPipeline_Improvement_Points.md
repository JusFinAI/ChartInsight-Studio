# 데이터 파이프라인 완성도 분석 및 개선점 보고서 (상세)

**문서 목적**: `dag_initial_loader`, `dag_daily_batch` 등 핵심 데이터 파이프라인을 단계적으로 분석하며 발견되는 구조적 문제점, 버그, 개선 아이디어를 상세히 기록하고 관리합니다.

**작성자**: Gemini CLI (총감독관)
**최초 작성일**: 2025년 10월 16일

---

## 1. `dag_initial_loader` 분석 결과

### 1.1. '필터 제로' 로직의 불완전성

- **현상**: `stock_limit=10`으로 테스트 실행 시, 'PLUS 한화그룹주'와 같은 ETF 종목(`0000J0`)이 `apply_filter_zero`에 의해 필터링되지 않고 `live.stocks` 및 `live.candles` 테이블에 포함됨을 확인했습니다.

- **상세 분석**: 현재 `apply_filter_zero` 함수는 'ETF', 'ETN', '스팩' 등 알려진 키워드가 종목명에 포함되어 있는지 여부로 필터링을 수행할 가능성이 높습니다. 하지만 'PLUS 한화그룹주'처럼 상품명에 해당 키워드가 직접적으로 포함되지 않는 경우, 필터 로직이 이를 감지하지 못하고 통과시키게 됩니다.

- **영향**: 
    1.  **분석 모델 오염**: 주식과 다른 특성을 가진 ETF, ETN 등의 데이터가 분석에 포함되어, RS 점수 계산이나 기술적 분석 모델의 정확도를 저해할 수 있습니다.
    2.  **리소스 낭비**: 분석 대상이 아닌 종목의 데이터를 수집하고 저장하며, 분석하는 데 불필요한 API 호출, DB 저장 공간, 연산 리소스를 낭비하게 됩니다.

- **개선 제안**: 필터 로직을 고도화해야 합니다. 종목명 키워드 목록을 확장하는 것뿐만 아니라, API가 제공하는 `market_name` (시장 구분), `company_class_name` (기업 구분) 등 다른 필드 정보를 종합적으로 활용하여, 신종 금융상품(ETF, ETN, 스팩, 리츠 등)을 보다 안정적으로 식별하고 제거하는 로직으로 강화해야 합니다.

### 1.1.1. 적용된 수정(부분 해결)

- **책임 분리 적용**: `sync_stock_master_to_db`에서 `apply_filter_zero` 호출을 제거하여 '원장 동기화'와 '분석 대상 선정'의 책임을 분리했습니다. (참조: `DataPipeline/src/master_data_manager.py`)  
- **분석단 필터링 위치 변경**: 필터링은 DAG 레벨(`dag_initial_loader`)에서 적용되도록 변경되어, 원장 동기화 시 분석 제외 규칙에 의해 정상 종목이 오인되어 비활성화되는 위험을 제거했습니다.  
- **매핑/포맷 보정으로 매핑 실패 감소**: `stock_code`와 `corp_code` 정규화(`stock_code.zfill(6)`, `corp_code.zfill(8)`)를 도입하여 매핑 누락으로 인한 스킵 발생을 줄였습니다. (참조: `DataPipeline/src/dart_api/dart_corp_map.py`, `DataPipeline/src/analysis/financial_engine.py`)  
- **운영 가시성 개선**: `dag_financials_update`에 매핑 디버그 로그를 추가하여 매핑 실패 원인 추적이 가능하도록 했습니다.

> 주의: 위 조치들로 매핑·스킵 관련 문제는 상당 부분 해소되었으나, `apply_filter_zero` 자체의 식별 로직(ETF/ETN/우선주 등 감지)은 여전히 고도화가 필요합니다. (예: 'PLUS 한화그룹주' 같이 이름에 키워드가 없는 ETF는 추가 규칙 필요)

---

## 2. `dag_daily_batch` 분석 결과

### 2.1. 암시적 데이터 의존성 및 비효율적 DB 조회

- **현상**: `sync_stock_master_task` 실행 후, 후속 Task인 `get_managed_stocks_task`가 동일한 정보를 얻기 위해 DB를 다시 조회합니다. `sync_stock_master_task`는 XCom으로 결과물을 반환하지 않습니다.

- **상세 분석**: 현재 DAG의 실행 흐름은 다음과 같습니다.
    1. `sync_stock_master_task`가 실행되어 DB의 `live.stocks` 테이블을 최신 상태로 만듭니다. 이 과정에서 어떤 종목이 활성 상태인지 이미 파악했지만, 이 정보는 Task 종료와 함께 사라집니다.
    2. `get_managed_stocks_task`가 실행되어, 방금 전 Task가 정리한 `live.stocks` 테이블에 다시 접속하여 `SELECT stock_code FROM live.stocks WHERE is_active = True` 쿼리를 실행합니다.
    3. 이 결과를 XCom으로 만들어 후속 분석 Task들(`calculate_rs_score` 등)에 전달합니다.

- **영향**:
    1.  **비효율**: 불필요한 DB 커넥션과 쿼리가 발생하여 미세한 성능 저하와 DB 부하를 유발합니다.
    2.  **가독성 저하**: Airflow UI의 Graph View에서 Task 간의 데이터 연결선(의존성)이 보이지 않아, DAG의 실제 데이터 흐름을 파악하기 어렵습니다. 이는 신규 참여자가 코드를 이해하는 데 드는 시간을 늘리고, 잠재적인 버그를 유발할 수 있습니다.

- **개선 제안**: 데이터 흐름을 명시적이고 효율적으로 만들어야 합니다.
    1. `get_managed_stocks_task`를 DAG에서 **제거**합니다.
    2. `_sync_stock_master` 함수(`sync_stock_master_task`의 callable)가 `sync_stock_master_to_db`의 결과(또는 동기화 후의 활성 종목 리스트)를 받아 `return` 하도록 수정합니다.
    3. 후속 Task들은 `ti.xcom_pull(task_ids='sync_stock_master', ...)`를 통해 이 목록을 직접 받도록 수정합니다.

**진행상태(요약)**
- 제안 1 (`get_managed_stocks_task` 제거): *부분 적용 [부분]* — `get_managed_stocks_task`는 아직 유지되고 있으나, `sync_stock_master_task >> get_managed_stocks_task` 의존성 추가로 경쟁 상태가 해소되었습니다.
- 제안 2 (`_sync_stock_master`가 활성 목록을 반환): *미완료 [대기]* — `_sync_stock_master`는 아직 활성 종목 리스트를 `return`하여 XCom을 생성하지 않습니다. 권장 후속: `_sync_stock_master`가 활성 목록을 반환하도록 간단한 코드 변경을 적용하면 `get_managed_stocks_task`를 제거하거나 역할을 축소할 수 있습니다.
- 제안 3 (후속 Task들이 `sync_stock_master`의 XCom을 사용): *부분 적용 [부분]* — DAG는 XCom 흐름을 사용할 수 있으나 현재 `sync_stock_master`가 XCom을 생산하지 않으므로 완전한 XCom 기반 전환은 미완료입니다.

**변경 이력 및 검증 노트**
- 변경: `dag_initial_loader`에서 `sync_stock_master_task >> get_managed_stocks_task` 의존성 추가로 경쟁 상태 완화 적용. (참조: `DataPipeline/dags/dag_initial_loader.py`)
- 검증: 수동 실행 후 `get_managed_stocks_task`가 `sync_stock_master_task` 완료 후 실행되는 로그 확인.

### 2.2. '필터 제로'의 부적절한 위치로 인한 데이터 오염 위험

- **현상**: `master_data_manager.py`의 `sync_stock_master_to_db` 함수가 DB와 동기화하기 **전에** `apply_filter_zero`를 호출하여, 필터링된 종목 리스트를 기준으로 DB와 비교합니다.

- **상세 분석 (오류 시나리오)**: 이 설계는 다음과 같은 심각한 오작동을 유발합니다.
    1.  **현재 상태**: DB의 `live.stocks` 테이블에는 'A'라는 ETF가 `is_active=True`로 저장되어 있습니다. (현재 필터가 놓치고 있으므로)
    2.  **필터 개선**: 우리가 `apply_filter_zero` 로직을 개선하여 'A' ETF를 완벽하게 걸러내도록 수정했다고 가정합니다.
    3.  **`sync_stock_master_task` 실행**:
        - API는 여전히 'A' ETF를 정상 종목으로 반환합니다.
        - 개선된 `apply_filter_zero`가 'A' ETF를 목록에서 제거합니다.
        - 동기화 로직은 DB에는 'A'가 있는데, 필터링된 API 목록에는 'A'가 없으므로, 이 ETF를 **'상장 폐지'된 것으로 오인**합니다.
    4.  **데이터 오염**: 동기화 로직이 DB에 있는 'A' ETF의 `is_active` 플래그를 `False`로 업데이트합니다. 정상적인 ETF가 상장 폐지된 것처럼 처리되어 버립니다.

- **영향**: 이는 사소한 버그가 아니라, **데이터 파이프라인의 신뢰도를 근본적으로 훼손하는 심각한 설계 결함**입니다. '분석에서 제외'해야 할 대상을 '시장에서 사라진' 대상으로 잘못 처리하여 데이터의 무결성을 파괴합니다.

**현 상태(업데이트)**
 - 적용: `sync_stock_master_to_db`에서 `apply_filter_zero` 호출을 제거하여 '원장 동기화'와 '분석 대상 선정'의 책임을 분리했습니다. 이는 의도치 않은 `is_active` 플래그 변경으로 인한 데이터 오염 위험을 해소합니다. (참조: `DataPipeline/src/master_data_manager.py`)
 - 남은 작업: `apply_filter_zero`의 식별 로직(ETF/ETN/우선주 감지)을 고도화해야 합니다. 현재 일부 ETF 상품명(예: 'PLUS 한화그룹주')처럼 키워드만으로는 탐지되지 않는 케이스가 존재합니다.

**변경 이력 및 검증 노트**
- 변경: `apply_filter_zero` 호출 제거(원장 동기화 단계). 검증: `dag_initial_loader` 수동 실행 시 `live.stocks`에 대한 의도치 않은 `is_active` 변경이 발생하지 않음을 확인.

### 2.3. 기능 누락: 'sector_rs' (업종 상대강도) 미구현

- **현상**: `calculate_rs_score` Task 실행 결과, 모든 종목의 `sector_rs` 값이 `None`으로 반환됨을 확인했습니다.
- **상세 분석**: 참조 코드로 제공된 `market_sector_rs_calcurator_all_final.py`와 비교했을 때, 현재 파이프라인에는 업종 RS 계산에 필수적인 (1) 업종 마스터 목록 수집, (2) 종목별 업종 코드 매핑, (3) 업종별 캔들 데이터 조회 및 계산 로직 전체가 누락되어 있습니다.
- **영향**: 서비스 기획의 핵심 분석 지표 중 하나인 '업종 대비 상대강도'를 사용자에게 제공할 수 없습니다. '시장 주도주'를 발굴한다는 파이프라인의 최종 목표 달성에 한계가 있습니다.
- **개선 제안**: 참조 코드를 청사진 삼아, (1) 업종 마스터 동기화 Task, (2) 종목 정보에 업종 코드 추가, (3) `calculate_rs_score` Task에 업종 RS 계산 로직 추가 등 단계적인 기능 구현이 필요합니다.

### 2.4. 기능 누락: '기술적 분석' 로직 미구현

- **현상**: `run_technical_analysis` Task 실행 결과, 모든 종목의 `sma_20`, `rsi_14`, `pattern` 등 모든 분석 값이 `None`으로 반환되었습니다. 또한, 1343개 종목에 대한 분석이 1초 이내에 비정상적으로 빠르게 완료되었습니다.
- **상세 분석**: Task가 호출하는 `analyze_technical_for_stocks` 함수(`src/analysis/technical_analyzer.py`)가 실제 계산 로직 없이, 단순히 `None` 값으로 채워진 딕셔너리를 반환하는 '목업(mock-up)' 상태로 추정됩니다. DB 조회나 계산이 없으므로 실행 시간이 비정상적으로 빠른 것입니다.
- **영향**: 기술적 분석 지표를 전혀 사용할 수 없습니다. 파이프라인이 '성공'으로 표시되지만 실제로는 핵심 분석 중 하나를 수행하지 않는 상태입니다.
- **개선 제안**: `analyze_technical_for_stocks` 함수 내부에 `live.candles` 테이블의 일봉 데이터를 조회하여, 이동평균선(SMA), RSI 등 실제 기술적 지표를 계산하는 로직을 구현해야 합니다.

### 2.5. 데이터 중복 적재 결함: 부정확한 UPSERT 기준

- **현상**: 동일한 날짜에 `dag_daily_batch`를 여러 번 실행할 경우, `daily_analysis_results` 테이블에 동일한 종목에 대한 분석 결과가 중복으로 쌓입니다. (예: '000150' 종목에 대해 2025-10-16 날짜로 2개의 행이 생성됨).
- **상세 분석**: `load_final_results` Task의 UPSERT 로직이 `on_conflict_do_update`의 기준으로 `['analysis_date', 'stock_code']`를 사용합니다. 이때 `analysis_date` 컬럼이 `DateTime` 타입이므로, 실행 시점(초 단위까지)이 다르면 DB는 이를 별개의 데이터로 인식하여 중복으로 처리하지 않고 새로운 행을 `INSERT`합니다.
- **영향**: 파이프라인의 멱등성(Idempotency, 여러 번 실행해도 결과가 동일한 성질)이 깨져, 재실행 시 데이터가 오염됩니다. 분석 시 정확한 '하루치' 데이터를 식별하기 어려워지며, 데이터 무결성을 심각하게 훼손합니다.
**현 상태(업데이트)**
 - 적용: `DailyAnalysisResult.analysis_date` 컬럼이 `Date` 타입으로 변경되어 중복 적재로 인한 문제를 해소했습니다. (참조: `DataPipeline/src/database.py`)
 - 검증: 다중 실행 시 동일 `analysis_date`/`stock_code`에 대해 `INSERT` 대신 `UPDATE`가 발생함을 로그로 확인했습니다.

**변경 이력 및 검증 노트**
- 변경: `DailyAnalysisResult.analysis_date` 컬럼 타입 변경 및 `_load_final_results`에서 `logical_date` 변환 적용. 검증: 동일 날짜에 DAG를 여러 번 실행해도 중복 행이 생성되지 않음을 확인.

### 2.6. DAG 의존성 설정 오류: 경쟁 상태(Race Condition) 발생

- **현상**: `dag_daily_batch`에서 `sync_stock_master_task`가 다른 분석 Task들과 아무런 의존성 없이 독립적으로 정의되어 있어, DAG 실행 시 병렬로 실행됩니다.
- **상세 분석**: `live.stocks` 테이블을 **수정하는** `sync_stock_master_task`와, 이 테이블을 **읽는** `get_managed_stocks_task`가 동시에 실행되어 '경쟁 상태(Race Condition)'를 유발합니다. 만약 `get_managed_stocks_task`가 먼저 실행되면, 당일의 최신 종목 변경(신규/상장폐지)이 반영되지 않은, 하루 전의 낡은 데이터를 가지고 전체 분석을 수행하게 됩니다.
- **영향**: 분석 데이터의 최신성을 보장할 수 없으며, 실행할 때마다 '운'에 따라 분석 대상이 달라져 결과의 일관성과 신뢰도를 보장할 수 없습니다.
- **개선 제안**: `sync_stock_master_task`가 모든 분석 Task의 **가장 첫 단계**로 실행되도록 명시적인 의존성을 설정해야 합니다. 구체적으로 `sync_stock_master_task >> get_managed_stocks_task` 관계를 설정하여, 종목 마스터 동기화가 완료된 후에만 분석 대상 선정이 시작되도록 보장해야 합니다.

---

### 2.7. 재무 분석 핵심 기능 누락: DART 기업 코드 매핑 로직 부재 (해결됨)

- 상태: **해결(완료)**

- 요약(조치 및 결과): `dag_financials_update`가 DART `corp_code`를 정상적으로 조회하지 못해 재무 분석이 건너뛰어지던 문제가 해결되었습니다. 주요 보정 내용은 다음과 같습니다:
  1. `DataPipeline/src/analysis/financial_engine.py`에서 `fetch_live_financial_data`에 `corp_code = str(corp_code).zfill(8)`를 추가하여 DART가 기대하는 8자리 포맷을 보장했습니다.
  2. `DataPipeline/src/dart_api/dart_corp_map.py`에서 `get_corp_code`에 `stock_code` 정규화(`stock_code = stock_code.zfill(6)`)와 반환되는 `corp_code`의 8자리 패딩을 적용했습니다.
  3. `DataPipeline/dags/dag_financials_update.py`에 매핑 디버그 로그를 추가하여 매핑 실패 원인 추적을 용이하게 했습니다.

- 검증: 변경 후 Airflow 스케줄러 재시작 및 DAG 수동 트리거로 아래 로그 요약을 확인했습니다:

```
DEBUG PRINT: 재무 분석 완료 - 성공: 6, 실패: 0, 건너뜀: 4, 총: 10
```

- 건너뜀 항목 설명(정상 제외):
  - `001`, `101`: KOSPI/KOSDAQ 지수(인덱스) — 의도적으로 매핑 대상이 아님
  - `000105`: 우선주(유한양행우) — CORPCODE.xml에 매핑되지 않음(우선주는 별도 처리 대상)
  - `0000J0`: 문자 포함 코드(예: ETF/상품) — CORPCODE.xml 캐시에는 숫자형 `stock_code`만 표준적으로 포함되어 매핑 누락

- 결론: 본 이슈의 근본 원인은 포맷 불일치 및 CORPCODE.xml의 정책(우선주/ETF 제외 가능성)이었으며, 정규화(zfill)와 캐시 조회 보정으로 문제를 해소했습니다. 이후 필터 제로 로직 고도화를 병행하면 동일한 현상이 재발하지 않습니다.


---

## 3. 테스트 및 운영 관련

### 3.1. 테스트 비효율성: 소규모 데이터셋 테스트의 어려움

- **현상**: 테스트를 위해 `dag_initial_loader`에서 `stock_limit=10`으로 DB를 구성했음에도, `dag_daily_batch`를 실행하자 첫 Task인 `sync_stock_master`가 이 설정을 무시하고 DB를 필터링된 전체 종목(~1300개)으로 다시 동기화해버립니다.
- **상세 분석**: `dag_daily_batch`는 `dag_initial_loader`의 실행 설정을 알지 못하며, `sync_stock_master`는 항상 전체 시장과의 동기화를 시도하도록 설계되어 있습니다. 이로 인해 빠른 단위 테스트나 디버깅을 위해 소규모 데이터셋을 구성한 의미가 사라지고, 전체 분석에 3시간 이상이 소요되는 비효율적인 테스트 사이클이 강제됩니다.
- **영향**: 개발 및 디버깅 과정에서의 '빠른 피드백'이 불가능해져 생산성이 저하되고, 잠재적인 버그를 수정하고 검증하는 데 과도한 시간이 소요됩니다.
- **개선 제안**: `dag_daily_batch`가 수동 실행 시 분석 대상을 지정할 수 있는 파라미터(예: `target_stock_codes`)를 받도록 수정해야 합니다. `get_managed_stocks_from_db` Task가 이 파라미터 유무를 확인하여, 파라미터가 있으면 해당 종목 리스트를, 없으면 기존처럼 DB 전체를 대상으로 분석을 진행하도록 분기 처리하는 로직을 추가하여 테스트 효율성을 확보해야 합니다.

---

## 4. DAG 실행 컨텍스트 문제

### 4.1. 특정 DAG의 DB 데이터 조회 실패 현상

- **현상**: `dag_financials_update` 실행 시, `analyze_and_store_financials` Task가 DB에 아무런 데이터를 저장하지 못하고 0건을 처리한 것으로 종료되었습니다. 상세 로그 분석 결과, Task가 DB에서 분석 대상 종목을 조회하는 첫 단계(`get_managed_stocks_from_db`)부터 0개의 결과를 반환하여, 후속 분석 로직이 전혀 실행되지 않았습니다.

- **상세 분석**: 이 현상의 심각성은, 동일한 `get_managed_stocks_from_db` 함수가 `dag_daily_batch` 내에서는 1343개의 종목을 정상적으로 반환했다는 점에 있습니다. 동일한 코드와 동일한 DB 상태임에도 불구하고, 어떤 DAG에서 실행되느냐에 따라 결과가 달라지는 모순적인 상황입니다. 이는 개별 Task의 로직 문제가 아닌, DAG가 실행되는 환경(Context) 자체의 문제일 가능성이 높습니다.

- **영향**: 이 문제는 데이터 파이프라인의 **신뢰성과 예측 가능성**을 근본적으로 위협합니다. 특정 DAG가 '조용한 실패(Silent Failure)'를 일으켜 데이터를 누락시키는 현상은 감지하기 매우 어려우며, 데이터의 완전성을 보장할 수 없게 만듭니다. 이는 전체 시스템에 대한 신뢰를 무너뜨릴 수 있는 심각한 문제입니다.
- **개선 제안**: 근본 원인으로 추정되는 **DAG별 DB 세션 또는 SQLAlchemy 모델 메타데이터의 초기화 문제**에 대한 심층적인 디버깅이 필요합니다. 각 DAG가 다른 DAG의 실행에 영향을 받지 않고, 독립적이며 일관된 DB 컨텍스트를 가질 수 있도록 보장하는 아키텍처 검토 및 수정이 시급합니다.
