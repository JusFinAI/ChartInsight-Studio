

---

**기술 문서: DTDB Strategy Grok V030 (Dash Prototype)**

**1. 목적 및 개요**

본 `DTDB_strategy_grok_V030_dash.py` 스크립트와 `analysis_engine.py` 모듈은 금융 시계열 데이터(주가, 암호화폐 등)에 대한 기술적 분석(추세, 극점, 주요 차트 패턴)을 수행하고, 그 결과를 상호작용이 가능한 웹 대시보드 형태로 시각화하는 것을 목적으로 합니다. 사용자는 대시보드를 통해 분석 결과를 확인하고, 표시할 요소를 선택적으로 제어할 수 있습니다. 특히, 이 프로토타입은 향후 웹 서비스(예: Next.js + FastAPI)의 백엔드 분석 엔진으로 활용될 핵심 로직(`analysis_engine.py`)을 검증하고, 프론트엔드 시각화 요구사항을 미리 파악하는 데 중점을 둡니다.

**2. 시스템 구조**

시스템은 분석 로직을 담당하는 모듈과 웹 대시보드를 담당하는 애플리케이션 파일로 분리되어 있습니다.

- **`analysis_engine.py`**: 핵심 분석 엔진
    
    - **역할**: 데이터 로드, 추세/극점 탐지, 차트 패턴 인식 등 모든 계산 로직을 포함합니다. 외부(Dash 앱, FastAPI 등)로부터 데이터를 받아 분석을 수행하고, 구조화된 결과를 반환합니다.
    - **주요 구성 요소 (예시)**:
        
        Python
        
        ```
        # analysis_engine.py
        
        import pandas as pd
        from typing import Dict, Any
        # ... 다른 import ...
        
        # --- 데이터 클래스 ---
        @dataclass
        class MarketTrendInfo: ...
        
        # --- 분석 클래스 ---
        class TrendDetector:
            def __init__(self, n_criteria=2): ...
            def process_candle(self, current, prev, i, date, data): ...
            def finalize(self, data): ...
            # ... (Peak/Valley 등록 및 기타 메서드) ...
        
        class PatternDetector: # Base class
            def update(self, candle, peak=None, valley=None): ...
            def is_complete(self): ...
            # ...
        
        class HeadAndShouldersDetector(PatternDetector): ...
        class InverseHeadAndShouldersDetector(PatternDetector): ...
        class DoubleTopDetector(PatternDetector): ...
        class DoubleBottomDetector(PatternDetector): ...
        
        class PatternManager:
            def __init__(self, data): ...
            def check_for_hs_ihs_start(self, peaks, valleys, mode): ...
            def add_detector(self, pattern_type, extremum, data, js_peaks, js_valleys): ...
            def update_all(self, candle, peak=None, valley=None): ...
        
        # --- 데이터 로드 함수 ---
        def download_data(ticker, period, interval, ...) -> Optional[pd.DataFrame]: ...
        
        # --- 메인 분석 함수 ---
        def run_full_analysis(data: pd.DataFrame) -> Dict[str, Any]:
            """ 분석 오케스트레이션 및 결과 구조화 """
            detector = TrendDetector(...)
            manager = PatternManager(data)
        
            # 데이터 캔들 순회 (메인 루프)
            for i in range(1, len(data)):
                # detector.process_candle(...)
                # manager.update_all(...)
                # manager.check_for_hs_ihs_start(...) / manager.add_detector(...)
                pass # 실제 로직 포함
        
            detector.finalize(data)
        
            # 결과 딕셔너리 구성
            analysis_results = {
                "base_data": {...},
                "peaks_valleys": {...},
                "trend_info": {...},
                "patterns": {...},
                "states": [...]
            }
            return analysis_results
        ```
        
