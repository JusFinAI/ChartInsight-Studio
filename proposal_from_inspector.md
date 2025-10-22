[1 tool called]

네, 이제 개발자 제안서를 확인했습니다. 더 체계적이고 전문적인 문서로 재구성하겠습니다. 문제 인식부터 구체적 코드 구현까지 단계적으로 설명하는 최종 제안서를 작성하겠습니다.

## 🎯 전문가 제안서: 데이터 수집 시스템 아키텍처 개선

### 1. 문제 인식 (Problem Recognition)

**현재 시스템의 근본적 결함 발견:**
- `dag_daily_batch`의 증분 수집과 `dag_initial_loader`의 초기 적재가 **업종 데이터 처리에 일관성 없음**
- 업종 코드(3자리)가 입력되면 **종목용 API를 잘못 호출**하는 치명적 오류
- RS 점수 계산에 필요한 **업종 주봉/일봉 데이터 전혀 수집 불가**

### 2. 문제 정의 (Problem Definition)

**핵심 문제점:**
```python
# collect_and_store_candles 함수의 잘못된 구현 (현재)
elif timeframe == 'mon':
    chart_data_obj = get_monthly_stock_chart(  # ❌ 업종 코드여도 무조건 종목용 API
        stock_code=stock_code,  # '001'(KOSPI), '101'(KOSDAQ) 등이 입력되어도
        base_date=None,
        num_candles=5,
        auto_pagination=False
    )
```

**API 지원 현황 (Kiwoom REST API 명세 확인):**
| 데이터 타입 | API ID | Response Key | 지원 상태 |
|------------|--------|--------------|-----------|
| 업종 일봉 | `ka20006` | `inds_dt_pole_qry` | ✅ 지원됨 |
| 업종 주봉 | `ka20007` | `inds_stk_pole_qry` | ✅ 지원됨 |
| 업종 월봉 | `ka20008` | `inds_mth_pole_qry` | ✅ 지원됨 |
| 종목 일봉 | `ka10081` | `stk_dt_pole_chart_qry` | ✅ 지원됨 |
| 종목 주봉 | `ka10082` | `stk_stk_pole_chart_qry` | ✅ 지원됨 |
| 종목 월봉 | `ka10083` | `stk_mth_pole_chart_qry` | ✅ 지원됨 |

### 3. 영향 분석 (Impact Analysis)

**즉각적 영향:**
- ✅ **RS 점수 계산 실패**: Sector RS에 필요한 업종 주봉 데이터 부재
- ✅ **데이터 정합성 파괴**: 종목 vs 업종 데이터 비대칭 구조
- ✅ **시스템 신뢰성 저하**: 무의미한 분석 결과 생성

**장기적 영향:**
- 🔄 **유지보수 어려움**: 코드 중복 및 관심사 혼합
- 📉 **확장성 제한**: 새로운 차트 타입 추가 시 광범위한 수정 필요
- ⚠️ **에러 추적困難**: 분산된 로직으로 디버깅 어려움

### 4. 구현 목표 (Implementation Goals)

**1. 관심사 분리 (Separation of Concerns)**
- 데이터 수집기: "무엇을, 언제" 수집할지 결정
- API 서비스: "어떻게" 수집할지 전담

**2. 코드 중복 제거 (DRY Principle)**
- 종목/업종 분기 로직 단일화
- 중복된 API 호출 코드 제거

**3. 일관성 확보 (Consistency)**
- 초기 적재 + 증분 수집 동일한 방식 동작
- 예측 가능한 에러 처리 메커니즘

### 5. 구체적 코드 구현 (Concrete Code Implementation)

#### 5.1. 코드 타입 판별 헬퍼 함수
```python
# DataPipeline/src/utils/code_type_detector.py
from typing import Optional
from sqlalchemy.orm import Session

def is_sector_or_index_code(code: str, db: Optional[Session] = None) -> bool:
    """
    코드가 업종/지수 코드인지 판별 (3자리 숫자 + DB 검증)
    """
    # 기본 검증: 3자리 숫자 코드
    if not isinstance(code, str) or len(code) != 3 or not code.isdigit():
        return False
    
    # DB 검증 (선택적): Sector 테이블에 존재하는지 확인
    if db is not None:
        try:
            from src.database import Sector
            return db.query(Sector).filter(Sector.sector_code == code).first() is not None
        except Exception:
            # DB 조회 실패 시 기본적으로 True 반환 (3자리 숫자이므로)
            return True
    
    return True
```

