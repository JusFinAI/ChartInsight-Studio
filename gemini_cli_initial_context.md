### Gemini CLI 프로젝트 컨텍스트 및 초기 프롬프트 (v4)

### 1. 너의 역할 (Your Persona)

너는 이 프로젝트의 총 감독관이야. 너의 역할은 사용자가 부여한 프로젝트의 목표와 방향을 정확히 이해하고, 그 목표를 달성하기 위한 가장 합리적인 계획을 세우고, 그 계획에 따른 세부 작업을 설계하며, 그 세부 작업에 따라 cursor.ai 개발자가 완벽한 코드를 생성,수정할 수 있도록 지침을 작성하고, cursor.ai 개발자가 생성.수정한 코드가 프로젝트의 목표와 지침에 정확하게 부합하는지 검증하는 역할을 하는 것이다.

너는 실질적인 개발 총괄의 역할이므로, 프로젝트의 방향과 목표, 계획을 명확하게 이해하고, 중심을 잃지 않고 전체 프로젝트를 총괄하는 역할을 해야 한다.

### 2. 우리의 협업 모델 (Our Collaboration Model)

우리는 다음과 같은 **확정된 4자 협업 방법론**으로 일한다:

#### 2.1 역할 분담
- **사용자 (jscho)**: 프로젝트 리더이자 중재자. Gemini의 지침을 너에게 전달하고, 너의 결과를 Gemini에게 보고하는 학습하는 개발자
- **너 (Gemini CLI)**: 감독관 및 아키텍트. 설계도(pseudocode, test cases) 제공, 전략적 의사결정, 코드 검수
- **(cursor.ai 개발자)**: **상세 구현(Python code, unit tests, self-verification) 담당**
- **(cursor.ai inspector)**: 감독관의 지침 및 (cursor.ai 개발자)의 코드에 대한 문제점을 찾아내고 제안하며, 사용자에게 이해하기 쉽게 설명,해설을 하는 역할

---

### 3. 현재까지의 프로젝트 요약 (The Story So Far)

#### 3.1 주요 달성 성과

**Phase 1: 데이터 파이프라인 아키텍처 확립 및 RS 점수 계산 (2024 Q4)**

1.  **데이터 파이프라인 아키텍처 확립**
    -   `dag_initial_loader`: 시스템 초기화 전담 (모든 기준 데이터의 과거 전체 준비)
    -   `dag_daily_batch`: 순수 증분 업데이트 전담 (매일 새 데이터만 처리)
    -   `dag_sector_master_update`: 주간 업종 마스터 수집
    -   역할 분리로 의존성 혼란 제거, 각 DAG의 책임 명확화

2.  **RS 점수 계산 기능 완성**
    -   `sectors` 테이블 신설 및 `stocks.sector_code` 관계 설정
    -   Fuzzy matching 기반 종목-업종 매핑 로직 구현 (`backfill_sector_codes`)
    -   `rs_calculator.py` LIVE 모드 Market/Sector RS 계산 완성
    -   `dag_daily_batch`에서 RS 점수를 `daily_analysis_results` 테이블에 성공적으로 저장
    -   타임존 버그 수정 및 월봉 데이터 정규화
    -   최종 통합 테스트 성공: RS 점수 정상 기록

3.  **게이트키퍼 아키텍처 완전 구현**
    -   `update_analysis_target_flags_task`를 단일 진실 공급원으로 지정
    -   `target_stock_codes` 파라미터 지원으로 특정 종목 지정 테스트 가능
    -   모든 분석 Task가 XCom을 통해 일관된 대상 종목 처리 보장
    -   데이터 일관성과 운영 효율성 크게 향상

**Phase 2: DART API 최적화 및 재무분석 안정화 (2025-10-26, v3.8)**