- **`dttb_strategy_grok_V030_dash.py`**: Dash 기반 웹 대시보드 애플리케이션
    
    - **역할**: 사용자 인터페이스(UI)를 제공하고, 사용자의 입력에 따라 `analysis_engine.py`의 함수를 호출하며, 반환된 분석 결과를 Plotly 그래프로 시각화하고 업데이트합니다.
    - **주요 구성 요소 (예시)**:
        
        Python
        
        ```
        # dttb_strategy_grok_V030_dash.py
        
        import dash
        from dash import dcc, html, Input, Output, State, callback
        import plotly.graph_objects as go
        # ... 다른 import ...
        
        # 분석 엔진 import
        try:
            from analysis_engine import run_full_analysis, download_data
            ANALYSIS_ENGINE_LOADED = True
        except ImportError:
            # ... 오류 처리 및 임시 함수 정의 ...
            ANALYSIS_ENGINE_LOADED = False
        
        # Dash 앱 초기화
        app = dash.Dash(__name__)
        
        # 앱 레이아웃 정의
        app.layout = html.Div([
            html.H1("..."),
            # 입력 컨트롤 (Ticker, Period, Interval, Button)
            html.Div([
                dcc.Input(id='input-ticker', ...),
                dcc.Dropdown(id='dropdown-period', ...),
                dcc.Dropdown(id='dropdown-interval', ...),
                html.Button('Run Analysis', id='button-run-analysis', ...)
            ]),
            # 시각화 옵션 컨트롤 (Checklist)
            html.Div([
                dcc.Checklist(id='checklist-options', ...)
            ]),
            # 그래프 영역 (로딩 포함)
            dcc.Loading(children=[dcc.Graph(id='analysis-graph')])
            # (선택적) 결과 저장소
            # dcc.Store(id='analysis-results-store')
        ])
        
        # 콜백 함수 정의
        @callback(
            Output('analysis-graph', 'figure'),
            Input('button-run-analysis', 'n_clicks'),
            Input('checklist-options', 'value'),
            State('input-ticker', 'value'),
            State('dropdown-period', 'value'),
            State('dropdown-interval', 'value')
        )
        def update_graph(n_clicks, selected_options, ticker, period, interval):
            # 1. 입력 값 및 트리거 확인
            # 2. 데이터 로드 (download_data 호출)
            # 3. 분석 실행 (run_full_analysis 호출)
            # 4. Figure 생성 (go.Figure)
            # 5. 기본 캔들스틱 추가
            # 6. selected_options 에 따라 조건부로 분석 요소(트레이스, 도형) 추가
            #    if 'show_js_peaks' in selected_options: fig.add_trace(...)
            #    if 'show_trend_background' in selected_options: shapes_to_draw.append(...)
            #    ...
            # 7. 레이아웃 업데이트 (fig.update_layout)
            # 8. Figure 반환
            return fig
        
        # 앱 실행
        if __name__ == '__main__':
            app.run_server(debug=True)
        ```
        

**3. 핵심 로직 요약**

- **추세/극점 탐지 (`TrendDetector.process_candle`)**: 캔들 단위로 상태 머신을 업데이트하며 추세 방향/강도를 결정하고 JS/Secondary Peak/Valley를 식별합니다. 실시간 돌파 감지 로직이 Secondary 극점 탐지 속도를 높입니다.
- **패턴 인식 (`PatternManager.update_all`, 각 `Detector.update`)**: `PatternManager`는 활성화된 모든 `Detector`에게 최신 캔들 정보와 새로 발생한 극점 정보를 전달합니다. 각 `Detector`는 이 정보를 받아 자신의 상태를 업데이트하고, 패턴 유효성(리셋 조건, 균형/대칭 규칙 등)을 검사하며, 완성 조건을 확인합니다. `PatternManager.check_for_hs_ihs_start`와 `add_detector`는 새로운 패턴 감지기 생성을 담당합니다.

**4. 향후 웹사이트 전환 가이드**

