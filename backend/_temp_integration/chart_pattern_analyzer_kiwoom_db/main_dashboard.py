# 프로젝트 루트와 `backend` 패키지가 `sys.path`에 포함되도록 설정합니다.
# 파일을 직접 실행하거나 에디터의 실행 버튼으로 실행할 때도 절대 import가 작동하도록 합니다.
import sys
from pathlib import Path

def ensure_project_paths(load_dotenv_flag: bool = True):
    """프로젝트 루트, backend 및 패키지 디렉토리를 `sys.path`에 추가하고
    필요 시 최상위 `.env` 파일을 로드합니다.

    반환값: (ROOT, BACKEND_DIR, SUBPROJECT_DIR)
    """
    import importlib
    ROOT = Path(__file__).resolve().parents[3]
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    BACKEND_DIR = ROOT / "backend"
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))

    SUBPROJECT_DIR = Path(__file__).resolve().parent
    if str(SUBPROJECT_DIR) not in sys.path:
        sys.path.insert(0, str(SUBPROJECT_DIR))

    if load_dotenv_flag:
        try:
            dotenv = importlib.import_module('dotenv')
            _load = getattr(dotenv, 'load_dotenv', None)
        except Exception:
            _load = None
        ROOT_ENV = ROOT / '.env'
        if _load and ROOT_ENV.exists():
            try:
                _load(ROOT_ENV.as_posix())
            except Exception:
                pass

    return ROOT, BACKEND_DIR, SUBPROJECT_DIR

# 경로 설정 및 .env 초기 로드
ROOT, BACKEND_DIR, SUBPROJECT_DIR = ensure_project_paths()


# --- DB 기반 래퍼: 원본 download_data 및 run_full_analysis을 DB 분석기로 교체
from analysis import run_analysis_from_df
from backend.app.database import SessionLocal
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.data_loader import load_candles_from_db
import pandas as pd
from dash import dcc, html, Input, Output, State, callback, ALL
import json
import ast
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 독립 실행 레이아웃용 한국 종목 로더 헬퍼
from korean_stock_loader import (
    get_category_options, get_symbols_by_category, get_interval_options, get_default_values
)

# 드롭다운 상수 초기화
CATEGORY_OPTIONS = get_category_options()
SYMBOLS_BY_CATEGORY = get_symbols_by_category()
INTERVAL_OPTIONS = get_interval_options()
DEFAULT_CATEGORY, DEFAULT_TICKER, DEFAULT_INTERVAL = get_default_values()

# 중복된 함수는 제거되었으며, 실제로 사용되는 구현은 파일 하단에 위치합니다

#!/usr/bin/env python3
"""Dash launcher that reuses the original Kiwoom Dash app UI but sources data
from the DB-based analyzer (`chart_pattern_analyzer_kiwoom_db.analysis`).

This script monkeypatches the `download_data` and `run_full_analysis` symbols
in the original `main_dashboard` module so the UI and callbacks remain
identical while data comes from the DB.
"""
import sys
from importlib import import_module
import logging
from pathlib import Path
import pandas as pd
import os
# Dynamically import python-dotenv if available to avoid static import errors in editors
load_dotenv = None
try:
    import importlib
    dotenv = importlib.import_module('dotenv')
    load_dotenv = getattr(dotenv, 'load_dotenv', None)
except Exception:
    load_dotenv = None


from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import configure_logger


# create module-specific logs directory path (creation delegated to configure_logger)
MODULE_LOG_DIR = SUBPROJECT_DIR / 'logs'

# 1. 대시보드 로거 설정
dashboard_logger = configure_logger("chartinsight.dashboard", log_file_prefix="dash_app_db", logs_dir=MODULE_LOG_DIR, level=logging.INFO)

# 2. 공통 백엔드 로거 설정 (patterns.py, trend.py, run_full_analysis.py 등에서 사용)
# 이 로거는 backend_events.log 파일을 생성합니다
backend_logger = configure_logger(
    logger_name="backend",
    log_file_prefix="backend_events",
    logs_dir=MODULE_LOG_DIR,
    level=logging.INFO,
)

dashboard_logger.info("🚀 Logging system initialized successfully")
backend_logger.info("🔧 Backend common logger configured for patterns.py, trend.py, run_full_analysis.py")

# backend 모듈들의 불필요한 로그 파일 생성 방지
logging.getLogger('chartinsight-api.data_loader').disabled = True
logging.getLogger('chartinsight-api.pattern-analysis').disabled = True  
logging.getLogger('TrendDetector').disabled = True
logger = dashboard_logger  # 위에서 설정한 로거 사용

# 단계별 복원 1단계: 독립 실행 가능한 `app`과 기본 `update_graph`를 준비합니다
# 이 콜백은 DB 래퍼를 통해 데이터를 로드하고 캔들 차트를 렌더링합니다.
# 이후 단계에서 트렌드 배경, ZigZag, 피크/밸리, 패턴 박스 등을 차례대로 복원합니다.

# --- Dash 앱 초기화 (독립 실행 모드) ---
import dash
app = dash.Dash(__name__, suppress_callback_exceptions=True)
app.title = "V02 Korean Stock Pattern Analysis (DB standalone)"

# 원본과 동일한 컨트롤을 가지도록 최소 레이아웃을 복사합니다
app.layout = html.Div([
    html.H1("Korean Stock Pattern Analysis V02 (DB)", style={'marginBottom': '10px', 'marginTop': '5px'}),
    html.Div([
        dcc.Dropdown(id='dropdown-category', options=[{'label':c['label'],'value':c['value']} for c in CATEGORY_OPTIONS], value=DEFAULT_CATEGORY, clearable=False, style={'width':'180px'}),
        dcc.Dropdown(id='dropdown-ticker', options=SYMBOLS_BY_CATEGORY.get(DEFAULT_CATEGORY, []), value=DEFAULT_TICKER, clearable=False, style={'width':'250px'}),
        dcc.Dropdown(id='dropdown-interval', options=INTERVAL_OPTIONS, value=DEFAULT_INTERVAL, clearable=False, style={'width':'150px'}),
        html.Button('Run Analysis', id='button-run-analysis', n_clicks=0, style={'height':'36px','width':'150px','margin-left':'10px'})
    ], style={'display':'flex','gap':'15px','marginBottom':'10px','alignItems':'center'}),
    html.Div([
        html.H3('Display Options:', style={'marginBottom':'5px','marginTop':'5px'}),
        dcc.Checklist(id='checklist-options', options=[
            {'label':'JS Peaks/Valleys','value':'show_js_extremums'},
            {'label':'Secondary Peaks/Valleys','value':'show_sec_extremums'},
            {'label':'Trend Background','value':'show_trend_background'},
            {'label':'ZigZag Line','value':'show_zigzag'},
            {'label':'Double Bottom/Top','value':'show_dt_db'},
            {'label':'(Inv) Head & Shoulder','value':'show_hs_ihs'},
        ], value=['show_trend_background'], inline=True, style={'display':'flex','flexWrap':'wrap','gap':'10px','marginBottom':'5px'})
    ]),
    # Indicator controls
    html.Div([
        html.H3('Indicators:', style={'marginBottom':'5px','marginTop':'5px'}),
        dcc.Checklist(id='checklist-indicators', options=[
            {'label':'SMA','value':'SMA'},
            {'label':'EMA','value':'EMA'},
            {'label':'RSI','value':'RSI'},
            {'label':'MACD','value':'MACD'},
            {'label':'Bollinger','value':'BBANDS'},
            {'label':'ATR','value':'ATR'},
            {'label':'OBV','value':'OBV'},
        ], value=[], inline=True, style={'display':'flex','flexWrap':'wrap','gap':'10px','marginBottom':'5px'})
    ]),
    # Dynamic indicator remove buttons (one button per dynamic row)
    html.Div(id='dynamic-ind-buttons', style={'marginTop':'8px','marginBottom':'8px'}),
    dcc.Loading(id='loading-graph', type='circle', children=[dcc.Graph(id='analysis-graph', figure=go.Figure(layout={'height':800, 'dragmode':'pan'}), config={'scrollZoom':True})])
], style={'padding':'10px'})


