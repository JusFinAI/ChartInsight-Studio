### **TradeSmartAI & ChartInsight Studio 통합 개발 계획/수행 보고 (Ver 6.0)**

버전: 5.0  
작성일: 2025년 8월 7일  
작성자: Gemini AI (AI 기술 코치)

#### **1\. 프로젝트 개요**

본 프로젝트는 "TradeSmartAI" 데이터 파이프라인을 기반으로, 개인 투자자에게 전문가 수준의 실시간 차트 분석 기능을 제공하는 웹 서비스 \*\*"ChartInsight Studio"\*\*를 구축하는 것을 최종 목표로 한다.

Ver 4.0까지는 안정적인 데이터 수집 파이프라인 구축에 중점을 두었으나, Ver 5.0부터는 수집된 데이터를 활용하는 **풀스택 웹 애플리케이션 개발**로 프로젝트의 범위가 공식적으로 확장되었다. 본 문서는 확장된 목표에 맞춰 재구성된 개발 환경, 진화된 아키텍처, 그리고 수정된 최종 배포 전략을 종합적으로 기록한다.

#### **2\. 기술 스택 (확장)**

| 구분 | 기술 | 목적 |
| :---- | :---- | :---- |
| **Orchestration** | Apache Airflow | 데이터 수집 파이프라인 자동화 |
| **Database** | PostgreSQL | 주식 데이터(OHLCV) 및 Airflow 메타데이터 저장 |
| **Backend** | FastAPI (Python 3.x) | 웹 애플리케이션 비즈니스 로직 및 API 서버 |
| **Frontend** | Next.js (TypeScript) | 사용자 인터페이스(UI) 및 차트 시각화 |
| **Development Env.** | Docker Desktop with WSL2 | 컨테이너 기반의 통합 로컬 개발 환경 |

#### **3\. 단계별 계획 및 수행 보고**

3.1. 1단계: 핵심 로직 및 프로토타입 검증 (완료)  
1단계에서는 데이터 파이프라인의 핵심 기능과 웹 애플리케이션의 프로토타입을 각개전투 방식으로 개발하고 그 가능성을 검증했다.

* **데이터 파이프라인**: Kiwoom API를 통해 OHLCV 데이터를 수집하고 PostgreSQL에 저장하는 Airflow DAG의 핵심 로직을 완성하고, dag\_initial\_loader와 dag\_live\_collectors를 통해 초기 적재 및 증분 업데이트 기능을 구현했다.  
* **웹 애플리케이션 프로토타입**: FastAPI와 Next.js를 사용하여 Trading Radar 페이지의 핵심 UI와 Peak/Valley 탐지 알고리즘 등 주요 기능을 상당 수준 구현했다. 이 단계에서는 데이터베이스 연동 없이 API 직접 호출 및 더미 데이터를 활용하여 기능의 실현 가능성을 검증했다.

3.2. 2단계: 풀스택 통합 개발 환경 구축 및 파이프라인 안정화 (완료)  
이번 단계는 분산되어 있던 각 구성 요소를 전문가 수준의 단일 통합 개발 환경으로 구축하고, 실제 운영을 위한 안정성을 확보하는 데 중점을 두었다. 이 과정에서 발생한 수많은 기술적 난제를 해결하며 시스템의 완성도를 비약적으로 높였다.

* **프로젝트 구조 통합**: 윈도우와 WSL2에 분산되어 있던 frontend, backend, DataPipeline 폴더를 WSL2 내부의 단일 루트 폴더(\~/ChartInsight-Studio)로 통합하고, 전체 프로젝트를 단일 Git 저장소에서 관리하는 모노레포 구조의 기반을 마련했다.  
* **Docker 환경 재구성**:  
  * **통합 오케스트레이션**: 프로젝트 전체를 총괄하는 마스터 docker-compose.yaml 파일을 루트에 생성했다. 이 과정에서 기존에 검증된 DataPipeline의 설정을 존중하되, frontend와 backend 서비스를 추가하고 **Profiles 기능**을 도입하여 '웹 앱(app)'과 '데이터 파이프라인(pipeline)'을 독립적으로 실행할 수 있는 유연성을 확보했다.  
  * **이미지 최적화**: frontend와 backend를 위한 Dockerfile을 각각 작성하고, node\_modules, venv 등 불필요한 파일을 빌드에서 제외하는 .dockerignore 파일을 추가하여 이미지 용량을 최적화하고 빌드 속도를 향상시켰다.  
