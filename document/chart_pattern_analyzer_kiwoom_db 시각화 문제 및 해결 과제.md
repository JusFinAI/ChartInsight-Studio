# chart_pattern_analyzer_kiwoom_db_v2 시각화 문제 및 해결 과제.md

이 문서는 `chart_pattern_analyzer_kiwoom_db_v2` 프로젝트의 차트(Plotly 기반 Dash 시각화)에서 발견된 문제와 그 원인, 해결 방안, 그리고 리스크 헷징(완화) 전략을 체계적으로 정리한 문서입니다. 주니어 개발자가 이 문서를 보고 1) 문제 상황을 이해하고 2) 수정 방법을 실행하며 3) 이후 발생할 수 있는 문제를 예방할 수 있도록 충분한 맥락과 예시를 포함했습니다.

목차
- 배경 및 개요
- 현상(증상) 상세
- 문제의 근본 원인(코드 레벨 분석)
- 해결 방안(선택지별 설명 및 구현 방법)
- 단계별 작업 계획(세부 단계 및 검증 방법)
- 리스크와 헷징 방안
- 검사 및 배포 체크리스트
- 부록: 관련 코드 스니펫 및 디버깅 명령


배경 및 개요
---------------
`chart_pattern_analyzer_kiwoom_db_v2`는 Kiwoom 기반의 차트 패턴 분석 결과를 DB에서 읽어와 Dash + Plotly를 이용해 시각화하는 모듈입니다. 사용자는 캔들 차트와 함께 트렌드 배경(Trend Background), ZigZag선, 주요 피크/밸리(JS Peaks/Valleys), 보조 피크/밸리(Secondary Peaks/Valleys), Double Top/Bottom, Head & Shoulder 등의 패턴을 화면에서 토글하여 표시할 수 있습니다.

시각화 부분은 다음 요소로 구성됩니다.
- 메인 캔들(Plotly `Candlestick`) - x 축은 시간(datetime) 인덱스
- 보조 트레이스(Plotly `Scatter`) - ZigZag, marker(피크/밸리), 패턴 라벨
- 도형(Plotly `Shape`) - 트렌드 배경, 패턴 박스(rect), 넥라인(line)
- 축(ticks) 및 레이블 - 사용자 친화적 날짜 포맷

문제 정의
---------
우리가 지금 해결해야 할 핵심 문제는 두 가지 계층으로 나뉩니다.

- 현재(우선 해결 대상): 분봉(예: 5m, 30m) 차트에서 한국 주식시장 거래 시간이 아닌 시간(영업 전/영업 후, 주말 등)이 그래프에 포함되어서 시각적으로 캔들이 듬성듬성 보이는 현상입니다. 이로 인해 사용자가 분봉 차트의 추세나 패턴을 직관적으로 파악하기 어렵고, 보조 요소(피크/밸리, zigzag, 패턴 박스 등)와의 정렬도 혼선이 발생합니다.

- 이전 이슈(이미 해결됨): 메인 캔들과 보조 요소들(x 좌표)의 타입이 혼재되어(예: datetime vs 정수 인덱스) Plotly의 축 매핑이 어긋나 ZigZag가 오른쪽으로 밀려 표시되거나 x축 라벨이 이상하게 보이는 문제가 있었습니다. 이 문제는 해당 문서의 수정 이력에 따라 코드 레벨에서 통일(보조 요소의 x를 datetime으로 맞춤 또는 x를 카테고리 인덱스로 통일)하는 방식으로 해결되었습니다. 아래 '이전 문제(해결됨)'에서 간단히 정리합니다.


현상(증상) 상세
------------------
아래는 사용자가 관찰한 주요 증상입니다. 실제 스크린샷과 로그를 바탕으로 정리했습니다.

