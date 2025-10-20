# DataPipeline Upgrade Report (Plan → Report 매핑)

작성일: 2025-10-13
작성자: 자동화 검사(assistant) 및 담당자

## 개요
본 문서는 `DataPipeline_Upgrade_Plan.md`의 Phase/Step 항목에 따라 이번 작업에서 실제로 수행된 변경사항(Report)을 단계별로 매핑하고, 누락된 항목 및 추가적으로 생성된 파일의 목적을 명확히 정리한 문서입니다. 감독자 리뷰 및 코드 승인 요청용입니다.

---

## Phase 1: 기반 공사 (Foundations)

Step 1: `daily_analysis_results` 테이블 모델 정의
- Plan: `src/database.py`에 `daily_analysis_results` 모델 정의 및 `init_db()` 반영
- 수행 결과: 완료
  - `DataPipeline/src/database.py`에 `DailyAnalysisResult` 모델이 추가되어 있으며, `init_db()`로 스키마/테이블 생성 로직을 수행할 수 있음을 확인했습니다.
  - 검증: `load_final_results` 실행 후 `live.daily_analysis_results`에 4건의 레코드가 UPSERT 되었음을 직접 쿼리로 확인함.
- 증거: DB 쿼리 결과 (4 rows) — 리포트 본문 참조

Step 2: 핵심 분석 로직 모듈화
- Plan: `src/analysis/`에 `rs_calculator.py`, `financial_analyzer.py`, `technical_analyzer.py` 생성 및 단위 테스트
- 수행 결과: 대부분 완료(모듈화 및 DAG 연동 완료)
  - `rs_calculator.py` / `financial_analyzer.py` / `technical_analyzer.py`가 `src/analysis/`에 존재하며 DAG에서 호출되도록 통합되었습니다.
  - 분석 로직은 현재 목업/초기 구현(특히 `technical_analyzer`는 스텁) 상태입니다. RS 및 재무 계산 로직은 실제 연산을 수행하여 XCom에 정상값을 반환함을 확인했습니다.
- 미완료 항목: 정교한 단위 테스트(주어진 시뮬레이션 데이터에 대한 검증 케이스) 일부 미구현 — 권장 작업으로 테스트 추가 필요.

---

## Phase 2: 유틸리티 DAG 업그레이드 (`dag_initial_loader`) — (Plan 항목 중 일부는 차후)

Step 3 ~ 4: `dag_initial_loader` 파라미터 및 분기 로직 확장
- Plan: UI 파라미터 확장 및 분기 처리
- 수행 결과: 이 리포트 작업 범위에서 해당 DAG에 대한 변경은 수행되지 않았음(해당 단계는 미완료).
- 권장: `dag_initial_loader` 관련 변경이 필요하면 별도 PR/검증 필요.

---

## Phase 3: 신규 배치 DAG 개발 (`Daily Batch DAG`)

Step 5: 신규 DAG 파일 및 기본 구조 생성
- Plan: `dags/dag_daily_batch.py` 작성
- 수행 결과: 완료 — 파일이 존재하며 Task 정의(동기화, 저빈도 업데이트, 필터, 병렬 분석, 최종 적재)를 포함합니다.

Step 6: Task 1 - `sync_stock_master` 구현
- 수행 결과: 구현 및 정상 실행 확인. `sync_stock_master_data()` 호출로 종목 리스트를 XCom으로 반환함.
- 증거: Task 로그 및 XCom 덤프에서 종목 리스트 확인.

Step 7: Task 2 - `update_low_frequency_ohlcv` 구현
- 수행 결과: 구현 및 정상 실행 확인. `collect_and_store_candles`를 사용해 시뮬레이션/라이브 흐름을 처리.
- 증거: Task 로그에서 각 종목(d/w/mon) 업데이트 로그 및 성공 메시지 확인.

Step 8: Task 3 - `filter_analysis_targets` 구현
- 수행 결과: 구현 및 정상 실행 확인. 목업 데이터 기반 필터링으로 4종목 선정.

Step 9: Task 4 - `calculate_core_metrics` 병렬 구현
- 수행 결과: TaskGroup으로 RS 점수 및 재무 등급 계산이 병렬로 실행되며 결과를 XCom으로 전달함. RS/Financial XCom 값 확인됨.

Step 10: Task 5 - `run_technical_analysis` 구현
- 수행 결과: 초기 스텁 형태로 구현되어 성공적으로 실행되었고 XCom으로 기본 구조 결과를 반환함.

Step 11: Task 6 - `load_final_results` 구현
- 수행 결과: 구현 및 정상 동작 확인. XCom으로 받은 결과들을 `live.daily_analysis_results` 테이블에 UPSERT함.
- 증거: DB 직접 쿼리로 4건 저장 확인.

Step 12: DAG 의존성 설정
- 수행 결과: DAG 내 Task 의존성이 `sync_stock_master >> update_low_frequency_ohlcv >> filter_analysis_targets >> [calculate_core_metrics_group, run_technical_analysis] >> load_final_results`로 올바르게 설정되어 있음.

---

## Phase 4: 통합 및 검증

Step 13: `dag_initial_loader` 기능 검증
- 수행 결과: 이 단계는 본 검증 범위에서 수행되지 않았음(미완료)

