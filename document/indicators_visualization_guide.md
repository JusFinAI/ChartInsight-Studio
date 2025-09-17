# 지표 계산 및 시각화 안내서 (pandas-ta-classic + Plotly/Plotly.js)

이 문서는 `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db`에서 구현한 지표 계산 로직(`indicators.py`)을 메인 프로젝트의 백엔드와 프론트엔드(Plotly.js)로 안전하고 재현 가능하게 이식하는 방법을 단계별로 정리합니다. 초보 개발자도 따라할 수 있도록 각 단계별 예제와 트러블슈팅을 제공합니다.

- **대상 파일**: `backend/_temp_integration/chart_pattern_analyzer_kiwoom_db/indicators.py`
- **목표**: `indicators.py`의 계산 로직을 그대로 재사용하여, 서버(백엔드)에서 지표를 계산하고 프론트엔드(Plotly.js)로 전달해 시각화한다.

---

1) 개요: 디자인 원칙
- 지표 계산(Algorithm)은 백엔드(서버)에서 실행한다. 이유: 파라미터 변경, 재현성, 캐싱, 성능(데이터 필터링) 측면에서 장점이 큼.
- 시각화는 프론트엔드(Plotly.js)에서 담당하되, 서버는 '시리즈 데이터(타임스탬프 인덱스 + 값)'를 JSON으로 반환한다.
- 서버는 계산 `spec`(예: SMA: [20,50], BBANDS: [{length:20, std:2}])와 함께 `meta`(params_hash, 라이브러리 버전 등)를 반환해 재현성을 보장한다.

2) `indicators.py` 재사용 방법 (백엔드)
- 현재 구현된 `compute_indicators(df, spec)` 함수는 다음을 반환합니다:

```python
{
  'meta': {'params_hash': '...', 'spec': {...}},
  'series': {
     'SMA_20': pd.Series(...),
     'RSI_14': pd.Series(...),
     'BBU_20_2.0': pd.Series(...),
     ...
  }
}
```

- 프론트엔드에 보낼 JSON 직렬화 방법 (예시):

```python
res = compute_indicators(df, spec=spec)
out = {'meta': res['meta'], 'series': {}}
for k, s in res['series'].items():
    out['series'][k] = {'index': [d.isoformat() for d in s.index], 'values': s.fillna(None).tolist()}
# 반환: JSON 응답
```

- 주의: datetime 인덱스는 ISO 포맷(예: `2023-09-01T00:00:00+09:00`)으로 보내세요. Plotly.js는 ISO 문자열을 x축으로 잘 처리합니다.

3) `spec` 예시 (요청 인자)
- 간단한 spec 예
```json
{
  "sma": [20, 50],
  "ema": [20],
  "rsi": [14],
  "macd": [{"fast":12, "slow":26, "signal":9}],
  "bbands": [{"length":20, "std":2}],
  "atr": [14],
  "obv": true
}
```

4) Plotly (Python) -> Plotly.js 매핑 가이드
- 기본 원칙: 서버는 시간축(x)과 값(y)을 전달. 프론트엔드는 각 series 키에 맞게 trace를 만든다.
- 추천 매핑
  - Candlestick: `go.Candlestick` (서버는 OHLC를 전달)
  - Volume: `go.Bar` (row 2)
  - SMA/EMA: `Scatter` (lines, overlay on price)
  - BB Upper/Mid/Lower: `Scatter` + `fill='tonexty'`로 밴드 채움
  - MACD: `Scatter` (MACD, Signal) + `Bar` (Histogram)
  - RSI: `Scatter` + 70/30 dashed lines
  - ATR, OBV: `Scatter` (별도 row 또는 volume row에 overlay)

- Plotly.js 예 (SMA/BB 추가 예):
```javascript
// server_res.series is a map {key: {index: [...], values: [...]}}
const traces = [];
traces.push({ // price candles handled separately
  x: server_res.price.index,
  open: server_res.price.open,
  high: server_res.price.high,
  low: server_res.price.low,
  close: server_res.price.close,
  type: 'candlestick',
  xaxis: 'x',
  yaxis: 'y'
});
// SMA
traces.push({ x: server_res['SMA_20'].index, y: server_res['SMA_20'].values, type: 'scatter', mode: 'lines', name: 'SMA20', line: {color:'orange', width:2}, xaxis:'x', yaxis:'y'});
// BB lower then fill
traces.push({ x: server_res['BBL_20_2.0'].index, y: server_res['BBL_20_2.0'].values, type:'scatter', mode:'lines', name:'BB Lower', line:{color:'purple', width:1}, xaxis:'x', yaxis:'y'});
traces.push({ x: server_res['BBU_20_2.0'].index, y: server_res['BBU_20_2.0'].values, type:'scatter', fill:'tonexty', fillcolor:'rgba(180,150,220,0.18)', mode:'lines', line:{color:'purple', width:1}, name:'BB Upper', xaxis:'x', yaxis:'y'});

Plotly.newPlot('chart', traces, layout);
```