- 현재 주요 증상(우선순위 1):
  - 분봉 차트에서 영업 외 시간(예: 00:00-09:00, 15:30-24:00, 토/일)이 포함되어 캔들 간격이 띄엄띄엄 보임. 결과적으로 분봉 특유의 연속된 캔들 연속성이 깨집니다.
  - 이로 인해 분봉 기반 패턴 인식(피크/밸리, 지그재그)이 시각적으로 혼동을 주며, 사용자가 패턴을 해석하기 어렵습니다.

- 이전 문제(해결됨, 기록용):
  - ZigZag Line이 마지막 캔들 범위를 벗어나 오른쪽에 그려지는 현상, x축 라벨 비정상, 옵션 토글 무시 등은 메인/보조 x값 타입 혼용과 옵션 로직 오류에서 기인했습니다.
  - 수정 내역(요약): 보조 요소의 x좌표를 datetime으로 변환하고(없는 경우 nearest 보정 적용), tick값(tickvals)도 datetime으로 통일하거나 반대로 모든 x를 정수 인덱스 카테고리로 통일하는 방법 중 하나를 선택하여 일관성을 확보했습니다. 또한 `JS/Secondary` peaks 표시 로직을 분리하여 옵션 토글이 올바르게 동작하도록 수정했습니다.

추가 관찰
- 캔들은 datetime 값을 x로 사용(`x=df.index`)한 반면, 이전 코드에서 일부 보조 요소는 인덱스 위치(정수)를 x로 사용하거나 날짜 문자열/타입이 혼재되어 있었습니다. 이 부분은 이전에 해결한 항목입니다.


문제의 근본 원인(코드 레벨 분석)
-----------------------------------
다음은 핵심 원인과 코드 상의 문제 지점을 자세히 설명한 내용입니다.

1) x 좌표 타입 혼용
- 메인 캔들: `fig.add_trace(go.Candlestick(x=df.index, ...))` — `df.index`는 `DatetimeIndex`로 datetime 객체(또는 tz-aware Timestamp)를 담고 있습니다.
- ZigZag: 기존 코드에서 `df.index.get_loc(pd.to_datetime(x0_date))`를 호출하여 정수 인덱스(예: 0, 1, 234)를 얻고 `go.Scatter(x=[x0_idx, x1_idx], ...)`을 사용한 경우가 있었습니다. 즉 ZigZag는 인덱스 위치(정수)를 x로 사용합니다.
- Plotly는 같은 figure 내에서 x 값들의 타입이 혼재하면(예: datetime과 정수) 각각을 별도의 카테고리로 처리하거나 의도치 않게 레이아웃을 잡습니다. 이로 인해 ZigZag가 엉뚱한 카테고리 위치에 그려지거나 x축 라벨이 이상하게 보입니다.

2) tickvals / 축 타입 혼선
- 코드에서 `fig.update_xaxes(type='category', tickvals=[정수 인덱스들], ticktext=[문자열 레이블])` 를 사용한 반면, 캔들에는 datetime이 x로 주어져 있어 tick 위치와 실제 데이터 포인트 매칭이 어긋났습니다.

3) 옵션(Feature toggle) 로직 실수
- JS와 Secondary 표시 로직이 한 블록에 묶여 있었고, 조건문으로는 `if 'show_js_extremums' in selected_options:`만 검사했습니다. 그 블록 내부에서 secondary peaks/valleys도 무조건 그려서 Secondary 옵션이 꺼져 있어도 표시되었습니다.

4) 타임존(tz) 처리 불일치
- DB에서는 UTC로 저장된 timestamp를 KST(Asia/Seoul)로 변환하여 데이터프레임에 넣는 과정에서 tz-aware를 제거하거나 혼재되면서 `df.index`의 타입과 분석 결과의 날짜 타입(`actual_date`) 간 매칭 오류가 발생할 수 있습니다.

5) shapes(도형) 좌표와 xref
- Plotly shapes에 `xref='x'`를 사용하면 x 값이 카테고리인지 datetime인지에 따라 shapes의 x0/x1 해석이 달라집니다. 타입 혼용 시 shapes가 엉뚱한 위치에 그려질 수 있습니다.