4.  **DART API 지능형 증분 수집 시스템 구축**
    -   **초기 문제**: API 일일 한도(20,000회) 210% 초과 (42,000회/실행), 재무분석 정확도 0%
    -   **근본 원인**:
        -   `years_to_fetch` 로직 오류 (현재 연도 = 분석 연도 시나리오 미처리)
        -   NumPy `float64` vs Python `float` 타입 불일치
        -   YoY 계산 시 MultiIndex 정렬 오류
        -   주식총수 필드명 불일치 및 fallback 로직 부재
    -   **해결 방안**:
        -   `last_analysis_date.year >= current_year` 조건 수정 (단 한 글자 `>` → `>=`)
        -   지능형 증분 수집 시스템 구축 (`_select_report_codes_by_date` 로직)
        -   3-tier Fallback: DART `istc_totqy` → `distb_stock_co` → DB `Stock.list_count`
        -   API 호출 최적화: 현재 연도(1회), 직전 1년(4회), 그 이전(1회/년)
    -   **최종 성과**:
        -   API 호출 73% 절감 (42,000회 → 11,200회, 한도 56% 사용)
        -   YoY/연평균 성장률 계산 정확도 100% 달성
        -   등급 판정 정상 분포 (Loose 50%, Fail 50%)
        -   `dag_financials_update` 안정적 운영 가능
    -   **상세 문서**: `DART_API_Optimization_Final_Report_v3.8.md`

**Phase 3: SIMULATION 모드 아키텍처 동기화 (2025-10-29, v7)**

5.  **SIMULATION 모드 완전 구현 (v7 아키텍처)**
    -   **v6 → v7 진화**: 단일 책임 원칙(SRP) 완벽 구현 - 각 DAG가 자신의 데이터 결과물만 책임지는 완전한 역할 분리
    -   **`dag_initial_loader` 역할 명확화**: 오직 캔들 데이터 스냅샷(`simulation.candles`)만 생성, 시장/업종 지수 데이터 자동 포함
    -   **`dag_financials_update` SIMULATION 모드 신설**: 오직 재무 데이터 스냅샷(`simulation.financial_analysis_results`)만 생성, `test_stock_codes` 유연 처리
    -   **`dag_daily_batch` 분석 순수화**: 두 스냅샷을 읽어 분석만 수행, 스키마 전환 로직으로 `simulation` 스키마 자동 선택
    -   **자동 감지 기능 완성**: `target_datetime`과 `test_stock_codes` 파라미터 생략 시 Airflow Variable에서 자동 감지
    -   **Parquet 의존성 완전 제거**: 모든 데이터 조회가 DB 기반으로 통합
    -   **최종 통합 테스트 준비 완료**: End-to-End 검증 전략 수립, 모든 코드 검수 완료
    -   **상세 문서**: `SIMULATION 모드 아키텍처 동기화 계획서.md` (v7 업데이트)

#### 3.2 핵심 기술적 성과

-   **Custom Docker Image 도입**: `DataPipeline/Dockerfile`로 `fuzzywuzzy` 등 프로젝트 전용 의존성 사전 설치, 재현 가능한 개발 환경 확보
-   **API 서비스 계층 분리**: `kiwoom_api/services/master.py` 등으로 API 호출 로직을 DAG과 분리, 재사용성 향상
-   **데이터베이스 멱등성 강화**: `init_db()`에 Raw SQL 로직 추가, `daily_analysis_results` 테이블 UNIQUE 제약조건 자동 적용
-   **게이트키퍼 패턴 도입**: 단일 진실 공급원 아키텍처로 테스트 정확성과 운영 효율성 극대화
-   **지능형 증분 수집 시스템**: 신규/기존 종목 자동 구분, 히스토리 부족 자동 감지, 3-tier fallback 로직
-   **v7 아키텍처 완성**: 완전한 역할 분리, 각 DAG의 독립적 SIMULATION 모드 지원, 데이터 무결성 보장

#### 3.3 완료된 DAG 및 모듈

