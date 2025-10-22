# 제안: 차트 데이터 수집 로직 통합 개선 방안

**문서 버전: 1.2**

**작성자: Gemini**

---

### 1. 문제 요약 (Problem Summary)

현재 데이터 파이프라인의 일일 증분 업데이트 Task(`_fetch_latest_low_frequency_candles`)가 **업종 및 지수**의 일봉/주봉/월봉 데이터를 갱신하지 못하고 있습니다. 이는 증분 수집을 담당하는 `collect_and_store_candles` 함수가 업종/지수 코드를 받았을 때, 존재하지 않거나 잘못된 API(개별 종목용 API)를 호출하기 때문입니다.

### 2. 근본 원인 (Root Cause)

`kiwoom_restapi_명세.md` 문서를 포함한 코드 분석 결과, 근본 원인은 세 가지로 압축됩니다.

1.  **API 서비스 계층의 기능 누락**: `src/kiwoom_api/services/chart.py`를 분석한 결과, 업종/지수의 **월봉** 조회 함수(`get_monthly_inds_chart`, API ID: `ka20008`)는 존재하지만, **일봉**(`ka20006`)과 **주봉**(`ka20007`)을 조회하는 `get_daily_inds_chart`, `get_weekly_inds_chart` 함수가 **아예 존재하지 않습니다.** 이것이 가장 직접적인 원인입니다.

2.  **API 호출 책임의 분리 실패**: `collect_and_store_candles` 함수(증분 갱신)는 어떤 API를 호출할지 스스로 결정하려 합니다. 하지만 필요한 `get_daily_inds_chart` 등의 함수가 없기 때문에, 대신 잘못된 `get_daily_stock_chart` 함수를 호출하여 에러가 발생합니다.

3.  **로직의 파편화 및 비일관성**: `dag_initial_loader`(초기 적재)는 업종 데이터에 대해 **월봉만** 적재를 시도하는 반면, `dag_daily_batch`(증분 갱신)는 **일/주/월봉 모두**를 갱신하려 시도합니다. 이처럼 두 핵심 DAG의 동작 방식이 달라 일관성이 없고 잠재적인 혼란을 야기합니다.

### 3. 해결 목표 (Resolution Goal)

버그 수정과 함께, 향후 확장과 유지보수가 용이한 **통합된 단일 구조**로 리팩토링하는 것을 목표로 합니다.

- **관심사의 분리 (Separation of Concerns)**: 데이터 수집기(`data_collector`)는 "무엇을, 언제"만 결정하고, API 서비스(`chart.py`)가 "어떻게" 가져올지를 완전히 책임지도록 합니다.
- **코드 중복 제거 (DRY Principle)**: 종목/업종을 구분하는 분기 로직이 단 한 곳(`chart.py`)에만 존재하도록 구조를 중앙화합니다.
- **동작의 일관성**: **초기 적재와 증분 갱신 모두**가 업종/지수의 **일/주/월봉을 동일한 로직으로 처리**하도록 통일합니다.

### 4. 제안하는 코드 구조 및 수정 방안

**핵심 아이디어: API 서비스 계층(`chart.py`)이 모든 차트 API 호출을 책임지도록 기능을 완성하고, 상위 계층(`data_collector`, DAGs)은 추상화된 단일 함수만 사용하도록 통일합니다.**

#### 4.1. API 서비스 계층 기능 구현 및 추상화 (`chart.py` 수정)

**1단계: 누락된 API 래퍼 함수 및 응답 키 추가**

`kiwoom_restapi_명세.md`에 따라, `chart.py`에 누락된 업종/지수용 일봉, 주봉 조회 함수와 응답 키를 추가합니다.

```python
# src/kiwoom_api/services/chart.py

# 1-1. _get_chart_data 함수 내의 RESPONSE_KEY_MAP 업데이트
RESPONSE_KEY_MAP = {
    'ka10081': 'stk_dt_pole_chart_qry',  # 종목 일봉
    'ka10082': 'stk_stk_pole_chart_qry', # 종목 주봉
    'ka10083': 'stk_mth_pole_chart_qry', # 종목 월봉
    'ka10080': 'stk_min_pole_chart_qry', # 종목 분봉
    'ka20006': 'inds_dt_pole_qry',       # [추가] 업종 일봉
    'ka20007': 'inds_stk_pole_qry',      # [추가] 업종 주봉
    'ka20008': 'inds_mth_pole_qry',      # 업종 월봉
}

# 1-2. 누락된 래퍼 함수 추가
def get_daily_inds_chart(inds_code, base_date=None, num_candles=252, auto_pagination=True, output_dir=None):
    """업종/지수 일봉 차트 데이터를 조회합니다. (API ID: ka20006)"""
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('daily', 'ka20006', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)

def get_weekly_inds_chart(inds_code, base_date=None, num_candles=52, auto_pagination=True, output_dir=None):
    """업종/지수 주봉 차트 데이터를 조회합니다. (API ID: ka20007)"""
    params = {'inds_cd': inds_code, 'base_dt': base_date or datetime.datetime.now().strftime('%Y%m%d')}
    return _get_chart_data('weekly', 'ka20007', params, auto_pagination, num_candles=num_candles, base_date=params['base_dt'], output_dir=output_dir)

# ... 기존 get_monthly_inds_chart 등 함수들 ...
```

**2단계: 통합 데이터 조회 함수 `get_chart` 신설**

이제 모든 저수준 함수가 준비되었으므로, 이들을 호출하는 단일 진입점(Single-Entry Point) 함수를 만듭니다.

