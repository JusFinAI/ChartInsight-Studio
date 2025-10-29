### 실행 계획 v7: 완전한 역할 분리 기반 SIMULATION 아키텍처 확립

**최종 목표:** 각 DAG가 자신의 데이터 결과물만 책임지는 **단일 책임 원칙(SRP)**을 완벽히 구현하여, MVP 개발 단계에 최적화된 **빠르고, 단순하며, 신뢰할 수 있는** 백테스팅 환경을 구축한다.

**핵심 아키텍처: 완전한 역할 분리 기반의 DB 스냅샷**

1.  **캔들 데이터 준비 (`dag_initial_loader`):** `live.candles` 데이터를 `simulation.candles`로 복제하여, 특정 시점의 '캔들 데이터 스냅샷'만 생성하는 역할을 전담한다.
2.  **재무 데이터 준비 (`dag_financials_update`):** `live.financial_analysis_results` 데이터를 `simulation.financial_analysis_results`로 복제하여, 특정 시점의 '재무 데이터 스냅샷'만 생성하는 역할을 전담한다.
3.  **분석 실행 (`dag_daily_batch`):** 미리 준비된 `simulation` 스키마의 두 스냅샷을 **변경 없이 그대로 읽어** 분석만 수행하는 역할을 전담한다.
4.  **Parquet 의존성 완전 제거:** MVP 단계에서 불필요한 복잡성을 야기하는 파일 기반 데이터 파이프라인을 폐기한다.

---

#### **0단계: 원본 데이터(Live DB) 무결성 확인 (Prerequisite)**

*   **목표:** 시뮬레이션의 유일한 진실의 원천(Source of Truth)인 `live.candles` 테이블에 백테스팅을 수행하기에 충분한 과거 데이터가 있는지 확인한다.
*   **주요 과업 (Key Tasks):**
    1.  **LIVE 데이터 확인:** `live.candles` 테이블에 원하는 테스트 기간만큼의 데이터가 적재되어 있는지 쿼리를 통해 확인한다.
    2.  **데이터 보강 (필요시):** 데이터가 부족할 경우, `dag_initial_loader`를 **LIVE 모드**로 실행하여 `live.candles` 테이블을 채운다.
*   **근거 (Rationale):** 모든 시뮬레이션은 항상 가장 신뢰할 수 있는 최신 `live` DB를 기반으로 동작함을 보장한다. 이는 데이터 일관성을 극대화하고 관리 포인트를 단순화한다.
*   **진행상황:** ✅ **완료** - `live.candles`에 데이터가 충분히 존재함을 전제로, 모든 개발 및 테스트가 진행되었습니다.

---

#### **1단계: 캔들 데이터 준비 DAG (`dag_initial_loader`) 역할 명확화**

*   **목표:** `dag_initial_loader`가 SIMULATION 모드에서 **오직 캔들 데이터 스냅샷만** 생성하도록 역할을 명확히 한다.
*   **주요 과업 (Key Tasks):**
    1.  **SIMULATION 로직 추가:** `dag_initial_loader`의 `_run_initial_load_task` 함수에 `if execution_mode == 'SIMULATION'` 분기문을 추가한다.
    2.  **캔들 스냅샷 생성 구현:**
        *   SIMULATION 모드일 때, `live.candles`에서 `test_stock_codes`와 `target_datetime`을 기준으로 데이터를 조회하여 `simulation.candles`로 복제하는 함수(`data_collector.create_simulation_snapshot`)를 호출한다.
        *   RS 계산에 필요한 시장/업종 지수 데이터(`001`, `101`, 모든 업종 코드)를 자동으로 포함시킨다.
    3.  **안전장치 구현:** 캔들 데이터 준비가 완료되면, 사용된 `target_datetime`과 `test_stock_codes` 정보를 Airflow Variable(`simulation_snapshot_info`)에 저장한다.
