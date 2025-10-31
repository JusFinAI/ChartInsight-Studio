# RS 점수 계산 기능 구현 완료 보고서 (v1.0)

**문서 목적**: `dag_daily_batch` 파이프라인의 핵심 기능인 시장/업종 상대강도(RS) 점수 계산 기능의 초기 계획부터, 아키텍처 논의, 단계별 구현, 오류 수정, 그리고 최종 검증까지의 전 과정을 상세히 기록하여, 프로젝트의 이력 관리 및 향후 유지보수를 위한 기술 자산으로 활용합니다.

**최종 결과**: **RS 점수 계산 기능 구현 및 통합 완료.**
- `dag_daily_batch`는 이제 매일 모든 분석 대상 종목에 대해 `market_rs_score`와 `sector_rs_score`를 성공적으로 계산하고 `daily_analysis_results` 테이블에 기록합니다.

**작업 기간**: 2025-10-22

---

## 1. 최종 아키텍처

수차례의 논의와 수정을 거쳐, 아래와 같이 역할과 책임이 명확한 최종 아키텍처를 확정하고 구현했습니다.

-   **`dag_initial_loader` (시스템 초기화 담당)**
    -   **역할**: 깨끗한 데이터베이스 상태에서, 시스템 운영에 필요한 모든 과거 데이터를 완벽하게 준비하는 '초기화' 책임을 가집니다.
    -   **수행 작업**:
        1.  업종 마스터 데이터(`sectors` 테이블) 생성 및 최신화.
        2.  시장 지수(`001`, `101`) 및 전체 업종의 10년치 과거 월봉 데이터 적재.
        3.  사용자가 지정한 개별 종목의 모든 타임프레임 과거 데이터 적재.
        4.  적재된 모든 종목의 `sector_code` 매핑(백필) 작업 수행.

-   **`dag_daily_batch` (매일 증분 업데이트 담당)**
    -   **역할**: 이미 준비된 과거 데이터를 기반으로, 매일 새로 발생한 데이터만 추가하는 '순수 증분 업데이트' 책임을 가집니다.
    -   **수행 작업**:
        1.  `is_analysis_target=True`로 설정된 모든 개별 종목의 일/주/월봉 증분 업데이트.
        2.  모든 시장 지수 및 업종의 일/주/월봉 증분 업데이트.
        3.  최신 데이터를 기반으로 RS 점수 및 기타 기술적 분석 수행.

---

## 2. 상세 실행 이력

### Phase 1: 데이터 기반 구축 (Foundation First)

**Task 1.1: 데이터베이스 스키마 확장**
-   **목표**: Sector RS 계산에 필요한 `sectors` 테이블과 `stocks.sector_code` 컬럼을 DB에 추가.
-   **핵심 지침**: `database.py`에 `Sector` 모델을 추가하고, `Stock` 모델에 `sector_code` 컬럼과 `ForeignKeyConstraint`를 정의.
-   **검증 내역**:
    -   `init_db()` 실행 시 `UndefinedColumn` 오류 발생.
    -   **원인**: `create_all()`은 기존 테이블에 컬럼을 추가하지 않음.
    -   **해결**: `init_db()` 함수에 `ALTER TABLE`과 `CREATE TABLE IF NOT EXISTS`를 실행하는 Raw SQL 로직을 추가하여, 언제 실행해도 스키마가 올바른 상태를 보장하도록 멱등성 확보. (지침서 2.2.2)

**Task 1.2: 업종 마스터 데이터 수집 DAG 신설**
-   **목표**: Kiwoom API(`ka10101`)를 호출하여 `sectors` 테이블을 채우는 주간 스케줄 DAG(`dag_sector_master_update`) 구현.
-   **핵심 지침**: API 호출 로직을 `kiwoom_api/services/master.py`로 분리하고, DAG는 이 서비스 함수를 호출하여 DB에 UPSERT 하도록 지시. (지침서 1.2 개선안)
-   **검증 내역**: DAG 수동 실행 후, `live.sectors` 테이블에 KOSPI/KOSDAQ의 전체 업종 65개가 정상적으로 적재됨을 확인.

**Task 1.3: 종목-업종 매핑 및 백필**
-   **목표**: `stocks` 테이블의 모든 분석 대상 종목에 `sector_code`를 채워 넣기.
-   **핵심 지침**: `fuzzywuzzy` 라이브러리를 이용한 유사도 매핑 알고리즘을 `master_data_manager.py`에 구현하고, 이를 사용하는 백필 스크립트(`scripts/backfill_sector_codes.py`)를 생성. (지침서 1.3 최종 수정안)
-   **검증 내역**:
    -   1차 실행: 4,196개 중 2,726개 성공. 나머지 120개(분석 대상)는 `industry_name` 부재 등으로 실패.
    -   **원인**: 'Filter Zero' 로직이 불완전하여 ETF 등 분석 제외 대상을 제대로 거르지 못함.
    -   **해결**: `Filter Zero` 로직에 `market_name`을 기준으로 ETF/ETN을 제외하는 규칙을 추가. (지침서 1.4)
    -   `upName`이 없는 7개 핵심 종목은 `STOCK_CODE_TO_SECTOR_CODE_MAP`을 이용한 수동 매핑으로 최종 해결. (지침서 1.4.1)
    -   **최종 결과**: 모든 분석 대상 종목의 `sector_code` 매핑 완료.

