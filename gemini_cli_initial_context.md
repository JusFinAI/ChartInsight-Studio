## Gemini CLI 프로젝트 컨텍스트 및 초기 프롬프트 (v2)

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

1.  **최종 데이터 파이프라인 아키텍처 확립**
    -   `dag_initial_loader`: 시스템 초기화 시, 모든 기준 데이터(업종 마스터, 지수/업종 캔들)의 **과거 전체**를 준비하는 역할로 책임 명확화.
    -   `dag_daily_batch`: `dag_initial_loader`가 준비한 데이터를 기반으로, 모든 대상(종목, 지수, 업종)의 **매일의 증분**만 업데이트하는 역할로 책임 명확화.

2.  **RS 점수 계산 기능 구현 완료**
    -   `dag_daily_batch` 내에서 Market RS와 Sector RS 점수를 모두 계산하고, `daily_analysis_results` 테이블에 성공적으로 저장함을 최종 통합 테스트를 통해 검증 완료.

3.  **견고한 데이터 기반 구축**
    -   `sectors` 테이블 신설 및 `stocks` 테이블과의 관계 설정을 통해 업종 데이터 관리 체계 마련.
    -   `fuzzywuzzy` 및 수동 매핑을 포함한 다단계 업종 코드 매핑 로직(`backfill_sector_codes`) 구현으로, 분석 대상 종목의 매핑되지 않은 `sector_code`를 0으로 만듦.
    -   `init_db()` 함수에 멱등성 있는 `UNIQUE` 제약조건 추가 로직을 구현하여, `daily_analysis_results` 테이블의 데이터 무결성 보장.

#### 3.2 기술적 성과
-   **Custom Docker Image 도입**: `DataPipeline/Dockerfile`을 통해 `fuzzywuzzy` 등 외부 라이브러리를 포함한 자체 Airflow 이미지를 구축하여, 재현 가능하고 일관된 개발 환경 확보.
-   **API 서비스 계층 분리**: `kiwoom_api/services/master.py`와 같이, API 호출 로직을 DAG과 분리하여 코드의 재사용성과 유지보수성 향상.
-   **Timezone 처리 안정화**: `data_collector.py`에서 발생했던 Timezone 비교 버그를 수정하여 증분 수집 로직의 안정성 확보.

#### 3.3 현재 상태 (요약)
-   **RS 점수 계산 기능 구현 및 통합 테스트가 성공적으로 완료되었습니다.**
-   데이터 파이프라인의 핵심 아키텍처가 안정화되었으며, 데이터의 흐름과 역할 분담이 명확해졌습니다.
-   이제 RS 점수 외의 다른 분석 기능을 추가하거나, 시스템의 안정성을 검증하는 다음 단계로 나아갈 준비가 되었습니다.

---

## 4. 향후 과제 (Next Tasks)

RS 점수 기능 구현 과정에서 식별된 추가 과제들이며, 아래 우선순위에 따라 진행할 예정입니다.

-   **P1 (Critical): `dag_daily_batch` 증분 업데이트 로직 통합 테스트**
    -   **목표**: `dag_daily_batch`를 여러 날짜에 걸쳐 연속으로 실행하는 상황을 시뮬레이션하여, `collect_and_store_candles` 함수가 마지막 데이터 이후의 '증분'만 올바르게 가져오는지 검증.

-   **P2 (High): Airflow DAG 실행 정책 안정화**
    -   **목표**: DAG 활성화(unpause) 시 의도치 않은 과거 DAG가 실행되는 문제를 해결하고, `catchup` 파라미터 등을 최적화하여 DAG가 예측 가능하게 동작하도록 안정화.

-   **P3 (Medium): 주간 배치 DAG 통합 테스트**
    -   **목표**: `dag_financials_update`와 `dag_sector_master_update`를 실행하고, 그 결과물을 `dag_daily_batch`가 정상적으로 소비하는지 전체 데이터 흐름을 검증.

