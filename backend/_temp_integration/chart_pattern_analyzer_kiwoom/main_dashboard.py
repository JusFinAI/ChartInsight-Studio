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

# 한국 주식 데이터 임포트 (V02)
from korean_stock_loader import (
    get_category_options, 
    get_symbols_by_category, 
    get_interval_options, 
    get_default_values
)



# --- 로거 설정 (모듈별 logs 디렉토리 사용) ---
from pathlib import Path
MODULE_LOG_DIR = Path(__file__).resolve().parent / 'logs'
MODULE_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 현재 날짜를 기반으로 로그 파일 이름 생성 (module-local)
current_date = datetime.now().strftime('%Y%m%d%H%M')
log_filename = MODULE_LOG_DIR / f'dash_app_{current_date}.log'

# 로거 설정 (module-local log file)
file_handler = logging.FileHandler(str(log_filename), mode='w')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
logger.setLevel(logging.INFO)
logger.info(f"로그 파일 경로: {str(log_filename)}")
# -----------------------------------------------------------

# --- 분석 엔진 모듈 import ---
# Load root .env into environment before importing DB/backed modules
try:
    from pathlib import Path as _Path
    _root_candidate = _Path(__file__).resolve().parents[3] if len(_Path(__file__).resolve().parents) >= 4 else _Path(__file__).resolve().parents[-1]
    _env_path = _root_candidate / '.env'
    if _env_path.exists():
        try:
            from dotenv import load_dotenv as _load_dotenv
            _load_dotenv(dotenv_path=str(_env_path))
            logger.info(f'Loaded root .env from {_env_path}')
        except Exception as _e:
            logger.warning(f'Failed to load root .env: {_e}')
    else:
        logger.info(f'No root .env found at {_env_path}')
except Exception as _e:
    logger.warning(f'.env loader skipped due to error: {_e}')

from analysis_engine import run_full_analysis, download_data

# 한국 주식 로더에서 데이터 가져오기
CATEGORY_OPTIONS = get_category_options()
SYMBOLS_BY_CATEGORY = get_symbols_by_category()
INTERVAL_OPTIONS = get_interval_options()
DEFAULT_CATEGORY, DEFAULT_TICKER, DEFAULT_INTERVAL = get_default_values()

# === Dash 앱 초기화 ===
app = dash.Dash(__name__, suppress_callback_exceptions=True) # 콜백 예외 처리 활성화
app.title = "V02 Korean Stock Pattern Analysis"

