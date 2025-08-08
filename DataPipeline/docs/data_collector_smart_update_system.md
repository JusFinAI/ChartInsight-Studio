# 스마트 증분 업데이트 시스템 기술 문서

## 📋 프로젝트 배경 및 개요

### 프로젝트 배경
본 시스템은 **"TradeSmartAI"** 프로젝트의 `src/data_collector.py` 모듈 개발에 앞서, **Airflow 연동 및 데이터 수집/저장 흐름을 검증**하기 위한 간소화된 테스트 환경으로 시작되었습니다. 

특히 **Airflow의 전반적인 사용법을 학습**하는 데 중점을 두었으며, 주말(시장 비운영) 상황에서도 **과거 데이터를 활용한 주기적 업데이트 시뮬레이션**을 가능하게 합니다.

### 최종 목적
- **Airflow 학습**: 스케줄링, DAG 실행, Task 관리, UI 모니터링 등 핵심 기능 마스터
- **실시간 데이터 수집**: 키움 API를 통한 한국 주식 분봉 데이터 실시간 수집
- **스마트 증분 업데이트**: 중복 없이 효율적인 신규 데이터만 수집
- **운영 환경 준비**: 실제 `data_collector.py` 개발을 위한 검증된 아키텍처 구축

### 진화된 핵심 특징
- **1개씩 순차 처리**: 배치 처리 대신 1개 캔들씩 처리하여 Airflow 스케줄링 동작 관찰
- **거래시간 자동 처리**: 장 마감 후 자동으로 다음 거래일 첫 캔들 선택
- **타임존 안전**: UTC↔KST 변환으로 정확한 시간 비교
- **API 순서 유지**: 정렬 없이 키움 API 원본 순서 그대로 유지
- **스마트 로직**: 단순 시간 계산 대신 실제 신규 데이터 감지

## 🏗️ 시스템 구조

### 파일 구성
```
src/
├── data_collector_test.py          # 핵심 데이터 수집 로직 (최종 구현)
└── database.py                     # DB 모델 및 연결
dags/
└── data_collector_test_dag.py      # Airflow DAG 정의
docs/
└── data_collector_smart_update_system.md  # 본 문서
```

### 주요 함수 진화 과정

#### 최초 계획된 함수들
1. **`fetch_and_store_initial_minute_data()`** (초기 요구사항)
   - 원래 시그니처: `(stock_code, timeframe_minutes, base_date_str, start_time_str, num_candles)`
   - 목적: 특정 날짜/시간부터 지정된 개수만큼 초기 데이터 적재

2. **`fetch_and_store_next_minute_candle()`** (초기 요구사항)
   - 원래 시그니처: `(stock_code, timeframe_minutes, last_timestamp_str)`
   - 목적: 마지막 타임스탬프 기준으로 다음 1개 캔들 수집

#### 최종 구현된 함수들
1. **`fetch_and_store_initial_minute_data()`** (개선된 버전)
   - 최종 시그니처: `(stock_code, timeframe_minutes, base_date_str, num_candles)`
   - 개선점: `start_time_str` 제거로 단순화, `num_candles` 파라미터 활용

2. **`fetch_and_store_next_minute_candle()`** (스마트 버전)
   - 최종 시그니처: `(stock_code, timeframe_minutes, last_timestamp_str=None)`
   - 혁신점: DB 자동 조회 + 스마트 증분 업데이트 로직

3. **`_db_upsert_candles()`** (새로 추가)
   - 목적: 배치 처리를 통한 효율적인 DB 저장 및 중복 방지

## 🔧 세부 구현

### 1. 스마트 증분 업데이트 로직 (핵심 혁신)

#### 초기 계획 vs 최종 구현
```python
# 초기 계획 (단순 시간 계산)
def fetch_and_store_next_minute_candle_v1(stock_code, timeframe_minutes, last_timestamp_str):
    # last_timestamp_str + timeframe_minutes로 다음 시간 계산
    next_time = last_timestamp + timedelta(minutes=timeframe_minutes)
    # 해당 시간의 캔들 1개 조회
    
# 최종 구현 (스마트 감지)
def fetch_and_store_next_minute_candle_v2(stock_code, timeframe_minutes, last_timestamp_str=None):
    # 1. DB에서 최신 캔들 자동 조회 (KST 변환)
    latest_candle = db.query(Candle).order_by(Candle.timestamp.desc()).first()
    latest_db_timestamp = latest_candle.timestamp.astimezone(ZoneInfo('Asia/Seoul'))
    
    # 2. API에서 최신 데이터 대량 가져오기
    chart_data = get_minute_chart(stock_code, num_candles=900)
    
    # 3. DB 이후 신규 데이터 스마트 필터링
    mask = df.index > latest_db_timestamp
    newer_data_df = df[mask]
    
    # 4. 첫 번째 1개만 선택 (Airflow 학습 목적)
    if not newer_data_df.empty:
        first_new_timestamp = newer_data_df.index.min()
        new_data_df = newer_data_df.loc[[first_new_timestamp]]
        
    # 5. DB에 저장
    _db_upsert_candles(db, stock_code, timeframe_minutes, new_data_df)
```