@callback(Output('dropdown-ticker','options'), Output('dropdown-ticker','value'), Input('dropdown-category','value'))
def update_ticker_options(selected_category):
    options = SYMBOLS_BY_CATEGORY.get(selected_category, [])
    default_value = options[0]['value'] if options else ''
    return options, default_value


@callback(Output('dynamic-ind-buttons','children'), Input('checklist-indicators','value'))
def render_dynamic_buttons(selected_indicators):
    # create small 'x' buttons for dynamic indicators and place them above the graph
    dyn = [i for i in (selected_indicators or []) if i in ('RSI', 'MACD', 'ATR', 'OBV')]
    children = []
    for ind in dyn:
        btn = html.Button(
            f"✖ {ind}",
            id={'type':'dyn-btn','index':ind},
            n_clicks=0,
            style={'marginRight':'8px','backgroundColor':'#eee','border':'1px solid #bbb','borderRadius':'4px','padding':'4px 8px','fontSize':'12px'}
        )
        children.append(btn)
    return children


@callback(Output('checklist-indicators','value'), Input({'type':'dyn-btn','index':ALL}, 'n_clicks'), State('checklist-indicators','value'), prevent_initial_call=True)
def handle_dyn_button_click(n_clicks_list, checklist_values):
    # determine which dynamic button was clicked via callback context and remove it from checklist
    ctx = dash.callback_context
    # Ignore cases where no button was actually clicked (e.g. buttons were recreated => n_clicks default 0)
    if not n_clicks_list or all((n is None or n == 0) for n in n_clicks_list):
        return dash.no_update
    if not ctx.triggered:
        return dash.no_update
    # only proceed if at least one button reports a positive click count
    positive_clicks = [((i or 0)) for i in n_clicks_list]
    if not any(c > 0 for c in positive_clicks):
        return dash.no_update

    # determine which dyn button corresponds to the clicked input by index
    # the order of n_clicks_list corresponds to the order of dynamic buttons,
    # which follows the order of checklist_values filtered for dynamic inds
    dyn = [v for v in (checklist_values or []) if v in ('RSI', 'MACD', 'ATR', 'OBV')]
    if not dyn:
        return dash.no_update
    # pick the index with the largest click count (most likely the most recently clicked)
    try:
        idx_clicked = int(max(range(len(positive_clicks)), key=lambda i: positive_clicks[i]))
    except Exception:
        return dash.no_update
    if idx_clicked < 0 or idx_clicked >= len(dyn):
        return dash.no_update
    ind = dyn[idx_clicked]
    new_vals = [v for v in checklist_values if v != ind]
    return new_vals