#### 5.2. 통합 API 라우팅 함수
```python
# DataPipeline/src/kiwoom_api/services/chart.py
def get_chart(code: str, timeframe: str, **kwargs):
    """
    통합 차트 데이터 조회 함수 - 코드 타입에 따라 적절한 API 자동 선택
    """
    from src.utils.code_type_detector import is_sector_or_index_code
    
    is_sector = is_sector_or_index_code(code)
    
    # 타임프레임별 API 라우팅
    if timeframe == 'd':
        if is_sector:
            return get_daily_inds_chart(inds_code=code, **kwargs)  # ka20006
        else:
            return get_daily_stock_chart(stock_code=code, **kwargs)  # ka10081
            
    elif timeframe == 'w':
        if is_sector:
            return get_weekly_inds_chart(inds_code=code, **kwargs)  # ka20007
        else:
            return get_weekly_stock_chart(stock_code=code, **kwargs)  # ka10082
            
    elif timeframe == 'mon':
        if is_sector:
            return get_monthly_inds_chart(inds_code=code, **kwargs)  # ka20008
        else:
            return get_monthly_stock_chart(stock_code=code, **kwargs)  # ka10083
            
    elif timeframe in ['5m', '30m', '1h']:
        # 분봉은 종목용 API만 지원
        return get_minute_chart(stock_code=code, interval=timeframe.replace('m', ''), **kwargs)
        
    else:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
```

#### 5.3. 데이터 수집기 단순화
```python
# DataPipeline/src/data_collector.py
# 기존 복잡한 분기문 전체 제거
from src.kiwoom_api.services.chart import get_chart

def collect_and_store_candles(stock_code: str, timeframe: str, execution_mode: str, **kwargs):
    """증분 데이터 수집 - 통합 API 함수 사용"""
    if execution_mode == 'LIVE':
        # ✅ 단일 호출로 모든 경우 처리
        chart_data_obj = get_chart(
            code=stock_code,
            timeframe=timeframe,
            base_date=None,
            num_candles=_get_optimal_candle_count(timeframe),
            auto_pagination=False
        )
        # ... 기존 증분 처리 로직 유지

def load_initial_history(stock_code: str, timeframe: str, **kwargs):
    """초기 데이터 적재 - 통합 API 함수 사용"""
    if execution_mode == 'LIVE':
        # ✅ 단일 호출로 모든 경우 처리
        chart_data_obj = get_chart(
            code=stock_code,
            timeframe=timeframe,
            base_date=base_date,
            num_candles=num_candles,
            auto_pagination=True
        )
        # ... 기존 적재 처리 로직 유지
```

#### 5.4. 초기 적재기 확장
```python
# DataPipeline/dags/dag_initial_loader.py
# 기준 데이터(지수+업종)에 일봉/주봉/월봉 모두 적재
for code in baseline_codes:
    for timeframe in ['d', 'w', 'mon']:  # 모든 타임프레임 처리
        try:
            load_initial_history(
                stock_code=code,
                timeframe=timeframe,
                period=TIMEFRAME_PERIOD_MAP.get(timeframe, '10y'),
                execution_mode=execution_mode
            )
            time.sleep(0.3)  # API Rate Limiting
        except Exception as e:
            logger.error(f"기준 데이터 적재 실패: {code}-{timeframe}: {e}")
            continue
```

## 6. 테스트 계획 (Test Plan)

### 6.1 단위 테스트 (Unit Testing)

**테스트 대상:**
1. `is_sector_or_index_code` 함수 - 코드 타입 판별 로직
2. `get_chart` 함수 - API 라우팅 로직  
3. 개별 API 래퍼 함수 - 응답 형식 변환

**테스트 케이스 설계:**
```python
# test_code_type_detector.py
def test_is_sector_or_index_code():
    # 업종/지수 코드 (3자리 숫자)
    assert is_sector_or_index_code("001") == True  # KOSPI
    assert is_sector_or_index_code("101") == True  # KOSDAQ
    assert is_sector_or_index_code("G25") == True  # 반도체 업종
    
    # 일반 종목 코드 (6자리)
    assert is_sector_or_index_code("005930") == False  # 삼성전자
    assert is_sector_or_index_code("000660") == False  # SK하이닉스
    
    # 잘못된 형식
    assert is_sector_or_index_code("ABC") == False  # 영문
    assert is_sector_or_index_code("1234") == False  # 4자리
    assert is_sector_or_index_code("12") == False    # 2자리
```

```python
# test_chart_routing.py  
def test_get_chart_routing():
    # 업종 코드 → 업종 API 호출
    assert get_chart("001", "d").api_id == "ka20006"  # KOSPI 일봉
    assert get_chart("101", "w").api_id == "ka20007"  # KOSDAQ 주봉
    assert get_chart("G25", "mon").api_id == "ka20008"  # 반도체 월봉
    
    # 종목 코드 → 종목 API 호출
    assert get_chart("005930", "d").api_id == "ka10081"  # 삼성전자 일봉
    assert get_chart("000660", "w").api_id == "ka10082"  # SK하이닉스 주봉
    assert get_chart("035720", "mon").api_id == "ka10083"  # 카카오 월봉
    
    # 분봉은 종목용 API만 지원
    assert get_chart("001", "5m").api_id == "ka10080"  # KOSPI 5분봉
    assert get_chart("005930", "30m").api_id == "ka10080"  # 삼성전자 30분봉
```

### 6.2 통합 테스트 (Integration Testing)

