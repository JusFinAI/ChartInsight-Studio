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
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.analysis import run_analysis_from_df
from backend.app.database import SessionLocal
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.data_loader import load_candles_from_db
import pandas as pd
from dash import dcc, html, Input, Output, State, callback
import plotly.graph_objects as go

# 독립 실행 레이아웃용 한국 종목 로더 헬퍼
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.korean_stock_loader import (
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

# configure local logger to write into module log dir using centralized util
dashboard_logger = configure_logger("chartinsight.dashboard", log_file_prefix="dash_app_db", logs_dir=MODULE_LOG_DIR, level=logging.INFO)

# 프로젝트 주요 이벤트(운영) 로그 파일 생성: INFO 레벨
# 엔트리포인트에서 백엔드 전역 이벤트를 기록할 별도 파일을 만듭니다.
configure_logger(
    logger_name="backend",
    log_file_prefix="backend_events",
    logs_dir=MODULE_LOG_DIR,
    level=logging.INFO,
)

# 알고리즘(엔진) 상세 로그 파일 생성: DEBUG 레벨
# run_full_analysis_impl의 자세한 디버깅/분석 로그를 별도 파일로 분리합니다.
configure_logger(
    logger_name="backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis_impl",
    log_file_prefix="algorithm_run",
    logs_dir=MODULE_LOG_DIR,
    level=logging.DEBUG,
)

# 분석 엔진의 기본 로깅 레벨(콘솔)는 위에서 파일 핸들러를 등록했으므로 추가로 조정
logging.getLogger('backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis_impl').setLevel(logging.INFO)

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
        ], value=['show_trend_background','show_zigzag'], inline=True, style={'display':'flex','flexWrap':'wrap','gap':'10px','marginBottom':'5px'})
    ]),
    dcc.Loading(id='loading-graph', type='circle', children=[dcc.Graph(id='analysis-graph', figure=go.Figure(layout={'height':800}), config={'scrollZoom':True})])
], style={'padding':'10px'})


@callback(Output('dropdown-ticker','options'), Output('dropdown-ticker','value'), Input('dropdown-category','value'))
def update_ticker_options(selected_category):
    options = SYMBOLS_BY_CATEGORY.get(selected_category, [])
    default_value = options[0]['value'] if options else ''
    return options, default_value