@callback(Output('analysis-graph','figure'), Input('button-run-analysis','n_clicks'), Input('checklist-options','value'), Input('checklist-indicators','value'), State('dropdown-ticker','value'), State('dropdown-interval','value'), State('dropdown-category','value'), prevent_initial_call=True)
def update_graph(n_clicks, selected_options, selected_indicators, ticker, interval, category):
    """Graph updater with caching: when only the checklist changes, reuse
    last analysis results and data to avoid re-running expensive analysis.
    """
    import pandas as pd  # 함수 내 import로 범위 문제 해결
    logger.info(f"=== Run Analysis 버튼 클릭: {ticker}, interval={interval} ===")
    
    if selected_options is None:
        selected_options = []

    # 트리거 발생 원인을 안전하게 판별
    ctx = dash.callback_context
    triggered_id = 'No trigger'
    try:
        if ctx.triggered:
            prop = ctx.triggered[0].get('prop_id', '')
            triggered_id = prop.split('.')[0] if prop else 'No trigger'
    except Exception:
        triggered_id = getattr(ctx, 'triggered_id', 'No trigger')

    is_checklist_trigger = (triggered_id == 'checklist-options' or triggered_id == 'checklist-indicators')

    # If checklist only changed and we have cached results, reuse them
    if is_checklist_trigger and hasattr(update_graph, 'last_analysis_results') and hasattr(update_graph, 'last_data'):
        result = update_graph.last_analysis_results
        df = update_graph.last_data
        if df is None or (hasattr(df, 'empty') and df.empty):
            fig_err = go.Figure(); fig_err.add_annotation(text='Cached data 없음', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False); fig_err.update_layout(title='No data', height=800); return fig_err
        # Create figure with dynamic rows based on selected indicators order
        def create_dynamic_figure(selected_inds):
            dyn = [i for i in (selected_inds or []) if i in ('RSI', 'MACD', 'ATR', 'OBV')]
            num_dyn = len(dyn)
            # base heights: price 0.6, volume 0.12, remaining 0.28 split
            row_heights = [0.6, 0.12]
            if num_dyn > 0:
                per = 0.28 / num_dyn
                row_heights.extend([per] * num_dyn)
            # total rows
            total_rows = 2 + num_dyn
            fig_local = make_subplots(rows=total_rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_heights)
            return fig_local, dyn

        fig, dynamic_inds = create_dynamic_figure(selected_indicators)
        try:
            # 각 캔들에 대한 hover 텍스트 준비 (포맷팅, 나노초 제외)
            hovertexts = [
                f"<b>{d.strftime('%Y-%m-%d %H:%M')}</b><br>Open: {o:,.0f}<br>High: {h:,.0f}<br>Low: {l:,.0f}<br>Close: {c:,.0f}"
                for d, o, h, l, c in zip(df.index, df['Open'], df['High'], df['Low'], df['Close'])
            ]
            fig.add_trace(go.Candlestick(
                x=df.index, 
                open=df['Open'], 
                high=df['High'], 
                low=df['Low'], 
                close=df['Close'], 
                name=ticker,
                hoverinfo='text',
                hovertext=hovertexts,
                hoverlabel=dict(
                    bgcolor='white',
                    bordercolor='black',
                    font=dict(size=12, color='black')
                )
            ), row=1, col=1)
            # Ensure Volume bar is added in cached-path as well
            try:
                vols = df['Volume'].fillna(0).tolist()
                closes = df['Close'].tolist()
                vol_colors = []
                for i in range(len(vols)):
                    if i == 0:
                        vol_colors.append('lightgrey')
                    else:
                        vol_colors.append('green' if closes[i] >= closes[i-1] else 'red')
                fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=vol_colors), row=2, col=1)
            except Exception:
                pass
        except Exception:
            # 폴백: 빈 Figure 반환(실행 흐름은 일관되게 유지)
            fig = go.Figure()
        finally:
            # Ensure default interaction mode is panning for cached-path figure
            try:
                fig.update_layout(dragmode='pan')
            except Exception:
                pass
    else:
        # 신규 실행: 데이터 다운로드 및 분석 수행
        try:
            logger.info(f"데이터 로드 시작: {ticker}, interval={interval}")
            db = SessionLocal()
            try:
                # KST(Asia/Seoul)로 반환하도록 고정
                df = load_candles_from_db(db, stock_code=ticker, timeframe=interval, period=None, limit=None, tz='Asia/Seoul')
            finally:
                db.close()
            logger.info(f"데이터 로드 완료: {len(df) if df is not None and not df.empty else 0}개 캔들")
        except Exception as e:
            logger.error(f"데이터 로드 실패: {e}")
            fig_err = go.Figure(); fig_err.add_annotation(text=f'다운로드 오류: {e}', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False); fig_err.update_layout(title='Error: Download failed', height=800); return fig_err

        if df is None or df.empty:
            fig_err = go.Figure(); fig_err.add_annotation(text='데이터 없음', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False); fig_err.update_layout(title='No data', height=800); return fig_err

        # 캔들스틱 + 서브플롯 생성 (dynamic rows)
        def create_dynamic_figure(selected_inds):
            dyn = [i for i in (selected_inds or []) if i in ('RSI', 'MACD', 'ATR')]
            num_dyn = len(dyn)
            row_heights = [0.6, 0.12]
            if num_dyn > 0:
                per = 0.28 / num_dyn
                row_heights.extend([per] * num_dyn)
            total_rows = 2 + num_dyn
            fig_local = make_subplots(rows=total_rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=row_heights)
            return fig_local, dyn

        fig, dynamic_inds = create_dynamic_figure(selected_indicators)
        try:
            # prepare hover text for each candle (formatted, no nanoseconds)
            hovertexts = [
                f"<b>{d.strftime('%Y-%m-%d %H:%M')}</b><br>Open: {o:,.0f}<br>High: {h:,.0f}<br>Low: {l:,.0f}<br>Close: {c:,.0f}"
                for d, o, h, l, c in zip(df.index, df['Open'], df['High'], df['Low'], df['Close'])
            ]
            fig.add_trace(go.Candlestick(
                x=df.index, 
                open=df['Open'], 
                high=df['High'], 
                low=df['Low'], 
                close=df['Close'], 
                name=ticker,
                hoverinfo='text',
                hovertext=hovertexts,
                hoverlabel=dict(
                    bgcolor='white',
                    bordercolor='black',
                    font=dict(size=12, color='black')
                )
            ), row=1, col=1)

            # Volume bar on row 2 (always show)
            # color volume bars by whether close >= previous close
            vols = df['Volume'].fillna(0).tolist()
            closes = df['Close'].tolist()
            vol_colors = []
            for i in range(len(vols)):
                if i == 0:
                    vol_colors.append('lightgrey')
                else:
                    vol_colors.append('green' if closes[i] >= closes[i-1] else 'red')
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=vol_colors), row=2, col=1)
        except Exception as e:
            # fallback: if preparing hovertexts/volume fails, create empty figure to keep flow consistent
            logger.warning(f"Failed preparing base traces (candles/volume): {e}")
            fig = go.Figure()

        # 분석 실행 및 결과 캐시
        try:
            logger.info(f"패턴 분석 시작: {ticker}")
            # 중간 래퍼 제거: 직접 분석 함수 호출
            result = run_analysis_from_df(df, ticker=ticker, period="MAX", interval=interval)
            update_graph.last_analysis_results = result
            update_graph.last_data = df
            logger.info(f"패턴 분석 완료: {ticker}")
        except Exception as e:
            logger.error(f"분석 실패: {e}")
            fig.update_layout(title_text=f"{ticker} (DB) - Candles", xaxis_title='Date', yaxis_title='Price', height=800, xaxis_rangeslider_visible=False)
            return fig

    # --- Indicator computation ---
    from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.indicators import compute_indicators
    # Deterministic: always compute indicators if any selected. Do not swallow exceptions.
    spec = {}
    # default spec could be extended; for now map simple selections
    if 'SMA' in (selected_indicators or []):
        spec.setdefault('sma', [20, 50])
    if 'EMA' in (selected_indicators or []):
        spec.setdefault('ema', [20])
    if 'RSI' in (selected_indicators or []):
        spec.setdefault('rsi', [14])
    if 'MACD' in (selected_indicators or []):
        spec.setdefault('macd', [{'fast':12,'slow':26,'signal':9}])
    if 'BBANDS' in (selected_indicators or []):
        spec.setdefault('bbands', [{'length':20,'std':2}])
    if 'ATR' in (selected_indicators or []):
        spec.setdefault('atr', [14])
    if 'OBV' in (selected_indicators or []):
        spec.setdefault('obv', True)

    indicators_res = compute_indicators(df, spec=spec)
    indicators_series = indicators_res.get('series', {})

    peaks_valleys = result.get("peaks_valleys", {})
    trend_info = result.get("trend_info", {})
    patterns = result.get("patterns", {})

    # 디버그: 마커/주석 누락 진단을 위해 극점 수를 로깅
    try:
        js_count = len(peaks_valleys.get('js_peaks', []))
        jv_count = len(peaks_valleys.get('js_valleys', []))
        sp_count = len(peaks_valleys.get('sec_peaks', []))
        sv_count = len(peaks_valleys.get('sec_valleys', []))
        logger.info(f"Peaks/Valleys counts: js_peaks={js_count}, js_valleys={jv_count}, sec_peaks={sp_count}, sec_valleys={sv_count}")
    except Exception:
        logger.debug("Peaks/Valleys count logging failed")

    # Y축 범위 계산
    y_min = df['Low'].min()
    y_max = df['High'].max()
    y_range = y_max - y_min if (y_max is not None and y_min is not None) else 0
    y_margin = y_range * 0.03 if y_range else 0
    plot_y_min = max(0, y_min - y_margin) if y_min is not None else None
    plot_y_max = y_max + y_margin if y_max is not None else None

    # 원본 대시보드 코드와의 호환을 위한 별칭
    dates = df.index

    shapes_to_draw = []

    # --- 트렌드 배경 복원 ---
    if 'show_trend_background' in selected_options:
        trend_periods = trend_info.get('periods', [])
        background_periods = []
        last_end_date = df.index[0] if len(df.index) > 0 else None
        if trend_periods:
            all_dates_in_data = set(df.index)
            try:
                first_period_start = pd.Timestamp(trend_periods[0]['start'])
            except Exception:
                first_period_start = None
            if first_period_start and first_period_start > df.index[0]:
                closest_start = min(d for d in all_dates_in_data if d >= df.index[0])
                closest_end = max(d for d in all_dates_in_data if d < first_period_start)
                if closest_start <= closest_end:
                    background_periods.append({'start': closest_start, 'end': closest_end, 'type': 'Sideways'})

            for i, period in enumerate(trend_periods):
                start_ts = pd.Timestamp(period['start'])
                end_ts = pd.Timestamp(period['end'])
                closest_start = min((d for d in all_dates_in_data if d >= start_ts), default=None)
                closest_end = max((d for d in all_dates_in_data if d <= end_ts), default=None)
                if closest_start and closest_end and closest_start <= closest_end:
                    if i > 0:
                        prev_end_ts = pd.Timestamp(trend_periods[i-1]['end'])
                        closest_prev_end = max((d for d in all_dates_in_data if d <= prev_end_ts), default=None)
                        if closest_prev_end and closest_start > closest_prev_end:
                            inter_start = min((d for d in all_dates_in_data if d > closest_prev_end), default=closest_start)
                            inter_end = max((d for d in all_dates_in_data if d < closest_start), default=inter_start)
                            if inter_start <= inter_end:
                                background_periods.append({'start': inter_start, 'end': inter_end, 'type': 'Sideways'})
                    background_periods.append({'start': closest_start, 'end': closest_end, 'type': period.get('type', 'Sideways')})
                    last_end_date = closest_end

            if last_end_date and last_end_date < df.index[-1]:
                final_start = min((d for d in all_dates_in_data if d > last_end_date), default=df.index[-1])
                if final_start <= df.index[-1]:
                    background_periods.append({'start': final_start, 'end': df.index[-1], 'type': 'Sideways'})
        elif len(df.index) > 0:
            background_periods.append({'start': df.index[0], 'end': df.index[-1], 'type': 'Sideways'})

        colors = {"Uptrend": 'rgba(0, 255, 0, 0.08)', "Downtrend": 'rgba(255, 0, 0, 0.08)', "Sideways": 'rgba(100, 100, 100, 0.03)'}
        for period in background_periods:
            try:
                fill_color = colors.get(period['type'], colors['Sideways'])
                shapes_to_draw.append(
                    go.layout.Shape(type="rect", xref="x", yref="y", x0=period['start'], y0=plot_y_min, x1=period['end'], y1=plot_y_max, fillcolor=fill_color, layer="below", line_width=0)
                )
            except Exception as shape_err:
                logger.error(f"배경색 shape 생성 오류: {period}, 오류: {shape_err}")

    # ZigZag 라인 - restore from trend_info (category 축에 맞게 좌표 변환)
    if 'show_zigzag' in selected_options:
        # Consolidate zigzag segments into a single trace for clarity
        zigzag_points = trend_info.get('zigzag_points', [])
        xs = []
        ys = []
        if zigzag_points:
            for p in zigzag_points:
                x_date = p.get('actual_date') or p.get('date') or p.get('detected_date')
                y_val = p.get('value')
                if x_date is None or y_val is None:
                    continue
                try:
                    dt = pd.to_datetime(x_date)
                    if dt not in df.index:
                        idx = df.index.get_indexer([dt], method='nearest')[0]
                        dt = df.index[idx]
                    xs.append(dt)
                    ys.append(y_val)
                except Exception:
                    continue
        if len(xs) > 1:
            try:
                fig.add_trace(go.Scatter(x=xs, y=ys, mode='lines', line=dict(color='grey', width=1), name='ZigZag', showlegend=False, hoverinfo='skip'))
            except Exception:
                pass

    # JS Peaks & Valleys
    if 'show_js_extremums' in selected_options:
        try:
            js_peaks = peaks_valleys.get('js_peaks', [])
            js_valleys = peaks_valleys.get('js_valleys', [])

            def build_xy(items):
                xs, ys = [], []
                for it in items:
                    d = it.get('actual_date') or it.get('date') or it.get('detected_date')
                    v = it.get('value') or it.get('high') or it.get('close')
                    if d is None or v is None:
                        continue
                    try:
                        dt = pd.to_datetime(d)
                    except Exception:
                        continue
                    xs.append(dt); ys.append(v)
                return xs, ys

            px, py = build_xy(js_peaks)
            if px:
                fig.add_trace(go.Scatter(x=px, y=[y * 1.01 for y in py], mode='text', text=['P'] * len(px), textposition='top center', textfont=dict(size=12, color='black'), name='JS Peaks'))

            vx, vy = build_xy(js_valleys)
            if vx:
                fig.add_trace(go.Scatter(x=vx, y=[y * 0.99 for y in vy], mode='text', text=['V'] * len(vx), textposition='bottom center', textfont=dict(size=12, color='black'), name='JS Valleys'))
        except Exception as e:
            logger.warning(f"JS 표시 오류: {e}")

    # Secondary Peaks & Valleys (separate option)
    if 'show_sec_extremums' in selected_options:
        try:
            sec_peaks = peaks_valleys.get('sec_peaks', [])
            sec_valleys = peaks_valleys.get('sec_valleys', [])

            def build_xy_sec(items):
                xs, ys = [], []
                for it in items:
                    d = it.get('actual_date') or it.get('date') or it.get('detected_date')
                    v = it.get('value') or it.get('high') or it.get('close')
                    if d is None or v is None:
                        continue
                    try:
                        dt = pd.to_datetime(d)
                    except Exception:
                        continue
                    xs.append(dt); ys.append(v)
                return xs, ys

            # 분류: live vs retro
            sec_peaks_live = [p for p in sec_peaks if p.get('confidence') == 'provisional' and p.get('promotion', 'live') == 'live']
            sec_peaks_retro = [p for p in sec_peaks if p.get('confidence') == 'provisional' and p.get('promotion') == 'retro']

            spx_live, spy_live = build_xy_sec(sec_peaks_live)
            if spx_live:
                # place marker slightly above candle high to avoid overlap
                spy_live_pos = [y * 1.01 for y in spy_live]
                fig.add_trace(go.Scatter(x=spx_live, y=spy_live_pos, mode='markers+text', marker=dict(symbol='circle', size=10, color='orange'), text=['sP']*len(spx_live), textposition='top center', textfont=dict(size=11, color='orange'), name='Sec Peaks (live)'))

            spx_retro, spy_retro = build_xy_sec(sec_peaks_retro)
            if spx_retro:
                spy_retro_pos = [y * 1.01 for y in spy_retro]
                fig.add_trace(go.Scatter(x=spx_retro, y=spy_retro_pos, mode='markers+text', marker=dict(symbol='square', size=10, color='darkorange'), text=['(sP)']*len(spx_retro), textposition='top center', textfont=dict(size=11, color='darkorange'), name='Sec Peaks (retro)'))

            sec_valleys_live = [v for v in sec_valleys if v.get('confidence') == 'provisional' and v.get('promotion', 'live') == 'live']
            sec_valleys_retro = [v for v in sec_valleys if v.get('confidence') == 'provisional' and v.get('promotion') == 'retro']

            svx_live, svy_live = build_xy_sec(sec_valleys_live)
            if svx_live:
                # place marker slightly below candle low to avoid overlap
                svy_live_pos = [y * 0.995 for y in svy_live]
                fig.add_trace(go.Scatter(x=svx_live, y=svy_live_pos, mode='markers+text', marker=dict(symbol='circle', size=10, color='blue'), text=['sV']*len(svx_live), textposition='bottom center', textfont=dict(size=11, color='blue'), name='Sec Valleys (live)'))

            svx_retro, svy_retro = build_xy_sec(sec_valleys_retro)
            if svx_retro:
                svy_retro_pos = [y * 0.995 for y in svy_retro]
                fig.add_trace(go.Scatter(x=svx_retro, y=svy_retro_pos, mode='markers+text', marker=dict(symbol='square', size=10, color='darkblue'), text=['(sV)']*len(svx_retro), textposition='bottom center', textfont=dict(size=11, color='darkblue'), name='Sec Valleys (retro)'))
        except Exception as e:
            logger.warning(f"Secondary 표시 오류: {e}")

    # Ensure Volume trace exists (some code paths may not have added it)
    try:
        vol_present = any((getattr(t, 'name', None) or '').lower() == 'volume' for t in fig.data)
    except Exception:
        vol_present = False
    if not vol_present:
        try:
            vols = df['Volume'].fillna(0).tolist()
            closes = df['Close'].tolist()
            vol_colors = []
            for i in range(len(vols)):
                if i == 0:
                    vol_colors.append('lightgrey')
                else:
                    vol_colors.append('green' if closes[i] >= closes[i-1] else 'red')
            fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name='Volume', marker_color=vol_colors), row=2, col=1)
        except Exception:
            pass

    # --- Indicator traces rendering ---
    try:
        # overlay indicators (SMA/EMA) on price
        for name, series in indicators_series.items():
            if name.startswith('SMA') or name.startswith('EMA'):
                try:
                    # stronger, more visible colors/widths and place on top subplot
                    if name.startswith('SMA_20'):
                        clr = 'orange'; w = 2
                    elif name.startswith('SMA_50'):
                        clr = 'magenta'; w = 2
                    elif name.startswith('EMA_'):
                        clr = 'green'; w = 1.5
                    else:
                        clr = 'black'; w = 1
                    fig.add_trace(go.Scatter(x=series.index, y=series.values, mode='lines', name=name, line=dict(color=clr, width=w)), row=1, col=1)
                except Exception:
                    continue

        # Bollinger bands: add upper/lower/middle on top subplot
        # keys in pandas-ta-classic usually like 'BBU_20_2.0', 'BBM_20_2.0', 'BBL_20_2.0'
        # Support different possible BB column name formats
        bb_upper_keys = [k for k in indicators_series.keys() if k.startswith('BBU_')]
        bb_mid_keys = [k for k in indicators_series.keys() if k.startswith('BBM_')]
        bb_lower_keys = [k for k in indicators_series.keys() if k.startswith('BBL_')]
        if bb_upper_keys and bb_mid_keys and bb_lower_keys:
            try:
                up = indicators_series[bb_upper_keys[0]]
                mid = indicators_series[bb_mid_keys[0]]
                low = indicators_series[bb_lower_keys[0]]
                # draw upper and mid lines, then fill between mid and lower for better visibility
                fig.add_trace(go.Scatter(x=up.index, y=up.values, mode='lines', name='BB Upper', line=dict(color='purple', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=mid.index, y=mid.values, mode='lines', name='BB Mid', line=dict(color='lightgrey', width=1)), row=1, col=1)
                fig.add_trace(go.Scatter(x=low.index, y=low.values, mode='lines', name='BB Lower', line=dict(color='purple', width=1), fill='tonexty', fillcolor='rgba(180,150,220,0.18)'), row=1, col=1)
            except Exception:
                pass

        # MACD / RSI / ATR / OBV -> dynamic rows based on dynamic_inds order
        macd_m = None
        macdh_m = None
        macds_m = None
        rsi_s = None
        atr_s = None
        obv_s = None
        for k, s in indicators_series.items():
            if k.startswith('MACD') and not k.startswith('MACDh') and not k.startswith('MACDs'):
                macd_m = s
            if k.startswith('MACDh'):
                macdh_m = s
            if k.startswith('MACDs'):
                macds_m = s
            if k.startswith('RSI'):
                rsi_s = s
            if k.startswith('ATR'):
                atr_s = s
            if k == 'OBV':
                obv_s = s

        # helper to map dynamic index to subplot row
        def dyn_row_for(idx):
            # row 1 = price, row 2 = volume, dynamic rows start at 3
            return 3 + idx

        try:
            for idx, ind in enumerate(dynamic_inds):
                row_idx = dyn_row_for(idx)
                if ind == 'MACD':
                    if macd_m is not None:
                        fig.add_trace(go.Scatter(x=macd_m.index, y=macd_m.values, mode='lines', name='MACD', line=dict(color='blue', width=1.5)), row=row_idx, col=1)
                    if macds_m is not None:
                        fig.add_trace(go.Scatter(x=macds_m.index, y=macds_m.values, mode='lines', name='Signal', line=dict(color='red', width=1)), row=row_idx, col=1)
                    if macdh_m is not None:
                        fig.add_trace(go.Bar(x=macdh_m.index, y=macdh_m.values, name='MACD Hist', marker_color='rgb(0,128,255)'), row=row_idx, col=1)
                elif ind == 'RSI':
                    if rsi_s is not None:
                        fig.add_trace(go.Scatter(x=rsi_s.index, y=rsi_s.values, mode='lines', name='RSI', line=dict(color='purple', width=1)), row=row_idx, col=1)
                        # add 30/70 bands
                        fig.add_trace(go.Scatter(x=[rsi_s.index[0], rsi_s.index[-1]], y=[70,70], mode='lines', line=dict(color='grey', width=1, dash='dash'), showlegend=False), row=row_idx, col=1)
                        fig.add_trace(go.Scatter(x=[rsi_s.index[0], rsi_s.index[-1]], y=[30,30], mode='lines', line=dict(color='grey', width=1, dash='dash'), showlegend=False), row=row_idx, col=1)
                elif ind == 'ATR':
                    if atr_s is not None:
                        fig.add_trace(go.Scatter(x=atr_s.index, y=atr_s.values, mode='lines', name='ATR', line=dict(color='brown', width=1)), row=row_idx, col=1)
                elif ind == 'OBV':
                    # place OBV in same row as Volume (row 2) OR in its own dynamic row depending on dynamic index
                    if obv_s is not None:
                        # if the dynamic row corresponds to volume slot (rare), ensure we map to row 2
                        if row_idx <= 2:
                            target_row = 2
                        else:
                            target_row = row_idx
                        fig.add_trace(go.Scatter(x=obv_s.index, y=obv_s.values, mode='lines', name='OBV', line=dict(color='navy', width=1.5)), row=target_row, col=1)
        except Exception:
            pass
    except Exception as e:
        logger.warning(f"Indicator rendering failed: {e}")

    # Patterns: DT / DB (boxes) and HS / IHS markers + necklines
    if 'show_dt_db' in selected_options:
        completed_dt = patterns.get('completed_dt', [])
        if completed_dt:
            dt_dates = [pd.Timestamp(p['date']) for p in completed_dt]
            fig.add_trace(go.Scatter(x=dt_dates, y=[df.loc[d]['Low'] * 0.99 for d in dt_dates], mode='markers+text', marker=dict(symbol='diamond-tall', size=11, color='magenta'), text=['DT' for _ in dt_dates], textposition='bottom center', name='DT Completed'))
            for dt in completed_dt:
                try:
                    start_peak = dt.get('start_peak')
                    if start_peak and 'actual_date' in start_peak:
                        start_date = pd.Timestamp(start_peak['actual_date'])
                        end_date = pd.Timestamp(dt['date'])
                        if start_date <= end_date and start_date in df.index and end_date in df.index:
                            slice_data = df.loc[start_date:end_date]
                            if not slice_data.empty:
                                date_index = df.index.get_loc(start_date)
                                if date_index > 0:
                                    prev_date = df.index[date_index - 1]
                                    adjusted_start = start_date - (start_date - prev_date) * 0.2
                                else:
                                    adjusted_start = start_date - pd.Timedelta(days=1)
                                try:
                                    end_index = df.index.get_loc(end_date)
                                    if end_index < len(df.index) - 1:
                                        next_date = df.index[end_index + 1]
                                        adjusted_end = end_date + (next_date - end_date) * 0.2
                                    else:
                                        adjusted_end = end_date + pd.Timedelta(days=1)
                                except Exception:
                                    adjusted_end = end_date + pd.Timedelta(days=1)
                                box_y0 = slice_data['Low'].min() * 0.99
                                box_y1 = slice_data['High'].max() * 1.01
                                shapes_to_draw.append(go.layout.Shape(type='rect', xref='x', yref='y', x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1, line=dict(color='#FF4560', width=1.5), fillcolor='rgba(0,0,0,0)', layer='above'))
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(x=mid_point, y=box_y1, text='DT', font=dict(family='Arial, sans-serif', size=11, color='#FF4560'), bordercolor='#FF4560', borderwidth=1.5, borderpad=3, bgcolor='rgba(255,255,255,0.8)', opacity=0.8, showarrow=False, yshift=5)
                except Exception as box_err:
                    logger.warning(f"DT 박스 생성 오류: {box_err}")

        completed_db = patterns.get('completed_db', [])
        if completed_db:
            db_dates = [pd.Timestamp(p['date']) for p in completed_db]
            fig.add_trace(go.Scatter(x=db_dates, y=[df.loc[d]['High'] * 1.01 for d in db_dates], mode='markers+text', marker=dict(symbol='diamond-wide', size=11, color='#00C853'), text=['DB' for _ in db_dates], textposition='top center', name='DB Completed'))
            for dbp in completed_db:
                try:
                    start_valley = dbp.get('start_valley')
                    if start_valley and 'actual_date' in start_valley:
                        start_date = pd.Timestamp(start_valley['actual_date'])
                        end_date = pd.Timestamp(dbp['date'])
                        if start_date <= end_date and start_date in df.index and end_date in df.index:
                            slice_data = df.loc[start_date:end_date]
                            if not slice_data.empty:
                                date_index = df.index.get_loc(start_date)
                                if date_index > 0:
                                    prev_date = df.index[date_index - 1]
                                    adjusted_start = start_date - (start_date - prev_date) * 0.2
                                else:
                                    adjusted_start = start_date - pd.Timedelta(days=1)
                                try:
                                    end_index = df.index.get_loc(end_date)
                                    if end_index < len(df.index) - 1:
                                        next_date = df.index[end_index + 1]
                                        adjusted_end = end_date + (next_date - end_date) * 0.2
                                    else:
                                        adjusted_end = end_date + pd.Timedelta(days=1)
                                except Exception:
                                    adjusted_end = end_date + pd.Timedelta(days=1)
                                box_y0 = slice_data['Low'].min() * 0.99
                                box_y1 = slice_data['High'].max() * 1.01
                                shapes_to_draw.append(go.layout.Shape(type='rect', xref='x', yref='y', x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1, line=dict(color='#00C853', width=1.5), fillcolor='rgba(0,0,0,0)', layer='above'))
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(x=mid_point, y=box_y1, text='DB', font=dict(family='Arial, sans-serif', size=11, color='#00C853'), bordercolor='#00C853', borderwidth=1.5, borderpad=3, bgcolor='rgba(255,255,255,0.8)', opacity=0.8, showarrow=False, yshift=5)
                except Exception as box_err:
                    logger.warning(f"DB 박스 생성 오류: {box_err}")

    # --- HS와 IHS 통합 처리 (원본 대시보드에서 복사됨) ---
    if 'show_hs_ihs' in selected_options:
        # HS 부분
        completed_hs = patterns.get("completed_hs", [])
        #completed_hs = [patterns.get("completed_hs", [])[0]] if patterns.get("completed_hs") else []
        if completed_hs:
            hs_dates = [pd.Timestamp(p['date']) for p in completed_hs]
            fig.add_trace(go.Scatter(
                x=hs_dates,
                y=[df.loc[d]['Low'] * 0.99 for d in hs_dates],
                mode='markers+text', marker=dict(symbol='star', size=11, color='#FF6B8A'),
                text=[f"HS" for p in completed_hs],
                textposition='bottom center', name='HS Completed'
            ))
            # HS 박스 및 넥라인 추가 (improved: fallback mapping + debug logs)
            for hs in completed_hs:
                try:
                    # HS 패턴 요소들 확인
                    v1 = hs.get('V1')
                    p1 = hs.get('P1')
                    v2 = hs.get('V2')
                    p2 = hs.get('P2')
                    v3 = hs.get('V3')
                    p3 = hs.get('P3')
                    mode = hs.get('mode', 'neckline')

                    # compute start_date with fallbacks (include V1/P1 first so left-shoulder is inside box)
                    start_date = None
                    if v1 and 'actual_date' in v1:
                        start_date = pd.Timestamp(v1['actual_date'])
                    elif p1 and 'actual_date' in p1:
                        start_date = pd.Timestamp(p1['actual_date'])
                    elif v2 and 'actual_date' in v2:
                        start_date = pd.Timestamp(v2['actual_date'])
                    elif p2 and 'actual_date' in p2:
                        start_date = pd.Timestamp(p2['actual_date'])

                    end_date = pd.Timestamp(hs['date']) if 'date' in hs else pd.Timestamp(hs.get('actual_date'))

                    # Debug logs to understand why box creation may be skipped
                    try:
                        logger.info(f"HS debug: start={start_date}, end={end_date}, has_p1={bool(p1)}, has_p2={bool(p2)}, has_v1={bool(v1)}, has_v2={bool(v2)}")
                    except Exception:
                        pass

                    if start_date is None or end_date is None:
                        try:
                            logger.info(f"HS skip: start or end None (start={start_date}, end={end_date})")
                        except Exception:
                            pass
                        continue

                    # If start/end exist but not in dates, log the nearest mapping
                    if not (start_date in dates and end_date in dates):
                        try:
                            ns = dates.get_indexer([start_date], method='nearest')[0]
                            ne = dates.get_indexer([end_date], method='nearest')[0]
                            logger.info(f"HS mapping fallback: nearest_start={dates[ns]}, nearest_end={dates[ne]}")
                        except Exception:
                            try:
                                logger.info("HS mapping fallback: unable to map nearest indices")
                            except Exception:
                                pass

                    # proceed only if date range makes sense
                    if start_date <= end_date and (start_date in dates or end_date in dates):
                        # Normalize to nearest indices if exact dates aren't present
                        try:
                            if start_date not in dates:
                                start_idx = dates.get_indexer([start_date], method='nearest')[0]
                                start_date = dates[start_idx]
                            if end_date not in dates:
                                end_idx = dates.get_indexer([end_date], method='nearest')[0]
                                end_date = dates[end_idx]
                        except Exception:
                            pass

                        slice_data = df.loc[start_date:end_date]
                        if slice_data.empty:
                            try:
                                logger.info(f"HS skip: slice_data empty for {start_date} to {end_date}")
                            except Exception:
                                pass
                            continue

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
                        except Exception:
                            adjusted_end = end_date + pd.Timedelta(days=1)

                        box_y0 = slice_data['Low'].min() * 0.99
                        box_y1 = slice_data['High'].max() * 1.01

                        try:
                            logger.info(f"HS box create attempt: start={adjusted_start}, end={adjusted_end}, y0={box_y0:.0f}, y1={box_y1:.0f}")
                        except Exception:
                            pass

                        # 박스 추가 - 투명한 배경으로
                        shapes_to_draw.append(go.layout.Shape(
                            type="rect", xref="x", yref="y",
                            x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1,
                            line=dict(color="#FF6B8A", width=1.5, dash=None),
                            fillcolor="rgba(255,105,135,0.06)",
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
                                size=11,
                                color="#FF6B8A"
                            ),
                            bordercolor="#FF6B8A",
                            borderwidth=1.5,
                            borderpad=3,
                            bgcolor="rgba(255,255,255,0.8)",
                            opacity=0.8,
                            showarrow=False,
                            yshift=5
                        )

                        # 넥라인 추가 (V2, V3 필요)
                        if v2 and v3 and 'value' in v2 and 'value' in v3 and 'actual_date' in v2 and 'actual_date' in v3:
                            v2_date = pd.Timestamp(v2['actual_date']); v3_date = pd.Timestamp(v3['actual_date']); v2_val = v2['value']; v3_val = v3['value']
                            day_span = (v3_date - v2_date).days
                            if day_span == 0: day_span = 1
                            neck_slope = (v3_val - v2_val) / day_span
                            try:
                                logger.info(f"HS neckline create: v2={v2_date}, v3={v3_date}, v2_val={v2_val:.0f}, v3_val={v3_val:.0f}")
                            except Exception:
                                pass
                            # Extend neckline to box end using index-based slope (safer across non-trading days)
                            try:
                                v2_idx = int(v2.get('index'))
                                v3_idx = int(v3.get('index'))
                                if v3_idx != v2_idx:
                                    adj_end_idx = dates.get_indexer([adjusted_end], method='nearest')[0]
                                    v_slope_idx = (v3_val - v2_val) / float(v3_idx - v2_idx)
                                    y_at_end = float(v2_val) + v_slope_idx * float(adj_end_idx - v2_idx)
                                else:
                                    y_at_end = float(v3_val)
                            except Exception:
                                # fallback to time-based slope if index-based fails
                                try:
                                    day_span = max((v3_date - v2_date).days, 1)
                                    slope_per_day = (v3_val - v2_val) / float(day_span)
                                    y_at_end = float(v2_val) + slope_per_day * float((adjusted_end - v2_date).days)
                                except Exception:
                                    y_at_end = float(v3_val)
                            # clamp to box verticals to avoid extreme extrapolation
                            try:
                                y_at_end = max(min(y_at_end, box_y1), box_y0)
                            except Exception:
                                pass
                            if mode == 'aggressive':
                                shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=v2_date, y0=v2_val, x1=v3_date, y1=v3_val, line=dict(color='#FF6B8A', width=1.2, dash='dash'), layer='above'))
                            else:
                                shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=v2_date, y0=v2_val, x1=adjusted_end, y1=y_at_end, line=dict(color='#FF6B8A', width=1.2, dash='dash'), layer='above'))
                except Exception as hs_err:
                    logger.warning(f"HS 요소 생성 오류: {hs_err}")

        # IHS 부분
        completed_ihs = patterns.get("completed_ihs", [])
        # completed_ihs = [patterns.get("completed_ihs", [])[1]] if len(patterns.get("completed_ihs", [])) > 1 else []
        if completed_ihs:
            ihs_dates = [pd.Timestamp(p['date']) for p in completed_ihs]
            fig.add_trace(go.Scatter(
                x=ihs_dates,
                y=[df.loc[d]['High'] * 1.01 for d in ihs_dates],
                mode='markers+text', marker=dict(symbol='star', size=11, color='#4CAF50'),
                text=[f"IHS" for p in completed_ihs],
                textposition='top center', name='IHS Completed'
            ))
            # IHS 박스 및 넥라인 추가
            for ihs in completed_ihs:
                try:
                # IHS 패턴 요소들 확인
                    p1 = ihs.get('P1')
                    v1 = ihs.get('V1')
                    p2 = ihs.get('P2')
                    v2 = ihs.get('V2')
                    p3 = ihs.get('P3')
                    v3 = ihs.get('V3')
                    mode = ihs.get('mode', 'neckline')
                    
                    # 패턴 시작과 끝 날짜 확인
                    # Prefer to start the IHS box after the left-shoulder points
                    # so that P1/V1 are visually excluded. Use P2 (or V2) first,
                    # then fall back to P1 if nothing else is available.
                    start_date = None
                    if p1 and 'actual_date' in p1:
                        start_date = pd.Timestamp(p1['actual_date'])
                    elif v1 and 'actual_date' in v1:
                        start_date = pd.Timestamp(v1['actual_date'])
                    elif p2 and 'actual_date' in p2:
                        start_date = pd.Timestamp(p2['actual_date'])
                    elif v2 and 'actual_date' in v2:
                        start_date = pd.Timestamp(v2['actual_date'])
                    end_date = pd.Timestamp(ihs['date']) if 'date' in ihs else pd.Timestamp(ihs.get('actual_date'))

                    if start_date <= end_date and start_date in dates and end_date in dates:
                            # 박스 영역 계산
                            slice_data = df.loc[start_date:end_date]
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
                                # make IHS box slightly filled and log creation for debugging
                                try:
                                    logger.info(f"IHS box create attempt: start={adjusted_start}, end={adjusted_end}, y0={box_y0:.0f}, y1={box_y1:.0f}")
                                except Exception:
                                    pass
                                shapes_to_draw.append(go.layout.Shape(type='rect', xref='x', yref='y', x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1, line=dict(color='#4CAF50', width=1.5), fillcolor='rgba(76,175,80,0.06)', layer='above'))
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(x=mid_point, y=box_y1, text='IHS', font=dict(family='Arial, sans-serif', size=11, color='#4CAF50'), bordercolor='#4CAF50', borderwidth=1.5, borderpad=3, bgcolor='rgba(255,255,255,0.8)', opacity=0.8, showarrow=False, yshift=5)
                            # 넥라인 추가 (P2, P3 필요)
                            if p2 and p3 and 'value' in p2 and 'value' in p3 and 'actual_date' in p2 and 'actual_date' in p3:
                                p2_date = pd.Timestamp(p2['actual_date']); p3_date = pd.Timestamp(p3['actual_date']); p2_val = p2['value']; p3_val = p3['value']
                                day_span = (p3_date - p2_date).days
                                if day_span == 0: day_span = 1
                                neck_slope = (p3_val - p2_val) / day_span
                                # 라인 그리기는 P2~P3 사이만
                                try:
                                    logger.info(f"IHS neckline create: p2={p2_date}, p3={p3_date}, p2_val={p2_val:.0f}, p3_val={p3_val:.0f}")
                                except Exception:
                                    pass
                                # Extend neckline to box end using index-based slope
                                try:
                                    p2_idx = int(p2.get('index'))
                                    p3_idx = int(p3.get('index'))
                                    if p3_idx != p2_idx:
                                        adj_end_idx = dates.get_indexer([adjusted_end], method='nearest')[0]
                                        p_slope_idx = (p3_val - p2_val) / float(p3_idx - p2_idx)
                                        y_at_end = float(p2_val) + p_slope_idx * float(adj_end_idx - p2_idx)
                                    else:
                                        y_at_end = float(p3_val)
                                except Exception:
                                    try:
                                        day_span = max((p3_date - p2_date).days, 1)
                                        slope_per_day = (p3_val - p2_val) / float(day_span)
                                        y_at_end = float(p2_val) + slope_per_day * float((adjusted_end - p2_date).days)
                                    except Exception:
                                        y_at_end = float(p3_val)
                                try:
                                    y_at_end = max(min(y_at_end, box_y1), box_y0)
                                except Exception:
                                    pass
                                if mode == 'aggressive':
                                    shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=p2_date, y0=p2_val, x1=p3_date, y1=p3_val, line=dict(color='#4CAF50', width=1.2, dash='dash'), layer='above'))
                                else:
                                    shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=p2_date, y0=p2_val, x1=adjusted_end, y1=y_at_end, line=dict(color='#4CAF50', width=1.2, dash='dash'), layer='above'))
                except Exception as ihs_err:
                    logger.warning(f"IHS 요소 생성 오류: {ihs_err}")

    # apply shapes and finalize
    # Ensure shapes are serializable dicts when applying to layout (plotly sometimes
    # ignores GraphObjects Shape instances when passing directly). Convert defensively.
    safe_shapes = []
    for s in shapes_to_draw:
        try:
            if hasattr(s, 'to_plotly_json'):
                safe_shapes.append(s.to_plotly_json())
            else:
                safe_shapes.append(dict(s))
        except Exception:
            # fallback: attempt to coerce via dict()
            try:
                safe_shapes.append(dict(s))
            except Exception:
                # skip unparsable shape to avoid breaking the layout update
                continue

    fig.update_layout(
        title_text=f"{ticker} (DB) - Candles",
        xaxis_title='Date',
        height=900,
        xaxis_rangeslider_visible=False,
        shapes=safe_shapes,
        showlegend=True,
        dragmode='pan'
    )
    # set y-axis range only for first subplot
    try:
        fig.update_yaxes(range=[plot_y_min, plot_y_max], row=1, col=1)
    except Exception:
        pass

    # 마우스 휠(스크롤)로 확대/축소 시 Y축 방향 고정 -> X축 방향으로만 확대/축소 되도록 함
    try:
        fig.update_yaxes(fixedrange=True)
    except Exception:
        pass

    # 커스텀 ticks 생성 (여기 추가)
    import pandas as pd  # 이미 import 되어 있음

    tickvals = []
    ticktext = []
    dates = df.index  # datetime 인덱스

    # timezone-naive 상태에서 커스텀 ticks 생성
    if interval in ['5m', '30m', '1h']:  # 분봉: 매일 첫 캔들 위치에 "월/일"
        daily_groups = dates.to_period('D')  # timezone-naive라 바로 period 변환
        for day in daily_groups.unique():
            day_mask = (daily_groups == day)
            if day_mask.any() and len(dates[day_mask]) > 0:
                first_date = dates[day_mask][0]  # 첫 datetime 값
                # tick 위치로 실제 datetime 값을 사용
                tickvals.append(first_date)
                ticktext.append(first_date.strftime('%m/%d'))
    else:  # 일/주봉: 매월 첫 캔들 위치에 "연도/월"
        monthly_groups = dates.to_period('M')  # timezone-naive라 바로 period 변환
        for month in monthly_groups.unique():
            month_mask = (monthly_groups == month)
            if month_mask.any() and len(dates[month_mask]) > 0:
                first_date = dates[month_mask][0]
                # tick 위치로 실제 datetime 값을 사용
                tickvals.append(first_date)
                ticktext.append(first_date.strftime('%Y/%m'))


    
    fig.update_xaxes(
        type='date',
        tickmode='array',
        tickvals=tickvals,  # 위치 (datetime 값)
        ticktext=ticktext,  # 표시 텍스트
        tickangle=-45  # 기울임
    )
    
    # y축 포맷 개선 (..k 표시 제거)
    fig.update_yaxes(
        tickformat='.0f'  # 정수 표시 (90000 형태)
    )

    return fig

# === 실제 사용되는 함수들 (중복 제거 완료) ===

# Note: _download_data_from_db wrapper removed; main code calls load_candles_from_db directly.


# _run_full_analysis_from_db wrapper는 중복이므로 제거되었습니다.

if __name__ == '__main__':
    logger.info('=== DB-backed Dash 앱 시작 ===')
    logger.info('UI 준비 완료: http://localhost:8058')
    print('🌐 브라우저에서 http://localhost:8058 으로 접속하세요!')
    # Start standalone app
    try:
        # app is defined earlier in this file (standalone implementation)
        app.run(debug=True, host='127.0.0.1', port=8058, use_reloader=False)
    except TypeError:
        app.run(debug=True, host='127.0.0.1', port=8058)