-   **P4 (Low): `SIMULATION` 모드 아키텍처 동기화**
    -   **목표**: `LIVE` 모드에 적용된 모든 아키텍처 개선사항(`rs_calculator` 로직, 데이터 흐름 등)을 `SIMULATION` 모드에도 동일하게 반영하여, 두 모드 간의 동작 일관성을 확보.

---

### 5. 주요 파일 구조 (Key File Structure)

```
ChartInsight-Studio/
├── DataPipeline/
│   ├── dags/
│   │   ├── dag_initial_loader.py      # ✅ 완성 (강화됨)
│   │   ├── dag_daily_batch.py         # ✅ 완성 (RS 계산 통합)
│   │   ├── dag_sector_master_update.py # ✅ 완성 (신규)
│   │   ├── dag_financials_update.py   # ⏳ 통합 테스트 대기
│   │   └── dag_live_collectors.py     # ⏳ 통합 테스트 대기
│   ├── src/
│   │   ├── analysis/
│   │   │   ├── financial_engine.py    # ✅ 완성
│   │   │   ├── financial_analyzer.py  # ✅ 완성
│   │   │   └── rs_calculator.py       # ✅ 완성 (LIVE 모드)
│   │   ├── kiwoom_api/
│   │   │   ├── stock_info.py          # ✅ 완성
│   │   │   └── services/master.py     # ✅ 완성 (신규)
│   │   ├── utils/
│   │   │   ├── filters.py             # ✅ 완성
│   │   │   └── sector_mapper.py       # ✅ 완성 (신규)
│   │   ├── data_collector.py          # ✅ 완성 (타임존 버그 수정)
│   │   ├── master_data_manager.py     # ✅ 완성 (백필 로직 통합)
│   │   └── database.py                # ✅ 완성 (멱등성 강화)
│   └── Dockerfile
└── .env.docker
└── .env.docker.local
└── docker-compose.yaml


### 6. 새로운 대화 세션을 위한 재개 템플릿

```
[세션 헤더]
- 세션 시작일: 2025-10-22
- 요약: RS 점수 계산 기능의 아키텍처 수립, 구현, 통합 테스트를 성공적으로 완료함. 이제 다음 우선순위 과제를 진행할 준비가 되었음.

[핵심 컨텍스트 요약(한 문단)]
- 우리는 `dag_initial_loader`(과거 전체)와 `dag_daily_batch`(매일 증분)의 역할을 명확히 분리하는 최종 아키텍처를 확립했으며, 이를 바탕으로 Market/Sector RS 점수 계산 기능의 구현 및 검증을 모두 마쳤습니다. 이 과정에서 DB 스키마 확장, 업종 코드 자동 매핑, Timezone 버그 수정, Custom Docker 이미지 도입 등 수많은 기술적 문제를 해결했습니다. 이제 다음으로, 정의된 '향후 과제' 목록에서 가장 우선순위가 높은 P1 과제를 수행하여 파이프라인의 증분 업데이트 기능의 안정성을 검증해야 합니다.

[현재 액션 아이템]
1. (P1) `dag_daily_batch` 증분 업데이트 로직 통합 테스트
2. (P2) Airflow DAG 실행 정책 안정화
3. (P3) 주간 배치 DAG 통합 테스트
4. (P4) `SIMULATION` 모드 아키텍처 동기화

[참고문서]
- `RS_SCORE_IMPLEMENTATION_REPORT.md` (이번 세션의 전체 작업 보고서)
- `DataPipeline/dags/dag_daily_batch.py` (최종 수정된 일일 배치 DAG)
- `DataPipeline/dags/dag_initial_loader.py` (최종 수정된 초기 적재 DAG)

[요청사항]
- '향후 과제' 목록에서 가장 우선순위가 높은 **P1: `dag_daily_batch` 증분 업데이트 로직 통합 테스트**를 수행하기 위한 상세 계획 및 지침을 제공해 주십시오.
```