# === 앱 레이아웃 정의 ===
app.layout = html.Div([
    html.H1("Korean Stock Pattern Analysis V02 (Kiwoom API)", style={'marginBottom': '10px', 'marginTop': '5px'}),  # 마진 축소

    # --- 입력 컨트롤 ---
    html.Div([
        # 카테고리 드롭다운 (KOSPI/KOSDAQ만)
        dcc.Dropdown(
            id='dropdown-category',
            options=CATEGORY_OPTIONS,
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
        # Period 드롭다운 제거됨 (키움증권에서 최대 데이터 수집)
        dcc.Dropdown(
            id='dropdown-interval',
            options=INTERVAL_OPTIONS,
            value=DEFAULT_INTERVAL, # 기본값
            clearable=False,
            style={'width': '150px'}  # 130px에서 150px로 확장
        ),
        html.Button('Run Analysis', id='button-run-analysis', n_clicks=0,
                    style={'height': '36px', 'width': '150px', 'margin-left': '10px'})  # 버튼 너비 확장
    ], style={'display': 'flex', 'gap': '15px', 'marginBottom': '10px', 'alignItems': 'center'}),  # 간격 확장, 요소 수직 정렬

    # --- 시각화 옵션 컨트롤 (V01과 100% 동일) ---
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

    # --- 결과 표시 영역 (V01과 100% 동일한 Plotly 설정) ---
    dcc.Loading( # 로딩 컴포넌트
        id="loading-graph",
        type="circle",
        children=[
            dcc.Graph(
                id='analysis-graph',
                figure=go.Figure(layout={'height': 800}),  # 그래프 높이 700에서 800으로 증가
                # --- config 속성 추가 (V01과 동일) ---
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
    # --- Input/State 수정 (Period 제거) ---
    Input('button-run-analysis', 'n_clicks'), # 버튼 Input
    Input('checklist-options', 'value'),      # <<< 체크리스트 Input으로 변경!
    State('dropdown-ticker', 'value'),        # dropdown-ticker로 변경
    State('dropdown-interval', 'value'),      # Interval은 State
    State('dropdown-category', 'value'),      # 카테고리 정보도 State로 추가
    prevent_initial_call=True
)
def update_graph(n_clicks, selected_options, ticker, interval, category):
    """
    사용자 입력 및 선택 옵션에 따라 데이터를 분석하고 그래프를 업데이트하는 콜백 함수.
    """
    ctx = dash.callback_context
    triggered_id = ctx.triggered_id if ctx.triggered_id else 'No trigger'
    logger.info(f"Callback triggered by: {triggered_id}")
    logger.info(f"Current selected options: {selected_options}") # 선택된 옵션 로깅 활성화

    # 체크리스트만 변경된 경우 감지
    is_checklist_trigger = triggered_id == 'checklist-options'

    # 성능 측정 시작
    start_time = time.time()
    
    # 체크리스트 옵션 처리 - None 체크 추가
    if selected_options is None:
        selected_options = []

    # 이미 분석된 결과가 있고 체크리스트만 변경된 경우, 데이터 재분석 없이 그래프만 업데이트
    if is_checklist_trigger and hasattr(update_graph, 'last_analysis_results') and hasattr(update_graph, 'last_data'):
        logger.info(f"[CHECKLIST] 체크리스트 옵션 변경으로 그래프만 업데이트합니다. 카테고리: {category}, 티커: {ticker}")
        result = update_graph.last_analysis_results
        data = update_graph.last_data
        
        # 체크리스트 변경 시에도 시간 측정을 위한 변수 초기화
        data_start_time = start_time
        data_end_time = start_time  # 데이터 로드 없음
        analysis_start_time = start_time
        analysis_end_time = start_time  # 분석 없음
    else:
        # 버튼 클릭으로 새로운 분석을 시작하는 경우
        logger.info(f"분석 시작 트리거: 카테고리={category}, 티커={ticker}, 기간=MAX, 타임프레임={interval}")

        # === 데이터 다운로드 ===
        try:
                data_start_time = time.time()
                # Period 파라미터 제거 (키움증권에서 최대 데이터 수집)
                data = download_data(ticker, period=None, interval=interval)
                data_end_time = time.time()
            
                if data is None or data.empty:
                    logger.error("데이터 다운로드 실패 또는 빈 데이터셋")
                    error_fig = go.Figure()
                    error_fig.add_annotation(text="데이터 다운로드 실패", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
                    error_fig.update_layout(title="Error: Failed to download data", height=800)
                    return error_fig
            
                logger.info(f"데이터 다운로드 완료: {len(data)}개 캔들 ({data_end_time - data_start_time:.2f}초)")
            
        except Exception as e:
            logger.error(f"데이터 다운로드 중 오류: {e}")
            error_fig = go.Figure()
            error_fig.add_annotation(text=f"다운로드 오류: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            error_fig.update_layout(title="Error: Download failed", height=800)
            return error_fig

        # === 데이터 분석 ===
        try:
            analysis_start_time = time.time()
            # Period 파라미터 제거
            result = run_full_analysis(data, ticker=ticker, period="MAX", interval=interval)
            analysis_end_time = time.time()
            
            logger.info(f"분석 완료 ({analysis_end_time - analysis_start_time:.2f}초)")
                        
            # 결과 저장 (체크리스트 변경 시 재사용)
            update_graph.last_analysis_results = result
            update_graph.last_data = data
            
        except Exception as e:
            logger.error(f"분석 중 오류: {e}")
            error_fig = go.Figure()
            error_fig.add_annotation(text=f"분석 오류: {str(e)}", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
            error_fig.update_layout(title="Error: Analysis failed", height=800)
            return error_fig

    # === 이하 모든 시각화 코드는 V01과 100% 동일하게 유지 ===
    # 시각화 시작 시간 측정
    plot_start_time = time.time()

    # === 단일 Figure 생성 (V030 방식) ===
    fig = go.Figure()

    # 결과 검증
    if 'error' in result:
        logger.warning(f"분석 결과에 오류: {result['error']}")
        # 오류가 있더라도 기본 데이터로 차트 그리기 시도
    
    # --- 기본 캔들스틱 추가 (V030과 완전 동일) ---
    base_data = result.get("base_data", {})
    dates = base_data.get("dates") # DatetimeIndex
    
    # 날짜 데이터 검증
    if dates is None or len(dates) == 0:
        logger.warning("dates가 비어있거나 None입니다!")
    
    if dates is None or len(dates) == 0:
        logger.error("날짜 데이터가 없습니다.")
        error_fig = go.Figure()
        error_fig.add_annotation(text="날짜 데이터 없음", xref="paper", yref="paper", x=0.5, y=0.5, showarrow=False)
        error_fig.update_layout(title="Error: No date data", height=800)
        return error_fig
    
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
    peaks_valleys = result.get("peaks_valleys", {})
    trend_info = result.get("trend_info", {})
    patterns = result.get("patterns", {})

    # Y축 범위 계산 (요소 추가 전에)
    y_min = data['Low'].min()
    y_max = data['High'].max()
    y_range = y_max - y_min
    y_margin = y_range * 0.03  # 0.05에서 0.03으로 축소하여 위아래 마진을 줄임
    plot_y_min = max(0, y_min - y_margin)
    plot_y_max = y_max + y_margin

    # 추가될 도형들을 위한 리스트
    shapes_to_draw = []

    # === 옵션별 시각화 (V01과 동일) ===
    # 3.1 추세 배경색
    if 'show_trend_background' in selected_options:
        trend_periods = trend_info.get("periods", [])
        # 추세 배경색 표시
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
                # 배경색 shape 추가 완료
            except Exception as shape_err:
                logger.error(f"배경색 shape 생성 오류: {period}, 오류: {shape_err}")

    # Peak/Valley 표시 (마커 제거, 문자만 표시) - V030 방식
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

    # Secondary Peak/Valley 텍스트 표시 - V030 방식
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


    # ZigZag 라인 - V030 방식
    if 'show_zigzag' in selected_options:
        zigzag_points = trend_info.get("zigzag_points", [])
        if len(zigzag_points) > 1:
            # V030 시각화 함수의 로직 참조 (점 타입에 따라 색상 다르게 등)
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
                                        size=11,
                                        color="#00C853"
                                    ),
                                    bordercolor="#00C853",
                                    borderwidth=1.5,
                                    borderpad=3,
                                    bgcolor="rgba(255,255,255,0.8)",
                                    opacity=0.8,
                                    showarrow=False,
                                    yshift=5
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
                                        size=11,
                                        color="#4CAF50"
                                    ),
                                    bordercolor="#4CAF50",
                                    borderwidth=1.5,
                                    borderpad=3,
                                    bgcolor="rgba(255,255,255,0.8)",
                                    opacity=0.8,
                                    showarrow=False,
                                    yshift=5
                                )
                            # 넥라인 추가 (P2, P3 필요)
                            if p2 and p3 and 'value' in p2 and 'value' in p3 and 'actual_date' in p2 and 'actual_date' in p3:
                                p2_date = pd.Timestamp(p2['actual_date']); p3_date = pd.Timestamp(p3['actual_date'])
                                p2_val = p2['value']; p3_val = p3['value']
                                day_span = (p3_date - p2_date).days
                                if day_span == 0: day_span = 1
                                neck_slope = (p3_val - p2_val) / day_span
                                # 라인 그리기는 P2~P3 사이만
                                shapes_to_draw.append(go.layout.Shape(
                                    type="line", xref="x", yref="y",
                                    x0=p2_date, y0=p2_val,
                                    x1=p3_date, y1=p3_val,
                                    line=dict(color="#4CAF50", width=1.2, dash="dash"),
                                    layer="above"
                                ))
                except Exception as ihs_err:
                    logger.warning(f"IHS 요소 생성 오류: {ihs_err}")

    # === shapes 적용 ===
    # Shapes 적용

    # === 최종 레이아웃 업데이트 (V01과 동일) ===
    fig.update_layout(
        title_text=f'{ticker} Analysis (MAX / {interval}) - Updated',  # Period 제거
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
    try:
        total_time = time.time() - start_time
        data_time = data_end_time - data_start_time if 'data_end_time' in locals() and 'data_start_time' in locals() else 0
        analysis_time = analysis_end_time - analysis_start_time if 'analysis_end_time' in locals() and 'analysis_start_time' in locals() else 0
        plot_time = plot_end_time - plot_start_time
        
        logger.info(f"작업 완료 - 총 시간: {total_time:.2f}초 (데이터: {data_time:.2f}초, 분석: {analysis_time:.2f}초, 시각화: {plot_time:.2f}초)")
    except Exception as time_err:
        logger.warning(f"시간 계산 오류: {time_err}")
    
    return fig

# === 앱 실행 ===
if __name__ == '__main__':
    logger.info("Dash 앱 서버를 시작합니다...")
    print("🌐 브라우저에서 http://localhost:8050 으로 접속하세요!")
    # host='0.0.0.0' 추가 시 외부에서도 접속 가능 (방화벽 설정 필요)
    # Dash v3에서는 app.run_server 대신 app.run을 사용합니다.
    try:
        app.run(debug=True, host='127.0.0.1', port=8050, use_reloader=False)
    except TypeError:
        # 일부 Dash/Flask 버전에서는 use_reloader 인자를 지원하지 않을 수 있으므로 재시도
        app.run(debug=True, host='127.0.0.1', port=8050)