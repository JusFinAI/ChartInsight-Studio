import dash
from dash import dcc, html, Input, Output, State, callback # State 추가, callback 명시적 임포트
import plotly.graph_objects as go
from plotly.subplots import make_subplots # 서브플롯 사용 위해 추가
import pandas as pd
import numpy as np
# import yfinance as yf # download_data가 engine에 있으므로 주석 처리 가능
import logging
import time # 로깅 및 성능 측정용
from typing import List, Dict, Any, Optional # 타입 힌팅 강화
import os
from datetime import datetime

# 카테고리 및 티커 데이터 임포트
from category_ticker_data import CATEGORY_OPTIONS, SYMBOLS_BY_CATEGORY, DEFAULT_CATEGORY, DEFAULT_TICKER

# --- 로거 설정 (날짜 기반 로그 파일 경로 구성) ---
# logs 디렉토리가 없으면 생성
os.makedirs('logs', exist_ok=True)

# 현재 날짜를 기반으로 로그 파일 이름 생성
current_date = datetime.now().strftime('%Y%m%d%H%M')
log_filename = f'logs/dash_app_{current_date}.log'

# 로거 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)
logger.info(f"로그 파일 경로: {os.path.abspath(log_filename)}")
# -----------------------------------------------------------

# --- 분석 엔진 모듈 import ---
try:
    from analysis_engine import run_full_analysis, download_data
    logger.info("analysis_engine 모듈 로드 성공")
    ANALYSIS_ENGINE_LOADED = True