* **환경 문제 심층 해결**:  
  * **WSL2 & Docker**: Docker Desktop의 'WSL Integration' 설정 오류를 해결하고, docker container prune, docker network inspect 등 심화 명령어를 통해 반복적으로 발생하던 '유령' 컨테이너 및 네트워크 문제를 완전히 해결하여 깨끗하고 안정적인 실행 환경을 확보했다.  
  * **Python 의존성**: WSL2(Ubuntu 24.04) 환경에서 발생한 distutils 누락 및 버전 비호환성 문제를 시스템 패키지(apt)와 애플리케이션 패키지(pip)의 차이점을 학습하며 해결했다. pip 등 빌드 도구 자체를 업그레이드하여 최종적으로 의존성 설치를 완료했다.  
* **파이프라인 안정성 확보 및 검증**:  
  * Airflow의 Pool 기능을 airflow-init을 통해 자동으로 생성하도록 설정하여, 다수의 DAG가 동시에 실행되어도 API 호출이 안전하게 순차적으로 처리되도록 보장했다.  
  * docker compose \--profile pipeline up \-d 명령어로 파이프라인을 실행하여, Airflow UI와 DBeaver 양쪽에서 증분 데이터가 스케줄에 맞춰 누락 없이 꾸준히 쌓이는 것을 최종 검증했다.  
* **풀스택 환경 구동 성공**: docker compose \--profile app up \-d 명령어로 frontend, backend, DB 컨테이너를 성공적으로 실행했다. localhost:3000에서 Next.js UI가, localhost:8000/docs에서 FastAPI API가 정상적으로 동작함을 확인하며, **완벽한 풀스택 로컬 개발 환경 구축을 완료**했다.

3.3. 3단계: ChartInsight Studio MVP 기능 완성 (진행 중)  
이제 안정적으로 구축된 통합 개발 환경 위에서 ChartInsight Studio의 핵심 기능을 완성하는 단계이다.

* **핵심 과제**: backend가 DataPipeline이 수집하여 PostgreSQL에 저장한 데이터를 직접 조회하여 frontend에 제공하도록 데이터 흐름을 연결한다. (현재는 API 직접 호출 또는 더미 데이터 사용)  
* **주요 활동**:  
  * backend에 SQLAlchemy ORM을 이용한 DB CRUD(Create, Read, Update, Delete) 로직 구현.  
  * frontend의 API 요청에 따라 backend가 DB에서 데이터를 조회하여 전달하도록 수정.  
  * 사용자 패턴 라벨링 기능 구현 및 DB 저장.

3.4. 4단계: PaaS 기반 프로토타입 배포 (계획 수정)  
초기 계획이었던 IaaS(GCP) 기반 배포는 MVP 단계에 비해 과도한 복잡성과 초기 비용을 유발할 수 있다고 판단하여, 더 빠르고 효율적인 PaaS 기반 배포로 전략을 수정한다.

* **목표**: MVP 기능이 완성된 ChartInsight Studio를 실제 사용자들이 접근할 수 있도록 인터넷에 배포한다.  
* **핵심 활동**:  
  * **Frontend 배포**: Next.js에 최적화된 **Vercel** 플랫폼을 사용하여 배포.  
  * **Backend & DB 배포**: **Railway**와 같은 PaaS를 사용하여 FastAPI 서버와 PostgreSQL 데이터베이스를 배포.  
  * **CI/CD 구축**: Github에 코드를 Push하면 자동으로 Vercel과 Railway에 새로운 버전이 배포되도록 파이프라인을 구성.

