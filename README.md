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
├─ DataPipeline/
│  ├─ dags/                            # Airflow DAGs: 초기 적재 및 증분 업데이트
+│  ├─ src/
│  │  ├─ database.py                   # 파이프라인용 DB 접속/모델 정의 (Candle/Stock)
│  │  ├─ utils/common_helpers.py       # 파이프라인 유틸(대상 종목 조회 등)
│  │  └─ ...
│  ├─ data/                            # 테스트/샘플 데이터
│  └─ docs/                            # 파이프라인 운영자용 문서(선택)
├─ backend/
│  ├─ app/
│  │  ├─ main.py                       # FastAPI 앱 생성 및 라우터 등록
│  │  ├─ routers/
│  │  │  └─ pattern_analysis.py        # Trading Radar 통합 API 라우터
│  │  ├─ crud.py                       # DB 조회 추상화 (예: get_candles)
│  │  ├─ models.py                     # ORM 모델(live.candles, live.stocks)
│  │  └─ database.py                   # SQLAlchemy 엔진/세션 구성
│  ├─ _temp_integration/
│  │  └─ chart_pattern_analyzer_kiwoom_db/  # 리팩토링/이식 준비된 실험 코드 (이전 v3 이름 변경)
│  │     ├─ run_full_analysis_impl.py  # 분석 엔진: DataFrame 입력 → 패턴/추세 분석 출력
│  │     │   - 입력: pandas.DataFrame (time, open, high, low, close, volume, ...) - UTC epoch seconds
│  │     │   - 출력: { patterns: [...], js_points: {peaks, valleys}, trend_periods: [...], price_levels: [...] }
│  │     ├─ data_loader.py              # DB → pandas.DataFrame (UTC→Asia/Seoul 변환 포함)
│  │     │   - 역할: DB 쿼리 래핑, timezone 변환, 필요한 컬럼 정리
│  │     │   - 권장 시그니처: load_candles_from_db(session, stock_code, timeframe, period=None, limit=None, tz='Asia/Seoul')
│  │     │   - 입력 예시:
│  │     │     ```python
│  │     │     df = load_candles_from_db(db_session, '005930', '1d', period='2y')
│  │     │     # 반환: pandas.DataFrame with columns [time (epoch sec), open, high, low, close, volume]
│  │     │     ```
│  │     │   - 출력 예시 (DataFrame sample):
│  │     │     ```
│  │     │     time, open, high, low, close, volume
│  │     │     1753920000, 80000, 80500, 79500, 80200, 12345
│  │     │     ```
│  │     ├─ main_dashboard.py           # 개발용 런처 및 데모 스크립트
│  │     ├─ logger_config.py            # 로거 설정(이식 시 앱 startup에서만 핸들러 추가)
│  │     └─ 기타 실험용 스크립트
│  ├─ requirements.txt
│  └─ Dockerfile
├─ frontend/
│  ├─ src/
│  │  ├─ app/trading-lab/trading-radar/page.tsx    # Trading Radar UI: 토글/필터/데이터 로드 로직
│  │  ├─ services/api.ts                           # API 클라이언트 래퍼 (fetchTradingRadarData 등)
│  │  └─ components/ui/Chart.tsx                   # Plotly 렌더링: epoch → ms 변환, 피크/밸리/넥라인 처리
│  ├─ next.config.ts
│  └─ Dockerfile
```

---

## 주요 파일/모듈

 - Backend
  - `app/main.py`: FastAPI 앱 생성, 라우터 등록, `/health` 등 기본 엔드포인트 구성
  - `app/routers/pattern_analysis.py`: Trading Radar 통합 API 라우터
    - `GET /api/v1/pattern-analysis/trading-radar-data` — 차트/JS 포인트/패턴/추세 정보를 통합 반환
    - `GET /api/v1/pattern-analysis/symbols/kr-targets` — 한국 주식 대상 심볼 목록 반환
    - 내부 동작: DB 조회 결과(UTC)를 KST로 변환해 epoch seconds로 응답, `period` 파라미터 해석 포함
  - `app/crud.py`: DB 조회 추상화
    - `get_candles(...)`: 특정 심볼/타임프레임/기간의 캔들 데이터 반환(UTC 기준)
    - `get_latest_candles(...)`, `get_time_range(...)` 등 재사용 가능한 쿼리 함수 포함
  - `app/models.py`: ORM 모델 정의 (`live.candles`, `live.stocks`), 스키마/인덱스 반영
  - `app/database.py`: SQLAlchemy 엔진/세션 설정 및 `get_db()` DI 헬퍼
  - `_temp_integration/chart_pattern_analyzer_kiwoom_db/` (이식 준비 폴더)
    - `run_full_analysis_impl.py`: 분석 엔진의 핵심 구현체
      - 입력 예시:
        ```python
        # pandas.DataFrame (UTC epoch seconds)
        df.head()
        # time, open, high, low, close, volume
        ```
      - 출력 예시:
        ```json
        {
          "patterns": [{"pattern_type":"HS","startTime":...,"endTime":...}],
          "js_points": {"peaks": [{"time":...,"value":...}], "valleys": [...]},
          "trend_periods": [{"type":"Uptrend","start":...,"end":...}],
          "price_levels": [{"type":"support","value":...}]
        }
        ```
      - 입력: pandas.DataFrame (캔들 데이터, UTC)
      - 출력: 패턴(HS/IHS/DT/DB), 피크/밸리(JSPoints), 추세 기간(trend_periods), 넥라인/가격 레벨
      - 변경 포인트: 시각화·다운로드 의존 제거, 모듈 레벨 부작용 제거, `logging.getLogger(__name__)` 사용
    - `data_loader.py`: DB에서 캔들 데이터를 로드해 pandas.DataFrame으로 반환
      - 기능: `get_candles` 호출 래핑, UTC 로컬화 후 `tz_convert('Asia/Seoul')` 수행, 필요한 컬럼 정리
      - 권장 인터페이스: `load_candles_from_db(session, stock_code, timeframe, period=None, limit=None, tz='Asia/Seoul')`
    - `main_dashboard.py`: 개발/데모용 런처 스크립트
      - 역할: 독립 실행 환경에서 엔진을 호출하고 결과를 시각화하는 간단한 데모 파이프라인
      - 주의: 운영으로 복사 시 모듈 임포트 부작용(핸들러/파일생성)이 없는지 확인 필요
    - `logger_config.py`: 과거 v3용 로거 설정 모듈(이식 시 앱 startup에서만 핸들러 추가하도록 변경 권장)

- Frontend
  - `src/app/trading-lab/trading-radar/page.tsx`: Trading Radar UI, 기본 심볼 `005930`
  - `src/services/api.ts`: `fetchTradingRadarData`, `fetchKrTargetSymbols` 등
  - `src/components/ui/Chart.tsx`: Plotly 차트(ms 변환)

- DataPipeline
  - `src/database.py`: 파이프라인 기준 ORM(스키마: `live`), `Candle`/`Stock`
  - `src/utils/common_helpers.py`: `get_target_stocks()` (타겟 30개)
  - `dags/*`: 초기 적재/증분 업데이트 DAG

---

## 구동/검증 예시

```bash
# 웹 앱 실행
docker compose --profile app up -d

# 백엔드 헬스체크
curl -s http://localhost:8000/health

# 한국 주식 대상 심볼 확인
docker compose exec backend printenv DATABASE_URL | cat
curl -s "http://localhost:8000/api/v1/pattern-analysis/symbols/kr-targets?limit=30"

# Trading Radar 응답 소스 확인 (expect: "source":"db")
curl -s "http://localhost:8000/trading-radar-data?symbol=005930&timeframe=5m&chart_type=candlestick&period=auto" | grep -o '"source":"[^\"]*"'

# KST 타임스탬프 검증 (예시 epoch)
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
