# TRADING LAB 데이터 파이프라인 구축 계획 (v2.1)

---
## ⚠️ 보관 문서 알림 (ARCHIVED DOCUMENT)

**작성 시점**: 2025-10-13  
**보관 일자**: 2025-10-31  
**보관 이유**: Phase 1-5 완료로 인한 통합

**⛔ 이 문서는 역사적 기록입니다.**
- 현재 프로젝트 상태를 반영하지 않습니다
- 학습 및 참조 목적으로만 사용하세요
- **최신 정보**: `DataPipeline_Project_Roadmap.md v2.0` 참조

**관련 통합 문서**: 
- `DataPipeline_Project_Roadmap.md v2.0` - Phase 1-4 섹션 참조
---

**문서 상태: `v1.1` 계획 대부분 완료. `Phase 5` 계획 수정 및 구체화.**

## 1. 계획의 목적 및 배경

본 계획의 최종 목표는 "TRADING LAB 서비스 기획서"에 명시된 데이터 중심의 투자 분석 워크플로우를 지원하는 핵심 데이터 파이프라인을 완성도 있게 구현하는 것입니다.

- **Level 1 (넓고 얕게)**: '필터 제로'를 통과한 전체 분석 대상 종목에 대해 저빈도 데이터(일/주/월봉) 기반의 핵심 지표(RS, 재무 등급 등)를 매일 계산합니다.
- **Level 2 (좁고 깊게)**: Level 1 종목 중 '주도주' 후보군에 대해서만 고빈도 데이터(5분봉 등)를 집중 수집하여 실시간 분석을 수행합니다.

이 문서는 `dag_daily_batch`를 중심으로 한 **Level 1** 데이터 파이프라인의 구축 과정과 향후 계획을 정의합니다.

---

## 2. 단계별 실행 계획 (v1.1) 및 결과

### [Phase 1: 기반 공사 (Foundations)]

- **Step 1: `daily_analysis_results` 테이블 모델 정의**
  - **수행 결과**: `[완료]` `database.py`에 모델이 성공적으로 추가되었고, `load_final_results` Task를 통해 DB에 실제 데이터가 적재됨을 확인했습니다.

- **Step 2: 핵심 분석 로직 모듈화**
  - **수행 결과**: `[완료]` `src/analysis/` 경로에 `rs_calculator.py`, `financial_analyzer.py`, `technical_analyzer.py` 모듈이 생성되었습니다. RS와 재무 분석기는 실제 계산 로직으로 구현되었고, 기술적 분석은 현재 목업 상태입니다.

### [Phase 2: 유틸리티 DAG 업그레이드 (`dag_initial_loader`)]

- **Step 3 ~ 4: `dag_initial_loader` 기능 확장**
  - **수행 결과**: `[보류]` `dag_daily_batch` 개발에 집중하기 위해, 해당 DAG의 기능 확장은 이번 작업 범위에서 제외되었습니다. 추후 필요시 진행합니다.

### [Phase 3: 신규 배치 DAG 개발 (`Daily Batch DAG`)]

- **Step 5 ~ 12: `dag_daily_batch` 전체 Task 구현**
  - **수행 결과**: `[완료]` `sync_stock_master`부터 `load_final_results`까지 모든 Task의 논리적 흐름이 구현되었고, XCom을 통한 데이터 전달이 정상적으로 작동함을 확인했습니다.

### [Phase 4: 통합 및 검증]

- **Step 13: `dag_initial_loader` 기능 검증**
  - **수행 결과**: `[보류]` Phase 2가 보류됨에 따라, 이 단계 역시 추후 진행합니다.

- **Step 14: `Daily Batch DAG` 통합 검증**
  - **수행 결과**: `[완료]` 수동 트리거를 통해 DAG 전체가 성공적으로 실행되었고, 최종 결과가 `daily_analysis_results` 테이블에 정상적으로 적재됨을 확인했습니다.

### [추가 단계: 개발 환경 및 운영 기반 개선]

*이 단계는 초기 계획에는 없었지만, 프로젝트의 안정성과 확장성을 위해 추가로 진행된 중요한 작업들입니다.*