해결 방안(선택지별 설명 및 구현 방법)
-------------------------------------
아래는 가능한 해결 방안들을 장단점과 구현 포인트와 함께 정리한 것입니다. 우선순위를 고려해 권장 순서도 표시합니다.

옵션 A (권장 시나리오): 정수 인덱스(0..N-1)를 카테고리로 사용하여 모든 trace 통일
- 핵심 아이디어: 모든 trace의 x 좌표를 정수 인덱스(0부터 시작하는 위치값)로 바꿉니다. 캔들, ZigZag, peaks, valleys, shapes 모두 동일한 인덱스 좌표계를 사용하도록 코드를 수정합니다. x축 표시(사람이 보는 레이블)는 ticktext로 포맷된 날짜 문자열을 사용합니다.
- 장점: 기존 코드가 인덱스 위치를 참조하는 부분이 많아 변경 범위가 작고, shapes/annotation이 카테고리 x에서 안정적으로 동작합니다. 성능상 문자열 카테고리보다 유리합니다.
- 단점: x축이 '정수' 기반 카테고리가 되므로 사용자 측 'date range' 기반 상호작용이 직관적이지 않을 수 있음(하지만 ticktext로 날짜를 보여주면 시각상 문제는 적음).
- 구현 포인트(요약):
  1. df_len = len(df); x_cats = list(range(df_len)); df['_x_cat'] = x_cats  # 내부 매핑
  2. Candlestick: x=df['_x_cat'] (또는 x=x_cats)
  3. ZigZag/peaks: datetime → idx = df.index.get_indexer([dt], method='nearest')[0] → x=idx
  4. shapes: x0/x1에 idx 사용
  5. tickvals = [idx1, idx2, ...]; ticktext = ['YYYY/MM', ...]; fig.update_xaxes(type='category', tickmode='array', ...)

옵션 B: 모든 x를 실제 datetime으로 통일 (xaxis type='date')
- 핵심 아이디어: 모든 trace와 shapes의 x를 datetime 값으로 통일하여 x축을 `type='date'`로 사용합니다.
- 장점: 사용자가 날짜 기반으로 직관적인 줌/팬을 할 수 있고 date-range 기반 상호작용이 자연스럽습니다.
- 단점: shapes/annotation에서 datetime x를 사용할 때 Plotly 버전·동작에 따라 미묘한 차이가 날 수 있고, 현재 코드가 인덱스 위치를 가정한 부분을 더 많이 변경해야 합니다.
- 구현 포인트(요약):
  1. Candlestick: x=df.index (이미 datetime)
  2. ZigZag/peaks: dt = pd.to_datetime(x0_date); if dt not in df.index: idx = df.index.get_indexer([dt], method='nearest')[0]; dt = df.index[idx]; x=[dt, ...]
  3. shapes: x0/x1에 datetime 값 사용(정수 대신)
  4. tickvals는 datetime 값, fig.update_xaxes(type='date')

옵션 C: 문자열 카테고리(예: 'YYYY-MM-DD HH:MM:SS')를 x로 사용
- 핵심 아이디어: 모든 datetime을 고유한 문자열로 포맷하여 카테고리 x에 사용.
- 장점: 사람 친화적 라벨, 모든 요소를 문자열 카테고리로 일관되게 매핑 가능
- 단점: 문자열 길이/갯수에 따라 렌더링 성능 저하 가능성(특히 수천개 카테고리), shapes 처리 불안정 가능성

선택지 고민
- 일반적으로 `옵션 A`(정수 인덱스 카테고리)를 고려하였습니다. 이유는 성능, 구현 용이성, 그리고 shapes/annotation과의 호환성 측면에서 가장 안정적입니다. 운영 환경에서 빠르게 적용하고 문제를 최소화할 수 있다고 생각합니다만,  축(캔들 + 보조요소)을 둘 다 카테고리 축으로 통일하는 방법(즉, 모든 trace의 x를 동일한 카테고리 라벨로 바꾸는 방안)도 검토 중입니다. 아래에 두 축을 모두 카테고리로 통일하는(문자열 카테고리) 구체적 구현 방법과, 각 선택지별 상세 단계 계획을 추가로 제시합니다.

