# ChartInsight Studio Monorepo

마지막 업데이트: 2025-09-11
기준 문서: TradeSmartAI & ChartInsight Studio 통합 개발 계획_수행 보고 (Ver 6.0).md

이 저장소는 다음 컴포넌트를 단일 모노레포로 통합합니다.
- DataPipeline: 한국 주식 데이터 수집/적재(Airflow, PostgreSQL)
- Backend: FastAPI 기반 API 서버, DB 조회/가공
- Frontend: Next.js(Typescript) 기반 UI, Plotly 시각화

참고 보고서:
- `document/TradeSmartAI & ChartInsight Studio 통합 개발 계획_수행 보고 (Ver 7.0).md` 
- `document/수동 디버깅 방법.md` 

---

## 아키텍처 개요

```mermaid
graph TD
  subgraph "Frontend (Next.js)"
    F1[trading-radar/page.tsx]
    F2[services/api.ts]
    F3[components/ui/Chart.tsx]
  end

  subgraph "Backend (FastAPI)"
    B1[routers/pattern_analysis.py]
    B2[crud.py]
    B3[models.py]
    B4[database.py]
  end

  subgraph "DataPipeline (Airflow)"
    P1[dags/*]
    P2[src/database.py]
    P3[src/utils/common_helpers.py]
  end

  subgraph "PostgreSQL"
    DB[(tradesmart_db: live.stocks, live.candles)]
  end

  F1 --> F2 -->|HTTP| B1
  B1 --> B2 --> B3 --> B4 --> DB
  P1 --> P2 --> DB
  P1 --> P3

```

- 데이터 흐름 요약
  - DataPipeline이 Kiwoom API 등에서 수집한 OHLCV 데이터를 PostgreSQL(live.*)에 저장
  - Backend는 DB를 조회하여 API 응답으로 가공(UTC→KST, epoch seconds)
  - Frontend는 Plotly 차트로 시각화(초 단위를 밀리초로 변환)
  - 한국 주식은 6자리 코드 사용(예: 005930), .KS 미사용

---

## 실행 개요 (Docker Compose Profiles)

- 웹 앱(App): Backend + Frontend + Tradesmart DB
  - `docker compose --profile app up -d`
- 데이터 파이프라인(Pipeline): Airflow + DB들
  - `docker compose --profile pipeline up -d`

접속 URL
- Next.js: `http://localhost:3000`
- FastAPI Docs: `http://localhost:8000/docs`
- Airflow: `http://localhost:8080`

---

## 환경 변수

- Backend
  - `DATABASE_URL` (예: `postgresql://tradesmart_db:1234@postgres-tradesmart:5432/tradesmart_db`)
- Frontend
  - `.env.local` 권장: `NEXT_PUBLIC_API_URL=http://localhost:8000`
  - 주의: `NEXT_PUBLIC_` 접두사가 있는 변수만 브라우저에 노출됨
- DataPipeline
  - `DataPipeline/.env` (엔트리포인트에서 `load_dotenv()` 처리)

---

## 데이터 표준/정책

- 한국 주식 심볼: 6자리 코드만 사용(예: `005930`), `.KS` 미사용
- 타임존: DB=UTC 저장 → 사용자 표시 단계에서 KST(Asia/Seoul) 변환
- 시간 단위: Backend 응답은 epoch seconds, Frontend(Plotly)는 milliseconds (프론트에서 `* 1000` 적용)
- 타임프레임 매핑: `5m→M5`, `30m→M30`, `1h→H1`, `1d→D`, `1wk→W`
- 데이터 소스: 한국 주식 경로는 DB 일원화, 응답 헤더 `X-Data-Source: db`

---

## 폴더 구조(요약)

