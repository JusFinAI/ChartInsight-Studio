# 데이터 파이프라인 RS 점수 계산 기능 구현 계획서 (v1.1)

**문서 목적**: `dag_daily_batch` 파이프라인의 핵심 분석 기능인 시장 상대강도(Market RS) 및 업종 상대강도(Sector RS) 점수 계산 로직을 구현하기 위한 체계적인 실행 계획을 수립합니다.

---

## 1. 배경 및 분석 요약

4단계에 걸친 심층 분석을 통해, RS 점수 계산 기능 구현에 필요한 모든 기술적 요구사항과 현재 아키텍처의 상태 파악을 완료했습니다.

-   **구조적 준비 완료**: `dag_daily_batch`는 RS 점수와 재무 등급을 `calculate_core_metrics` TaskGroup으로 통합할 준비가 되어 있습니다.
-   **청사진 확보**: Sector RS 구현에 필수적인 업종 마스터 수집 및 종목-업종 매핑 로직의 완벽한 청사진(`market_sector_rs_calcurator_all_final.py`)을 확보했습니다.
-   **기반 기술 존재**: `data_collector.py`는 이미 업종/지수(3자리 코드)와 일반 주식(6자리 코드)을 구분하여 처리할 수 있는 스마트한 기능을 내장하고 있습니다.
-   **선행 데이터 확보**: Market RS 계산의 기준이 되는 시장 지수(KOSPI/KOSDAQ) 월봉 데이터는 `dag_initial_loader`를 통해 이미 안정적으로 수집되고 있습니다.

## 2. 실행 원칙

-   **데이터 기반 우선 (Foundation First)**: 계산 로직 구현에 앞서, 데이터가 수집되고 가공되는 파이프라인의 아키텍처를 먼저 견고하게 구축합니다. 이는 장기적인 안정성과 확장성을 보장하는 최우선 원칙입니다.
-   **단계적 구현 (Phased Implementation)**: 기능의 의존성을 고려하여, **데이터 기반 구축(Phase 1)**을 먼저 완료한 후, **계산 로직 구현(Phase 2)**을 진행하여 복잡성을 관리하고 점진적으로 가치를 전달합니다.
-   **기존 아키텍처 존중 (Respect Existing Architecture)**: 새로운 모듈을 만들기보다, 이미 검증된 `data_collector.py`와 `dag_daily_batch.py`의 구조를 최대한 재사용하고 확장하여 아키텍처의 일관성을 유지합니다.

---

## 3. 단계별 실행 계획

### Phase 1: 업종(Sector) 데이터 기반 구축 (Foundation First)
> **목표**: Sector RS 구현에 필요한 데이터 수집/가공 아키텍처를 먼저 완성합니다.

**Task 1.1: 데이터베이스 스키마 확장**
-   **대상 파일**: `DataPipeline/src/database.py`
-   **수행 작업**: 
    1.  **`Sector` 테이블 추가**: 업종 마스터 목록(업종 코드, 업종명, 소속 시장 등)을 저장할 `Sector` 모델(테이블)을 새로 정의합니다.
    2.  **`Stock` 테이블 수정**: 기존 `Stock` 모델에 `sector_code` 컬럼(String, nullable)을 추가하여, 각 종목이 어떤 업종에 속하는지 저장할 수 있도록 합니다.

**Task 1.2: 업종 마스터 데이터 수집 DAG 신설**
-   **대상 파일**: `DataPipeline/dags/dag_sector_master_update.py` (신규 생성)
-   **수행 작업**: 
    1.  매주 1회 실행되는 간단한 신규 DAG를 생성합니다.
    2.  이 DAG는 Kiwoom API(`ka10101`)를 호출하여 KOSPI/KOSDAQ의 전체 업종 목록을 가져와 `sectors` 테이블에 UPSERT하는 단일 Task를 가집니다.

**Task 1.3: 종목 마스터 동기화 로직 수정 (업종 코드 매핑)**
-   **대상 파일**: `DataPipeline/src/master_data_manager.py`
-   **수행 작업**: 
    1.  `sync_stock_master_to_db` 함수를 수정합니다.
    2.  Kiwoom API(`ka10099`)로부터 받은 개별 종목 정보의 업종명(`upName`)을, DB의 `sectors` 테이블과 조인/비교하여 해당하는 `sector_code`를 찾습니다.
    3.  찾아낸 `sector_code`를 `Stock` 객체의 `sector_code` 필드에 업데이트하는 로직을 추가합니다.

**Task 1.4: 업종 월봉 데이터 수집 기능 추가**
-   **대상 파일**: `DataPipeline/dags/dag_daily_batch.py`
-   **수행 작업**: 
    1.  `_fetch_latest_low_frequency_candles` Task를 수정합니다.
    2.  DB의 `sectors` 테이블에서 모든 `sector_code` 리스트를 조회합니다.
    3.  기존의 분석 대상 종목 리스트와 방금 조회한 업종 코드 리스트를 합쳐, `collect_and_store_candles` 함수를 호출하여 업종의 월봉 데이터도 함께 수집하도록 확장합니다.

---

### Phase 2: RS 점수 계산 로직 구현 및 통합
> **목표**: 견고하게 구축된 데이터 기반 위에서 실제 계산 로직을 구현하고 최종 검증합니다.

**Task 2.1: `rs_calculator.py` 로직 통합 구현**
-   **대상 파일**: `DataPipeline/src/analysis/rs_calculator.py`
-   **수행 작업**: Phase 1에서 준비된 데이터를 활용하여, `calculate_rs_for_stocks` 함수 내에 Market RS와 Sector RS를 계산하는 로직을 모두 구현합니다.

**Task 2.2: `dag_daily_batch` 통합 및 최종 검증**
-   **대상 파일**: `DataPipeline/dags/dag_daily_batch.py`
-   **수행 작업**: `dag_daily_batch`를 최종 실행하여, `market_rs_score`와 `sector_rs_score` 두 컬럼 모두에 `NULL`이 아닌 숫자 값이 정상적으로 저장되는지 확인합니다.

---

## 4. 다음 단계

본 계획에 대한 승인이 완료되면, **Phase 1: 업종(Sector) 데이터 기반 구축**의 **Task 1.1**부터 즉시 착수하겠습니다.