두 축을 문자열 카테고리로 통일하는 방법(구체적 구현)
- 핵심 아이디어: 모든 datetime 인덱스를 고유한 문자열 라벨(예: `YYYY-MM-DD HH:MM:SS`)로 포맷하여, 그 문자열을 모든 trace의 x로 사용한다. 보조 요소는 datetime → nearest index → 해당 인덱스의 문자열 라벨로 변환하여 동일한 카테고리 축 위에 그린다.
- 상세 구현 절차(코드 레벨):
  1. 내부 카테고리 라벨 생성
     ```python
     # df.index는 DatetimeIndex
     x_labels = [d.strftime('%Y-%m-%d %H:%M:%S') for d in df.index]
     df['_x_label'] = x_labels
     ```
  2. Candlestick을 문자열 카테고리 x로 그려
     ```python
     fig.add_trace(go.Candlestick(
         x=df['_x_label'],
         open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
         name=ticker, ...
     ))
     ```
  3. 보조 요소(zigzag, peaks, markers): datetime → nearest index → 대응 라벨로 변환
     ```python
     dt = pd.to_datetime(point_date)
     idx = df.index.get_indexer([dt], method='nearest')[0]
     x_cat = df['_x_label'].iloc[idx]
     fig.add_trace(go.Scatter(x=[x_cat], y=[value], ...))
     ```
  4. shapes의 x0/x1, lines: 카테고리 문자열 사용
     - Plotly shapes에 문자열 카테고리를 바로 넣을 수 있으나 버전별 동작 차이가 있으므로 검증 필요.
     - 대안: shapes 좌표를 domain 좌표나 xref='x domain'으로 변환해 적용.
  5. tick 설정: tickvals에 카테고리 라벨, ticktext에 사람이 읽는 축 레이블
     ```python
     fig.update_xaxes(type='category', tickmode='array', tickvals=[df['_x_label'].iloc[i] for i in selected_idxs], ticktext=[...] )
     ```
- 장단점 및 주의점:
  - 장점: 모든 trace가 같은 카테고리 축에 매핑되어 정렬 오류가 발생하지 않음.
  - 단점: 문자열 카테고리가 많아지면 렌더링 성능 저하 가능, Plotly shapes 동작 차이로 추가 보정 필요.
  - 검증 팁: 구현 후 반드시 shapes/annotation의 좌표(문자열 라벨)를 로그로 남겨 렌더 결과와 비교.


단계별 작업 계획(선택지별 세부 단계 및 검증 방법)
- 아래의 단계 계획은 각 선택지(A/B/C)에 대해 독립적으로 적용 가능한 체크리스트 형태로 정리했습니다. 각 선택지별로 단계 1~4(비파괴 실험 → 전환 → 성능 테스트 → QA 및 배포)를 따릅니다.

옵션 A: 정수 인덱스 카테고리 방식(권장)
- 단계 1 (비파괴 실험)
  1. 새 브랜치 생성(`fix/visualization-int-index`)
  2. `df['_x_idx'] = list(range(len(df)))` 추가
  3. Candlestick을 임시로 `x=df['_x_idx']`로 추가(원본 캔들 trace는 보존)
  4. ZigZag/peaks에 대해 datetime→idx(nearest) 매핑을 적용하고, 임시 trace로 그려 비교
  5. 로컬 UI에서 시각 정렬 확인(캔들 vs zigzag 위치 일치)
- 검증 기준
  - 캔들과 모든 보조 trace의 x 위치가 시각적으로 일치할 것
  - shapes(rect/line)의 x0/x1이 의도한 캔들 구간을 덮을 것
- 단계 2 (전체 전환)
  1. 모든 trace의 x를 `_x_idx`(정수)로 변경
  2. shapes의 x0/x1를 정수 인덱스로 변경
  3. `fig.update_xaxes(type='category', tickmode='array', tickvals=[idx...], ticktext=[date_str...])` 설정