```
ChartInsight-Studio/
├─ docker-compose.yaml
├─ README.md
├─ document/
│  ├─ TradeSmartAI & ChartInsight Studio 통합 개발 계획_수행 보고 (Ver 7.0).md
│  └─ 수동 디버깅 방법.md
├─ DataPipeline/
│  ├─ dags/                            # Airflow DAGs (초기 적재 및 증분 업데이트)
│  │  ├─ dag_initial_loader.py         # 초기(legacy) 적재 DAG
│  │  ├─ dag_live_collectors.py        # 실시간/지속 수집 관련 DAG
│  │  ├─ dag_simulation_tester.py      # 시뮬레이션/테스트 DAG
│  │  └─ data_collector_test_dag.py    # 수집기 테스트용 DAG
│  │  # (추가 수집 주기별 DAG들이 존재할 수 있음: dag_5min_collector 등)
│  ├─ src/
│  │  ├─ database.py                   # 파이프라인 DB 접속/ORM 및 모델 정의 (Candle/Stock)
│  │  └─ utils/
│  │     └─ common_helpers.py          # 파이프라인 유틸(타겟 종목 조회 등)
│  └─ docs/                            # 운영자/운영 문서
├─ backend/
│  ├─ app/
│  │  ├─ main.py                       # FastAPI 앱 엔트리 (앱 생성, 라우터 등록)
│  │  ├─ routers/
│  │  │  └─ pattern_analysis.py        # Trading Radar 관련 엔드포인트
│  │  ├─ crud.py                       # DB 조회/비즈니스 로직 래퍼 (get_candles 등)
│  │  ├─ models.py                     # ORM 모델 정의 (live.candles, live.stocks)
│  │  └─ database.py                   # SQLAlchemy 엔진/세션 + DI 헬퍼
│  ├─ _temp_integration/
│  │  └─ chart_pattern_analyzer_kiwoom_db/
│  │     ├─ run_full_analysis_impl.py  # 분석 엔진: DataFrame -> patterns, js_points, trend_periods
│  │     ├─ data_loader.py              # DB -> pandas.DataFrame (UTC → Asia/Seoul 변환 포함)
│  │     └─ logger_config.py
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ app/
│  │  │  ├─ page.tsx                    # 앱 루트 페이지
│  │  │  ├─ layout.tsx                  # 전역 레이아웃
│  │  │  ├─ globals.css                 # 전역 스타일
│  │  │  ├─ favicon.ico
│  │  │  ├─ trading-lab/
│  │  │  │  ├─ page.tsx                 # Trading Lab 메인
│  │  │  │  ├─ trading-radar/page.tsx   # Trading Radar UI (토글/필터/데이터 로드)
│  │  │  │  ├─ trading-journal/page.tsx # Trading Journal
│  │  │  │  ├─ live-scanner/page.tsx    # 실시간 스캐너 UI
│  │  │  │  ├─ backtest-lab/page.tsx    # 백테스트 랩
│  │  │  │  └─ pattern-strategy-analyzer/page.tsx
│  │  │  ├─ pattern-studio/
│  │  │  │  ├─ page.tsx                 # 패턴 스튜디오 메인
│  │  │  │  └─ pattern-library/page.tsx  # 패턴 라이브러리
│  │  │  ├─ knowledge-hub/
│  │  │  │  ├─ page.tsx                 # 지식 허브 메인
│  │  │  │  └─ price-action/page.tsx    # 가격 행동 아티클
│  │  │  └─ community/
│  │  │     ├─ page.tsx                 # 커뮤니티 메인
│  │  │     └─ trading-ideas/page.tsx   # 아이디어 공유
│  │  ├─ services/
│  │  │  └─ api.ts                      # API 클라이언트 래퍼 (fetchTradingRadarData 등)
│  │  └─ components/
│  │     └─ ui/
│  │        └─ Chart.tsx                # Plotly 기반 차트 컴포넌트 (epoch→ms 변환, 오버레이)
│  ├─ next.config.ts
│  └─ Dockerfile
```

---

## 주요 파일/모듈

- **Backend** (`backend/app`)
  - `main.py` — FastAPI 앱 엔트리. CORS, 요청 로깅 미들웨어, 라우터/호환 엔드포인트(`/chart-data`, `/trading-radar-data` 등) 등록.
  - `routers/pattern_analysis.py` — Trading Radar 관련 라우터. 주요 엔드포인트:
    - `/pattern-analysis/symbols/kr-targets` (한국 주식 대상 목록)
    - `/pattern-analysis/chart-data`, `/pattern-analysis/js-points`, `/pattern-analysis/patterns`, `/pattern-analysis/price-levels`
    - `/trading-radar-data` (프론트 통합 응답): DB 조회(KR 코드), 엔진 호출, KST 변환 및 통합 포맷 반환
  - `crud.py` — DB 조회 유틸(예: `get_candles`, `get_latest_candles`, `normalize_timeframe`)로 라우터와 분석 엔진 사이의 추상 계층 제공
  - `models.py` — SQLAlchemy ORM 모델(`live.candles`, `live.stocks` 등)
  - `database.py` — SQLAlchemy 엔진 및 `SessionLocal`/`get_db()` DI 헬퍼
  - `services/`
    - `data_loader.py` — `load_candles_from_db(...)` 같은 DB→pandas 래퍼(UTC→Asia/Seoul 변환 포함)
    - `peak_valley_detector.py` — JS 포인트(피크/밸리) 검출 유틸
  - `utils/`
    - `logger_config.py` — 중앙 로거 설정(파일 핸들러, 포맷, 로테이션)
    - `data_loader.py` — 외부 데이터 다운로드·보정 헬퍼 (엔진/샘플 데이터용)
    - `cache.py` — 간단 캐시 유틸
  - `analysis/engine_impl.py` — 핵심 분석 엔진(`run_full_analysis`): DataFrame→patterns, peaks/valleys, trend_periods, price_levels 반환
  - `kiwoom/` — 키움 통합 유틸 (예: `minute_chart.py`, `daily_chart.py`, `weekly_chart.py`, `auth.py`, `config.py`) — DataPipeline/백엔드에서의 외부 데이터 적재/테스트용 모듈
  - `_temp_integration/chart_pattern_analyzer_kiwoom_db/` — 실험·이식용 스크립트(이전 버전 코드)