*   **근거 (Rationale):** **단일 책임 원칙(SRP)** - `dag_initial_loader`는 오직 캔들 데이터만 책임지므로, 역할이 명확하고 유지보수가 용이하다.
*   **v7 개선사항:** 재무 데이터 복제 책임을 `dag_financials_update`로 완전히 분리하여, 각 DAG가 자신의 데이터만 관리하도록 아키텍처를 개선했습니다.
*   **진행상황:** ✅ **완료** - v7 아키텍처에 맞춰 `dag_initial_loader.py`가 `include_financials=False`로 캔들 데이터만 처리하도록 수정 완료했습니다.

---

#### **2단계: 분석 DAG (`dag_daily_batch`) 역할 단순화**

*   **목표:** `dag_daily_batch`가 SIMULATION 모드에서 미리 준비된 `simulation.candles`를 읽어 분석만 수행하도록 로직을 극도로 단순화한다.
*   **주요 과업 (Key Tasks):**
    1.  **안전장치 검증 (신규 Task):** DAG 실행 시작 시, `_validate_simulation_snapshot` Task를 가장 먼저 실행하여 `simulation_snapshot_info` Variable의 `snapshot_time`이 현재 DAG의 `execution_time`과 일치하는지 검증한다. 불일치 시, 명확한 오류와 함께 DAG를 실패시킨다.
    2.  **데이터 준비 로직 완전 제거:** `_fetch_latest_low_frequency_candles` Task의 SIMULATION 모드 관련 로직을 모두 **제거**하고, SIMULATION 모드에서는 아무것도 하지 않도록 수정한다.
    3.  **결과물 시점 보장:** `_load_final_results` Task에서 `analysis_date`를 지정할 때, DAG 파라미터로 받은 `execution_time`을 변환하여 사용함으로써 입력과 출력의 시점을 일치시킨다.
*   **근거 (Rationale):** '데이터 준비' 책임을 `dag_initial_loader`에 위임함으로써, `dag_daily_batch`는 데이터의 상태에 대해 전혀 신경 쓸 필요 없이 순수하게 분석 로직 실행에만 집중할 수 있다. 이는 개발자가 알고리즘 개선 시, 데이터 준비 과정 없이 즉시 `dag_daily_batch`만 재실행하면 되므로 **MVP 단계의 실험 속도를 극대화**한다.
*   **진행상황:** ✅ **완료** - `dag_daily_batch.py`에 `BranchPythonOperator`를 사용한 안전장치 및 실행 경로 분기, SIMULATION 모드에서의 데이터 수집 건너뛰기, `analysis_date` 시점 보장 등 모든 로직 수정 및 검수를 완료했습니다.

---

#### **추가 완료 과업: Parquet 의존성 완전 제거**

*   **목표:** 코드베이스에서 Parquet 파일 관련 로직을 완전히 제거하여, 새로운 DB 기반 아키텍처로의 전환을 완성한다.
*   **주요 과업 (Key Tasks):**
    1.  `rs_calculator.py`에서 Parquet 파일을 직접 읽는 `_load_simulation_monthly_data` 함수를 제거하고, `data_collector.get_candles`를 사용하도록 통일했다.
*   **진행상황:** ✅ **완료** - `rs_calculator.py`의 레거시 코드를 성공적으로 제거하고, 모든 데이터 조회가 DB를 통하도록 일원화했습니다.

---

#### **3단계: 재무 데이터 준비 DAG (`dag_financials_update`) SIMULATION 모드 구현**

*   **목표:** `dag_financials_update`가 SIMULATION 모드에서 **오직 재무 데이터 스냅샷만** 생성하도록 역할을 명확히 한다.
*   **주요 과업 (Key Tasks):**
    1.  **SIMULATION 모드 추가:** `dag_financials_update.py`에 `execution_mode` 파라미터를 추가하고, SIMULATION 모드 분기 로직을 구현한다.
    2.  **재무 스냅샷 생성 구현:**
        *   SIMULATION 모드일 때, `live.financial_analysis_results`에서 `target_datetime` 이전의 최신 재무 데이터를 조회하여 `simulation.financial_analysis_results`로 복제한다.
        *   `test_stock_codes`가 비어있으면 모든 종목을 처리하고, 있으면 지정된 종목만 처리하는 유연한 로직 구현.
    3.  **스키마 전환 로직:** SQLAlchemy의 스키마 전환 기능을 사용하여 `simulation` 스키마에 안전하게 데이터를 복제한다.
