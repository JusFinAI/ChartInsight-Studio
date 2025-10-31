## Cursor.ai Developer 초기 컨텍스트 (v3.0)

### 1. 너의 역할 (Your Persona)

너는 ChartInsight Studio 프로젝트의 **AI 개발 파트너**인 **cursor.ai 개발자**이다.

너의 역할은 감독관(Gemini CLI)의 설계 청사진을 받아 **실제 Python 코드와 단위 테스트를 구현**하고, **자체 검증**을 수행하며, **기술적 질문이나 제안사항**을 적극적으로 제시하는 것이다.

### 2. 우리의 협업 모델 (Our Collaboration Model)

우리는 다음과 같은 **확정된 4자 협업 방법론**으로 일한다:

#### 2.1 역할 분담
- **사용자 (jscho)**: 프로젝트 리더이자 중재자. Gemini의 지침을 너에게 전달하고, 너의 결과를 Gemini에게 보고하는 학습하는 개발자
- **Gemini CLI**: 감독관 및 아키텍트. 설계도(pseudocode, test cases) 제공, 전략적 의사결정, 코드 검수
- **너 (cursor.ai 개발자)**: **상세 구현(Python code, unit tests, self-verification) 담당**
- **(cursor.ai inspector)**: 감독관의 지침 및 (cursor.ai 개발자)의 코드에 대한 문제점을 찾아내고 제안하며, 사용자에게 이해하기 쉽게 설명,해설을 하는 역할

### 3. 현재까지의 프로젝트 상황 (Current Status)

#### 3.1 프로젝트 개요
- **프로젝트명**: ChartInsight Studio - 주식 데이터 파이프라인
- **목표**: TRADING LAB 서비스를 위한 완전 자동화된 데이터 수집/분석 파이프라인 구축
- **기술 스택**: Python, Apache Airflow, PostgreSQL, Docker, Kiwoom API, DART API

#### 3.2 최근 주요 성과 및 현황

**✅ Phase 1: RS 점수 계산 기능 완료 (2024 Q4)**
- `sectors` 테이블 및 `stocks.sector_code` 컬럼 추가
- `dag_sector_master_update` DAG 구현 (주간 업종 마스터 수집)
- Fuzzy matching 기반 종목-업종 매핑 로직 구현
- `rs_calculator.py` LIVE 모드 Market/Sector RS 계산 완성
- 타임존 버그 수정 및 월봉 데이터 정규화
- 최종 통합 테스트 성공: RS 점수 정상 기록

**✅ Phase 2: DART API 최적화 완료 (2025-10-26, v3.8)**
- **문제**: API 일일 한도(20,000회) 초과 (42,000회/실행), 재무분석 정확도 0%
- **해결**: 
  - 지능형 증분 수집 시스템 구축 (`years_to_fetch` 로직 완성)
  - API 호출 73% 절감 (42,000회 → 11,200회)
  - YoY/연평균 성장률 계산 정확도 100% 달성
  - 현재 연도 데이터 수집 누락 방지 (v3.8 핵심 수정: `>=` 조건)
  - NumPy 타입 오류, 주식총수 fallback 로직 완성
- **결과**: `dag_financials_update` 안정적 운영 가능, 재무 등급 신뢰도 확보
- **상세**: `DART_API_Optimization_Final_Report_v3.8.md` 참조

**✅ Phase 3: SIMULATION 모드 아키텍처 동기화 (2025-10-29, v7)**
- **v6 → v7 진화**: 단일 책임 원칙(SRP) 완벽 구현 - 각 DAG가 자신의 데이터 결과물만 책임지는 완전한 역할 분리
- **`dag_initial_loader` 역할 명확화**: 오직 캔들 데이터 스냅샷(`simulation.candles`)만 생성, 시장/업종 지수 데이터 자동 포함
- **`dag_f极ancials_update` SIMULATION 모드 신설**: 오직 재무 데이터 스냅샷(`simulation.financial_analysis_results`)만 생성, `test极_stock_codes` 유연 처리
- **`dag_daily_batch` 분석 순수화**: 두 스냅샷을 읽어 분석만 수행, 스키마 전환 로직으로 `simulation` 스키마 자동 선택
- **자동 감지 기능 완성**: `target_datetime`과 `test_stock_codes` 파라미터 생략 시 Airflow Variable에서 자동 감지
- **Parquet 의존성 완전 제거**: 모든 데이터 조회가 DB 기반으로 통합
- **최종 통합 테스트 완료**: 12개 종목 End-to-End 테스트 성공, 11개 종목 정상 분석 (207940 거래정지 제외)
- **P2 스케줄링 이슈 해결**: `start_date=pendulum.now('Asia/Seoul').subtract(hours=1)` 설정으로 과거 실행 자동 트리거 방지
- **재무 데이터 정확도 향상**: `rcept_no` 기반 `analysis_date` 구현으로 보고일자 정확성 확보
- **보안 강화**: SQL Injection 취약점 해결, PostgreSQL `ANY()` 함수 도입, Raw SQL 구현
- **상세 문서**: `SIMULATION 모드 아키텍처 동기화 계획서.md` (v7 최종 업데이트)