- **Frontend** (`frontend/src`)
  - `app/` — Next.js 앱 라우트
    - `page.tsx` (앱 루트), `layout.tsx` (전역 레이아웃), `globals.css`, `favicon.ico`
    - `trading-lab/` — Trading 관련 서브앱
      - `page.tsx` (Trading Lab 메인)
      - `trading-radar/page.tsx` (Trading Radar UI: 토글/필터/데이터 로드)
      - `trading-journal/page.tsx`, `live-scanner/page.tsx`, `backtest-lab/page.tsx`, `pattern-strategy-analyzer/page.tsx`
    - `pattern-studio/`, `knowledge-hub/`, `community/` 등 페이지 폴더
  - `services/api.ts` — API 클라이언트 래퍼 (`fetchTradingRadarData`, `fetchKrTargetSymbols`, 공통 응답 파싱 및 에러 처리)
  - `components/ui/Chart.tsx` — Plotly 차트 컴포넌트(epoch→ms 변환, JS 포인트/패턴/추세 오버레이, volume 표시)

- **DataPipeline** (`DataPipeline`)
  - `dags/` — Airflow DAGs (초기 적재, 증분 수집, 테스트용 DAG)
    - `dag_initial_loader.py`, `dag_live_collectors.py`, `dag_simulation_tester.py`, `data_collector_test_dag.py`, 등(주기별 collector DAG 포함)
      - 참고: `dag_live_collectors.py`는 **하나의 파일에서 여러 DAG id를 동적으로 생성**합니다. 예: `dag_daily_collector`, `dag_weekly_collector`, `dag_5m_collector` 등 — UI에 표시되는 여러 DAG은 이 파일이 생성한 것입니다.
  - `src/database.py` — 파이프라인용 DB 접속/모델 정의 (Candle/Stock)
  - `src/utils/common_helpers.py` — 운영 유틸(타겟 종목 조회 등)

(필요하면 각 파일별 더 자세한 책임/함수 목록을 추가해 드립니다.)

---

## 구동/검증 예시

아래는 로컬 개발 환경에서 서비스(백엔드/프론트엔드) 실행 및 간단한 디버깅/확인용 명령 모음입니다.

```bash
# 1) 도커 기반 전체 스택(권장)
docker compose --profile app up -d

# 2) 백엔드(컨테이너 내부가 아닌 로컬에서 직접 실행/디버그할 때)
# 포트 사용 확인 및 기존 프로세스 종료
ss -ltn | grep 8000       # 8000 포트 사용 프로세스 확인
pkill -f uvicorn          # uvicorn 프로세스 종료
pkill -f debugpy          # debugpy 프로세스 종료

# 백엔드 디렉토리로 이동
cd backend

# 환경변수 설정
export DATABASE_URL="postgresql+psycopg2://tradesmart_db:1234@localhost:5433/tradesmart_db"

# 빠른 실행(개발 모드)
uvicorn app.main:app --reload --port 8000

# 디버그모드(디버거 연결 대기)
./venv/bin/python -Xfrozen_modules=off -m debugpy --listen 5680 --wait-for-client -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# 디버거 포트 확인 (다른 터미널)
ss -ltn | grep 5680

# 3) Frontend 실행 (새 터미널에서)
cd ~/ChartInsight-Studio/frontend
npm run dev

# 4) 헬스체크 및 간단한 API 호출
curl -s http://localhost:8000/health
curl -s "http://localhost:8000/api/v1/pattern-analysis/symbols/kr-targets?limit=30"
curl -s "http://localhost:8000/trading-radar-data?symbol=005930&timeframe=5m&chart_type=candlestick&period=auto" | grep -o '"source":"[^\"]*"'

# (타임존 확인 예시)
TZ=Asia/Seoul date -d @1753929300
```

---

## 트러블슈팅 메모

- `psql: FATAL: role "root" does not exist` → 정확한 사용자 지정(`-U tradesmart_db`)
- `jq` 미설치 → `sudo apt install jq` 또는 `curl` 단독 사용
- Plotly 1970년 표기 → 초→밀리초 변환 누락 여부 확인(`Chart.tsx`)
- `.KS` 접미사 제거 → 6자리 코드만 사용

---

## 로드맵(요약)

- 사용자 패턴 라벨링 저장(프론트 라벨 → 백엔드 API → DB)
- 실제 가격 레벨 계산(샘플 제거, 지지/저항 자동 탐지)
- 성능 최적화(인덱스/제한/페이지네이션/캐싱)
- 가용 데이터 안내 UI(보유 구간 KST)
- PaaS 배포(Vercel, Railway) 및 환경변수 구성

(세부 사항은 "TradeSmartAI & ChartInsight Studio 통합 개발 계획_수행 보고 (Ver 6.0).md"를 참조하십시오.)