- **환경 변수 관리 체계 수립**:
  - **수행 결과**: `[완료]` 로컬 개발용(`.env.local`)과 Docker 컨테이너용(`.env.docker`) 환경 변수 파일을 분리하여, 어떤 환경에서든 동일한 코드가 유연하게 작동할 수 있는 기반을 마련했습니다.

- **데이터 생성 스크립트 표준화**:
  - **수행 결과**: `[완료]` `prepare_test_data.py`를 `scripts/prepare_simulation_dataset.py`으로 리팩토링하고, `fetch_sector_master.py`를 신규 개발하여, 시뮬레이션에 필요한 모든 데이터를 체계적으로 생성하고 관리할 수 있게 되었습니다.

- **KST 로깅 헬퍼 도입**:
  - **수행 결과**: `[완료]` `src/utils/logging_kst.py`를 통해 운영자가 로그를 더 쉽게 판독할 수 있도록 가독성을 향상시켰습니다.

---

## 3. 향후 계획: Phase 5 (수정안 v2.1)

### [Phase 5: 아키텍처 개선 및 분석 엔진 고도화]

*이 단계의 목표는, 혼재되어 있던 LIVE/SIMULATION 모드를 명확히 분리하고, 현재 목업 상태인 분석 엔진들을 실제 운영 로직으로 전환하는 것입니다.*

- **Step 15 (신규): `dag_daily_batch` 실행 모드 파라미터 추가**
  - **작업 내용**: `dag_daily_batch.py`를 수정하여, Airflow UI에서 `execution_mode` ('LIVE' 또는 'SIMULATION')를 선택할 수 있는 파라미터를 추가합니다. 각 Task 함수들이 이 파라미터 값을 읽어 하위 분석 모듈로 전달하도록 데이터 흐름을 변경합니다.
  - **검증**: UI에서 SIMULATION 모드로 DAG 실행 시, API를 호출하는 Task(`sync_stock_master`, `update_low_frequency_ohlcv`)들이 실행을 건너뛰고, 분석 Task들은 시뮬레이션 데이터로 동작하는지 로그를 통해 확인합니다.

- **Step 16 (신규): 분석 모듈, 실행 모드에 따라 분기 처리**
  - **작업 내용**: `rs_calculator.py`, `financial_analyzer.py` 등 분석 모듈들이 `execution_mode` 파라미터를 받도록 수정합니다. 함수 내부에 `if/else` 분기 구조를 추가하여, 'SIMULATION'일 경우 기존처럼 로컬 파일을 읽고, 'LIVE'일 경우 DB를 읽도록 준비합니다. (LIVE 로직은 아직 비워둠)
  - **검증**: 각 분석 모듈을 SIMULATION 모드로 호출했을 때 기존과 동일하게 동작하는지 단위 테스트로 확인합니다.

- **Step 17 (구 15): 재무 분석 엔진 - LIVE 연동**
  - **작업 내용**: `financial_analyzer.py`의 LIVE 모드 분기에, 실제 DART API 또는 사전에 구축된 재무 데이터베이스를 조회하는 로직을 구현합니다. 이를 위해 `fetch_financial_data.py`와 같은 별도의 데이터 수집 스크립트 개발이 필요할 수 있습니다.
  - **검증**: LIVE 모드로 실행 시, 실제 재무 데이터를 기반으로 등급이 부여되는지 확인합니다.

- **Step 18 (구 16): 기술적 분석 엔진 - 실제 로직 구현**
  - **작업 내용**: `technical_analyzer.py`의 목업 함수를, `live.candles` DB의 일봉/주봉 데이터를 사용하여 이동평균선(SMA), RSI 등 핵심 기술적 지표를 계산하는 실제 로직으로 교체합니다.
  - **검증**: `run_technical_analysis` Task 실행 후, XCom 결과에 실제 계산된 지표 값들이 포함되어 있는지 확인합니다.

- **Step 19 (구 17): `dag_daily_batch` - LIVE 모드 최종 검증**
  - **작업 내용**: 모든 분석 엔진이 LIVE 로직으로 전환된 후, `dag_daily_batch`를 'LIVE' 모드로 실행하여 처음부터 끝까지 모든 과정이 실제 API와 DB 데이터로 정상 작동하는지 최종 통합 테스트를 진행합니다.
  - **검증**: `daily_analysis_results` 테이블에 실제 API를 통해 계산된 최종 분석 결과가 모두 저장되었는지 확인합니다.