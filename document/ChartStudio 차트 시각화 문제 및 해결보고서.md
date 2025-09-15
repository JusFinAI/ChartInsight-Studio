# ChartStudio 차트 시각화 문제 및 해결보고서

이 문서는 `frontend/src/components/ui/Chart.tsx`의 호출/데이터 흐름을 상세히 정리하고, 분석 엔진(`engine_impl.py`)에서 생성되는 `analysis_results` JSON과의 연계를 포함해 이번 시각화 문제의 원인과 해결 과정을 단계별로 설명합니다. 초보 개발자도 이해할 수 있도록 가능한 한 친절하고 자세히 작성했습니다.

---

## 1) 호출 순서 및 데이터 흐름 (상세)

아래는 페이지 로드 시점부터 차트가 렌더될 때까지의 상세한 동작 순서와 각 단계에서 생성되는 데이터 형식(특히 시간 필드)의 설명입니다.

1) 페이지 진입 및 초기화
   - 사용자가 `frontend/src/app/trading-lab/trading-radar/page.tsx`에 진입하면 컴포넌트의 초기화(useEffect)가 실행됩니다.
   - 이 시점에서 `loadData()` 같은 초기화 루틴이 호출되어 백엔드의 통합 엔드포인트 `/api/v1/pattern-analysis/trading-radar-data`를 호출합니다.

2) 백엔드 처리(라우터 + 엔진)
   - `pattern_analysis.get_trading_radar_data`가 호출되면, DB에서 캔들(OHLC) 데이터를 읽어옵니다(예: `load_candles_from_db`).
   - 읽어온 캔들 데이터를 `engine_impl.run_full_analysis(df, ticker, period, interval)`에 전달합니다.
   - `run_full_analysis`는 내부적으로 다음을 수행합니다:
     - 피크/밸리 검출: `js_peaks`, `js_valleys` 등 극점 리스트 생성. 각 극점 객체는 `index`, `value`, `actual_date`, `detected_date`, `open/high/low/close` 같은 O H L C 정보를 가집니다.
     - 패턴 감지기(PatternDetector들) 동작: DT/DB/HS/IHS 감지기들이 활성화/완성되며, 완성된 패턴은 `completed_dt`, `completed_db`, `completed_hs`, `completed_ihs` 리스트로 취합됩니다.
     - 결과 구조화: `analysis_results` 딕셔너리를 만들어 `base_data`(원본 캔들), `peaks_valleys`, `trend_info`, `patterns`, `states` 등을 반환합니다.

   - 핵심: `patterns` 내 각 패턴 객체는 반드시 **패턴의 의미적 시작(start)** 과 **종료(end)** 를 나타내는 필드를 갖춰야 합니다. 권장 필드 형식은 다음과 같습니다:
     - `startTimeEpoch`: 시작 시각 (Unix epoch seconds, UTC)
     - `endTimeEpoch`: 종료 시각 (Unix epoch seconds, UTC)
     - `startTimeISO`: 시작 시각 ISO 문자열(예: "2024-04-22T00:00:00+09:00")
     - `endTimeISO`: 종료 시각 ISO 문자열
     - `meta`: 패턴 내부 구조(P1, V1, start_peak, start_valley, neckline 등)

   - 라우터는 `analysis_results`에서 `patterns`를 추출하고, 프론트가 기대하는 형태로 **정규화**하여 응답합니다(예: top-level `startTimeEpoch`이 비어있으면 `meta.startTimeEpoch`에서 값을 복사해서 채우는 등).

3) 프론트 수신 및 상태 저장
   - `fetchTradingRadarData()`는 통합 JSON 응답을 받아 `radarData.chart_data`는 `setChartData()`로, `radarData.js_points`는 `setJSPoints()`로, `radarData.patterns`는 `setPatterns()` 또는 `setRawAnalysisData()`로 저장합니다.
   - `page.tsx` 내부에서 UI 토글(HS/IHS/DT/DB)에 따라 `rawAnalysisData.patterns`를 필터링하고 `analysisData.patterns`를 만들어 `Chart`에 전달합니다.

4) Chart 컴포넌트의 처리(중요)
   - `Chart.tsx`는 `plotData` useMemo에서 traces 배열(캔들스틱, 피크/밸리 scatter 등)을 만든 뒤, `layout` useMemo에서 `shapes`/`annotations`를 계산합니다.
   - 패턴 박스 생성 로직(요약):
     1. 패턴의 시작/종료 시간 선택(우선순위: top-level startTimeEpoch/startTimeISO -> meta.startTimeEpoch/startTimeISO -> meta.start_peak/ start_valley.actual_date -> p.date)
     2. 시간 정규화: 초 단위(epoch seconds)를 밀리초(epoch ms)로 변환(Plotly는 ms 사용)
     3. 캔들 데이터에서 해당 구간에 포함되는 캔들 인덱스들을 찾아 `y` 범위(min low, max high)를 계산
     4. `shapes.push({type:'rect', xref:'x', yref:'y', x0, x1, y0, y1})`를 호출

   - 주의: `x0` 또는 `x1`이 `null`이거나 `x0 >= x1`이면 박스 폭이 0이 되거나 스킵됩니다. 따라서 시간 필드의 위치/형식 불일치가 치명적입니다.