**Task 1.4: 아키텍처 최종 수정**
-   **목표**: `dag_initial_loader`와 `dag_daily_batch`의 역할을 최종 확정하여 아키텍처의 비일관성 제거.
-   **핵심 지침**:
    1.  `dag_initial_loader`가 모든 기준 데이터(지수, 업종)의 '과거 전체'를 책임지도록 수정. (지침서 1.7)
    2.  `dag_daily_batch`는 '매일의 증분'만 책임지도록, 불필요한 `_refresh_baseline_monthly_candles` Task를 제거하고 `_fetch_latest_low_frequency_candles`를 확장. (지침서 1.8, 1.10)
-   **검증 내역**: 코드 리뷰를 통해 두 DAG의 역할과 책임이 최종 아키텍처에 맞게 완벽하게 수정되었음을 확인.

### Phase 2: RS 계산 로직 구현 및 통합

**Task 2.1: `rs_calculator.py` 로직 활성화**
-   **목표**: `rs_calculator.py`의 `LIVE` 모드에서 `sector_rs` 계산 로직을 최종 활성화.
-   **핵심 지침**: `sector_rs = None` 코드를 삭제하고, `stock_info.sector_code`를 사용하여 업종 캔들 데이터를 조회하고 `calculate_weighted_rs`를 호출하도록 수정. (지침서 2.1 수정안)
-   **검증 내역**: 코드 리뷰를 통해 로직이 올바르게 수정되었음을 확인.

**Task 2.2: 최종 통합 테스트**
-   **목표**: 완성된 아키텍처에서 `dag_daily_batch`를 실행하여, Market/Sector RS가 모두 정상 계산되는지 최종 검증.
-   **핵심 지침**: DB 초기화 후, `dag_initial_loader`로 12개 테스트 종목의 모든 데이터를 적재하고, 이어서 `dag_daily_batch`를 실행. (지침서 2.2 최종 실행)
-   **검증 내역**:
    -   `psql`을 통해 `daily_analysis_results` 테이블을 조회.
    -   `market_rs_score`와 `sector_rs_score` 두 컬럼 모두에 `NULL`이 아닌 유효한 숫자 값이 저장된 것을 최종 확인.
    -   **결과**: **성공.**

---

## 3. 결론 및 향후 과제

**결론**:
본 과제는 초기 계획 수립, 아키텍처 논의, 반복적인 테스트와 수정을 통해 **RS 점수 계산 기능의 안정적인 구현 및 통합을 성공적으로 완료**했습니다. 이 과정에서 데이터 파이프라인의 역할과 책임이 명확해졌으며, 코드의 안정성과 품질이 크게 향상되었습니다.

**향후 과제 (우선순위 순)**:

**1. (P1-Critical) `dag_daily_batch` 증분 업데이트 로직 통합 테스트**
-   **현상**: 현재까지 `dag_initial_loader` 실행 직후의 '첫 실행'만 테스트 완료. 다음 날에도 증분 업데이트가 올바르게 동작하는지는 미검증 상태.
-   **목표**: `dag_daily_batch`를 여러 날짜에 걸쳐 연속으로 실행하는 상황을 시뮬레이션하여, `collect_and_store_candles` 함수가 마지막 데이터 이후의 '증분'만 올바르게 가져오는지 로그와 DB 데이터를 통해 검증.

**2. (P2-High) Airflow DAG 실행 정책 안정화**
-   **현상**: DAG 활성화(unpause) 시, `start_date`가 과거이므로 의도치 않은 과거 날짜의 DAG가 실행되는 등 혼란스러운 동작 발생.
-   **목표**: `catchup`, `max_active_runs` 등 Airflow 파라미터를 검토하고 최적화하여, DAG가 오직 스케줄 또는 명시적 수동 실행에만 반응하도록 동작을 안정화하고 예측 가능하게 만듦.

**3. (P3-Medium) 주간 배치 DAG 통합 테스트**
-   **현상**: `dag_financials_update`(재무)와 `dag_sector_master_update`(업종) DAG가 아직 전체 파이프라인의 일부로서 통합 테스트되지 않음.
-   **목표**: 두 주간 배치 DAG를 실행하고, 그 결과물(DB 테이블)을 `dag_daily_batch`가 다음 실행 시 정상적으로 소비하여 분석을 수행하는지 전체 데이터 흐름을 검증.

**4. (P4-Low) `SIMULATION` 모드 아키텍처 동기화**
-   **현상**: `LIVE` 모드의 아키텍처를 대대적으로 개선하는 동안, `SIMULATION` 모드의 코드는 수정되지 않아 현재 아키텍처와 불일치 상태.
-   **목표**: `rs_calculator.py` 등 `SIMULATION` 모드 분기 로직을 가진 모든 코드를 찾아, `LIVE` 모드와 동일한 데이터 흐름을 따르도록 리팩토링하고, 시뮬레이션 모드 전체에 대한 테스트를 수행.