**테스트 시나리오 1: 업종 데이터 수집 검증**
```python
# test_sector_data_collection.py
def test_sector_incremental_update():
    """업종 증분 수집 테스트"""
    # 1. 테스트 업종 코드 설정
    test_sector_codes = ["001", "101", "G25"]  # KOSPI, KOSDAQ, 반도체
    
    # 2. collect_and_store_candles 실행
    for sector_code in test_sector_codes:
        for timeframe in ["d", "w", "mon"]:
            success = collect_and_store_candles(
                stock_code=sector_code,
                timeframe=timeframe,
                execution_mode="LIVE"
            )
            assert success == True, f"{sector_code} {timeframe} 수집 실패"
    
    # 3. DB에서 데이터 존재 확인
    db = SessionLocal()
    try:
        for sector_code in test_sector_codes:
            for timeframe in ["D", "W", "MON"]:  # DB 형식
                candles = db.query(Candle).filter(
                    Candle.stock_code == sector_code,
                    Candle.timeframe == timeframe
                ).count()
                assert candles > 0, f"{sector_code} {timeframe} 데이터 없음"
    finally:
        db.close()
```

**테스트 시나리오 2: 초기 적재 검증**
```python
# test_initial_loader.py  
def test_baseline_data_loading():
    """기준 데이터 초기 적재 테스트"""
    # 1. 기준 데이터 코드 수집
    index_codes = ["001", "101"]
    sector_codes = ["G25", "G35", "G50"]  # 테스트용 업종 코드
    
    # 2. 초기 적재 실행
    for code in index_codes + sector_codes:
        for timeframe in ["d", "w", "mon"]:
            success = load_initial_history(
                stock_code=code,
                timeframe=timeframe,
                period="1y",  # 테스트용 짧은 기간
                execution_mode="LIVE"
            )
            assert success == True, f"{code} {timeframe} 초기 적재 실패"
    
    # 3. 데이터 정합성 검증
    verify_baseline_data_completeness()
```

### 6.3 시스템 테스트 (System Testing)

**전체 DAG 실행 검증:**
```bash
# 테스트 실행 명령어
# 1. 업종 데이터 초기 적재 테스트
python -m pytest tests/test_initial_loader.py -v

# 2. 증분 수집 테스트  
python -m pytest tests/test_sector_data_collection.py -v

# 3. 전체 DAG 통합 테스트
python -m pytest tests/integration/test_dag_integration.py -v
```

**성능 및 부하 테스트:**
```python
# test_performance.py
def test_api_rate_limiting():
    """API Rate Limiting 동작 검증"""
    start_time = time.time()
    
    # 여러 종목/업종 혼합 요청
    test_codes = ["001", "101", "005930", "000660", "G25", "G35"]
    for code in test_codes:
        for timeframe in ["d", "w", "mon"]:
            get_chart(code, timeframe, num_candles=10)
    
    end_time = time.time()
    duration = end_time - start_time
    
    # 최소 0.2초 간격 유지 확인 (API 제한 준수)
    assert duration >= len(test_codes) * 3 * 0.2, "Rate Limiting 미준수"
```

### 6.4 모니터링 및 로깅 테스트

**로깅 포맷 검증:**
```python
# test_logging.py
def test_diagnostic_logging():
    """진단 로깅 형식 검증"""
    # API 호출 로그 형식
    expected_log_patterns = [
        r"BRANCH=SECTOR code=\d{3} timeframe=\w+ action=CALL_API",
        r"BRANCH=STOCK code=\d{6} timeframe=\w+ action=CALL_API",
        r"API_RESPONSE code=\w+ timeframe=\w+ status=(SUCCESS|FAILED)"
    ]
    
    # 로그 메시지 형식 검증
    for pattern in expected_log_patterns:
        assert re.search(pattern, log_output), f"로그 패턴 불일치: {pattern}"
```

### 6.5 회귀 테스트 (Regression Testing)

**기존 기능 보존 검증:**
```python
# test_regression.py  
def test_existing_functionality():
    """기존 종목 데이터 수집 기능 회귀 테스트"""
    test_stock_codes = ["005930", "000660", "035720"]  # 삼성전자, SK하이닉스, 카카오
    
    for stock_code in test_stock_codes:
        for timeframe in ["d", "w", "mon", "5m", "30m", "1h"]:
            success = collect_and_store_candles(
                stock_code=stock_code,
                timeframe=timeframe,
                execution_mode="LIVE"
            )
            assert success == True, f"기존 기능 오류: {stock_code} {timeframe}"
```

### 6.6 테스트 자동화 계획

**CI/CD 파이프라인 구성:**
```yaml
# .github/workflows/test.yml
name: Data Pipeline Tests

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: testpassword
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v2미얀해 
    - name: Set up Python
      uses: actions/setup-python@v2
      with:
        python-version: '3.9'
    - name: Install dependencies
      run: |
        pip install -r DataPipeline/requirements.txt
        pip
- `