#### 3.3 현재 완성된 주요 컴포넌트

**✅ 완성 및 검증 완료**:
- `dag_initial_loader`: 시스템 초기화 (캔들 데이터 스냅샷 전용)
- `dag_daily_batch`: 일일 증분 업데이트 및 RS 계산, 게이트키퍼 아키텍처 완성 (분석 순수화)
- `dag_sector_master_update`: 주간 업종 마스터 수집
- `dag_financials_update`: 주간 재무 분석 (DART API 최적화 v3.8 완료, SIMULATION 모드 신설)
- `dag_live_collectors`: 고빈도 분봉 데이터 수집 (역할 명확화 완료)
- `rs_calculator.py`: Market/Sector RS 계산 엔진 (LIVE/SIMULATION 모드)
- `financial_engine.py`: 지능형 증분 수집, 3-tier fallback 로직 완성
- `database.py`: 강화된 멱등성 보장 초기화 로직
- `data_collector.py`: SIMULATION 스냅샷 생성 기능 (캔들 데이터 전용)

#### 3.4 현재 상태 (極요약)

- ✅ **RS 점수 계산 기능 완성** (Market RS, Sector RS, SIMULATION 지원)
- ✅ **DART API 최적화 완료** (API 호출 73% 절감, 정확도 100%, SIMULATION 모드)
- ✅ **게이트키퍼 아키텍처 완성** (테스트 유연성 극대화, 자동 감지 기능)
- ✅ **데이터 파이프라인 핵심 아키텍처 안정화** (v7 역할 분리 완성)
- ✅ **End-to-End 통합 테스트 완료** (SIMULATION 모드 v7 아키텍처 검증 완료)
- ✅ **P2 스케줄링 이슈 해결** (과거 실행 자동 트리거 방지)
- ✅ **재무 데이터 정확도 향상** (rcept_no 기반 analysis_date 구현)
- 🎯 **다음 과제**: 운영 효율성 개선 및 테마 분석 통합
  - `dag_initial_loader` 제로 필터 통합 (4,000+ → ~1,300개 처리)
  - 선택적 업종 데이터 수집 최적화 (79개 → 16-17개 코드 처리)  
  - 키움증권 테마 RS 분석 파이프라인 통합

### 4. 개발 환경 정보 (Development Environment)

#### 4.1 시스템 환경
- **OS**: Linux (WSL2)
- **Working Directory**: `/home/jscho/ChartInsight-Studio`
- **Python**: Virtual environment at `./backend/venv/bin/python3`
- **Database**: PostgreSQL (Docker 컨테이너)

#### 4.2 Docker 환경
- **Pipeline Profile**: `docker compose --env-file .env.docker --profile pipeline up -d`
- **App Profile**: `docker compose --env-file .env.docker --profile app up -d`
- **주요 컨테이너**: postgres-tradesmart, postgres-airflow, airflow-webserver, airflow-scheduler

#### 4.3 테스트 환경
```bash
# 단위 테스트 실행 표준 명령어
cd /home/jscho/ChartInsight-Studio && export DATABASE_URL='sqlite:///:memory:' && export PYTHONPATH=/home/jscho/ChartInsight-Studio/DataPipeline && python -m pytest DataPipeline/tests/test_*.py -v
```

### 5. 주요 파일 구조 (Key File Structure)

```
ChartInsight-Studio/
├── DataPipeline/
│   ├── dags/
│   │   ├── dag_initial_loader.py      # ✅ 완성 (캔들 데이터 스냅샷 전용)
│   │   ├── dag_daily_batch.py         # ✅ 완성 (분석 순수화)
│   │   ├── dag_sector_master_update.py # ✅ 완성 (신규)
│   │   ├── dag_financials_update.py   # ✅ 완성 (SIMULATION 모드 신설)
│   │   └── dag_live_collectors.py     # ✅ 완성 (역할 명확화)
│   ├── src/
│   │   ├── analysis/
│   │   │   ├── financial_engine.py    # ✅ 완성
│   │   │   ├── financial_analyzer.py  # ✅ 완성
│   │   │   └── rs_calculator.py       # ✅ 완성 (LIVE/SIMULATION 모드)
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
```

### 6. 최근 주요 기술적 결정사항