3.5. 5단계: IaaS 기반 확장 운영 (장기 계획)  
PaaS 배포를 통해 서비스의 시장성을 검증하고 사용자가 충분히 확보된 이후, 더 높은 수준의 확장성과 제어권을 위해 IaaS(GCP/AWS) 환경으로의 마이그레이션을 고려한다. 이 단계는 장기적인 비전으로 남겨둔다.

---

### **TradeSmartAI & ChartInsight Studio 통합 개발 계획/수행 보고 (Ver 6.0)**

버전: 6.0  
작성일: 2025년 8월 16일  
작성자: GPT-5 (AI 코딩 어시스턴트)

#### **A. 이번 세션에서 수행한 수정/추가 및 검증 결과**

- **백엔드 변경 사항**
  - `backend/requirements.txt`: `SQLAlchemy`, `psycopg2-binary` 추가(포스트그레스 연동)
  - `backend/app/database.py` 신규: 엔진/세션 팩토리/`Base` 정의 및 `get_db()` DI 제공. `DATABASE_URL` 환경변수 사용.
  - `backend/app/models.py` 신규: `live.stocks`, `live.candles` ORM 모델 정의. `UniqueConstraint`, `Index`, `timezone=True` 구성 반영.
  - `backend/app/crud.py` 신규: 데이터 액세스 계층 분리.
    - `normalize_timeframe(api_tf)`: `5m→M5`, `30m→M30`, `1h→H1`, `1d→D`, `1wk→W` 매핑
    - `get_candles(db, stock_code, api_timeframe, start_time, end_time, limit, sort_asc)`
    - `get_latest_candles(db, stock_code, api_timeframe, limit)`
    - `get_time_range(db, stock_code, api_timeframe)`
    - `list_stocks(db)`, `get_stock(db, stock_code)`
  - `backend/app/routers/pattern_analysis.py` 보강:
    - 한국 주식(6자리 코드) 요청은 항상 내부 DB에서 조회하도록 일원화
    - DB의 UTC 타임스탬프를 KST로 변환 후 epoch seconds로 응답
    - `period` 파라미터 해석(`_parse_period_to_timedelta`) 및 기간 기반 조회 구현, `limit` 상한 적용
    - 응답에 `"source":"db"` 포함, 응답 헤더 `X-Data-Source: db` 추가
    - `/symbols/kr-targets` 신설: 실제 캔들이 존재하는 한국 종목만 반환
    - 인기심볼 API에서 한국 종목의 `.KS` 접미사 제거

- **프론트엔드 변경 사항**
  - `frontend/src/services/api.ts`:
    - `fetchKrTargetSymbols(limit)` 추가(`/api/v1/pattern-analysis/symbols/kr-targets` 호출)
    - `fetchTradingRadarData()`에 응답 `source`/헤더 인지 로직 반영(내부 로깅)
  - `frontend/src/app/trading-lab/trading-radar/page.tsx`:
    - 한국 주식 탭: 드롭다운을 백엔드 DB 대상 30종목으로 동적 로드
    - 기본 심볼을 `005930`으로 설정(삼성전자)
    - 한국 주식 선택 시 `.KS` 제거(6자리 코드만 사용)
    - 타임프레임 드롭다운에서 `1m` 제거
    - 현재가 원화 표기(예: `68,800원`), 추세 시작일 KST 가독 형식으로 표시
    - 기간 드롭다운은 상태만 갱신하고, ‘적용’ 클릭 시 데이터 로드로 경합 조건 제거
  - `frontend/src/components/ui/Chart.tsx`:
    - Plotly 요구사항에 맞게 `epoch seconds → milliseconds` 변환(`x = time * 1000`)