```python
# src/kiwoom_api/services/chart.py

def get_chart(code: str, timeframe: str, **kwargs):
    """코드를 분석하여 적절한 차트 API를 자동으로 호출하는 통합 함수"""
    is_index_or_sector = len(code) == 3

    if timeframe == 'd':
        return get_daily_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_daily_stock_chart(stock_code=code, **kwargs)
    elif timeframe == 'w':
        return get_weekly_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_weekly_stock_chart(stock_code=code, **kwargs)
    elif timeframe == 'mon':
        return get_monthly_inds_chart(inds_code=code, **kwargs) if is_index_or_sector else get_monthly_stock_chart(stock_code=code, **kwargs)
    else:
        raise ValueError(f"지원하지 않는 타임프레임: {timeframe}")
```

#### 4.2. 데이터 수집 로직 단순화 (`data_collector.py` 수정)

`data_collector.py`의 두 함수(`load_initial_history`, `collect_and_store_candles`)가 새로 만든 통합 함수 `get_chart`만 호출하도록 변경합니다.

```python
# DataPipeline/src/data_collector.py

# 1. 임포트 구문 변경
from src.kiwoom_api.services.chart import get_chart, get_minute_chart # 분봉은 별도 유지

# 2. load_initial_history 함수 수정
def load_initial_history(stock_code: str, timeframe: str, **kwargs):
    # ...
    if execution_mode == 'LIVE':
        if timeframe in ['d', 'w', 'mon']:
            chart_data_obj = get_chart(code=stock_code, timeframe=timeframe, **kwargs)
        else: # 분봉 등 기타
            chart_data_obj = get_minute_chart(stock_code=stock_code, **kwargs)
    # ...

# 3. collect_and_store_candles 함수 수정
def collect_and_store_candles(stock_code: str, timeframe: str, **kwargs):
    # ...
    if execution_mode == 'LIVE':
        if timeframe in ['d', 'w', 'mon']:
            chart_data_obj = get_chart(code=stock_code, timeframe=timeframe, **kwargs)
        else: # 분봉 등 기타
            chart_data_obj = get_minute_chart(stock_code=stock_code, **kwargs)
    # ...
```

#### 4.3. DAG 동작 일관성 확보 (`dag_initial_loader.py` 수정)

`dag_initial_loader`가 업종/지수에 대해 월봉만 적재하는 비일관적인 동작을 수정하여, 다른 저빈도 타임프레임도 모두 적재하도록 변경합니다.

**의사코드 (dag_initial_loader.py의 `_run_initial_load_task` 내부):**

```python
# AS-IS (현재 상태)
# ...
logger.info("기준 데이터(지수, 업종)의 전체 과거 월봉 적재를 시작합니다.")
# ...
baseline_codes = index_codes + sector_codes
for code in baseline_codes:
    # timeframe이 'mon'으로 고정되어 있음
    load_initial_history(stock_code=code, timeframe='mon', period='10y', ...)

# TO-BE (변경 후)
# ...
logger.info("기준 데이터(지수, 업종)의 전체 과거 일/주/월봉 적재를 시작합니다.")
# ...
baseline_codes = index_codes + sector_codes
baseline_timeframes = ['d', 'w', 'mon'] # <-- 처리할 타임프레임 목록

for code in baseline_codes:
    for timeframe in baseline_timeframes: # <-- 타임프레임 루프 추가
        period = TIMEFRAME_PERIOD_MAP.get(timeframe, '5y') # 타임프레임별 기간 적용
        # 이제 모든 타임프레임에 대해 안전하게 호출 가능
        load_initial_history(stock_code=code, timeframe=timeframe, period=period, ...)
```

### 5. 기대 효과 (Expected Benefits)

1.  **버그 완벽 해결**: 업종/지수의 모든 저빈도 데이터(일/주/월봉)가 초기 적재와 증분 업데이트 모두에서 정상적으로 처리됩니다.
2.  **유지보수성 극대화**: 향후 API 변경 시 `chart.py`만 수정하면 모든 데이터 수집 로직에 일괄 적용됩니다.
3.  **완전한 일관성**: 초기 적재와 증분 갱신, 종목과 업종의 처리 방식이 모두 단일한 `get_chart` 함수로 통일되어 파이프라인 전체의 예측 가능성과 안정성이 크게 향상됩니다.

### 6. 다음 단계 (Next Steps)

1.  **누락된 API 래퍼 함수 구현**: `src/kiwoom_api/services/chart.py`에 `kiwoom_restapi_명세.md`를 참조하여 `get_daily_inds_chart`(`ka20006`), `get_weekly_inds_chart`(`ka20007`) 함수를 추가하고 `RESPONSE_KEY_MAP`을 업데이트합니다.
2.  **통합 함수 생성**: `chart.py`에 제안된 `get_chart` 통합 함수를 구현합니다.
3.  **데이터 수집기 리팩토링**: `DataPipeline/src/data_collector.py`의 `load_initial_history`와 `collect_and_store_candles` 함수가 새로운 `get_chart` 함수를 사용하도록 수정합니다.
4.  **초기 적재 로직 수정**: `DataPipeline/dags/dag_initial_loader.py`의 기준 데이터 적재 로직이 일/주/월봉을 모두 처리하도록 수정합니다.
5.  **통합 테스트**: 수정된 코드를 바탕으로 `dag_initial_loader`와 `dag_daily_batch`를 순차 실행하여, 업종 데이터의 초기 적재 및 증분 업데이트가 모두 정상 동작하는지 확인합니다.