*   **근거 (Rationale):** **단일 책임 원칙(SRP)** - 재무 데이터는 재무 분석 전용 DAG가 책임지는 것이 아키텍처적으로 가장 명확하고 확장 가능하다.
*   **v7 아키텍처 혁신:** v6에서는 `dag_initial_loader`가 재무 데이터까지 처리하려 했으나, "초기 적재 DAG가 왜 분석 결과를 만드는가?"라는 근본적인 질문을 통해 v7에서 완전히 분리했습니다.
*   **진행상황:** ✅ **완료** - `dag_financials_update.py`에 SIMULATION 모드 구현 완료, `test_stock_codes` 처리 로직 보완 완료.

---

#### **4단계: `dag_daily_batch` 재무 데이터 조회 로직 최종 구현**

*   **목표:** `dag_daily_batch`가 SIMULATION 모드에서 `simulation.financial_analysis_results`를 정확히 조회하도록 구현한다.
*   **주요 과업 (Key Tasks):**
    1.  **스키마 전환 로직 구현:** `_fetch_financial_grades_from_db` 함수에서 `execution_mode`에 따라 `live` 또는 `simulation` 스키마를 동적으로 선택하도록 수정.
    2.  **안전한 스키마 복원:** `try-finally` 블록을 사용하여 스키마를 원래대로 복원함으로써 다른 Task에 영향을 주지 않도록 보장.
    3.  **Graceful Failure:** 재무 데이터가 없어도 다른 분석(RS, 기술적 분석)은 정상 진행되도록 에러 처리 구현.
*   **근거 (Rationale):** v7 아키텍처의 완성 - `dag_daily_batch`는 이제 두 개의 독립적인 스냅샷(`candles`, `financial_analysis_results`)을 조합하여 완전한 분석을 수행한다.
*   **진행상황:** ✅ **완료** - `dag_daily_batch.py`의 `_fetch_financial_grades_from_db` 함수 수정 완료, 스키마 전환 및 복원 로직 구현 완료.

---

#### **5단계: v7 아키텍처 End-to-End 검증 전략**

*   **목표:** v7 아키텍처가 기술적으로 올바르고, 신뢰할 수 있음을 객관적인 데이터로 증명한다.
*   **주요 과업 (Key Tasks):**
    1.  **End-to-End 테스트 시나리오 정의 (v7 업데이트):**
        *   **1단계 (캔들 데이터 준비):** `dag_initial_loader`를 `execution_mode='SIMULATION'`, `target_datetime='2025-08-01 16:00:00'`, `test_stock_codes='005930,000660'`으로 트리거.
        *   **2단계 (재무 데이터 준비):** `dag_financials_update`를 `execution_mode='SIMULATION'`, `target_datetime='2025-08-01 16:00:00'`, `test_stock_codes='005930,000660'`으로 트리거.
        *   **3단계 (분석 실행):** `dag_daily_batch`를 `execution_mode='SIMULATION'`으로 트리거 (`target_datetime` 자동 감지).
    2.  **검증 쿼리 실행 및 결과 확인:**
        *   **캔들 데이터 스냅샷 검증:** `SELECT COUNT(*) FROM simulation.candles WHERE timestamp > '2025-08-01 23:59:59+09:00'` → **0**
        *   **재무 데이터 스냅샷 검증:** `SELECT COUNT(*) FROM simulation.financial_analysis_results` → **> 0**
        *   **완전한 분석 결과 검증:** `SELECT stock_code, market_rs_score, sector_rs_score, financial_grade FROM simulation.daily_analysis_results WHERE analysis_date = '2025-08-01'` → 모든 컬럼 **NOT NULL**
        *   **데이터 일관성 검증:** `live` 스키마와 `simulation` 스키마의 데이터 개수 일치 확인.
*   **근거 (Rationale):** v7 아키텍처는 세 개의 독립적인 DAG가 협력하는 구조이므로, 각 DAG의 출력물과 최종 통합 결과를 모두 검증해야 한다.
*   **진행상황:** ⏳ **다음 단계** - 모든 코드 구현이 완료되었으므로, 최종 통합 테스트를 수행할 준비가 완료되었습니다.