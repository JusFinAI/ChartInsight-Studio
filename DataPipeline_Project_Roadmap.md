
# DataPipeline 프로젝트 로드맵

**문서 버전: 1.1**

**작성자: Gemini (Project Supervisor)**
**업데이트: cursor.ai inspector**

---

### 1. 프로젝트 목표 (Project Goal)

이 DataPipeline 프로젝트의 최종 목표는 **TRADING LAB 서비스**의 핵심 엔진을 완성하는 것입니다. 매일 시장의 모든 데이터를 수집, 분석, 가공하여 'Stage 1: 퀀트 기반 주도주 스크리닝'에 필요한 모든 데이터를 `daily_analysis_results` 테이블에 안정적으로 준비하는 것을 목표로 합니다.

### 2. 현재까지의 진행 상황 (Current Progress)

우리는 최근의 집중적인 리팩토링을 통해 프로젝트의 가장 중요하고 복잡했던 부분들을 성공적으로 해결했으며, 이제 안정적인 데이터 처리의 기반이 마련되었습니다.

- **데이터 수집 계층 리팩토링 완료**: `chart.py`와 `data_collector.py`의 구조를 개선하여, 업종/지수 데이터 수집이 누락되던 핵심 버그를 해결하고 API 호출 로직을 중앙화했습니다.

- **초기 적재 파이프라인 안정성 확보**: `dag_initial_loader`가 이제 모든 기준 데이터(업종/지수)에 대해 일/주/월봉 데이터를 빠짐없이 초기 적재하도록 개선되었습니다.

- **핵심 아키텍처 정립**: 데이터 수집(collector), API 서비스(services), 분석(analysis), DAG 흐름(dags) 간의 역할과 책임이 명확히 분리된 견고한 아키텍처의 기틀이 완성되었습니다.

### 3. 완료된 과제 (Completed Tasks)

#### **✅ 과제 1: `dag_live_collectors.py` 역할 명확화**

- **목표**: 과거 리팩토링 과정에서 남겨진 기술 부채를 청산하고, DAG의 역할을 코드 수준에서 명확히 합니다.
- **수행 방안**: `dag_live_collectors.py` 파일의 `DAG_CONFIGS` 딕셔너리에서 `'daily'`, `'weekly'` 항목을 제거합니다. 이를 통해 이 DAG가 오직 고빈도 분봉 데이터(`5m`, `30m`, `1h`) 수집에만 집중한다는 것을 코드상으로 명시합니다.
- **완료 상태**: 성공적으로 구현 및 검수 완료

#### **✅ 과제 2: `dag_financials_update` 테스트 기능 강화**

- **목표**: 특정 종목 지정 테스트 기능을 추가하여 통합 테스트 유연성을 크게 향상시킵니다.
- **수행 방안**: `dag_financials_update`에 `stock_codes` 파라미터를 추가하고, 분석 로직에서 해당 파라미터를 최우선으로 처리하도록 수정합니다.
- **완료 상태**: 성공적으로 구현 및 검수 완료


#### **✅ 과제 3: `dag_daily_batch` 게이트키퍼 아키텍처 구현**

- **목표**: 단일 진실 공급원 패턴을 구현하여 테스트 정확성과 운영 효율성을 극대화합니다.
- **수행 방안**: 
  - `update_analysis_target_flags_task`를 게이트키퍼로 지정
  - 모든 분석 Task가 XCom을 통해 일관된 대상 종목 처리
  - **`target_stock_codes` 파라미터 지원으로 빠른 개발-테스트 사이클 구현**
  - UI에서 특정 종목 지정시 전체 DAG에 일관되게 적용
- **완료 상태**: 성공적으로 구현 및 검수 완료


#### **과제 4: `dag_daily_batch` 기술적 분석 Task 구현 및 검증**

- **목표**: `run_technical_analysis_task`의 실제 기술적 분석 로직을 구현하고 통합 테스트를 수행합니다.
- **수행 방안**: 
  - `analyze_technical_for_stocks` 함수에 실제 기술적 지표(SMA, RSI, 패턴 인식) 계산 로직 구현
  - 기술적 분석 결과가 `daily_analysis_results` 테이블에 정확히 저장되는지 검증
  - `target_stock_codes` 파라미터로 특정 종목 기술적 분석 테스트 지원
- **예상 소요**: **중간** (기술적 분석 알고리즘 구현 및 테스트 필요)
- **우선순위**: P2
 **완료 상태**: 성공적으로 구현 및 검수 완료
---

### 4. 남은 과제 로드맵 (Remaining Tasks Roadmap)

프로젝트 완성을 위해 남은 과제들을 **리팩토링 소요가 적은 순서 (간단한 작업부터)** 로 아래와 같이 정렬했습니다. 이 순서대로 과제를 해결해 나가는 것을 권장합니다.

