---
# proposal_from_developer.md

문제 인식
---------
- `dag_daily_batch`(증분)와 `dag_initial_loader`(초기 적재)가 업종(3자리 코드)을 처리하는 방식에 불일치가 있습니다. 제공된 Kiwoom REST API 명세(`DataPipeline/docs/kiwoom_restapi_명세.md`)에는 업종(인덱스)용 엔드포인트가 존재하므로 이를 일관되게 사용해야 합니다.

문제 정의
---------
- 핵심: 증분 함수(`collect_and_store_candles`)는 업종/종목 판별 없이 종목용 API만 호출합니다. 반면 `load_initial_history`는 `mon`에서 3자리 코드를 인덱스용 API(`ka20008`)로 호출합니다. 결과적으로 업종의 `mon`은 초기 적재로 채워지나, `d`(일)/`w`(주)는 누락 또는 잘못 호출로 실패할 위험이 있습니다.

참고: Kiwoom REST API 명세(중요)
- 업종 월봉: `ka20008` (inds monthly)
- 업종 주봉: `ka20007` (inds weekly)
- 업종 일봉: `ka20006` (inds daily)
- 종목 월봉: `ka10083` 등
(상세는 `DataPipeline/docs/kiwoom_restapi_명세.md` 참조)

영향
----
- RS/섹터 분석 정확도 저하
- Airflow 태스크 실패 및 불필요한 재시도 증가

구현 목표
---------
1. 업종/지수와 개별 종목을 정확히 판별하여 올바른 API 래퍼를 호출하도록 수정
2. 월봉(mon)은 기본 보장, 일/주(d/w)는 API 지원 여부에 따라 명확한 폴백 적용
3. 분기 로직과 로그를 명확히 하여 추적성을 확보

구체적 구현 방안 (코드 중심)
---------------------------
1) 판별 헬퍼 (`is_index_code`)
```python
# 파일: DataPipeline/src/data_collector.py
from typing import Optional
from sqlalchemy.orm import Session

def is_index_code(code: str, db: Optional[Session] = None) -> bool:
    # 기본: 3자리 숫자 코드
    if not isinstance(code, str):
        return False
    if len(code) == 3 and code.isdigit():
        # 선택적 확인: DB의 Sector 테이블에 존재하면 확증
        if db is not None:
            try:
                from src.database import Sector
                return db.query(Sector).filter(Sector.sector_code == code).first() is not None
            except Exception:
                return True
        return True
    return False
```

2) `collect_and_store_candles` 분기(핵심 변경)
- 변경 포인트: `timeframe`이 `mon`/`d`/`w`일 때 `is_index_code` 판별 후 적절한 래퍼 호출

```python
# 변경 요약 (의사 코드)
if is_index_code(stock_code, db):
    # 업종/인덱스 처리
    if timeframe == 'mon':
        chart_data_obj = get_monthly_inds_chart(inds_code=stock_code, base_date=None, num_candles=...)  # ka20008
    elif timeframe == 'w':
        # ka20007이 사용 가능하면 호출, 아니면 폴백
        if hasattr(chart_module, 'get_weekly_inds_chart'):
            chart_data_obj = get_weekly_inds_chart(inds_code=stock_code, base_date=None, num_candles=...)
        else:
            logger.warning(f"SECTOR DW API missing for {stock_code}. Skipping or fallback.")
            # fallback: skip or schedule load_initial_history for d/w
    elif timeframe == 'd':
        if hasattr(chart_module, 'get_daily_inds_chart'):
            chart_data_obj = get_daily_inds_chart(inds_code=stock_code, base_date=None, num_candles=...)
        else:
            logger.warning(f"SECTOR D API missing for {stock_code}. Skipping or fallback.")
else:
    # 종목 기존 경로 유지 (get_daily_stock_chart, get_weekly_stock_chart, get_monthly_stock_chart)
```

3) `dag_initial_loader` 옵션 추가 (선택적)
- 목적: 운영자가 섹터 `d/w` 초기 적재를 명시적으로 실행할 수 있게 함

```python
# 파일: DataPipeline/dags/dag_initial_loader.py
# params에 추가
"include_sector_dw": Param(type='boolean', default=False, description='업종에 대해 일/주 초기 적재 수행')

# baseline 처리 부분
for code in baseline_codes:
    load_initial_history(stock_code=code, timeframe='mon', period='10y', execution_mode=execution_mode)
    if config.get('include_sector_dw'):
        load_initial_history(stock_code=code, timeframe='d', period='10y', execution_mode=execution_mode)
        load_initial_history(stock_code=code, timeframe='w', period='10y', execution_mode=execution_mode)
```

4) 차트 래퍼 점검/추가
- 파일: `DataPipeline/src/kiwoom_api/services/chart.py`
- 작업: `get_daily_inds_chart`, `get_weekly_inds_chart`가 없으면 `ka20006`, `ka20007` 호출용 래퍼를 추가

의사 코드 예:
```python
def get_daily_inds_chart(inds_code, base_date=None, num_candles=..., auto_pagination=True):
    params = {'inds_cd': inds_code, 'base_dt': base_date}
    return _get_chart_data('daily_inds', 'ka20006', params, auto_pagination, num_candles=num_candles)
```

5) 로그/모니터링
- 분기 로그: `BRANCH=SECTOR code=... timeframe=... action=CALL_IND|SKIP|FALLBACK`
- WARN 로그 발생 시 운영자가 빠르게 확인 가능하도록 메시지에 원인 표기

테스트
-----
- 단위: SIMULATION 모드에서 `collect_and_store_candles` 분기 동작(섹터 mon/d/w 및 종목 케이스)을 검증
- 통합: `dag_simulation_tester`로 baseline(mon) 및 `include_sector_dw` 시나리오 검증

결론
-----
- Kiwoom 명세에 인덱스용 일/주/월 엔드포인트가 존재하므로(`ka20006`,`ka20007`,`ka20008`) 이를 이용해 `collect_and_store_candles`와 `dag_initial_loader`를 일관되게 개선하는 것이 합리적입니다. 우선 `is_index_code` 도입과 `mon` 분기 적용을 즉시 반영한 뒤, d/w 래퍼 존재 여부 확인 후 순차적으로 확장하세요.