5) 동적 row 할당 설계 (프론트엔드/백엔드 협업)
- 서버는 `series` 키만 반환하고, 프론트엔드는 표시 우선순위(사용자가 체크한 순서)를 기반으로 행(row)을 동적으로 생성합니다.
- 권장 데이터 모델 (서버 응답):
```json
{
  "meta": {...},
  "series": {"SMA_20": {...}, "OBV": {...}},
  "render_order": ["SMA_20", "OBV"]  // optional: if server knows desired order
}
```
- 프론트엔드 동작
  1. 기본으로 `row1`은 가격, `row2`는 볼륨
  2. 사용자가 체크한 인디케이터 순서에 따라 추가 행 생성
  3. 각 행에는 삭제 버튼(X)를 노출하여 사용자가 해당 행을 제거하면 내부 체크박스 상태를 갱신

6) 트러블슈팅 (자주 발생하는 문제)
- 지표가 계산되었지만 보이지 않는 경우
  - `fig.add_trace`(또는 Plotly.newPlot의 traces)에 올바른 `x`/`y` 가 전달됐는지 확인
  - y축(row) 지정이 잘못되었는지 확인 (예: volume row로 추가되었는지)
  - 초기 NaN(rolling window) 값들은 정상으로, non-null count를 확인

- 라이브러리 함수가 없거나 시그니처가 다른 경우
  - `pandas-ta-classic`의 API가 버전에 따라 다를 수 있으니, 로컬 환경에서 `import pandas_ta_classic as pta; dir(pta)`로 확인
  - 예: `atr`는 `(high, low, close, length=...)` 시그니처를 가짐

- 디버거 사용 팁
  - compute 직후 브레이크포인트에서 `indicators_res['series'].keys()`와 각 Series의 `non-null` 개수를 확인
  - 브레이크포인트에서 `fig.data`를 확인해 어떤 trace가 추가되었는지 확인

7) Plotly.py 와 Plotly.js 차이 요약
- Plotly.py는 Python 객체(go.Scatter 등)를 사용하고 `plotly`가 내부적으로 JSON으로 변환합니다.
- Plotly.js는 브라우저에서 동작하며 JSON 형식의 traces/layout을 직접 필요로 합니다.
- 서버는 가능한 한 `series`를 JSON-serializable 형태로 반환(ISO datetime + numeric/null 값 배열)하면, 프론트엔드 변환 작업이 간단해짐.

8) 예제: 백엔드 엔드포인트 (FastAPI) 반환 예
```python
from fastapi import APIRouter
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.indicators import compute_indicators

router = APIRouter()

@router.post('/indicators')
async def indicators_endpoint(req: dict):
    df = load_df_somehow(req['ticker'], req['interval'])
    res = compute_indicators(df, spec=req.get('spec', {}))
    out = {'meta': res['meta'], 'series': {}}
    for k, s in res['series'].items():
        out['series'][k] = {'index': [d.isoformat() for d in s.index], 'values': [None if pd.isna(v) else float(v) for v in s.values]}
    return out
```

9) 마무리 요약(핵심 체크리스트)
- [ ] 서버 `compute_indicators` 사용해 시리즈 계산
- [ ] 시리즈를 ISO datetime + numbers 배열로 직렬화
- [ ] 프론트엔드에서 체크 순서로 동적 행 생성
- [ ] 각 행에 닫기(X) 버튼을 두어 사용자가 제거 가능
- [ ] 시각화는 Plotly.js trace 매핑 규칙에 따름

---

문서 생성 완료했습니다. 추가로 원하시면 이 문서에 예시 요청/응답 샘플(HTTP 요청/응답 페이로드), Plotly.js 구체적 레이아웃(JSON 레이아웃) 템플릿, 또는 `indicators.py`의 함수별 동작(입력값과 출력 시리즈 예시)을 더 상세히 추가해 드리겠습니다.