- **검증 결과(발췌)**
  - DB 보유 구간(UTC): `2023-02-20 15:00` ~ `2025-08-05 15:00`  
    - KST 기준: 대략 `2023-02-21 00:00` ~ `2025-08-06 00:00`
  - API 응답 소스 확인:
    ```bash
    curl -s "http://localhost:8000/trading-radar-data?symbol=005930&timeframe=5m&chart_type=candlestick&period=auto" | grep -o '"source":"[^\"]*"'
    # "source":"db"
    ```
  - 타임스탬프 KST 검증:
    ```bash
    TZ=Asia/Seoul date -d @1753929300
    # Thu Jul 31 11:35:00 KST 2025
    ```
  - KR 타겟 심볼 API:
    ```bash
    curl -s "http://localhost:8000/api/v1/pattern-analysis/symbols/kr-targets?limit=30"
    ```
  - 프론트 차트의 1970년 표시 문제 해결: ms 단위 변환 적용 후 정상 동작
  - 현재가 `$` 문제 해결: 원화로 표기, 천단위 구분
  - 기간 드롭다운 매핑 문제 해결: 1년/2년 선택 시 데이터 범위 차등 반영, 5년은 보유 데이터까지 표시

- **발생 이슈와 해결**
  - 한국 종목 `.KS` 접미사로 인한 404: 6자리 코드로 통일해 해결
  - `Stock.table` 오타: `Stock.__table__`로 수정하여 ORM 메타 확인 성공
  - `jq` 미설치: 설치 안내 또는 `curl` 단독 사용 대안 제시
  - `psql` 접속 시 `role "root" does not exist`: 정확한 사용자 지정(`-U tradesmart_db`)으로 해결
  - Plotly 시간 단위 오해(초 vs 밀리초): 프론트에서 밀리초 변환 적용으로 해결

- **정책/설계 결정**
  - 한국 주식 데이터 소스는 DB로 일원화(외부 API 경로는 비한국 종목에 한해 유지)
  - 백엔드는 UTC→KST 변환 후 epoch seconds로 응답, 프론트는 Plotly 입력을 위해 ms 변환
  - `period`는 서버에서 기간 기반 조회로 해석(성능 위해 분/시간봉 기본 상한 적용)

#### **B. Ver 5.0 계획 대비 완료 항목(3.3 관련)**

- Backend에 SQLAlchemy ORM 기반 CRUD 로직 구현 및 분리 완료(`database.py`, `models.py`, `crud.py`)
- Frontend 요청이 Backend를 통해 DB 조회로 이어지는 통합 경로 구축(한국 주식 일원화)
- Trading Radar 핵심 UX 개선(기간, 통화, 시간 포맷, 기본 심볼) 및 데이터 신뢰성 향상

#### **C. 초보 개발자를 위한 필수 지식·운영 노하우(기록 권장)**

- **환경변수(Next.js)**: `NEXT_PUBLIC_` 프리픽스가 붙은 값만 브라우저에 노출됨. 프로젝트에 `.env.local` 등을 생성해 `NEXT_PUBLIC_API_URL`을 정의할 수 있음. 미정의 시 `api.ts`의 기본값(`http://127.0.0.1:8000`) 사용.
- **타임존 원칙**: DB는 UTC로 저장, 사용자 표시 단계에서 Asia/Seoul(KST)로 변환. 서버에서는 `ZoneInfo("Asia/Seoul")` 활용.
- **타임스탬프 단위**: 서버 응답은 epoch seconds, Plotly는 milliseconds 요구. 프론트에서 `* 1000` 필수.
- **한국 종목 심볼 형식**: 내부 DB 및 파이프라인은 6자리 코드(`005930`). `.KS` 미사용.
- **기간(period) 처리**: `1y/2y/5y` 등 문자열을 서버에서 기간으로 해석해 시작일 계산. 보유 구간을 초과하면 가용 데이터까지만 표시.
- **컨테이너·로그 확인**: `docker compose --profile app up -d`, `docker logs -f <container>`로 추적. 서비스명/컨테이너명 일치 확인.
- **DB 점검**: `docker compose exec postgres-tradesmart psql -U tradesmart_db -d tradesmart_db -c '\dt live.*'`로 테이블 존재 확인.
- **엔드투엔드 검증 루틴**: `curl`로 백엔드 응답/헤더 확인 → 프론트 시각 검증 → 필요 시 Playwright로 UI 자동화 검증.

#### **D. API/데이터 흐름 다이어그램**

