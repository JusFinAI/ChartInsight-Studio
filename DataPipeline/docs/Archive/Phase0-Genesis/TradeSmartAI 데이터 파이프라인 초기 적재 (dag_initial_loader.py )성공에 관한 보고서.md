# TradeSmartAI 데이터 파이프라인 초기 적재 (dag_initial_loader.py )성공에 관한 보고서

## 📋 프로젝트 개요
- **프로젝트명**: TradeSmartAI 주식 데이터 수집 파이프라인
- **목표**: 30개 종목 × 5개 타임프레임 데이터 자동 수집 시스템 구축
- **환경**: WSL2 Ubuntu, Docker Compose, Apache Airflow, PostgreSQL
- **기간**: 2025년 7월 11일 완료

## 🎯 최종 성과
- ✅ **150개 작업 100% 성공** (30개 종목 × 5개 타임프레임)
- ✅ **9,450개 캔들 데이터 완벽 저장** (각 종목당 315개 × 30개 종목)
- ✅ **타임존 처리 완벽 해결** (KST ↔ UTC 변환)
- ✅ **멱등성 보장** (중복 데이터 없음)
- ✅ **사용자 경험 개선** (Airflow UI 한국 시간 표시)

## 🔧 주요 기술 문제 해결 과정

### 1. ImportError 해결
**문제**: `stock_info_load_task` 실패
```
ImportError: cannot import name 'load_stock_data_from_json' from 'src.stock_info_collector'
```

**원인**: 함수명 불일치
- 실제 함수: `load_stock_data_from_json_files`
- 호출 시도: `load_stock_data_from_json`

**해결**: `dags/dag_initial_loader.py` 수정
```python
# 수정 전
from src.stock_info_collector import load_stock_data_from_json

# 수정 후
from src.stock_info_collector import load_stock_data_from_json_files
```

### 2. 중복 데이터 오류 (핵심 문제)
**문제**: 150개 작업 모두 실패
```
UniqueViolation: duplicate key value violates unique constraint "candles_pkey"
```

**근본 원인**: 타임존 불일치로 인한 멱등성 로직 실패
- DB 조회 타임스탬프: UTC 시간대
- DataFrame 타임스탬프: KST 시간대 (timezone-naive)
- 같은 데이터를 다른 데이터로 인식하여 중복 삽입 시도

**해결 과정**:

#### 2-1. 타임존 비교 로직 수정
```python
# src/data_collector.py _db_upsert_candles 함수
def _db_upsert_candles(stock_code: str, timeframe: str, df: pd.DataFrame) -> int:
    # ... existing code ...
    
    # 타임존 통일: KST를 UTC로 변환하여 비교
    for _, row in df.iterrows():
        candle_timestamp_kst = row.name
        
        # timezone-naive 타임스탬프 처리
        if candle_timestamp_kst.tzinfo is None:
            candle_timestamp_kst = candle_timestamp_kst.replace(tzinfo=ZoneInfo('Asia/Seoul'))
        
        # UTC로 변환
        candle_timestamp_utc = candle_timestamp_kst.astimezone(ZoneInfo('UTC'))
        
        # DB와 비교 (UTC 기준)
        if candle_timestamp_utc not in existing_timestamps_utc:
            # 신규 데이터 삽입
```

#### 2-2. 파일명 매핑 문제 해결
**문제**: 시뮬레이션 데이터 파일명 불일치
```python
# 수정 전
'1h': '60'  # 005930_60_full.parquet (존재하지 않음)

# 수정 후  
'1h': '60m'  # 005930_60m_full.parquet (실제 파일)
```

### 3. Pool 설정 문제
**문제**: `kiwoom_api_pool` 존재하지 않음
**해결**: Airflow Admin → Pools에서 `kiwoom_api_pool` 생성 (슬롯 2개)

### 4. 타임존 표시 문제 (사용자 경험)
**문제**: Airflow UI에서 모든 시간이 UTC로 표시
- 예: `manual__2025-07-11T17:45:10+00:00`
- 사용자 혼란: 실제 한국 시간 오후 5시 45분 → UTC 표시로 인해 새벽 시간으로 오해

**해결**: `docker-compose.yaml`에 타임존 설정 추가
```yaml
environment:
  # 타임존 설정: UI와 로그에서 한국 시간으로 표시
  AIRFLOW__CORE__DEFAULT_TIMEZONE: Asia/Seoul
  AIRFLOW__WEBSERVER__DEFAULT_UI_TIMEZONE: Asia/Seoul
```

## 🛠️ 핵심 기술 원칙 확립

### 1. 타임존 처리 원칙
- **저장**: 모든 데이터는 UTC로 DB에 저장
- **사용**: 사용자에게 표시할 때는 Asia/Seoul로 변환
- **비교**: 멱등성 검사 시 동일한 타임존(UTC)으로 통일하여 비교

### 2. 멱등성 보장 로직
```python
# 핵심 로직: 타임존 통일 후 중복 검사
if candle_timestamp_kst.tzinfo is None:
    candle_timestamp_kst = candle_timestamp_kst.replace(tzinfo=ZoneInfo('Asia/Seoul'))

candle_timestamp_utc = candle_timestamp_kst.astimezone(ZoneInfo('UTC'))

if candle_timestamp_utc not in existing_timestamps_utc:
    # 신규 데이터만 삽입
```

