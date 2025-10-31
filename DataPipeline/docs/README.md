# ChartInsight Studio - DataPipeline 문서 센터

**최종 업데이트**: 2025-10-31  
**프로젝트 버전**: DataPipeline v7.1  
**문서 버전**: 2.0

---

## 📋 Quick Navigation

- [프로젝트 개요](#프로젝트-개요)
- [문서 구조](#문서-구조)
- [시작하기](#시작하기)
- [아키텍처](#아키텍처)
- [주요 성과](#주요-성과)
- [보관 문서](#보관-문서)

---

## 🎯 프로젝트 개요

**ChartInsight Studio DataPipeline**은 **TRADING LAB 서비스**를 위한 완전 자동화된 주식 데이터 수집 및 분석 파이프라인입니다.

### 핵심 기능

매일 자동으로:
- 📊 **데이터 수집**: 1,400개 종목의 OHLCV 데이터 (일/주/월봉, 분봉)
- 📈 **상대강도 계산**: Market RS, Sector RS 점수
- 💼 **재무 분석**: DART API 기반 기업 재무 등급
- 🔍 **기술적 분석**: 이동평균선, RSI 등 기술 지표
- 💾 **결과 저장**: `daily_analysis_results` 테이블에 통합 저장

### 프로젝트 비전

**"오늘 주목해야 할 종목을 자동으로 찾아주는 데이터 파이프라인"**

---

## 📚 문서 구조

### 🔴 핵심 프로젝트 문서 (이 폴더)

| 문서 | 목적 | 대상 |
|------|------|------|
| **`DataPipeline_Project_Roadmap.md`** | 프로젝트 전체 로드맵 및 현황 | 모든 사용자 ⭐ |

### 🟠 최종 보고서 (`Reports/`)

| 문서 | 목적 | 대상 |
|------|------|------|
| **`Reports/DART_API_Optimization_Final_Report_v3.8.md`** | DART API 최적화 상세 보고 | 개발자, 아키텍트 |
| **`Reports/RS_SCORE_IMPLEMENTATION_REPORT.md`** | RS 점수 계산 기능 구현 | 개발자 |
| **`Reports/report_test_simulation_architechture.md`** | SIMULATION v7 검증 결과 | 개발자, QA |
| **`Reports/report_과거실행자동트리거.md`** | P2 스케줄링 해결 보고 | 개발자, DevOps |

### 🔵 초기 컨텍스트 문서 (루트)

| 문서 | 목적 | 대상 |
|------|------|------|
| **`initial_context_for_gemini_cli.md`** | Gemini AI 감독관용 컨텍스트 | AI 협업 |
| **`initial_context_for_inspector.md`** | Inspector AI용 컨텍스트 | AI 협업 |

### 🟢 DataPipeline 기술 문서 (이 폴더)

| 문서 | 목적 |
|------|------|
| **`README.md`** (이 문서) | 문서 센터 및 가이드 |
| **`Reference/`** | 개발 참조 문서 (디버깅, API 명세) |
| **`Reports/`** | Phase 5-7 최종 보고서 모음 |
| **`Archive/Phase1-4/`** | Phase 1-4 보관 문서 |
| **`Archive/Plans/`** | Phase 5-7 계획서 및 중간 문서 |

---

## 🚀 시작하기

### 1. 프로젝트 이해하기

**첫 방문자라면:**
```
1. DataPipeline_Project_Roadmap.md 읽기
   → 프로젝트 전체 흐름 파악
   
2. "현재 상태" 섹션 확인
   → 최신 완료 마일스톤 확인
   
3. "Phase 1-7" 섹션 읽기
   → 개발 과정 이해
```

**개발자라면:**
```
1. Reference/ 폴더 먼저 확인 ⭐
   → Reference/debugging_commands.md (필수)
   → Reference/kiwoom_restapi_specs.md (API 개발 시)
   
2. Roadmap "아키텍처" 섹션
   → 시스템 구조 파악
   
3. Reports/ 폴더의 최종 보고서 읽기
   → Reports/RS_SCORE_IMPLEMENTATION_REPORT.md
   → Reports/DART_API_Optimization_Final_Report_v3.8.md
```

### 2. 로컬 환경 설정

```bash
# 1. 저장소 클론
cd /home/jscho/ChartInsight-Studio/DataPipeline

# 2. 가상환경 생성 및 활성화
python3 -m venv venv
source venv/bin/activate

# 3. 의존성 설치
pip install -r requirements.txt

# 4. 환경 변수 설정
cp .env.example .env.local
# .env.local 파일 편집 (API 키, DB 정보)

# 5. Docker 컨테이너 실행
docker compose --env-file .env.docker --profile pipeline up -d

# 6. DB 초기화
python src/database.py

# 7. Airflow 웹 UI 접속
# http://localhost:8080 (admin/admin)
```

---

## 🏗️ 아키텍처

### 시스템 구조

```
┌─────────────────────────────────────────────┐
│           Apache Airflow                     │
│  ┌─────────────────────────────────────┐    │
│  │     DAG Orchestration               │    │
│  │                                     │    │
│  │  dag_initial_loader                 │    │
│  │  dag_daily_batch                    │    │
│  │  dag_sector_master_update           │    │
│  │  dag_financials_update              │    │
│  │  dag_live_collectors                │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
         ↓                    ↓
┌─────────────────┐   ┌──────────────────┐
│  Kiwoom API     │   │   DART API       │
│  (시세 데이터)    │   │   (재무 데이터)   │
└─────────────────┘   └──────────────────┘
         ↓                    ↓
┌─────────────────────────────────────────────┐
│         PostgreSQL Database                  │
│  ┌─────────────────────────────────────┐    │
│  │  live schema (운영 데이터)           │    │
│  │  simulation schema (백테스팅 데이터) │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

### 주요 컴포넌트

#### 1. DAG (Directed Acyclic Graph)

| DAG | 역할 | 스케줄 |
|-----|------|--------|
| **dag_initial_loader** | 시스템 초기화, 과거 데이터 적재 | 수동 |
| **dag_daily_batch** | 매일 증분 업데이트 및 분석 | 매일 오전 |
| **dag_sector_master_update** | 업종 마스터 수집 | 주간 |
| **dag_financials_update** | 재무 분석 (DART API) | 주간 |
| **dag_live_collectors** | 고빈도 분봉 데이터 수집 | 5분/30분/1시간 |

#### 2. 분석 모듈

```
src/analysis/
├── rs_calculator.py        # 상대강도 계산
├── financial_analyzer.py   # 재무 분석
└── technical_analyzer.py   # 기술적 지표 계산
```

#### 3. 데이터베이스 스키마

```sql
-- LIVE 스키마 (운영)
live.stocks                     -- 종목 마스터
live.sectors                    -- 업종 마스터
live.candles                    -- OHLCV 데이터
live.financial_analysis_results -- 재무 분석 결과
live.daily_analysis_results     -- 통합 분석 결과

-- SIMULATION 스키마 (백테스팅)
simulation.candles              -- 과거 시점 캔들 스냅샷
simulation.financial_analysis_results -- 과거 시점 재무 스냅샷
simulation.daily_analysis_results     -- 시뮬레이션 분석 결과
```

---

## 🏆 주요 성과

### Phase 1-4: 기반 구축 (2025-10-13 ~ 10-26)
- ✅ 데이터 모델 및 DAG 아키텍처 완성
- ✅ 전체 배치 파이프라인 구축
- ✅ 데이터 무결성 이슈 해결 (중복 적재, Race Condition 등)

### Phase 5: RS 점수 계산 (2025-10-22)
- ✅ Market RS / Sector RS 계산 엔진 완성
- ✅ 업종 마스터 수집 및 Fuzzy Matching 매핑
- ✅ 월봉 기반 상대강도 알고리즘 구현

### Phase 6: DART API 최적화 (2025-10-26)
- ✅ API 호출 **73% 절감** (42,000회 → 11,200회)
- ✅ 재무 분석 정확도 **100% 달성**
- ✅ 지능형 증분 수집 시스템 구축

### Phase 7: SIMULATION v7 (2025-10-30)
- ✅ 완전한 역할 분리 아키텍처 (SRP 완벽 구현)
- ✅ Look-Ahead Bias 완전 제거
- ✅ P2 스케줄링 안정화 (과거 실행 99.7% 절감)
- ✅ End-to-End 검증 완료

---

## 📖 개발 참조 문서

### Reference 폴더

**위치**: `DataPipeline/docs/Reference/`

**목적**: 현재 개발 중 **지속적으로 참조**해야 하는 기술 문서

```
Reference/
├── README.md                    # Reference 가이드
├── debugging_commands.md        # Docker/PostgreSQL/Airflow 명령어
└── kiwoom_restapi_specs.md      # Kiwoom API 명세서
```

### debugging_commands.md ⭐
**사용 빈도**: 매일  
**내용**: Docker, PostgreSQL, Airflow 디버깅 명령어 레퍼런스

**핵심 명령어**:
- DAG 수동 트리거 (SIMULATION 모드)
- PostgreSQL DB 조회 (분석 결과 검증)
- Airflow 로그 확인
- 컨테이너 관리

**언제 사용하나요?**
- ✅ DAG 테스트 후 결과 확인
- ✅ 버그 디버깅
- ✅ DB 데이터 검증
- ✅ 로그 분석

### kiwoom_restapi_specs.md
**사용 빈도**: API 개발 시  
**내용**: Kiwoom REST API 6개 명세 및 예제 코드

**포함 API**:
- `ka10099`: 종목정보 리스트 (현재 사용 중)
- `ka10101`: 업종코드 리스트 (현재 사용 중 - `dag_sector_master_update`)
- `ka10083`: 주식 월봉 (현재 사용 중 - RS 계산)
- `ka20008`: 업종 월봉 (현재 사용 중 - Sector RS)
- `ka20007`: 업종 주봉 (향후 사용 예정)
- `ka20006`: 업종 일봉 (향후 사용 예정)

**언제 사용하나요?**
- ✅ 신규 API 추가 시
- ✅ API 응답 형식 확인 시
- ✅ RS 계산 로직 개선 시
- ✅ 테마 분석 기능 개발 시 (과제 10)

**빠른 참조**:
- 디버깅 중? → `debugging_commands.md`
- API 개발 중? → `kiwoom_restapi_specs.md`

자세한 내용은 `Reference/README.md`를 참조하세요.

---

## 📦 보관 문서

### Archive 폴더 구조

**위치**: `DataPipeline/docs/Archive/`

```
Archive/
├── Phase0-Genesis/     # 🌱 프로젝트 탄생기 (2025-07)
│   ├── README.md       # 30개 종목 프로토타입 스토리
│   ├── TradeSmartAI 초기 적재 보고서.md
│   └── TradeSmartAI 개발 계획 Ver 4.0.md
│
├── Phase1-4/           # Phase 1-4 기반 구축 기간 문서
│   ├── README.md       # 상세 가이드
│   ├── DataPipeline_Upgrade_Plan.md
│   ├── DataPipeline_Upgrade_Report.md
│   ├── DataPipeline_Improvement_Plan.md
│   └── DataPipeline_Improvement_Points.md
│
└── Plans/              # Phase 5-7 계획서 및 중간 문서
    ├── README.md       # 상세 가이드
    ├── RS_SCORE_IMPLEMENTATION_PLAN.md
    ├── SIMULATION 모드 아키텍처 동기화 계획서.md
    ├── SIMULATION_아키텍처_근본적_재검토_보고서.md
    └── p2_dag_scheduling_stability_report.md
```

### Archive/Phase0-Genesis/ 🌱
**기간**: 2025-07  
**내용**: 프로젝트 탄생기 - 30개 종목 프로토타입

**핵심 문서**:
- `TradeSmartAI 초기 적재 보고서.md` - 첫 번째 성공
- `TradeSmartAI 개발 계획 Ver 4.0.md` - 초기 설계

**학습 가치**:
- 프로젝트 시작 스토리 (30개 → 1,400개 성장)
- 타임존 처리 문제의 근본 해결 과정
- 작은 것에서 큰 것으로 성장하는 과정

**⚠️ 주의**: 현재 시스템과 완전히 다름!

### Archive/Phase1-4/
**기간**: 2025-10-13 ~ 10-26  
**내용**: Phase 1-4 기반 구축 과정의 완전한 기록

**핵심 문서**:
- `DataPipeline_Upgrade_Plan.md` - 초기 구축 계획
- `DataPipeline_Upgrade_Report.md` - 구현 검증 결과
- `DataPipeline_Improvement_Plan.md` - 개선 계획
- `DataPipeline_Improvement_Points.md` - 문제점 상세 분석 ⭐

**학습 가치**:
- 실제 버그 해결 과정 (데이터 중복, Race Condition 등)
- 아키텍처 설계 원칙 (단일 책임, 관심사 분리)
- 협업 방법론 (Plan → Report 매핑)

### Archive/Plans/
**기간**: 2025-10-21 ~ 10-31  
**내용**: Phase 5-7 계획서 및 중간 검토 문서

**핵심 문서**:
- `SIMULATION 모드 아키텍처 동기화 계획서.md` - v7 설계 ⭐
- `p2_dag_scheduling_stability_report.md` - 스케줄링 문제 해결
- `SIMULATION_아키텍처_근본적_재검토_보고서.md` - v6→v7 전환 배경

**학습 가치**:
- 계획 → 실행 → 변경 과정
- 아키텍처 의사결정 과정
- 문제 접근 방법론

**⚠️ 주의**: 보관 문서는 과거/중간 시점의 기록입니다.
- **최신 정보** → `DataPipeline_Project_Roadmap.md`
- **최종 결과** → `Reports/` 폴더

자세한 내용은 각 폴더의 `README.md`를 참조하세요.

---

## 🛠️ 기술 스택

### 핵심 기술
- **Python 3.8+**: 주 개발 언어
- **Apache Airflow**: 워크플로우 오케스트레이션
- **PostgreSQL**: 데이터베이스
- **Docker**: 컨테이너화

### 주요 라이브러리
```python
# 데이터 처리
pandas
numpy
pyarrow

# API 연동
requests
dart-fss

# 데이터베이스
SQLAlchemy
psycopg2-binary

# Airflow
apache-airflow[postgres]

# 유틸리티
python-dotenv
pendulum
fuzzywuzzy
```

### 외부 API
- **키움증권 REST API**: 시세 데이터 (일/주/월봉, 분봉)
- **DART API**: 금융감독원 전자공시 (재무제표)

---

## 📖 개발 가이드

### 코드 구조

```
DataPipeline/
├── dags/                    # Airflow DAG 정의
│   ├── dag_initial_loader.py
│   ├── dag_daily_batch.py
│   ├── dag_sector_master_update.py
│   ├── dag_financials_update.py
│   └── dag_live_collectors.py
│
├── src/                     # 핵심 소스 코드
│   ├── analysis/            # 분석 모듈
│   │   ├── rs_calculator.py
│   │   ├── financial_engine.py
│   │   ├── financial_analyzer.py
│   │   └── technical_analyzer.py
│   │
│   ├── kiwoom_api/          # 키움 API 클라이언트
│   │   ├── core/
│   │   ├── services/
│   │   └── models/
│   │
│   ├── dart_api/            # DART API 클라이언트
│   │   └── dart_corp_map.py
│   │
│   ├── utils/               # 유틸리티
│   │   ├── filters.py       # Filter Zero
│   │   ├── sector_mapper.py # Fuzzy Matching
│   │   └── logging_kst.py   # KST 로깅
│   │
│   ├── database.py          # DB 모델 및 세션
│   ├── data_collector.py    # 데이터 수집
│   └── master_data_manager.py # 마스터 관리
│
├── tests/                   # 테스트 코드
├── scripts/                 # 유틸리티 스크립트
├── docs/                    # 문서 (이 폴더)
└── requirements.txt         # Python 의존성
```

### 주요 설계 원칙

#### 1. 단일 책임 원칙 (SRP)
각 모듈, 함수, DAG는 하나의 명확한 책임만 가집니다.

#### 2. 멱등성 (Idempotency)
같은 작업을 여러 번 실행해도 결과가 동일합니다.

#### 3. 관심사 분리
- 데이터 수집 ≠ 데이터 분석
- 동기화 ≠ 필터링
- LIVE ≠ SIMULATION

---

## 🐛 문제 해결

### 자주 발생하는 이슈

#### 1. DAG 실행 실패
```bash
# 로그 확인
docker logs airflow-scheduler

# DB 연결 확인
docker exec -it postgres-tradesmart psql -U postgres -d tradesmart_db
```

#### 2. API 호출 한도 초과
- DART API: 20,000회/일
- 키움 API: 초당 20회 제한
- 해결: 지능형 증분 수집 시스템 활용

#### 3. 타임존 이슈
- 모든 날짜/시간은 `Asia/Seoul` 타임존 사용
- `pendulum` 라이브러리로 일관성 보장

### 디버깅 팁

```python
# 1. 소수 종목으로 테스트
target_stock_codes = "005930,000660"  # 삼성전자, SK하이닉스만

# 2. SIMULATION 모드로 안전 테스트
execution_mode = "SIMULATION"

# 3. 로그 레벨 조정
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 📊 데이터베이스 확인

### 유용한 쿼리

```sql
-- 1. 분석 결과 최신 데이터 확인
SELECT 
    stock_code,
    market_rs_score,
    sector_rs_score,
    financial_grade,
    analysis_date
FROM live.daily_analysis_results
WHERE analysis_date = (SELECT MAX(analysis_date) FROM live.daily_analysis_results)
ORDER BY market_rs_score DESC
LIMIT 10;

-- 2. 재무 분석 상태 확인
SELECT 
    COUNT(*) as total_analyzed,
    COUNT(DISTINCT stock_code) as unique_stocks,
    MAX(analysis_date) as latest_date
FROM live.financial_analysis_results;

-- 3. 캔들 데이터 적재 현황
SELECT 
    timeframe,
    COUNT(*) as candle_count,
    COUNT(DISTINCT stock_code) as stock_count
FROM live.candles
GROUP BY timeframe;

-- 4. SIMULATION 스냅샷 확인
SELECT 
    'candles' as table_name,
    COUNT(*) as record_count
FROM simulation.candles
UNION ALL
SELECT 
    'financial_analysis_results',
    COUNT(*)
FROM simulation.financial_analysis_results
UNION ALL
SELECT 
    'daily_analysis_results',
    COUNT(*)
FROM simulation.daily_analysis_results;
```

---

## 🎓 학습 리소스

### 초보자를 위한 학습 순서

#### 1주차: 프로젝트 이해
- `DataPipeline_Project_Roadmap.md` 전체 읽기
- "프로젝트 개요", "현재 상태" 섹션 집중

#### 2주차: 기반 지식
- `Archive/Phase1-4/DataPipeline_Upgrade_Plan.md` - Phase 1-4 계획
- Airflow 기본 개념 학습 (DAG, Task, XCom)

#### 3주차: 핵심 기능
- `Reports/RS_SCORE_IMPLEMENTATION_REPORT.md` - RS 계산 로직
- `Reports/DART_API_Optimization_Final_Report_v3.8.md` - API 최적화

#### 4주차: 고급 주제
- `Reports/report_test_simulation_architechture.md` - SIMULATION 모드
- `Archive/Phase1-4/DataPipeline_Improvement_Points.md` - 문제 해결 사례

### 개발자를 위한 참고 자료

- **아키텍처 패턴**: Roadmap v2.0 "주요 기술적 성과"
- **버그 해결 사례**: Archive/Phase1-4/DataPipeline_Improvement_Points.md
- **API 최적화**: Reports/DART_API_Optimization_Final_Report_v3.8.md
- **테스트 전략**: Reports/report_test_simulation_architechture.md

---

## 🤝 기여 가이드

### 3-AI 협업 모델

이 프로젝트는 독특한 협업 방식을 사용합니다:

1. **Gemini CLI (감독관)**: 고수준 설계, 전략적 의사결정
2. **Cursor.ai Developer (개발자)**: 상세 구현, 코드 작성
3. **Cursor.ai Inspector (검수자)**: 코드 리뷰, 문제점 발견

### 문서 작성 원칙

1. **개발 초보자도 이해 가능하게**
2. **자상하고 설명적인 방식**
3. **학습 목적에 부합**
4. **Why → What → How 순서**

---

## 📞 연락처 및 지원

### 프로젝트 정보
- **프로젝트명**: ChartInsight Studio DataPipeline
- **버전**: v7.1
- **마지막 업데이트**: 2025-10-31

### 문서 관리
- **문서 관리자**: cursor.ai Documentation Manager
- **최종 검수**: cursor.ai Inspector

---

**이 문서는 DataPipeline 프로젝트의 중앙 문서 허브입니다.  
궁금한 내용이 있다면 위 Navigation을 활용하여 관련 문서를 찾아보세요!** 🚀