- **백엔드 (FastAPI)**:
    - **`analysis_engine.py` 이식**: `analysis_engine.py`의 클래스와 `run_full_analysis` 함수를 FastAPI 프로젝트로 가져옵니다.
    - **API 엔드포인트**: `/analyze` 엔드포인트에서 요청 파라미터(ticker, period, interval)를 받아 `download_data`와 `run_full_analysis`를 호출합니다.
    - **데이터 직렬화**: `run_full_analysis` 결과 딕셔너리 내의 **Timestamp, DatetimeIndex 객체** 등을 **JSON 호환 형식(ISO 문자열 또는 Unix 타임스탬프)**으로 변환하는 로직을 추가합니다. Pydantic 모델 사용을 권장합니다.
        
        Python
        
        ```
        # FastAPI 엔드포인트 예시 (의사코드)
        from fastapi import FastAPI, HTTPException
        from analysis_engine import run_full_analysis, download_data
        # from .utils import serialize_analysis_results # 직렬화 함수
        
        app = FastAPI()
        
        @app.get("/analyze/{ticker}")
        async def analyze_endpoint(ticker: str, period: str = "1y", interval: str = "1d"):
            try:
                data = download_data(ticker, period, interval)
                # ... 데이터 검증 ...
                results_raw = run_full_analysis(data)
                # ... 결과 검증 ...
                # results_serializable = serialize_analysis_results(results_raw) # 직렬화
                return results_serializable # JSON 응답
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        ```
        
- **프론트엔드 (Next.js / Plotly.js)**:
    - **API 호출**: 백엔드 API(`/analyze`)를 호출하여 분석 결과 JSON을 받아옵니다.
    - **상태 관리**: 사용자 입력(Ticker, 체크박스 등) 상태를 관리합니다.
    - **Plotly.js 렌더링**: 받아온 JSON 데이터와 사용자 선택 상태를 기반으로 Plotly Figure 객체를 JavaScript 환경에서 동적으로 생성하거나 업데이트합니다.
        - Dash 콜백(`update_graph` 함수) 내의 Figure 생성 및 요소 추가 로직을 참고하여 JavaScript로 구현합니다. 체크박스 상태에 따라 `figure.data` 배열과 `figure.layout.shapes` 배열을 조작하여 요소를 켜고 끕니다. `Plotly.react()` 또는 `Plotly.update()`를 사용하여 차트를 업데이트합니다.
    - **데이터 구조 예시 (API 응답 / Plotly.js 입력)**:
        
        JSON
        
        ```
        // 예시: run_full_analysis 결과가 JSON으로 변환된 형태
        {
          "base_data": {"dates": ["2024-01-01T00:00:00", ...], "open": [...], ...},
          "peaks_valleys": {
            "js_peaks": [{"actual_date": "2024-03-15T00:00:00", "value": 150.5, "type": "js_peak", ...}, ...],
            ...
          },
          "trend_info": {
            "periods": [{"start": "2024-02-01T00:00:00", "end": "2024-04-10T00:00:00", "type": "Uptrend"}, ...],
            ...
          },
          "patterns": {
            "completed_hs": [{"date": "2024-05-01T00:00:00", "price": 140.0, "P1": {"actual_date": ...}, ...}, ...],
            ...
          }
        }
        ```
        

**5. 기술적 고려사항 및 제언**

- **데이터 직렬화**: Python의 Timestamp/DatetimeIndex와 JSON 간의 변환 표준(ISO 8601 권장)을 명확히 정의하고 일관되게 적용해야 합니다.
- **성능**: Dash 프로토타입에서 사용된 "매번 재계산" 방식은 최종 웹 서비스에서는 성능 저하를 유발할 수 있습니다. 백엔드 API 레벨에서 분석 결과 캐싱 또는 `dcc.Store`와 유사한 서버 측 상태 관리 메커니즘 도입을 고려해야 합니다.
- **라이브러리 버전**: Python(Plotly)과 JavaScript(Plotly.js) 라이브러리 버전 간 호환성을 확인합니다.

이 보강된 기술 문서가 V030 코드의 이해와 향후 계획 수립에 더욱 도움이 되기를 바랍니다.