except ImportError as e:
    logger.error(f"analysis_engine.py 모듈 import 실패: {e}. 임시 함수를 사용합니다.")
    # 임시 함수 정의
    def run_full_analysis(data):
        return {
            "error": "Analysis engine module not loaded or failed to import.",
            "base_data": {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
            "peaks_valleys": {"js_peaks": [], "js_valleys": [], "sec_peaks": [], "sec_valleys": []},
            "trend_info": {"periods": [], "zigzag_points": []},
            "patterns": {"completed_dt": [], "completed_db": [], "completed_hs": [], "completed_ihs": [], "failed_detectors_count": 0},
            "states": []
        }
    def download_data(ticker, period, interval):
        logger.warning("Using placeholder download_data function.")
        return pd.DataFrame()
    ANALYSIS_ENGINE_LOADED = False
# --------------------------------------------------------

# === Dash 앱 초기화 ===
app = dash.Dash(__name__, suppress_callback_exceptions=True) # 콜백 예외 처리 활성화
app.title = "V030 Analysis"

# === 앱 레이아웃 정의 ===
app.layout = html.Div([
    html.H1("DTDB Strategy Analysis V030 (Dash)", style={'marginBottom': '10px', 'marginTop': '5px'}),  # 마진 축소

    # --- 입력 컨트롤 ---
    html.Div([
        # 카테고리 드롭다운
        dcc.Dropdown(
            id='dropdown-category',
            options=[{'label': cat, 'value': cat} for cat in CATEGORY_OPTIONS],
            value=DEFAULT_CATEGORY,  # 기본값
            clearable=False,
            style={'width': '180px'}  # 150px에서 180px로 확장
        ),
        # 티커 드롭다운 (카테고리에 따라 동적 업데이트)
        dcc.Dropdown(
            id='dropdown-ticker',
            options=SYMBOLS_BY_CATEGORY[DEFAULT_CATEGORY],  # 초기 옵션
            value=DEFAULT_TICKER,  # 기본값
            clearable=False,
            style={'width': '250px'}  # 220px에서 250px로 확장
        ),
        dcc.Dropdown(
            id='dropdown-period',
            options=[
                {'label': '1 Month', 'value': '1mo'}, {'label': '3 Months', 'value': '3mo'},
                {'label': '6 Months', 'value': '6mo'}, {'label': '1 Year', 'value': '1y'},
                {'label': '2 Years', 'value': '2y'}, {'label': '5 Years', 'value': '5y'},
                {'label': 'Year to Date', 'value': 'ytd'}, {'label': 'Max', 'value': 'max'}
            ],
            value='2y', # 기본값
            clearable=False,
            style={'width': '150px'}  # 130px에서 150px로 확장
        ),
        dcc.Dropdown(
            id='dropdown-interval',
            options=[
                {'label': '1 Day', 'value': '1d'}, {'label': '1 Week', 'value': '1wk'},
                {'label': '1 Month', 'value': '1mo'},
                # 분/시간 단위는 데이터 양과 분석 시간에 영향 주의
                # {'label': '1 Hour', 'value': '1h'},
                # {'label': '30 Minutes', 'value': '30m'},
            ],
            value='1d', # 기본값
            clearable=False,
            style={'width': '150px'}  # 130px에서 150px로 확장
        ),
        html.Button('Run Analysis', id='button-run-analysis', n_clicks=0,
                    style={'height': '36px', 'width': '150px', 'margin-left': '10px'})  # 버튼 너비 확장
    ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '10px', 'alignItems': 'center'}),  # 간격 확장, 요소 수직 정렬

    # --- 시각화 옵션 컨트롤 ---
    html.Div([
        html.H3("Display Options:", style={'marginBottom': '5px', 'marginTop': '5px'}),  # 마진 축소
        dcc.Checklist(
            id='checklist-options',
            options=[
                {'label': 'JS Peaks/Valleys', 'value': 'show_js_extremums'},
                {'label': 'Secondary Peaks/Valleys', 'value': 'show_sec_extremums'},
                {'label': 'Trend Background', 'value': 'show_trend_background'},
                {'label': 'ZigZag Line', 'value': 'show_zigzag'},
                {'label': 'Double Bottom/Top', 'value': 'show_dt_db'},
                {'label': '(Inv) Head & Shoulder', 'value': 'show_hs_ihs'},
            ],
            value=[ # 기본적으로 선택될 옵션들
                # 'show_js_extremums', 'show_sec_extremums', # 기본 표시에서 제외
                'show_trend_background', 'show_zigzag',
                #'show_dt_db', 'show_hs_ihs'
            ],
            inline=True, # 가로로 표시
            style={'display': 'flex', 'flexWrap': 'wrap', 'gap': '10px', 'marginBottom': '5px'}  # 간격과 마진 축소
        )
    ]),

    # --- 결과 표시 영역 ---
    dcc.Loading( # 로딩 컴포넌트
        id="loading-graph",
        type="circle",
        children=[
            dcc.Graph(
                id='analysis-graph',
                figure=go.Figure(layout={'height': 800}),  # 그래프 높이 700에서 800으로 증가
                # --- config 속성 추가 ---
                config={
                    'scrollZoom': True,  # 마우스 휠 줌 활성화!
                    # 'displayModeBar': True, # 상단 도구 모음 항상 표시 (선택 사항)
                    # 'editable': True      # 그래프 편집 기능 활성화 (선택 사항)
                }
                # ----------------------
            )
        ]
    ),

    # --- 분석 결과 저장소 (선택적) ---
    # dcc.Store(id='analysis-results-store') # 나중에 성능 최적화 시 사용 가능

], style={'padding': '10px'})  # 전체 패딩 20px에서 10px로 축소

# === 콜백 함수 정의 ===
# 카테고리 변경 시 티커 드롭다운 업데이트
@callback(
    Output('dropdown-ticker', 'options'),
    Output('dropdown-ticker', 'value'),
    Input('dropdown-category', 'value')
)
def update_ticker_options(selected_category):
    """
    카테고리 선택에 따라 티커 드롭다운 옵션 업데이트
    """
    options = SYMBOLS_BY_CATEGORY.get(selected_category, [])
    
    # 선택된 카테고리의 첫 번째 티커를 기본값으로 설정
    default_value = options[0]['value'] if options else ''
    
    return options, default_value

@callback(
    Output('analysis-graph', 'figure'),
    # --- Input/State 수정 ---
    Input('button-run-analysis', 'n_clicks'), # 버튼 Input
    Input('checklist-options', 'value'),      # <<< 체크리스트 Input으로 변경!
    State('dropdown-ticker', 'value'),        # dropdown-ticker로 변경
    State('dropdown-period', 'value'),        # Period는 State
    State('dropdown-interval', 'value'),      # Interval은 State
    State('dropdown-category', 'value'),      # 카테고리 정보도 State로 추가
    prevent_initial_call=True
)
def update_graph(n_clicks, selected_options, ticker, period, interval, category):
    """
    사용자 입력 및 선택 옵션에 따라 데이터를 분석하고 그래프를 업데이트하는 콜백 함수.
    """
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id if ctx.triggered_id else 'No trigger'
    logger.info(f"Callback triggered by: {triggered_id}")
    logger.info(f"Current selected options: {selected_options}") # 선택된 옵션 로깅 활성화

    # 버튼 클릭 또는 체크리스트 변경으로 실행된 경우 구분
    is_checklist_trigger = triggered_id == 'checklist-options'
    
    # 이미 분석된 결과가 있고 체크리스트만 변경된 경우, 데이터 재분석 없이 그래프만 업데이트
    if is_checklist_trigger and hasattr(update_graph, 'last_analysis_results'):
        logger.info(f"체크리스트 옵션 변경으로 그래프만 업데이트합니다. 카테고리: {category}, 티커: {ticker}")
        analysis_results = update_graph.last_analysis_results
        data = update_graph.last_data
        
        # 체크리스트 변경 시에도 시간 측정을 위한 변수 초기화
        start_load_time = time.time()
        load_end_time = start_load_time  # 데이터 로드 없음
        analysis_end_time = load_end_time  # 분석 없음
    else:
        # 버튼 클릭으로 새로운 분석을 시작하는 경우
        logger.info(f"분석 시작 트리거: 카테고리={category}, 티커={ticker}, 기간={period}, 타임프레임={interval}")
        start_load_time = time.time()

        if not ticker:
            logger.warning("Ticker가 입력되지 않았습니다.")
            fig = go.Figure()
            fig.update_layout(title_text="Ticker를 입력하세요.", height=700)
            return fig

        # 1. 데이터 로드
        try:
            data = download_data(ticker, period, interval)
            if data is None or data.empty:
                raise ValueError(f"No data found for {ticker}")
        except Exception as e:
            logger.error(f"데이터 로드 오류 ({ticker}): {e}")
            fig = go.Figure()
            fig.update_layout(title_text=f"데이터 로드 실패: {e}", height=700)
            return fig

        load_end_time = time.time()
        logger.info(f"데이터 로드 완료 ({load_end_time - start_load_time:.2f}초)")

        # 2. 분석 실행
        if not ANALYSIS_ENGINE_LOADED:
            logger.error("분석 엔진이 로드되지 않았습니다.")
            fig = go.Figure()
            fig.update_layout(title_text="분석 엔진 로드 실패", height=700)
            return fig

        try:
            # 티커, 기간, 타임프레임 정보 전달
            analysis_results = run_full_analysis(data, ticker=ticker, period=period, interval=interval)
            if analysis_results.get("error"):
                 raise RuntimeError(analysis_results["error"])
                 
            # 분석 결과와 데이터 저장 (체크리스트 변경시 재사용)
            update_graph.last_analysis_results = analysis_results
            update_graph.last_data = data
            
        except Exception as e:
            logger.error(f"분석 실행 오류 ({ticker}): {e}")
            import traceback
            logger.error(traceback.format_exc()) # 상세 오류 로그 추가
            fig = go.Figure()
            fig.update_layout(title_text=f"분석 중 오류 발생: {e}", height=700)
            return fig

        analysis_end_time = time.time()
        logger.info(f"분석 완료 ({analysis_end_time - load_end_time:.2f}초)")

    # 3. Plotly Figure 생성
    fig = go.Figure()

    # --- 기본 캔들스틱 추가 ---
    base_data = analysis_results.get("base_data", {})
    dates = base_data.get("dates") # DatetimeIndex
    if dates is not None and len(dates) > 0:
        fig.add_trace(go.Candlestick(
            x=dates,
            open=base_data.get("open"),
            high=base_data.get("high"),
            low=base_data.get("low"),
            close=base_data.get("close"),
            name=ticker
        ))
    else:
        logger.warning("차트를 그릴 기본 데이터가 없습니다.")
        fig.update_layout(title_text="차트 데이터 없음", height=700)
        return fig

    # --- 선택된 옵션에 따라 요소 추가 ---
    peaks_valleys = analysis_results.get("peaks_valleys", {})
    trend_info = analysis_results.get("trend_info", {})
    patterns = analysis_results.get("patterns", {})

    # Y축 범위 계산 (요소 추가 전에)
    y_min = data['Low'].min()
    y_max = data['High'].max()
    y_range = y_max - y_min
    y_margin = y_range * 0.03  # 0.05에서 0.03으로 축소하여 위아래 마진을 줄임
    plot_y_min = max(0, y_min - y_margin)
    plot_y_max = y_max + y_margin

    # 배경색 그리기 용 shapes 리스트
    shapes_to_draw = []

    # 3.1 추세 배경색
    if 'show_trend_background' in selected_options:
        trend_periods = trend_info.get("periods", [])
        # V023 시각화 함수의 배경색 로직 참조하여 구현
        background_periods = []
        last_end_date = dates[0] if len(dates) > 0 else None

        if trend_periods:
            all_dates_in_data = set(dates) # 빠른 검색을 위해 set 사용

            # 첫 추세 시작 전 Sideways 구간
            first_period_start = pd.Timestamp(trend_periods[0]['start']) # Timestamp 변환
            if first_period_start > dates[0]:
                 # 데이터 내에 실제 존재하는 가장 가까운 시작 날짜 찾기 (선택적)
                 closest_start = min(d for d in all_dates_in_data if d >= dates[0])
                 closest_end = max(d for d in all_dates_in_data if d < first_period_start)
                 if closest_start <= closest_end:
                     background_periods.append({'start': closest_start, 'end': closest_end, 'type': 'Sideways'})

            for i, period in enumerate(trend_periods):
                start_ts = pd.Timestamp(period['start'])
                end_ts = pd.Timestamp(period['end'])

                # 실제 데이터 범위 내 날짜로 조정
                closest_start = min((d for d in all_dates_in_data if d >= start_ts), default=None)
                closest_end = max((d for d in all_dates_in_data if d <= end_ts), default=None)

                if closest_start and closest_end and closest_start <= closest_end:
                     # 추세 구간 사이 Sideways 구간
                     if i > 0:
                         prev_end_ts = pd.Timestamp(trend_periods[i-1]['end'])
                         closest_prev_end = max((d for d in all_dates_in_data if d <= prev_end_ts), default=None)
                         if closest_prev_end and closest_start > closest_prev_end:
                             inter_start = min((d for d in all_dates_in_data if d > closest_prev_end), default=closest_start)
                             inter_end = max((d for d in all_dates_in_data if d < closest_start), default=inter_start)
                             if inter_start <= inter_end:
                                background_periods.append({'start': inter_start, 'end': inter_end, 'type': 'Sideways'})

                     # 현재 추세 구간 추가
                     background_periods.append({'start': closest_start, 'end': closest_end, 'type': period['type']})
                     last_end_date = closest_end # 마지막 종료 날짜 업데이트

            # 마지막 추세 종료 후 Sideways 구간
            if last_end_date and last_end_date < dates[-1]:
                final_start = min((d for d in all_dates_in_data if d > last_end_date), default=dates[-1])
                if final_start <= dates[-1]:
                     background_periods.append({'start': final_start, 'end': dates[-1], 'type': 'Sideways'})

        # 데이터는 있는데 추세 구간이 전혀 없는 경우 전체 Sideways
        elif len(dates) > 0:
             background_periods.append({'start': dates[0], 'end': dates[-1], 'type': 'Sideways'})

        # 배경색 shapes 생성
        colors = {"Uptrend": 'rgba(0, 255, 0, 0.08)', "Downtrend": 'rgba(255, 0, 0, 0.08)', "Sideways": 'rgba(100, 100, 100, 0.03)'}
        for period in background_periods:
            try:
                # fillcolor 확인 및 기본값 설정
                fill_color = colors.get(period['type'], colors['Sideways'])
                shapes_to_draw.append(
                    go.layout.Shape(
                        type="rect",
                        xref="x", yref="y",
                        x0=period['start'], y0=plot_y_min, # 계산된 y축 범위 사용
                        x1=period['end'], y1=plot_y_max,
                        fillcolor=fill_color,
                        layer="below", # 캔들 아래에
                        line_width=0,
                        name=f"{period['type']} BG" # 이름 추가 (디버깅용)
                    )
                )
            except Exception as shape_err:
                 logger.error(f"배경색 shape 생성 오류: {period}, 오류: {shape_err}")


    # 3.2 Peak/Valley 표시 (마커 제거, 문자만 표시)
    if 'show_js_extremums' in selected_options:
        peaks = peaks_valleys.get("js_peaks", [])
        if peaks:
            fig.add_trace(go.Scatter(
                x=[p['actual_date'] for p in peaks], 
                y=[p['value'] * 1.005 for p in peaks], # 위치 살짝 위로
                mode='text', 
                text=[f"P" for p in peaks], 
                textposition='top center', 
                textfont=dict(
                    family="Arial, sans-serif",
                    size=12,
                    color="black"
                ),
                name='JS Peak',
                hoverinfo='x+y+name'
            ))
        valleys = peaks_valleys.get("js_valleys", [])
        if valleys:
            fig.add_trace(go.Scatter(
                x=[v['actual_date'] for v in valleys], 
                y=[v['value'] * 0.995 for v in valleys], # 위치 살짝 아래로
                mode='text', 
                text=[f"V" for v in valleys], 
                textposition='bottom center', 
                textfont=dict(
                    family="Arial, sans-serif",
                    size=12,
                    color="black"
                ),
                name='JS Valley',
                hoverinfo='x+y+name'
            ))
    
    # Secondary Peak/Valley 텍스트 표시
    if 'show_sec_extremums' in selected_options:
        peaks = peaks_valleys.get("sec_peaks", [])
        if peaks:
            logger.info(f"Secondary Peaks 표시 ({len(peaks)}개)")
            # actual_date가 있는지 확인하고 변환
            valid_dates = [p['actual_date'] for p in peaks if 'actual_date' in p and p['actual_date'] is not None]
            if valid_dates:
                fig.add_trace(go.Scatter(
                    x=valid_dates, 
                    y=[p['value'] * 1.005 for p in peaks if 'actual_date' in p and p['actual_date'] is not None],
                    mode='text', 
                    text=[f"(p)" for p in peaks if 'actual_date' in p and p['actual_date'] is not None], 
                    textposition='top center', 
                    textfont=dict(
                        family="Arial, sans-serif",
                        size=12,
                        color="black"
                    ),
                    name='Sec Peak',
                    hoverinfo='x+y+name'
                ))
            else:
                logger.warning("Secondary Peaks에 valid dates가 없습니다.")
                
        valleys = peaks_valleys.get("sec_valleys", [])
        if valleys:
            logger.info(f"Secondary Valleys 표시 ({len(valleys)}개)")
            # actual_date가 있는지 확인하고 변환
            valid_dates = [v['actual_date'] for v in valleys if 'actual_date' in v and v['actual_date'] is not None]
            if valid_dates:
                fig.add_trace(go.Scatter(
                    x=valid_dates,
                    y=[v['value'] * 0.995 for v in valleys if 'actual_date' in v and v['actual_date'] is not None],
                    mode='text',
                    text=[f"(v)" for v in valleys if 'actual_date' in v and v['actual_date'] is not None],
                    textposition='bottom center',
                    textfont=dict(
                        family="Arial, sans-serif",
                        size=12,
                        color="black"
                    ),
                    name='Sec Valley',
                    hoverinfo='x+y+name'
                ))
            else:
                logger.warning("Secondary Valleys에 valid dates가 없습니다.")

    # 3.3 ZigZag 라인
    if 'show_zigzag' in selected_options:
        zigzag_points = trend_info.get("zigzag_points", [])
        if len(zigzag_points) > 1:
            # V023 시각화 함수의 로직 참조 (점 타입에 따라 색상 다르게 등)
            for i in range(len(zigzag_points) - 1):
                p1 = zigzag_points[i]
                p2 = zigzag_points[i+1]
                line_color = 'grey' # 기본 색상
                # (선택적) 추세에 따른 색상 변경 로직 추가 가능
                fig.add_trace(go.Scatter(
                    x=[p1['actual_date'], p2['actual_date']],
                    y=[p1['value'], p2['value']],
                    mode='lines', line=dict(color=line_color, width=1),
                    showlegend=False, hoverinfo='skip'
                ))

    # 3.4 완성된 패턴 표시 - 통합된 값 처리
    # --- DT와 DB 통합 처리 ---
    if 'show_dt_db' in selected_options:
        # DT 부분
        completed_dt = patterns.get("completed_dt", [])
        if completed_dt:
            dt_dates = [pd.Timestamp(p['date']) for p in completed_dt] # Timestamp로 변환
            fig.add_trace(go.Scatter(
                x=dt_dates,
                y=[data.loc[d]['Low'] * 0.99 for d in dt_dates], # 마커 위치
                mode='markers+text', marker=dict(symbol='diamond-tall', size=11, color='magenta'),
                text=[f"DT" for p in completed_dt],
                textposition='bottom center', name='DT Completed'
            ))
            # DT 박스 추가
            for dt in completed_dt:
                try:
                    start_peak = dt.get('start_peak')
                    if start_peak and 'actual_date' in start_peak:
                        start_date = pd.Timestamp(start_peak['actual_date'])
                        end_date = pd.Timestamp(dt['date'])
                        if start_date <= end_date and start_date in dates and end_date in dates:
                             slice_data = data.loc[start_date:end_date]
                             if not slice_data.empty:
                                 # 1. 시작일 바로 이전 날짜 찾기
                                 date_index = dates.get_loc(start_date)
                                 if date_index > 0:
                                     prev_date = dates[date_index - 1]
                                     adjusted_start = start_date - (start_date - prev_date) * 0.2
                                 else:
                                     adjusted_start = start_date - pd.Timedelta(days=1)  # 첫 날짜면 하루 전으로
                                 
                                 # 2. 종료일 바로 다음 날짜 찾기
                                 try:
                                     end_index = dates.get_loc(end_date)
                                     if end_index < len(dates) - 1:
                                         next_date = dates[end_index + 1]
                                         adjusted_end = end_date + (next_date - end_date) * 0.2
                                     else:
                                         adjusted_end = end_date + pd.Timedelta(days=1)  # 마지막 날짜면 하루 후로
                                 except:
                                     adjusted_end = end_date + pd.Timedelta(days=1)
                                 
                                 box_y0 = slice_data['Low'].min() * 0.995
                                 box_y1 = slice_data['High'].max() * 1.005
                                 shapes_to_draw.append(go.layout.Shape(
                                     type="rect", xref="x", yref="y",
                                     x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1,
                                     line=dict(color="#FF4560", width=1.5, dash=None),
                                     fillcolor="rgba(0,0,0,0)",
                                     layer="above"
                                 ))
                                 
                                 # 패턴 라벨 추가 - 박스 중앙 상단에 표시
                                 mid_point = start_date + (end_date - start_date) / 2
                                 fig.add_annotation(
                                     x=mid_point,
                                     y=box_y1,
                                     text="DT",
                                     font=dict(
                                         family="Arial, sans-serif",
                                         size=11,  # 14에서 11로 축소
                                         color="#FF4560"
                                     ),
                                     bordercolor="#FF4560",
                                     borderwidth=1.5,
                                     borderpad=3,  # 4에서 3으로 축소하여 패딩도 줄임
                                     bgcolor="rgba(255,255,255,0.8)",
                                     opacity=0.8,
                                     showarrow=False,
                                     yshift=5  # 10에서 5로 축소하여 위로 덜 올라가게 함
                                 )
                except Exception as box_err:
                     logger.warning(f"DT 박스 생성 오류: {box_err}")

        # DB 부분
        completed_db = patterns.get("completed_db", [])
        if completed_db:
             db_dates = [pd.Timestamp(p['date']) for p in completed_db]
             fig.add_trace(go.Scatter(
                 x=db_dates,
                 y=[data.loc[d]['High'] * 1.01 for d in db_dates],
                 mode='markers+text', marker=dict(symbol='diamond-wide', size=11, color='#00C853'),
                 text=[f"DB" for p in completed_db],
                 textposition='top center', name='DB Completed'
             ))
             # DB 박스 추가 (DT와 유사하게 구현)
             for db in completed_db:
                try:
                    start_valley = db.get('start_valley')
                    if start_valley and 'actual_date' in start_valley:
                        start_date = pd.Timestamp(start_valley['actual_date'])
                        end_date = pd.Timestamp(db['date'])
                        if start_date <= end_date and start_date in dates and end_date in dates:
                             slice_data = data.loc[start_date:end_date]
                             if not slice_data.empty:
                                 # 1. 시작일 바로 이전 날짜 찾기
                                 date_index = dates.get_loc(start_date)
                                 if date_index > 0:
                                     prev_date = dates[date_index - 1]
                                     adjusted_start = start_date - (start_date - prev_date) * 0.2
                                 else:
                                     adjusted_start = start_date - pd.Timedelta(days=1)  # 첫 날짜면 하루 전으로
                                 
                                 # 2. 종료일 바로 다음 날짜 찾기
                                 try:
                                     end_index = dates.get_loc(end_date)
                                     if end_index < len(dates) - 1:
                                         next_date = dates[end_index + 1]
                                         adjusted_end = end_date + (next_date - end_date) * 0.2
                                     else:
                                         adjusted_end = end_date + pd.Timedelta(days=1)  # 마지막 날짜면 하루 후로
                                 except:
                                     adjusted_end = end_date + pd.Timedelta(days=1)
                                 
                                 box_y0 = slice_data['Low'].min() * 0.995
                                 box_y1 = slice_data['High'].max() * 1.005
                                 shapes_to_draw.append(go.layout.Shape(
                                     type="rect", xref="x", yref="y",
                                     x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1,
                                     line=dict(color="#00C853", width=1.5, dash=None),
                                     fillcolor="rgba(0,0,0,0)",
                                     layer="above"
                                 ))
                                 
                                 # 패턴 라벨 추가 - 박스 중앙 상단에 표시
                                 mid_point = start_date + (end_date - start_date) / 2
                                 fig.add_annotation(
                                     x=mid_point,
                                     y=box_y1,
                                     text="DB",
                                     font=dict(
                                         family="Arial, sans-serif",
                                         size=11,  # 14에서 11로 축소
                                         color="#00C853"
                                     ),
                                     bordercolor="#00C853",
                                     borderwidth=1.5,
                                     borderpad=3,  # 4에서 3으로 축소
                                     bgcolor="rgba(255,255,255,0.8)",
                                     opacity=0.8,
                                     showarrow=False,
                                     yshift=5  # 10에서 5로 축소
                                 )
                except Exception as box_err:
                     logger.warning(f"DB 박스 생성 오류: {box_err}")

    # --- HS와 IHS 통합 처리 ---
    if 'show_hs_ihs' in selected_options:
        # HS 부분
        completed_hs = patterns.get("completed_hs", [])
        if completed_hs:
             hs_dates = [pd.Timestamp(p['date']) for p in completed_hs]
             fig.add_trace(go.Scatter(
                 x=hs_dates,
                 y=[data.loc[d]['Low'] * 0.99 for d in hs_dates],
                 mode='markers+text', marker=dict(symbol='star', size=11, color='#FF6B8A'),
                 text=[f"HS" for p in completed_hs],
                 textposition='bottom center', name='HS Completed'
             ))
             # HS 박스 및 넥라인 추가
             for hs in completed_hs:
                try:
                    # HS 패턴 요소들 확인
                    p1 = hs.get('P1')
                    v2 = hs.get('V2')
                    p2 = hs.get('P2') 
                    v3 = hs.get('V3')
                    p3 = hs.get('P3')
                     
                    # 패턴 시작과 끝 날짜 확인
                    if p1 and 'actual_date' in p1:
                        start_date = pd.Timestamp(p1['actual_date'])
                        end_date = pd.Timestamp(hs['date']) if 'date' in hs else pd.Timestamp(hs['actual_date'])
                         
                        if start_date <= end_date and start_date in dates and end_date in dates:
                            # 박스 영역 계산
                            slice_data = data.loc[start_date:end_date]
                            if not slice_data.empty:
                                # 1. 시작일 바로 이전 날짜 찾기
                                date_index = dates.get_loc(start_date)
                                if date_index > 0:
                                    prev_date = dates[date_index - 1]
                                    adjusted_start = start_date - (start_date - prev_date) * 0.2
                                else:
                                    adjusted_start = start_date - pd.Timedelta(days=1)  # 첫 날짜면 하루 전으로
                                
                                # 2. 종료일 바로 다음 날짜 찾기
                                try:
                                    end_index = dates.get_loc(end_date)
                                    if end_index < len(dates) - 1:
                                        next_date = dates[end_index + 1]
                                        adjusted_end = end_date + (next_date - end_date) * 0.2
                                    else:
                                        adjusted_end = end_date + pd.Timedelta(days=1)  # 마지막 날짜면 하루 후로
                                except:
                                    adjusted_end = end_date + pd.Timedelta(days=1)
                                
                                box_y0 = slice_data['Low'].min() * 0.995
                                box_y1 = slice_data['High'].max() * 1.005
                                
                                # 박스 추가 - 투명한 배경으로
                                shapes_to_draw.append(go.layout.Shape(
                                    type="rect", xref="x", yref="y",
                                    x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1,
                                    line=dict(color="#FF6B8A", width=1.5, dash=None),
                                    fillcolor="rgba(0,0,0,0)",
                                    layer="above"
                                ))
                                
                                # 패턴 라벨 추가 - 박스 중앙 상단에 표시
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(
                                    x=mid_point,
                                    y=box_y1,
                                    text="HS",
                                    font=dict(
                                        family="Arial, sans-serif",
                                        size=11,  # 14에서 11로 축소
                                        color="#FF6B8A"
                                    ),
                                    bordercolor="#FF6B8A",
                                    borderwidth=1.5,
                                    borderpad=3,  # 4에서 3으로 축소
                                    bgcolor="rgba(255,255,255,0.8)",
                                    opacity=0.8,
                                    showarrow=False,
                                    yshift=5  # 10에서 5로 축소
                                )
                             
                            # 넥라인 추가 (V2, V3 필요)
                            if v2 and v3 and 'value' in v2 and 'value' in v3 and 'actual_date' in v2 and 'actual_date' in v3:
                                v2_date = pd.Timestamp(v2['actual_date']); v3_date = pd.Timestamp(v3['actual_date'])
                                v2_val = v2['value']; v3_val = v3['value']
                                day_span = (v3_date - v2_date).days
                                if day_span == 0: day_span = 1
                                neck_slope = (v3_val - v2_val) / day_span
                                # 라인 그리기는 V2~V3 사이만
                                shapes_to_draw.append(go.layout.Shape(
                                    type="line", xref="x", yref="y",
                                    x0=v2_date, y0=v2_val,
                                    x1=v3_date, y1=v3_val,
                                    line=dict(color="#FF6B8A", width=1.2, dash="dash"),
                                    layer="above"
                                ))
                except Exception as hs_err:
                    logger.warning(f"HS 요소 생성 오류: {hs_err}")

        # IHS 부분
        completed_ihs = patterns.get("completed_ihs", [])
        if completed_ihs:
            ihs_dates = [pd.Timestamp(p['date']) for p in completed_ihs]
            fig.add_trace(go.Scatter(
                x=ihs_dates,
                y=[data.loc[d]['High'] * 1.01 for d in ihs_dates],
                mode='markers+text', marker=dict(symbol='star', size=11, color='#4CAF50'),
                text=[f"IHS" for p in completed_ihs],
                textposition='top center', name='IHS Completed'
            ))
            # IHS 박스 및 넥라인 추가
            for ihs in completed_ihs:
                try:
                    # IHS 패턴 요소들 확인
                    v1 = ihs.get('V1')
                    p2 = ihs.get('P2')
                    v2 = ihs.get('V2')
                    p3 = ihs.get('P3')
                    v3 = ihs.get('V3')
                    
                    # 패턴 시작과 끝 날짜 확인
                    if v1 and 'actual_date' in v1:
                        start_date = pd.Timestamp(v1['actual_date'])
                        end_date = pd.Timestamp(ihs['date']) if 'date' in ihs else pd.Timestamp(ihs['actual_date']) 
                        
                        if start_date <= end_date and start_date in dates and end_date in dates:
                            # 박스 영역 계산
                            slice_data = data.loc[start_date:end_date]
                            if not slice_data.empty:
                                # 1. 시작일 바로 이전 날짜 찾기
                                date_index = dates.get_loc(start_date)
                                if date_index > 0:
                                    prev_date = dates[date_index - 1]
                                    adjusted_start = start_date - (start_date - prev_date) * 0.2
                                else:
                                    adjusted_start = start_date - pd.Timedelta(days=1)  # 첫 날짜면 하루 전으로
                                
                                # 2. 종료일 바로 다음 날짜 찾기
                                try:
                                    end_index = dates.get_loc(end_date)
                                    if end_index < len(dates) - 1:
                                        next_date = dates[end_index + 1]
                                        adjusted_end = end_date + (next_date - end_date) * 0.2
                                    else:
                                        adjusted_end = end_date + pd.Timedelta(days=1)  # 마지막 날짜면 하루 후로
                                except:
                                    adjusted_end = end_date + pd.Timedelta(days=1)
                                
                                box_y0 = slice_data['Low'].min() * 0.995
                                box_y1 = slice_data['High'].max() * 1.005
                                
                                # 박스 추가 - 투명한 배경으로
                                shapes_to_draw.append(go.layout.Shape(
                                    type="rect", xref="x", yref="y",
                                    x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1,
                                    line=dict(color="#4CAF50", width=1.5, dash=None),
                                    fillcolor="rgba(0,0,0,0)",
                                    layer="above"
                                ))
                                
                                # 패턴 라벨 추가 - 박스 중앙 상단에 표시
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(
                                    x=mid_point,
                                    y=box_y1,
                                    text="IHS",
                                    font=dict(
                                        family="Arial, sans-serif",
                                        size=11,  # 14에서 11로 축소
                                        color="#4CAF50"
                                    ),
                                    bordercolor="#4CAF50",
                                    borderwidth=1.5,
                                    borderpad=3,  # 4에서 3으로 축소
                                    bgcolor="rgba(255,255,255,0.8)",
                                    opacity=0.8,
                                    showarrow=False,
                                    yshift=5  # 10에서 5로 축소
                                )
                            
                            # 넥라인 추가 (P2, P3 필요)
                            if p2 and p3 and 'value' in p2 and 'value' in p3 and 'actual_date' in p2 and 'actual_date' in p3:
                                p2_date = pd.Timestamp(p2['actual_date']); p3_date = pd.Timestamp(p3['actual_date'])
                                p2_val = p2['value']; p3_val = p3['value']
                                day_span = (p3_date - p2_date).days
                                if day_span == 0: day_span = 1
                                neck_slope = (p3_val - p2_val) / day_span
                                shapes_to_draw.append(go.layout.Shape(
                                    type="line", xref="x", yref="y",
                                    x0=p2_date, y0=p2_val,
                                    x1=p3_date, y1=p3_val,
                                    line=dict(color="#4CAF50", width=1.2, dash="dash"),
                                    layer="above"
                                ))
                except Exception as ihs_err:
                    logger.warning(f"IHS 요소 생성 오류: {ihs_err}")

    # --- 최종 레이아웃 업데이트 ---
    fig.update_layout(
        title_text=f'{ticker} Analysis ({period} / {interval}) - Updated',
        xaxis_title='Date',
        yaxis_title='Price',
        xaxis_rangeslider_visible=False,
        height=800,  # 700에서 800으로 증가
        shapes=shapes_to_draw, # 계산된 shapes 적용
        yaxis_range=[plot_y_min, plot_y_max], # Y축 범위 적용
        hovermode='x unified', # 호버 모드 설정
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), # 범례 위치
        dragmode='pan', # <<< 마우스 드래그 기본 모드를 'pan'(이동)으로 설정!
        margin=dict(l=50, r=50, t=50, b=50)  # 마진 값 축소하여 그래프 영역 확대
    )

    plot_end_time = time.time()
    
    # 로그 메시지 - 실행 시간 계산 부분 안전하게 처리
    if 'analysis_end_time' in locals():
        logger.info(f"그래프 생성 완료: 카테고리={category}, 티커={ticker}, 기간={period}, 타임프레임={interval} ({plot_end_time - analysis_end_time:.2f}초)")
    else:
        logger.info(f"그래프 생성 완료: 카테고리={category}, 티커={ticker} (체크리스트 변경)")

    return fig

# === 앱 실행 ===
if __name__ == '__main__':
    logger.info("Dash 앱 서버를 시작합니다...")
    # host='0.0.0.0' 추가 시 외부에서도 접속 가능 (방화벽 설정 필요)
    # Dash v3에서는 app.run_server 대신 app.run을 사용합니다.
    try:
        app.run(debug=True, port=8051, use_reloader=False)
    except TypeError:
        # 일부 Dash/Flask 버전에서는 use_reloader 인자를 지원하지 않을 수 있으므로
        # 안전하게 재시도합니다.
        app.run(debug=True, port=8051)