```mermaid
graph TD
  A[사용자: Trading Radar 페이지] --> B[frontend/src/app/trading-lab/trading-radar/page.tsx]
  B --> C[frontend/src/services/api.ts<br/>fetchTradingRadarData]
  C --> D[HTTP 요청<br/>${API_URL}/api/v1/pattern-analysis/trading-radar-data]
  D --> E[backend/app/main.py 라우팅]
  E --> F[backend/app/routers/pattern_analysis.py<br/>get_trading_radar_data]
  F --> G{한국 주식 코드?}
  G -->|예| H[backend/app/crud.py<br/>get_candles/get_latest_candles]
  G -->|아니오| I[외부 API 경로]
  H --> J[UTC→KST 변환·가공<br/>TradingRadarData 응답]
  I --> J
  J --> K[프론트 응답 수신]
  K --> L[frontend/src/components/ui/Chart.tsx<br/>Plotly ms 변환 후 렌더]
```

#### **E. 검증 명령어 기록(참고용)**

```bash
# 백엔드 헬스체크
curl -s http://localhost:8000/health

# 한국 종목(분봉) DB 응답 검사 및 소스 표기 확인
curl -s "http://localhost:8000/trading-radar-data?symbol=005930&timeframe=5m&chart_type=candlestick&period=auto" | grep -o '"source":"[^\"]*"'

# KST 변환 검증(예시 Epoch)
TZ=Asia/Seoul date -d @1753929300

# DB 보유 구간 확인(일봉 예시)
docker compose exec backend python -c "from app.database import SessionLocal; from app.crud import get_time_range; db=SessionLocal(); print(get_time_range(db,'005930','1d')); db.close()"

# 라이브 스키마 테이블 확인
docker compose exec postgres-tradesmart psql -U tradesmart_db -d tradesmart_db -c '\dt live.*'

# 한국 주식 대상 심볼 목록 확인
curl -s "http://localhost:8000/api/v1/pattern-analysis/symbols/kr-targets?limit=30"
```

#### **F. 다음 단계 제안(로드맵 연계)**

- **사용자 패턴 라벨링**: 프론트에서 사용자가 Peak/Valley/패턴을 라벨링 → 백엔드 API → DB 저장(히스토리 포함)
- **실제 가격 레벨 계산**: 샘플 레벨 제거, `ohlcv` 기반의 지지/저항 자동 탐지 로직 도입
- **성능 최적화**: 분/시간봉 조회에 인덱스 점검, 제한/페이지네이션, 서버 캐싱 계층 검토
- **가용 데이터 안내 UI**: 차트 상단에 DB 보유 구간(KST) 노출, 5년 선택 시 안내 문구 표시
- **테스트 자동화**: Playwright 시나리오 확장(기간 변경, 통화 표시, 시작일 포맷 등 리그레션)
- **배포 준비**: Ver 5.0의 3.4 계획대로 Vercel/Railway PaaS로 MVP 배포, 환경변수 구성 점검(`NEXT_PUBLIC_API_URL`, `DATABASE_URL`)

#### **G. 향후 개발 필요 사항**

- **프론트 환경변수 운영 가이드**
  - `.env.local` 예시(개발):
    - `NEXT_PUBLIC_API_URL=http://localhost:8000`
  - 배포 시 플랫폼 환경변수로 설정(Vercel/Cloud 환경)
  - 주의: `NEXT_PUBLIC_` 접두사만 브라우저에 노출됨

- **사용자 패턴 라벨링 저장 설계(초안)**
  - 테이블: `live.user_patterns`
  - 주요 컬럼: `id`, `user_id`, `stock_code`, `timeframe`, `pattern_type`, `start_ts_utc`, `end_ts_utc`, `created_at_utc`, `meta_json`
  - 인덱스: `(user_id, stock_code, timeframe, start_ts_utc)`
  - API: POST/GET/DELETE 라우트 초안 수립 후 프론트 연동

---

본 Ver 6.0 문서는 Ver 5.0 문서의 모든 문장을 그대로 유지하면서, 이번 세션에서 수행된 변경 사항과 검증 결과, 운영 지식, 다음 단계 제안을 **추가(append)** 형식으로 반영하였다.