5) 요약 표
   - 엔진(분석) → 라우터(정규화) → 프론트(정규화 확인 & 시각화) 순으로 체크해야 함. 시간 단위(초/밀리초), 필드 위치(최상위/meta), 타입(숫자/문자열) 중 하나라도 불일치하면 박스가 보이지 않는 문제가 발생합니다.


## 2) 관찰된 현상

- 초기 페이지 로드 시 사이드패널에는 패턴이 정상적으로 나열되지만, 차트 상에는 패턴 박스가 보이지 않음.

- 프론트 콘솔 로그상으로는 `patterns` prop이 Chart에 전달되어 있음이 확인됨.

- Plotly 내부 DOM(`_fullLayout.shapes`)에는 rect 객체들이 존재했으나 `y0/y1`가 전체 `paper` 기준이거나 가격 범위가 비어있어 의도한 박스가 보이지 않았음.


## 3) 현재 코드의 문제점(요약)

1. 초기 구현은 패턴 shapes의 `yref`를 `paper`로 설정해 차트 전체 높이를 채우는 밴드로 렌더링되었음(잘못된 시각적 표현).
2. 엔진이 패턴의 시작/종료를 `meta` 내부에만 넣고 라우터가 이를 최상위 필드로 일관되게 복사/정규화하지 않아 프론트가 빈 값 또는 잘못된 값을 읽는 경우가 있었음.
3. 프론트의 방어적 논리가 부족하여 top-level 필드만 확인하고 meta 내부를 충분히 고려하지 않았음(이후 수정됨).
4. start==end 또는 폭이 0인 경우를 처리하는 로직이 완벽하지 않아 박스가 스킵되거나 너무 작게 표시됨.


## 4) 이미 적용한 수정

1. `Chart.tsx`에서 패턴 `shapes` 생성 시 `yref: 'y'`로 변경하고, 해당 구간 내 캔들들의 high/low를 이용해 `y0/y1`을 계산하도록 개선했습니다.
2. 프론트에서 시간 선택 시 top-level 필드 우선 → meta 필드 폴백 순으로 읽도록 변경했습니다.
3. 백엔드 라우터에서 `meta`에만 존재하던 시간 필드를 최상위(`startTimeEpoch`/`endTimeEpoch` 등)로 복사해 응답을 정규화하도록 수정했습니다.
4. 디버그 로그를 추가해 각 패턴에 대해 어떤 필드를 사용했는지와 계산한 `x0/x1/cx0/cx1/indicesCount/y0/y1` 정보를 출력하여 문제를 추적했습니다.


## 5) 남아 있는 문제(재현된 현상)

1. React/Plotly의 재렌더링 타이밍에 따른 race condition 가능성: `patterns`가 빈 배열로 먼저 전달된 뒤 업데이트되면 Plotly가 relayout을 제대로 반영하지 못할 가능성.
2. 극히 짧은 기간 또는 포인트형 패턴(start==end) 처리 방식 개선 필요: 현재는 최소 폭을 강제하지만 더 자연스러운 확장(이웃 캔들 사용)이 필요.


## 6) Chart.tsx(Plotly.js)의 전체 핵심 구조 및 메카니즘 — 백엔드, `api.ts`와의 연계

아래는 개발 초보자도 이해할 수 있도록 Plotly와 React가 어떻게 상호작용하는지, 그리고 백엔드 반환값이 프론트에서 어떻게 사용되는지를 단계별로 설명합니다.

1) Plotly와 React의 상호작용(핵심 개념)
   - React 컴포넌트에서 Plotly를 사용하면 `data`와 `layout` 객체가 변경될 때마다 Plotly가 내부적으로 DOM/Canvas를 업데이트합니다.
   - `react-plotly.js`는 `data`와 `layout`이 참조가 바뀔 때만 Plotly에 재전달하며, 변경 감지를 위해 `useMemo`로 객체를 캐싱하는 것이 일반적입니다.
   - 중요: `useMemo` 의존성 배열에 `patterns`, `data`, `isDarkMode` 등 관련 상태를 명확히 넣지 않으면 최신 상태가 반영되지 않습니다.