### 3. 환경 변수 관리 원칙
- **엔트리포인트**: 실행 스크립트에서 `load_dotenv()` 호출
- **라이브러리**: 이미 설정된 환경 변수만 사용
- **kiwoom_api**: 내부 Config 클래스가 자동 처리

## 🔍 디버깅 도구 및 방법

### 1. Docker 로그 확인
```bash
# 특정 DAG 실행 로그 확인
docker exec -it datapipeline-airflow-webserver-1 cat "/opt/airflow/logs/dag_id=dag_initial_loader/run_id=manual__2025-07-11T17:45:10+00:00/task_id=initial_load_task/attempt=1.log"

# PostgreSQL 로그 확인
docker logs datapipeline-postgres-tradesmart-1 --tail 20
```

### 2. 데이터베이스 검증
```bash
# DB 접속 (호스트 명시 필요)
docker exec -it datapipeline-postgres-tradesmart-1 psql -U tradesmart_db -d tradesmart_db -h localhost

# 데이터 검증 쿼리
SELECT COUNT(*) as total_candles FROM candles;
SELECT stock_code, COUNT(*) as count FROM candles GROUP BY stock_code ORDER BY count DESC;
SELECT timeframe, COUNT(*) as count FROM candles GROUP BY timeframe ORDER BY count DESC;
```

### 3. 컨테이너 상태 확인
```bash
# 실행 중인 컨테이너 확인
docker ps

# 환경 변수 확인
docker exec -it datapipeline-postgres-tradesmart-1 env | grep POSTGRES
```

## 📊 최종 데이터 검증 결과

### 전체 통계
- **총 캔들 데이터**: 9,450개
- **종목 수**: 30개 (각각 315개씩)
- **타임프레임**: 5개 (각각 1,890개씩)

### 종목별 데이터 분포
```
모든 종목: 315개 (5개 타임프레임 × 63개 캔들)
예상 계산: 30 × 315 = 9,450개 ✅
```

### 타임프레임별 데이터 분포
```
M5 (5분봉): 1,890개 (30개 종목 × 63개 캔들)
M30 (30분봉): 1,890개
H1 (1시간봉): 1,890개  
D (일봉): 1,890개
W (주봉): 1,890개
총합: 5 × 1,890 = 9,450개 ✅
```

### 데이터 품질 확인
- **타임스탬프**: UTC 시간대로 정확히 저장
- **가격 데이터**: 소수점 4자리까지 정확히 저장
- **가격 범위**: 24,850원 ~ 1,470,000원 (정상 범위)

## 🎓 핵심 교훈 및 베스트 프랙티스

### 1. 타임존 처리의 중요성
- **절대 규칙**: 타임존이 다른 데이터를 비교할 때는 반드시 통일 후 비교
- **디버깅 팁**: `tzinfo is None` 체크로 timezone-naive 데이터 처리
- **사용자 경험**: 내부는 UTC, 표시는 로컬 타임존

### 2. 멱등성 구현 시 주의사항
- **데이터 타입 일치**: 비교 대상의 타입과 포맷 통일 필수
- **타임스탬프 비교**: 동일한 타임존으로 변환 후 비교
- **테스트 방법**: 동일한 작업을 여러 번 실행해도 결과가 같은지 확인

### 3. Docker 환경에서의 DB 접속
- **권한 문제**: 사용자명과 패스워드 정확히 확인
- **네트워크 설정**: 호스트 명시 (`-h localhost`) 필요한 경우 있음
- **환경 변수**: 컨테이너 내부 환경 변수로 접속 정보 확인

### 4. Airflow 개발 팁
- **Pool 설정**: API 호출 제한을 위한 Pool 미리 생성
- **파라미터 전달**: `op_kwargs`로 동적 파라미터 전달
- **로그 확인**: 컨테이너 내부 로그 파일 직접 확인

## 🚀 향후 개선 방향

### 1. 모니터링 강화
- **알림 시스템**: 실패 시 Slack/이메일 알림
- **대시보드**: 데이터 수집 현황 실시간 모니터링
- **성능 메트릭**: API 호출 시간, DB 저장 시간 추적

### 2. 확장성 개선
- **동적 종목 관리**: DB에서 타겟 종목 목록 관리
- **설정 외부화**: 타임프레임, 수집 주기 등 설정 파일로 관리
- **에러 복구**: 실패한 작업 자동 재시도 로직

### 3. 데이터 품질 관리
- **데이터 검증**: 수집된 데이터의 이상치 검사
- **백업 전략**: 정기적인 DB 백업 및 복구 테스트
- **히스토리 관리**: 데이터 수정 이력 추적

## 🏆 결론

이번 프로젝트를 통해 **타임존 처리**라는 복잡한 문제를 완벽히 해결하고, **멱등성**을 보장하는 안정적인 데이터 파이프라인을 구축했습니다. 

특히 **"저장은 UTC, 사용은 로컬"** 원칙을 확립하고, 사용자 경험까지 고려한 완성도 높은 시스템을 만들어냈습니다.

**150개 작업 100% 성공**이라는 결과는 단순한 숫자가 아니라, 모든 기술적 도전을 극복한 증거입니다! 🎉

---

*이 보고서는 향후 유사한 프로젝트나 확장 개발 시 귀중한 참고 자료가 될 것입니다.*