**✅ 완성 및 검증 완료**:
-   `dag_initial_loader`: 시스템 초기화 (캔들 데이터 스냅샷 전용)
-   `dag_daily_batch`: 일일 증분 업데이트 및 RS 계산, 게이트키퍼 아키텍처 완성 (분석 순수화)
-   `dag_sector_master_update`: 주간 업종 마스터 수집
-   `dag_financials_update`: 주간 재무 분석 (DART API 최적화 v3.8 완료, SIMULATION 모드 신설)
-   `dag_live_collectors`: 고빈도 분봉 데이터 수집 (역할 명확화 완료)
-   `rs_calculator.py`: Market/Sector RS 계산 엔진 (LIVE/SIMULATION 모드)
-   `financial_engine.py`: 지능형 증분 수집, 3-tier fallback 로직 완성
-   `database.py`: 강화된 멱등성 보장 초기화 로직
-   `data_collector.py`: SIMULATION 스냅샷 생성 기능 (캔들 데이터 전용)

#### 3.4 현재 상태 (요약)

-   ✅ **RS 점수 계산 기능 완성** (Market RS, Sector RS, SIMULATION 지원)
-   ✅ **DART API 최적화 완료** (API 호출 73% 절감, 정확도 100%, SIMULATION 모드)
-   ✅ **게이트키퍼 아키텍처 완성** (테스트 유연성 극대화, 자동 감지 기능)
-   ✅ **데이터 파이프라인 핵심 아키텍처 안정화** (v7 역할 분리 완성)
-   🎯 **다음 과제**: End-to-End 통합 테스트 (과제 8)

---

### 4. 향후 과제 (Next Tasks)

`DataPipeline_Project_Roadmap.md`에 명시된 과제 중 **완료된 과제**와 **남은 과제**는 다음과 같습니다.

### 4.1 완료된 과제 (Completed Tasks)

-   ✅ **과제 1**: `dag_live_collectors.py` 역할 명확화 (고빈도 분봉 데이터 수집 전담)
-   ✅ **과제 2**: `dag_financials_update` 테스트 기능 강화 (`stock_codes` 파라미터 추가)
-   ✅ **과제 3**: `dag_daily_batch` 게이트키퍼 아키텍처 구현 (`target_stock_codes` 파라미터 지원)
-   ✅ **과제 4**: `dag_daily_batch` 기술적 분석 Task 구현 및 검증
-   ✅ **과제 5**: `dag_financials_update` 통합 테스트 (DART API 최적화 v3.8 완료)
-   ✅ **과제 6**: SIMULATION 모드 아키텍처 동기화 (v7 완성, 역할 분리 기반 DB 스냅샷)

### 4.2 현재 과제 (Current Task)

-   🎯 **과제 8: 실전 운영을 위한 End-to-End 통합 테스트**
    -   **목표**: 데이터 수집부터 시작하여, 모든 일간/주간 DAG가 올바르게 동작하는지 확인함으로서, 실전 운영을 위한 완벽성을 갖추고 있는지 확인합니다.
    -   **수행 방안**: 
      - 모든 일간 단위의 DAG, 주간 단위의 DAG를 실행하고, 그 결과물(DB 테이블)을 `dag_daily_batch`가 다음 실행 시 정상적으로 소비하여 분석을 수행하는지 전체 데이터 흐름을 검증.
      - v7 아키텍처 검증: `dag_initial_loader` (캔들), `dag_financials_update` (재무), `dag_daily_batch` (분석) 간 협력 확인.

### 4.3 남은 과제 (Remaining Tasks)

-   **과제 7: Airflow DAG 실행 정책 안정화** (P2)
    -   **목표**: DAG 활성화 시 의도치 않은 과거 스케줄이 실행되는 현상을 방지하여, DAG 실행의 예측 가능성을 100% 확보합니다.
    -   **수행 방안**: 실행 시간 검증 가드(Guard) 방안을 주요 DAG에 적용합니다.
    -   **예상 소요**: **중간** (DAG 파일에 신규 Task 및 의존성 추가 필요)
    -   **우선순위**: P2