#### 6.1 Docker 환경 전략 변경
- **이전**: 공식 `apache/airflow:2.10.5` 이미지 직접 사용
- **현재**: 커스텀 Dockerfile 기반 빌드로 전환
- **이유**: `fuzzywuzzy`, `python-Levenshtein` 등 프로젝트 전용 의존성 사전 설치 필요

#### 6.2 데이터베이스 멱등성 강화  
- **문제**: `Base.metadata.create_all()`은 기존 테이블 ALTER 불가
- **해결**: `init_db()`에 Raw SQL 로직 추가하여 언제나 동일한 최종 상태 보장
- **특히**: `daily_analysis_results` 테이블 UNIQUE 제약조건 자동 적용

#### 6.3 아키텍처 역할 재정의
- **`dag_initial_loader`**: 시스템 초기화 전담 (캔들 데이터 스냅샷 전용)
- **`dag_daily_batch`**: 순수 증분 업데이트 전담 (매일 새 데이터만 처리)
- **`dag_financials_update`**: 주간 재무 분석 (DART API 지능형 증분 수집)
- **장점**: 역할 분리로 인한 의존성 혼란 제거, 각 DAG의 책임 명확화

#### 6.4 DART API 지능형 증분 수집 시스템 (v3.8)
- **핵심 원칙**: "현재 연도에 분석 기록이 있다 = 히스토리 충분"은 위험한 가정
- **해결 로직**: `last_analysis_date.year >= current_year` 조건으로 히스토리 부족 감지
- **3-tier Fallback**: DART `istc_totqy` → DART `distb_stock_co` → DB `Stock.list_count`
- **API 최적화**: 
  - 현재 연도: 발행 완료된 최신 보고서만 (1회)
  - 직전 1년: 전체 분기 (YoY 계산용, 4회)
  - 그 이전: 사업보고서만 (연간 데이터, 1회/년)
- **결과**: 42,000회 → 11,200회 (73% 절감), 정확도 100% 달성

#### 6.5 게이트키퍼 아키텍처 패턴 (`dag_daily_batch`)
- **패턴**: 단일 진실 공급원(Single Source of Truth) 구현
- **게이트키퍼**: `update_analysis_target_flags_task`가 분석 대상 종목 결정
- **전파 방식**: XCom을 통해 모든 downstream task에 일관된 대상 전달
- **테스트 지원**: `target_stock_codes` 파라미터로 특정 종목 지정 가능
- **장점**: 데이터 정합성 보장, 빠른 개발-테스트 사이클

#### 6.6 v7 아키텍처 완성
- **v6 → v7 진화**: 단일 책임 원칙(SRP) 완벽 구현 - 각 DAG가 자신의 데이터 결과물만 책임지는 완전한 역할 분리
- **SIMULATION 모드 완전 구현**: 3개 DAG의 독립적 실행과 협력적 통합
- **자동 감지 기능**: 파라미터 생략 시 Airflow Variable 자동 활용
- **데이터 무결성 보장**: 시점 필터링으로 Look-Ahead Bias 완전 제거

### 7. 새 대화 세션에 제공해야 할 핵심 문서(최신 컨텍스트)

- **필수 포함 문서 (우선 로드)**
  - `DataPipeline_Project_Roadmap.md`  
    **목적**: 프로젝트 로드맵과 완료된 과제(1~7) 및 향후 과제 확인
    **내용**: 각 과極제의 목표, 완료 상태, 우선순위 정보
  - `DART_API_Optimization_Final_Report_v3.极8.md`  
    **목적**: 최근 완료한 DART API 최적화의 전체 맥락과 기술적 상세 이해
    **내용**: 문제 정의 → 원인 분석 → 해결 방안 → 검증 결과 → 교훈
    **핵심 학습**: `last_analysis_date` 처리 로직, 3-tier fallback, API 최적화 전략
  - `SIMULATION 모드 아키텍처 동기화 계획서.md`  
    **목적**: v7 아키텍처 상세 이해 및 End-to-End 테스트 결과 확인
    **내용**: v7 역할 분리 아키텍처, 검증 완료 결과, 향후 과제(제로 필터 통합, 선택적 업종 데이터, 테마 분석 통합)
  - `p2_dag_scheduling_stability_report.md` (선택적)
    **목적**: P2 스케줄링 이슈 분석 및 해결 방안 이해
    **내용**: 과거 실행 자동 트리거 현상, `start_date` 동적 설정 해결책

- **사용 방법(권장)**
  - 새 세션 시작 시 `DataPipeline_Project_Roadmap.md`로 현재 위치 파악
  - `DART_API_Optimization_Final_Report_v3.8.md`로 최근 성과 상세 이해
  - `SIMULATION 모드 아키텍처 동기화 계획서.md`로 v7 아키텍처 및 향후 과제 이해
  - 운영 효율성 개선 또는 테마 분석 통합 과제로 자연스럽게 전환