- 단계 3 (성능/상호작용 테스트)
  - 분봉(5m/30m) 포함 500~2000개 캔들에서 렌더 및 상호작용 테스트
  - hover/zoom 동작 확인
- 단계 4 (QA/배포)
  - PR 작성, 스크린샷 첨부, 리뷰 후 병합
  - 운영 모니터링(롤아웃 후 일정 기간 로그 수집)

옵션 B: 모든 x를 datetime으로 통일 (xaxis type='date')
- 단계 1 (비파괴 실험)
  1. 새 브랜치 생성(`fix/visualization-date-axis`)
  2. Candlestick은 기존 `x=df.index` 유지
  3. ZigZag/peaks에 대해 `pd.to_datetime(...)` 사용 후, `if dt not in df.index: dt = df.index.get_indexer([dt], method='nearest')` 보정
  4. 보조 trace를 datetime x로 추가하고 시각 정렬 확인
- 검증 기준
  - datetime x 기반에서 shapes/annotations가 캔들과 정확히 일치하는지 확인
  - date-range 기반 상호작용이 직관적으로 동작하는지 검증
- 단계 2 (전체 전환)
  1. 모든 trace 및 shapes의 x값을 datetime으로 통일
  2. `fig.update_xaxes(type='date', tickformat=...)` 설정
- 단계 3 (성능/상호작용 테스트)
  - 시간대 변환(tz) 관련 edge-case(주말/장막 시간)에 대한 테스트
  - shapes가 datetime 좌표에서 정상 동작하는지 여러 Plotly 버전에서 검증
- 단계 4 (QA/배포)
  - PR/스크린샷/자동 테스트 포함

옵션 C: 문자열 카테고리 방식
- 단계 1 (비파괴 실험)
  1. 새 브랜치 생성(`fix/visualization-str-cat`)
  2. `df['_x_label']` 문자열 라벨 컬럼 추가
  3. Candlestick, 보조 trace를 문자열 카테고리 x로 추가(원본 보존)
  4. shapes 적용 시 동작을 확인(특히 rect/line의 xref 동작)
- 검증 기준
  - 문자열 라벨 기반에서 모든 trace가 정확히 일치하는지 확인
  - 렌더 성능(초당 프레임, 초기 렌더 시간)이 허용 범위인지 측정
- 단계 2 (전환)
  1. 모든 trace 및 shapes의 x를 문자열 라벨로 통일
  2. `fig.update_xaxes(type='category', tickmode='array', tickvals=labels, ticktext=human_readable)` 설정
- 단계 3 (성능/상호작용 테스트)
  - 대량 데이터(1k+)에서 렌더 성능과 메모리 사용량을 측정
- 단계 4 (QA/배포)
  - PR/문서/모니터링 포함

각 옵션 공통 검증 포인트
- 타임존(tz) 일관성 확인: df.index와 분석 결과의 날짜 필드(actual_date 등)가 동일한 tz 또는 모두 naive인지 확인
- 옵션 토글별 동작 확인: Trend Background, ZigZag, JS/Secondary, DT/DB, HS/IHS 등 개별 옵션 켜고 끄며 시각 결과 확인
- shapes/annotations 좌표 로그: 변경 전/후 좌표(예: x0,x1) 값을 로그로 남겨 비교


리스크와 헷징 방안
-------------------
(이미 상단에 요약했지만, 실무에서 바로 참조할 수 있도록 상세히 정리합니다.)

리스크 1: shapes가 의도치 않게 위치해 어긋남
- 원인: xref의 타입(카테고리 vs date) 불일치
- 헷징: idx→dt 매핑 맵을 유지하고, 문제가 발생하면 즉시 `fig.update_xaxes(type='date')`로 전환해 비교. 변경 전/후 스냅샷 저장.