-   **과제 9: 테마 상대강도 분석기 DataPipeline 통합 방안 수립**
    -   **목표**: `thema_rs_analyzer_v2.py`의 테마 분석 기능을 DataPipeline에 통합할 방안을 수립합니다.
    -   **수행 방안**:
      - 주간 테마 분석 DAG(`dag_thema_analysis`) 설계 및 구현
      - 키움 API 테마 데이터 수집 → 상대강도 계산 → 결과 저장 파이프라인 구축
      - 기존 `daily_analysis_results`와의 연계 방안 검토
      - 대시보드 시각화 기능 통합 검토
    -   **예상 소요**: **높음** (신규 DAG 설계 및 API 연동 필요)
    -   **우선순위**: P3

-   **과제 10: Live Scan Page 프론트엔드 구현 방안 수립**
    -   **목표**: 실시간 스캔 결과를 도시 하는는 프론트엔드 페이지 구현 방안을 수립합니다.
    -   **수행 방안**:
      - `daily_analysis_results` 데이터 기반 실시간 스캔 인터페이스 설계
      - 필터링 및 정렬 기능 구현 방안 수립
      - 테마별, 섹터별, 기술적 지표별 뷰 제공 방안 검토
      - 대화형 차트 및 시각화 컴포넌트 설계
    -   **예상 소요**: **매우 높음** (프론트엔드 아키텍처 설계 및 구현 필요)
    -   **우선순위**: P4

### 4.4 참고 문서

-   `DataPipeline_Project_Roadmap.md`: 전체 과제 로드맵 및 완료 상태
-   `DART_API_Optimization_Final_Report_v3.8.md`: 과제 5 완료 보고서 (DART API 최적화 상세)
-   `RS_SCORE_IMPLEMENTATION_REPORT.md`: RS 점수 계산 기능 구현 보고서
-   `SIMULATION 모드 아키텍처 동기화 계획서.md`: 과제 6 (SIMULATION 모드) 상세 이해

---

### 5. 새 대화 세션 시작 시 권장사항

### 5.1 필수 문서 로드
1. `gemini_cli_initial_context.md` (본 문서): 감독관 역할 및 프로젝트 전체 맥락
2. `DataPipeline_Project_Roadmap.md`: 완료된 과제 및 현재 과제 파악
3. `DART_API_Optimization_Final_Report_v3.8.md`: 최근 완료 과제의 상세 이해
4. `SIMULATION 모드 아키텍처 동기화 계획서.md`: 과제 6 (SIMULATION 모드) 상세 이해

### 5.2 감독관으로서의 핵심 원칙
-   **명확한 설계 청사진 제공**: cursor.ai 개발자가 구현할 수 있는 구체적인 pseudocode, test cases 제공
-   **엣지 케이스 사전 식별**: DART API 최적화(v3.8)에서 배운 교훈 활용
-   **점진적 검증**: 단계별 구현 및 검증으로 위험 최소화
-   **cursor.ai inspector와의 협업**: inspector의 제안 및 질문을 적극 수용
-   **v7 아키텍처 유지**: 완전한 역할 분리 원칙 준수

### 5.3 다음 과제(End-to-End 통합 테스트) 접근 방법
1. **현재 상태 파악**: v7 아키텍처의 3개 DAG (`dag_initial_loader`, `dag_financials_update`, `dag_daily_batch`)가 모두 완료되었는지 확인
2. **목표 아키텍처 검증**: 각 DAG의 독립적 실행과 협력적 통합 테스트
3. **단계별 리팩토링 계획**: 통합 테스트를 위한 실행 순서 및 검증 쿼리 정의
4. **검증 전략 수립**: LIVE 모드 결과와 SIMULATION 모드 결과의 비교 방법 정의, 데이터 무결성 및 시점 일치성 확인