Step 14: `Daily Batch DAG` 통합 검증
- 수행 결과: 수행 및 완료
  - 수동 트리거(Run ID: manual__2025-10-13T02:40:57+00:00)로 DAG 전체 실행 확인
  - 모든 핵심 Task success, XCom 반환, DB 저장까지 검증됨
- 증거: Task 상태 출력, 로그 스니펫, XCom 덤프, DB 쿼리 결과 첨부(리포트 본문)

---

## 환경 변경 및 운영 스크립트 (추가된 변경사항)

1) `.env` 분리
- 변경 내용: 개발 환경에서 기존 단일 `.env` 파일을 제거하고, 환경을 분리하여 사용하도록 변경함.
  - `.env.local` (개발자 로컬용)
  - `.env.docker` (도커/컨테이너용)
- 목적: 개발 환경과 컨테이너 실행 환경의 환경변수(예: DB URL, SIMULATION_DATA_PATH 등)를 명확히 분리하여 혼선 방지 및 보안 개선.
- 검증: 컨테이너 실행 시 `--env-file .env.docker`를 통해 환경변수 로딩이 정상 작동함을 확인.

2) 개발 실행 스크립트 이동/추가
- 변경 내용: 루트 `scripts/dev` 디렉토리에 `dev_run_datapipelin.sh` 스크립트를 생성하여 개발자가 로컬에서 파이프라인을 실행/테스트하는 절차를 단순화함.
- 목적: 개발자가 로컬에서 필요한 환경(.env.local) 로드, 가상환경 활성화, 간단한 pre-steps(예: DB init, mock data 생성)을 자동화하여 재현성을 확보.
- 검증: 스크립트의 존재 및 실행 가능 여부(실제 실행은 환경에 따라 다름).

3) 기타 환경 수정
- `DataPipeline/src/database.py`에서 `DATABASE_URL`을 주요 연결 소스로 사용하도록 리팩토링하여 컨테이너/로컬 환경에서 동일한 `DATABASE_URL`로 동작할 수 있게 조정함.
- `prepare_simulation_dataset.py` 및 관련 스크립트의 기본 경로를 `SIMULATION_DATA_PATH` 환경변수 기준으로 사용하도록 변경함.

(참고: 위 환경 파일들과 스크립트는 보안상 비밀번호/민감정보를 직접 커밋하지 않도록 `.gitignore`에 반영할 것을 권장합니다.)

---

## 새로 생성된 파일들과 생성 이유(보완 설명)

1) `DataPipeline/src/utils/logging_kst.py` (새 파일)
- 이유: 여러 핵심 모듈에서 동일한 방식으로 KST(Asia/Seoul) 타임스탬프를 출력하기 위한 공통 헬퍼가 필요했습니다. 모듈별로 직접 포맷을 반복 작성하면 유지보수 부담과 중복이 커지므로 헬퍼로 통합했습니다.
- 역할: 로거 생성시 KST 컨버터를 설정하고, 핸들러 중복(중복출력) 방지를 위해 `propagate=False`를 설정. 모듈 단위로 `configure_kst_logger(__name__)`를 호출하면 KST 포맷 로그를 사용하게 됩니다.

2) `DataPipeline/scripts/prepare_simulation_dataset.py` (추가/개편된 스크립트)
- 이유: 시뮬레이션 모드에서 사용할 Parquet 파일을 일관된 규격으로 생성하기 위한 스크립트가 필요했습니다. 원래의 `prepare_test_data.py`를 복원/개편하여 로컬 및 컨테이너 환경에서 재사용 가능하도록 만들었습니다.
- 역할: 키움 API(또는 목업 데이터)를 사용해 타임프레임별 Parquet 파일을 생성하고, 타임존/컬럼 정규화, 파일명 규칙, 저장 경로(`SIMULATION_DATA_PATH`)를 관리합니다.

3) `DataPipeline/scripts/fetch_sector_master.py` (새 파일)
- 이유: 업종/섹터 마스터 데이터(업종코드↔종목 매핑)를 Kiwoom API에서 수집해 로컬 JSON으로 저장하기 위한 스크립트가 필요했습니다. 필터링(필터 제로 정책) 및 매핑 로직을 분리하여 재사용성을 높였습니다.
- 역할: API 호출 → 필터링/보정 → `sector_master.json` 및 mismatch 샘플 저장.

4) 기타 스크립트(예: `scripts/dev/dev_run_datapipelin.sh`)
- 이유: 개발자 로컬 재현성 및 컨테이너 기반 실행을 간소화하기 위해 추가.

---

## 최종 권고(요약)
1. Plan 문서는 유지하되, 각 Step 하단에 이번 수행결과(Completed / In progress / Not started) 및 증거 링크(로그/XCom/DB 쿼리)를 표기하여 "Plan + Report" 형태로 관리하세요.
2. Parquet 생성·검증 작업과 pyarrow 버전 통일을 우선순위로 수행하십시오.
3. 자동화 스크립트에서 Run ID 추적은 `--run-id` 지정 또는 REST API(JSON)를 사용하도록 개선해 주세요.
4. 감독자 리뷰: `DataPipeline/src/utils/logging_kst.py`와 DB UPSERT 로직에 대한 코드 리뷰 및 배포 전 보안·운영 영향 검토 바랍니다.

---

원하시면 위 내용을 `DataPipeline_Upgrade_Report.md`에 반영해 두었으니, 추가 수정(문구/증거 첨부/스크린샷 포함)을 진행해 드리겠습니다.