---

#### **과제 5: `dag_financials_update` 통합 테스트**

- **목표**: `dag_daily_batch`의 중요한 데이터 소스인 재무 등급이 정상적으로 생성되는지 확인하고, 최근 리팩토링의 영향을 받지 않았는지 검증합니다.
- **수행 방안**: `dag_financials_update`를 수동으로 실행한 후, `psql`을 통해 `live.financial_analysis_results` 테이블에 최신 날짜의 재무 분석 결과가 잘 저장되었는지 확인합니다.
- **예상 소요**: **매우 낮음** (코드 수정 없음, 실행 및 검증만 필요)


#### **과제 6: Airflow DAG 실행 정책 안정화 (P2 과제)**

- **목표**: DAG 활성화 시 의도치 않은 과거 스케줄이 실행되는 현상을 방지하여, DAG 실행의 예측 가능성을 100% 확보합니다.
- **수행 방안**: `p2_dag_scheduling_stability_report.md` 문서에 기술된 **"실행 시간 검증 가드(Guard)"** 방안을 `dag_daily_batch` 등 주요 DAG에 적용합니다. `BranchPythonOperator`를 사용해 DAG의 첫 단계에서 실행 시간을 검증하고, 너무 과거의 실행일 경우 후속 작업을 건너뛰도록(Skip) 구현합니다.
- **예상 소요**: **중간** (DAG 파일에 신규 Task 및 의존성 추가 필요)

---

####**과제 7: SIMULATION 모드 아키텍처 동기화**

- **목표**: `LIVE` 모드와 `SIMULATION` 모드의 동작을 일치시켜 시뮬레이션의 신뢰도를 확보하고, 과거 데이터 기반의 전략 백테스팅을 가능하게 합니다.
- **수행 방안**: `execution_mode='SIMULATION'` 파라미터가 데이터 소스(API 대신 Parquet 파일 로드)만 교체하도록 `data_collector.py`를 리팩토링합니다. `rs_calculator.py`, `financial_analyzer.py` 등 분석 모듈들이 `LIVE` 모드와 동일한 코드를 공유하도록 구조를 개선합니다.
- **예상 소요**: **높음** (다수 파일에 걸친 구조 변경 및 테스트 필요)


---

#### **과제 8: `dag_daily_batch` End-to-End 통합 테스트**

- **목표**: 데이터 수집 이후의 핵심 분석 Task들(`calculate_rs_score`, `run_technical_analysis`)과 최종 결과를 `daily_analysis_results` 테이블에 저장하는 `load_final_results` Task까지, `dag_daily_batch`의 전 과정이 올바르게 동작하는지 최종 검증합니다.
- **수행 방안**: `dag_daily_batch`를 수동으로 실행한 후, `psql`을 통해 `live.daily_analysis_results` 테이블에 최신 날짜의 데이터가 생성되었는지, 그리고 `market_rs_score`, `financial_grade` 등의 분석 컬럼들이 값으로 잘 채워져 있는지 확인합니다.
- **예상 소요**: **낮음** (코드 수정 없음, 실행 및 검증만 필요)

---


#### **과제 9: 테마 상대강도 분석기 DataPipeline 통합 방안 수립**

- **목표**: `thema_rs_analyzer_v2.py`의 테마 분석 기능을 DataPipeline에 통합할 방안을 수립합니다.
- **수행 방안**:
  - 주간 테마 분석 DAG(`dag_thema_analysis`) 설계 및 구현
  - 키움 API 테마 데이터 수집 → 상대강도 계산 → 결과 저장 파이프라인 구축
  - 기존 `daily_analysis_results`와의 연계 방안 검토
  - 대시보드 시각화 기능 통합 검토
- **예상 소요**: **높음** (신규 DAG 설계 및 API 연동 필요)
- **우선순위**: P3

=> 구현 및 테스트 완료
---

#### **과제 10: Live Scan Page 프론트엔드 구현 방안 수립*

- **목표**: 실시간 스캔 결과를도시 하는는 프론트엔드 페이지 구현 방안을 수립합니다.
  -TradeSmartAI & ChartInsight Studio 통합 개발 계획_수행 보고 (Ver 7.0).md 참조

- **수행 방안**:
  - `daily_analysis_results` 데이터 기반 실시간 스캔 인터페이스 설계
  - 필터링 및 정렬 기능 구현 방안 수립
  - 테마별, 섹터별, 기술적 지표별 뷰 제공 방안 검토
  - 대화형 차트 및 시각화 컴포넌트 설계
- **예상 소요**: **매우 높음** (프론트엔드 아키텍처 설계 및 구현 필요)
- **우선순위**: P4