#### 거래시간 자동 처리의 혁신
- **초기 계획**: 수동으로 거래시간 계산 필요
- **최종 구현**: 자동 감지
  - **장 마감 후** (예: 15:35) → **다음 거래일 첫 캔들** (예: 09:05) 자동 선택
  - **점심휴장** (11:30-12:30) 자동 건너뛰기
  - **휴일/주말** 자동 건너뛰기

### 2. 타임존 처리 (중요한 발견과 해결)

#### 발견된 문제점
```python
# PostgreSQL 저장: 2025-05-29 15:35:00+09:00 (KST)
# SQLAlchemy 읽기: 2025-05-29 06:35:00+00:00 (UTC 변환됨)
# API 데이터: 2025-05-29 15:35:00+09:00 (KST)
# 비교 실패: 06:35:00 ≠ 15:35:00
```

#### 해결책 개발
```python
# DB에서 읽은 즉시 KST로 변환
latest_db_timestamp = latest_candle.timestamp.astimezone(ZoneInfo('Asia/Seoul'))

# API 데이터와 동일한 타임존에서 비교
mask = df.index > latest_db_timestamp  # 둘 다 KST
```

### 3. 정렬 문제 해결 (예상치 못한 이슈)

#### 발견된 문제점
- `chart_data.py`에서 `sort_index()`, `sort_values()` 호출
- API 원본 순서 → 시간순 정렬 → DB에서 새 캔들이 중간 삽입

#### 해결책
```python
# chart_data.py에서 정렬 제거
# df_processed = df_processed.sort_index()  # 주석 처리
# start_date = df['Date'].min()  # sort_values 대신 min/max 사용
# end_date = df['Date'].max()

# 결과: API 순서 그대로 → DB 맨 아래 자연스러운 삽입
```

### 4. DB 최적화 (성능 개선)

#### 배치 삽입 구현
```python
def _db_upsert_candles(db: Session, stock_code: str, timeframe_minutes: int, df_candles: pd.DataFrame):
    # 기존 데이터 배치 조회
    existing_timestamps = set(db.query(Candle.timestamp).filter(...).all())
    
    # 새로운 데이터만 배치 삽입
    new_candles = [Candle(...) for timestamp in new_timestamps]
    if new_candles:
        db.add_all(new_candles)  # 배치 삽입
        db.commit()
```

#### 커밋 최적화
- **신규 데이터 있을 때만** 커밋
- **중복 데이터 없을 때** 커밋 생략

## 🚀 Airflow DAG 구성

### 초기 계획 vs 최종 구현

#### 초기 계획된 DAG 설정
```python
# 원래 요구사항
schedule_interval='*/2 * * * *'  # 매 2분마다
start_date=days_ago(1)           # 상대적 날짜
```

#### 최종 구현된 DAG 설정
```python
dag = DAG(
    dag_id='data_collector_test_dag',
    schedule_interval='*/1 * * * *',  # 매 1분마다 (학습 최적화)
    start_date=pendulum.datetime(2025, 5, 30, tz="Asia/Seoul"),  # 절대 날짜
    catchup=False,
    tags=['test', 'data_collector', 'smart_update']
)
```

### Task 구성 진화

#### 초기 계획
1. **`initial_load_minute_data_task`**: 조건부 실행 (Variable 체크)
2. **`periodic_update_minute_data_task`**: 의존성 기반 실행

#### 최종 구현
1. **`initial_load_task`**: 스마트 스킵 로직 (한 번만 실행)
2. **`smart_incremental_update_task`**: 독립적 실행 (DB 자동 조회)

### Airflow Variables 설계

#### 계획된 Variables
```python
# 초기 요구사항
VAR_TEST_STOCK_CODE = "005930"
VAR_TEST_TIMEFRAME_MINUTES = "5"
VAR_TEST_BASE_DATE_STR = "20250530"
VAR_TEST_START_TIME_STR = "090000"  # 제거됨
VAR_TEST_NUM_INITIAL_CANDLES = "5"  # 77로 확장됨
VAR_LAST_COLLECTED_TIMESTAMP = "자동관리"
```

#### 최종 구현된 Variables
```python
VAR_TEST_STOCK_CODE = "005930"           # 삼성전자
VAR_TEST_TIMEFRAME_MINUTES = "5"         # 5분봉
VAR_TEST_BASE_DATE_STR = "20250529"      # 실제 거래일로 조정
VAR_TEST_NUM_INITIAL_CANDLES = "77"      # 하루치 데이터로 확장
VAR_LAST_COLLECTED_TIMESTAMP = "자동관리"  # 마지막 수집 타임스탬프
```

## 📋 테스트 시나리오

### 계획된 시나리오 vs 실제 검증

#### 원래 계획된 테스트 흐름
1. Airflow UI에서 DAG 활성화
2. 수동으로 `initial_load_minute_data_task` 실행 → 5개 캔들 적재
3. 스케줄에 따라 `periodic_update_minute_data_task` 주기 실행
4. Variable 값 변화 모니터링