@callback(Output('analysis-graph','figure'), Input('button-run-analysis','n_clicks'), Input('checklist-options','value'), State('dropdown-ticker','value'), State('dropdown-interval','value'), State('dropdown-category','value'), prevent_initial_call=True)
def update_graph(n_clicks, selected_options, ticker, interval, category):
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

    is_checklist_trigger = (triggered_id == 'checklist-options')

    # If checklist only changed and we have cached results, reuse them
    if is_checklist_trigger and hasattr(update_graph, 'last_analysis_results') and hasattr(update_graph, 'last_data'):
        result = update_graph.last_analysis_results
        df = update_graph.last_data
        if df is None or (hasattr(df, 'empty') and df.empty):
            fig_err = go.Figure(); fig_err.add_annotation(text='Cached data 없음', xref='paper', yref='paper', x=0.5, y=0.5, showarrow=False); fig_err.update_layout(title='No data', height=800); return fig_err
        # 캐시된 데이터로 기본 캔들 차트를 구성합니다. 이후 추가 그리기 코드가
        # 초기화되지 않은 `fig` 변수를 참조하지 않고 트레이스/도형을 추가할 수 있게 합니다.
        fig = go.Figure()
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
            ))
        except Exception:
            # 폴백: 빈 Figure 반환(실행 흐름은 일관되게 유지)
            fig = go.Figure()
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

        # 캔들스틱 차트 생성
        fig = go.Figure()
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
            ))
        except Exception:
            # fallback: empty figure but keep execution path consistent
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
        zigzag_points = trend_info.get('zigzag_points', [])
        if len(zigzag_points) > 1:
            for i in range(len(zigzag_points) - 1):
                p1 = zigzag_points[i]
                p2 = zigzag_points[i + 1]
                x0_date = p1.get('actual_date')
                x1_date = p2.get('actual_date')
                y0 = p1.get('value')
                y1 = p2.get('value')
                if x0_date is not None and x1_date is not None and y0 is not None and y1 is not None:
                    try:
                        # datetime을 그대로 사용하여 모든 trace의 x를 일관되게 유지
                        dt0 = pd.to_datetime(x0_date)
                        dt1 = pd.to_datetime(x1_date)
                        # 만약 df.index에 정확히 존재하지 않으면 nearest 방식으로 보정
                        if dt0 not in df.index:
                            idx0 = df.index.get_indexer([dt0], method='nearest')[0]
                            dt0 = df.index[idx0]
                        if dt1 not in df.index:
                            idx1 = df.index.get_indexer([dt1], method='nearest')[0]
                            dt1 = df.index[idx1]
                        fig.add_trace(go.Scatter(x=[dt0, dt1], y=[y0, y1], mode='lines', line=dict(color='grey', width=1), showlegend=False, hoverinfo='skip'))
                    except Exception:
                        # 날짜 매칭 실패 시 건너뜀
                        continue

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
                fig.add_trace(go.Scatter(x=px, y=[y * 1.005 for y in py], mode='text', text=['P'] * len(px), textposition='top center', textfont=dict(size=12, color='black'), name='JS Peaks'))

            vx, vy = build_xy(js_valleys)
            if vx:
                fig.add_trace(go.Scatter(x=vx, y=[y * 0.995 for y in vy], mode='text', text=['V'] * len(vx), textposition='bottom center', textfont=dict(size=12, color='black'), name='JS Valleys'))
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

            spx, spy = build_xy_sec(sec_peaks)
            if spx:
                fig.add_trace(go.Scatter(x=spx, y=spy, mode='markers+text', marker=dict(symbol='circle', size=10, color='orange'), text=['sP']*len(spx), textposition='top center', textfont=dict(size=11, color='orange'), name='Sec Peaks'))

            svx, svy = build_xy_sec(sec_valleys)
            if svx:
                fig.add_trace(go.Scatter(x=svx, y=svy, mode='markers+text', marker=dict(symbol='circle', size=10, color='blue'), text=['sV']*len(svx), textposition='bottom center', textfont=dict(size=11, color='blue'), name='Sec Valleys'))
        except Exception as e:
            logger.warning(f"Secondary 표시 오류: {e}")

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
                                box_y0 = slice_data['Low'].min() * 0.995
                                box_y1 = slice_data['High'].max() * 1.005
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
                                box_y0 = slice_data['Low'].min() * 0.995
                                box_y1 = slice_data['High'].max() * 1.005
                                shapes_to_draw.append(go.layout.Shape(type='rect', xref='x', yref='y', x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1, line=dict(color='#00C853', width=1.5), fillcolor='rgba(0,0,0,0)', layer='above'))
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(x=mid_point, y=box_y1, text='DB', font=dict(family='Arial, sans-serif', size=11, color='#00C853'), bordercolor='#00C853', borderwidth=1.5, borderpad=3, bgcolor='rgba(255,255,255,0.8)', opacity=0.8, showarrow=False, yshift=5)
                except Exception as box_err:
                    logger.warning(f"DB 박스 생성 오류: {box_err}")

    # --- HS와 IHS 통합 처리 (원본 대시보드에서 복사됨) ---
    if 'show_hs_ihs' in selected_options:
        # HS 부분
        completed_hs = patterns.get("completed_hs", [])
        if completed_hs:
            hs_dates = [pd.Timestamp(p['date']) for p in completed_hs]
            fig.add_trace(go.Scatter(
                x=hs_dates,
                y=[df.loc[d]['Low'] * 0.99 for d in hs_dates],
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
                        end_date = pd.Timestamp(hs['date']) if 'date' in hs else pd.Timestamp(hs.get('actual_date'))
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
                                # 라인 그리기는 V2~V3 사이만
                                shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=v2_date, y0=v2_val, x1=v3_date, y1=v3_val, line=dict(color='#FF6B8A', width=1.2, dash='dash'), layer='above'))
                except Exception as hs_err:
                    logger.warning(f"HS 요소 생성 오류: {hs_err}")

        # IHS 부분
        completed_ihs = patterns.get("completed_ihs", [])
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
                    v1 = ihs.get('V1')
                    p2 = ihs.get('P2')
                    v2 = ihs.get('V2')
                    p3 = ihs.get('P3')
                    v3 = ihs.get('V3')
                    
                    # 패턴 시작과 끝 날짜 확인
                    if v1 and 'actual_date' in v1:
                        start_date = pd.Timestamp(v1['actual_date'])
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
                                shapes_to_draw.append(go.layout.Shape(type='rect', xref='x', yref='y', x0=adjusted_start, y0=box_y0, x1=adjusted_end, y1=box_y1, line=dict(color='#4CAF50', width=1.5), fillcolor='rgba(0,0,0,0)', layer='above'))
                                mid_point = start_date + (end_date - start_date) / 2
                                fig.add_annotation(x=mid_point, y=box_y1, text='IHS', font=dict(family='Arial, sans-serif', size=11, color='#4CAF50'), bordercolor='#4CAF50', borderwidth=1.5, borderpad=3, bgcolor='rgba(255,255,255,0.8)', opacity=0.8, showarrow=False, yshift=5)
                            # 넥라인 추가 (P2, P3 필요)
                            if p2 and p3 and 'value' in p2 and 'value' in p3 and 'actual_date' in p2 and 'actual_date' in p3:
                                p2_date = pd.Timestamp(p2['actual_date']); p3_date = pd.Timestamp(p3['actual_date']); p2_val = p2['value']; p3_val = p3['value']
                                day_span = (p3_date - p2_date).days
                                if day_span == 0: day_span = 1
                                neck_slope = (p3_val - p2_val) / day_span
                                # 라인 그리기는 P2~P3 사이만
                                shapes_to_draw.append(go.layout.Shape(type='line', xref='x', yref='y', x0=p2_date, y0=p2_val, x1=p3_date, y1=p3_val, line=dict(color='#4CAF50', width=1.2, dash='dash'), layer='above'))
                except Exception as ihs_err:
                    logger.warning(f"IHS 요소 생성 오류: {ihs_err}")

    # apply shapes and finalize
    fig.update_layout(
        title_text=f"{ticker} (DB) - Candles",
        xaxis_title='Date',
        yaxis_title='Price',
        height=800,
        xaxis_rangeslider_visible=False,
        shapes=shapes_to_draw,
        yaxis_range=[plot_y_min, plot_y_max]
    )

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
    logger.info('UI 준비 완료: http://localhost:8054')
    print('🌐 브라우저에서 http://localhost:8054 으로 접속하세요!')
    # Start standalone app
    try:
        # app is defined earlier in this file (standalone implementation)
        app.run(debug=True, host='127.0.0.1', port=8054, use_reloader=False)
    except TypeError:
        app.run(debug=True, host='127.0.0.1', port=8054)