2) `Chart.tsx`의 핵심 블록
   - normalizeTime(t): 다양한 시간 표현(숫자초, 숫자밀리, ISO 문자열)을 밀리초(epoch ms)로 통일합니다.
   - plotData useMemo: 캔들스틱 트레이스(x: times(ms), open/high/low/close), peaks/valleys scatter 등을 구성.
   - layout useMemo: axes, margin, shapes(패턴 박스), annotations(레이블) 등을 구성.
   - shapes 생성은 `patterns` prop을 순회하면서 start/end를 선택하고 ms로 변환한 뒤 해당 구간의 캔들들을 찾아 y0/y1을 계산해 `rect`를 추가합니다.

3) 백엔드/라우터(`pattern_analysis.py`)와의 연계 포인트
   - `api.ts`(프론트의 API 래퍼)는 `/trading-radar-data`를 호출하여 받은 JSON을 그대로 `Chart`에 전달합니다.
   - 라우터는 엔진의 복잡한 내부 구조(`completed_dt`, `start_peak`, `P1`, ...)를 프론트가 바로 소비할 수 있는 평탄화된 구조(최상위 `startTimeEpoch`/`endTimeEpoch`, `meta`)로 정규화합니다.
   - 따라서 프론트는 이 정규화된 응답만 신뢰하면 되고, 엔진의 내부 구조 변경이 있더라도 라우터가 일관된 응답을 제공해야 합니다.

4) 실무 팁(간단)
   - 시간 관련 필드는 항상 명시적으로 문서화하고(초 vs ms, timezone), 라우터 단계에서 값의 존재 여부를 확인하고 로그를 남기세요.
   - Plotly 레이아웃 수정은 가능한 한 불변 객체로 만들어 `react-plotly.js`에 넘겨 다시 렌더링 되도록 하세요.


## 7) 원인 분석 및 해결 (초보자용, 단계별 설명)

이제 왜 문제가 발생했는지, 그리고 우리가 어떤 절차로 해결했는지를 자세히 설명합니다. 나중에 읽어도 이해되도록 단계와 예제를 포함합니다.

1) 문제의 본질 — 데이터 계약 불일치
   - 한 줄 요약: 엔진은 시작 시간을 `meta` 내부에 넣었는데, 프론트는 최상위 필드를 먼저 읽었고 그 값이 비어있거나 잘못되어 박스 폭이 0이 되었다.
   - 예: 엔진이 `meta.startTimeEpoch = 1713711600` 을 넣었지만, 라우터가 최종 응답의 최상위 `startTime` 필드에 이를 복사하지 않았거나 요구 형식(초 vs 문자열)을 맞춰주지 않았습니다.

2) 디버깅 절차(우리가 실제로 한 것)
   - 1) 재현: 브라우저 콘솔에서 `/trading-radar-data`의 `patterns`를 확인하여 `DB-3`, `DB-4` 등 문제 패턴의 `startTime`과 `meta.startTime` 값을 비교함.
   - 2) 프론트 로그 추가: `Chart.tsx`에 디버그 로그를 넣어 각 패턴의 `prefStart`, `prefEnd`, 정규화된 `x0/x1` 값을 콘솔에 찍음.
   - 3) 프론트 방어 보강: `Chart.tsx`에서 우선순위를 `top-level -> meta -> structural` 로 변경해 임시로 동작하게 함.
   - 4) 근본 해결(라우터 보정): `pattern_analysis.py`의 응답 직렬화 부분에서 `meta` 내부의 시작/종료 시간을 최상위 필드로 복사/정규화하도록 수정함(이후 프론트는 일관된 필드만 읽으면 됨).

3) 기술적 요점(왜 이 방식이 안전한가)
   - 라우터가 응답을 정규화하면 엔진 내부 구조 변경(예: P1/P2에서 P1.V3로 네이밍 변경)과 무관하게 프론트는 동일한 키를 읽게 되어 유지보수가 쉬워집니다.
   - 프론트는 항상 방어적으로 데이터를 읽어야 합니다: top-level이 비어있으면 meta를 확인하고, 그래도 없으면 경고 로그를 남기고 최소한의 표시(예: 축소된 박스)를 하게 합니다.

4) 재발 방지 계획
   - 문서화: `patterns` 객체 스펙(필드 이름, 타입, 단위, 우선순위)을 `README`나 API 문서에 추가합니다.
   - 테스트: 라우터 직렬화 로직에 대한 단위 테스트를 추가해 `meta`만 있는 케이스가 생기더라도 top-level 필드가 채워지는지 검증합니다.

5) 초보자를 위한 추가 팁
   - 시간 변환: JS에서는 `new Date(epochSeconds * 1000)` 처럼 초→밀리 변환을 항상 명시적으로 하세요.
   - 로그: 문제 추적을 쉽게 하려면 '어떤 필드를 사용했는지'를 콘솔에 남기는 습관을 들이세요. (예: `using startTimeEpoch from meta`)


---

작성자: ChartStudio 팀
작성일: (자동)