#### 실제 검증된 시나리오
1. **초기 적재**: 77개 캔들 (하루치 5분봉) 성공적 저장
2. **스마트 증분**: 장 마감 후 → 다음 거래일 첫 캔들 자동 감지
3. **타임존 안전**: UTC↔KST 변환 문제 해결 확인
4. **DB 순서**: 새 캔들이 자연스럽게 맨 아래 추가 확인
5. **Airflow 모니터링**: 1분마다 정확한 스케줄링 확인

## 🔍 학습 포인트

### Airflow 스케줄링 관찰
1. **매 1분 실행**: DAG가 정확히 1분마다 트리거되는지 확인
2. **Task 실행 시간**: 각 Task가 몇 초에 완료되는지 측정
3. **의존성 관리**: initial_load → smart_update 순서 확인
4. **Variable 관리**: Airflow UI에서 Variable 변경 및 영향 확인

### 데이터 수집 패턴 관찰
1. **거래시간 동작**: 15:35 이후 → 다음날 09:05 자동 처리
2. **순차 처리**: 1개씩 처리로 스케줄링 효과 극대화
3. **API 호출 최적화**: 불필요한 호출 방지

### 실무 경험 축적
1. **PostgreSQL 타임존**: `DateTime(timezone=True)` 동작 이해
2. **키움 API 특성**: ka10080 고정 900개 반환, 역순 정렬
3. **DataFrame 처리**: 인덱스 vs 컬럼, 타임존 처리

## 🐛 주요 해결된 이슈

### 1. PostgreSQL 타임존 변환 이슈
- **원인**: `DateTime(timezone=True)` 설정으로 UTC 자동 변환
- **증상**: DB 최신 캔들이 06:35:00 (UTC)로 읽힘 → 거래시간 아님
- **해결**: 읽기 시 `astimezone(ZoneInfo('Asia/Seoul'))` 변환

### 2. 거래시간 계산 오류
- **원인**: 단순 `+5분` 계산으로 비거래시간 포함
- **증상**: 15:35 + 5분 = 15:40 (거래시간 아님)
- **해결**: DB 이후 신규 데이터 중 첫 번째 선택

### 3. 정렬로 인한 삽입 순서 문제
- **원인**: `sort_index()`, `sort_values()` 호출
- **증상**: 새 캔들이 시간 순서대로 중간 삽입
- **해결**: 정렬 제거하여 API 원본 순서 유지

### 4. API 데이터 특성 이해
- **ka10080 API**: 항상 ~900개 캔들 반환 (고정)
- **역순 정렬**: 최신→과거 순서
- **연속 조회**: `cont_yn`, `next_key`로 페이징

### 5. 함수 시그니처 진화
- **초기**: `start_time_str` 파라미터 포함
- **최종**: `start_time_str` 제거, `last_timestamp_str` 선택적 파라미터
- **이유**: 스마트 로직으로 DB 자동 조회

## 📊 성능 특성

### API 호출
- **주기**: 매 1분 (학습용, 운영 시 5분 권장)
- **응답시간**: ~2-3초
- **데이터량**: ~900개 캔들 (15일치 5분봉)

### DB 성능
- **중복 체크**: 배치 쿼리로 최적화
- **삽입**: 1개 캔들만 삽입 (빠름)
- **인덱스**: `(stock_code, timeframe, timestamp)` 복합 인덱스

## 🔧 운영 고려사항

### 확장 방안
1. **다중 종목**: 종목 리스트로 확장
2. **다중 시간프레임**: 1분, 5분, 30분 동시 수집
3. **실시간 모드**: WebSocket 연계
4. **실제 운영 모드**: `data_collector.py` 개발 시 참조

### 모니터링
1. **Airflow UI**: Task 성공/실패 모니터링
2. **DB 모니터링**: 신규 캔들 추가 확인 (DBeaver timestamp DESC 정렬)
3. **로그 분석**: 타임스탬프 처리 과정 추적

### 주의사항
1. **API 제한**: 키움 API 호출 제한 준수
2. **타임존**: KST 기준 철저히 유지
3. **거래시간**: 한국 주식시장 거래시간 고려

## 🎯 다음 단계

### TradeSmartAI 프로젝트 연계
1. **검증된 아키텍처**: 본 시스템에서 검증된 패턴을 `data_collector.py`에 적용
2. **스마트 로직 이식**: 타임존 처리, 거래시간 자동 감지 로직 활용
3. **성능 최적화**: 배치 처리, 중복 방지 로직 확장

### Airflow 학습 목표
1. **스케줄링 마스터**: 다양한 cron 표현식 테스트
2. **센서 활용**: FileSensor, TimeSensor 등 학습
3. **브랜칭**: BranchPythonOperator로 조건부 실행
4. **서브 DAG**: 복잡한 워크플로우 구성

### 시스템 고도화
1. **알림 시스템**: Slack, 이메일 연동
2. **대시보드**: Grafana, Superset 연동
3. **백업 전략**: 데이터 백업 자동화
4. **장애 복구**: 자동 재시작 메커니즘

---

**작성일**: 2025-06-01  
**작성자**: AI Trading System  
**버전**: 2.0 (통합 완료)  
**상태**: Production Ready 