리스크 2: 줌/팬 동작이 기대와 다름
- 원인: 카테고리 x에서는 연속적 범위 선택이 datetime과 다르게 동작
- 헷징: 사용자 가이드로 'Zoom 동작 제한' 문서화 혹은 설정으로 `use_category` 토글 제공. 또한, 범위를 datetime으로 변환해 별도의 range-selection UI 제공 가능.

리스크 3: 타임존 매칭 오류
- 원인: DB(UTC) → KST 변환과정에서 tz-aware/naive 혼용
- 헷징: _download_data_from_db에서 명확히 tz-aware로 변환 후 내부 비교(예: 분석 결과의 actual_date도 tz-aware로 표준화). 변경 로그/디버그 출력을 통해 변환된 dt의 tzinfo를 기록.

리스크 4: Plotly 버전별 동작 차이
- 원인: Plotly의 shapes/카테고리 처리 세부 동작 차이
- 헷징: 사용 중인 Plotly 버전을 `requirements.txt`에 고정하고, PR에 테스트 결과(스크린샷 포함)를 추가.

리스크 5: 대규모 데이터에서 성능 저하
- 원인: 많은 annotations/shapes/markers 렌더링
- 헷징: default로 일부 annotation을 limit(예: 최근 N개만 표시)하거나, lazy-loading(zoom 시 상세 표시) 전략 적용.


검사 및 배포 체크리스트
-----------------------
- [ ] 변경 전 현재 코드를 `git commit` 및 별도 브랜치 생성
- [ ] 모든 변경 사항에 대해 린트 실행(예: flake8/pylint) 및 수정
- [ ] 기능별 스냅샷(변경 전/후) 캡처: ZigZag, Trend Background, JS/Secondary, HS/IHS, DT/DB
- [ ] 주요 인터랙션 점검: Zoom, Pan, Hover, Range selection
- [ ] 다양한 인터벌로 테스트(5m, 30m, 1h, 1d, 1wk)
- [ ] 여러 종목(거래량 많음/적음, 결측/비거래 구간 포함)으로 테스트
- [ ] performance profiling(500~2000 캔들) 후 렌더 시간 측정
- [ ] PR 생성 및 팀 코드 리뷰
- [ ] QA 승인 후 병합 및 배포


부록: 관련 코드 스니펫 및 디버깅 명령
-------------------------------------
- df의 인덱스 및 타입 확인 (디버깅)
```python
print(df.index[:10])
print(type(df.index))
print(df.index.dtype)
print(df.index[0].tzinfo)
```

- peaks_valleys 구조 확인
```python
print(result.get('peaks_valleys', {}).keys())
print(len(result.get('peaks_valleys', {}).get('js_peaks', [])))
print(result.get('peaks_valleys', {}).get('js_peaks', [])[:3])
```

- quick mapping function (datetime -> index)
```python
def dt_to_idx(df_index, dt):
    idx = df_index.get_indexer([pd.to_datetime(dt)], method='nearest')[0]
    return idx
```

- 브랜치 생성/롤백 명령 예시
```
# 브랜치 생성
git checkout -b fix/visualization-category-index
# 변경 적용 후 커밋
git add backend/_temp_integration/chart_pattern_analyzer_kiwoom_db_v2/main_dashboard.py
git commit -m "visual: unify x-axis as integer category index for stable shapes"
# 필요시 롤백
git reset --hard HEAD~1
```


마무리
-------
이 문서는 1달 뒤에 읽어도 바로 따라 작업할 수 있도록 배경과 코드 수준의 원인, 구체적 구현 방법 및 리스크 완화 방안을 포함해 작성했습니다. 원하시면 이 문서를 레포지토리의 `docs/` 폴더에 `visualization-issues.md` 형태로 추가하거나, 작업 지시서로 바로 적용 가능한 패치(단계별 작은 PR)를 생성해 드리겠습니다.

제가 다음으로 무엇을 도와드릴까요? (예: 문서를 영어로 번역, PR 생성, 단계 1 자동 적용 등)
