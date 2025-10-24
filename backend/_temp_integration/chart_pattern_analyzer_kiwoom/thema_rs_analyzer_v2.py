import requests
import json
import sys
import os
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Any
import logging
import glob
import re
import numpy as np

# Dash / Plotly imports (앱 구성에 사용)
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def get_index_data(loader: KiwoomDataLoader, index_code: str, base_date: str) -> List[Dict]:
    """
    지수 일봉 데이터 조회 (ka20006)
    """
    print(f"📊 지수 데이터 조회 중: {index_code} ({base_date})")
    
    params = {
        'inds_cd': index_code,
        'base_dt': base_date or datetime.now().strftime('%Y%m%d'),
        'num_candles': 100
    }
    
    # ka20006 API 호출
    api_result, cont_yn, next_key = fn_ka20006(loader, params)  # ✅ 튜플 전체 받기
    
    # 🔍 DEBUG: API 응답 확인
    print(f"🔍 DEBUG - api_result type: {type(api_result)}")
    if api_result is not None:
        print(f"🔍 DEBUG - api_result keys: {list(api_result.keys()) if hasattr(api_result, 'keys') else 'N/A'}")
        
        # return_code 확인
        if 'return_code' in api_result:
            print(f"🔍 DEBUG - return_code: {api_result['return_code']}")
        
        # 실제 데이터 확인
        if 'inds_dt_pole_qry' in api_result:
            data = api_result['inds_dt_pole_qry']
            print(f"🔍 DEBUG - 데이터 개수: {len(data) if data else 0}")
            return data
    
    print("❌ 지수 데이터 조회 실패")
    return []

def calculate_index_returns(index_data: List[Dict], periods: List[int]) -> Dict[int, float]:
    """
    지수 데이터에서 다양한 기간별 수익률 계산
    """
    returns = {}
    
    if not index_data:
        return returns
    
    # 최신 가격 (가장 최근 데이터)
    latest_price = float(index_data[0]['cur_prc'])
    
    for period in periods:
        if len(index_data) > period:
            # period일 전 가격
            past_price = float(index_data[period]['cur_prc'])
            # 수익률 계산: (최신가 - 과거가) / 과거가 * 100
            return_rate = ((latest_price - past_price) / past_price) * 100
            returns[period] = return_rate
        else:
            print(f"⚠️  {period}일 데이터 부족: {len(index_data)}개 데이터만 있음")
    
    return returns

def get_thema_returns(loader: KiwoomDataLoader, periods: List[int]) -> List[Dict]:
    """
    다양한 기간별 테마 수익률 조회 (ka90001)
    """
    thema_returns = []
    
    for period in periods:
        print(f"🔍 {period}일 테마 수익률 조회 중...")
        
        params = {
            'qry_tp': '0',
            'date_tp': str(period),
            'flu_pl_amt_tp': '1',
            'stex_tp': '1'
        }
        
        # ka90001 API 호출
        result = fn_ka90001(loader, params)
        
        if result and 'thema_grp' in result:
            for theme in result['thema_grp']:
                theme_return = float(theme['dt_prft_rt'].rstrip('%'))
                thema_returns.append({
                    'thema_grp_cd': theme['thema_grp_cd'],
                    'thema_nm': theme['thema_nm'],
                    'period': period,
                    'return_rate': theme_return
                })
    
    return thema_returns

def calculate_relative_strength(thema_return: float, index_return: float) -> float:
    """
    상대강도 계산: (테마수익률 - 지수수익률) / 지수수익률 * 100
    """
    if index_return == 0:
        return 0.0
    return ((thema_return - index_return) / abs(index_return)) * 100

def analyze_thema_relative_strength(base_date: str = None):
    """
    테마 상대강도 분석 메인 함수
    """
    print("🚀 테마 상대강도 분석 시작")
    print(f"🕐 실행 시간: {datetime.now()}")
    
    # 기준일자 설정 (오늘 날짜 기본)
    if not base_date:
        base_date = datetime.now().strftime('%Y%m%d')
    
    print(f"📅 기준일자: {base_date}")
    
    # 분석 기간 설정
    periods = [5, 10, 20, 30]
    
    # KiwoomDataLoader 인스턴스 생성
    data_loader = KiwoomDataLoader()
    
    # 1. 지수 데이터 수집 및 수익률 계산
    print("\n📈 지수 데이터 수집 중...")
    index_returns = {}
    
    for index_code in ['001', '101']:  # KOSPI, KOSDAQ
        index_data = get_index_data(data_loader, index_code, base_date)
        index_returns[index_code] = calculate_index_returns(index_data, periods)
        print(f"   {index_code} 수익률: {index_returns[index_code]}")
    
    # 2. 테마 수익률 조회
    print("\n🎯 테마 수익률 조회 중...")
    thema_returns = get_thema_returns(data_loader, periods)
    print(f"   총 {len(thema_returns)}개 테마 수익률 데이터 수집")
    
    # 3. 상대강도 계산
    print("\n📊 상대강도 계산 중...")
    rs_results = []
    
    for theme_data in thema_returns:
        theme_cd = theme_data['thema_grp_cd']
        theme_nm = theme_data['thema_nm']
        period = theme_data['period']
        theme_return = theme_data['return_rate']
        
        # KOSPI 대비 상대강도
        kospi_rs = calculate_relative_strength(theme_return, index_returns['001'].get(period, 0))
        
        # KOSDAQ 대비 상대강도
        kosdaq_rs = calculate_relative_strength(theme_return, index_returns['101'].get(period, 0))
        
        rs_results.append({
            'thema_grp_cd': theme_cd,
            'thema_nm': theme_nm,
            'period': period,
            'theme_return': theme_return,
            'kospi_rs': kospi_rs,
            'kosdaq_rs': kosdaq_rs
        })
    
    # 4. 결과 저장
    print("\n💾 결과 저장 중...")
    data_dir = os.path.join(current_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # CSV로 저장
    df = pd.DataFrame(rs_results)
    csv_filename = os.path.join(data_dir, f'thema_relative_strength_{base_date}.csv')
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    
    print(f"✅ 분석 완료: {len(rs_results)}개 데이터 저장")
    print(f"📁 파일 위치: {csv_filename}")
    
    return rs_results

# 기존 API 함수 import
from test_ka90001_테마그룹별요청 import fn_ka90001
from test_ka20006 import fn_ka20006  # ✅ 구현 완료

if __name__ == '__main__':
    # 실행 모드: 기본은 기존 분석 실행
    # 'dash' 인자를 주면 대시보드 서버를 실행합니다: python thema_rs_analyzer_v2.py dash
    def _find_latest_csv(data_directory: str) -> str:
        """
        data 디렉토리에서 최신 생성된 thema_relative_strength_*.csv 파일 경로를 반환합니다.
        """
        pattern = os.path.join(data_directory, 'thema_relative_strength_*.csv')
        files = glob.glob(pattern)
        if not files:
            return ''
        # 최신 수정시간 기준으로 선택
        latest_file = max(files, key=os.path.getmtime)
        return latest_file

    def _load_and_prepare_dataframe(csv_path: str) -> pd.DataFrame:
        """
        CSV 파일을 안전하게 로드하고 컬럼 검사 및 타입 변환을 수행합니다.
        """
        required_columns = ['thema_grp_cd', 'thema_nm', 'period', 'theme_return', 'kospi_rs', 'kosdaq_rs']
        df_local = pd.read_csv(csv_path)

        # 컬럼 유효성 검사
        missing_cols = [c for c in required_columns if c not in df_local.columns]
        if missing_cols:
            raise ValueError(f"필수 컬럼 누락: {missing_cols}")

        # 퍼센트 문자가 있을 수 있어서 제거 후 숫자 변환
        def _to_numeric_percent(series: pd.Series) -> pd.Series:
            return pd.to_numeric(series.astype(str).str.replace('%', '', regex=False).str.strip(), errors='coerce')

        df_local['period'] = pd.to_numeric(df_local['period'], errors='coerce')
        df_local['theme_return'] = _to_numeric_percent(df_local['theme_return'])
        df_local['kospi_rs'] = _to_numeric_percent(df_local['kospi_rs'])
        df_local['kosdaq_rs'] = _to_numeric_percent(df_local['kosdaq_rs'])

        # 결측치 제거(핵심 값이 없는 행 제거)
        df_local = df_local.dropna(subset=['thema_nm', 'period'])

        return df_local

    # Dash 앱을 생성하는 함수
    def _create_dash_app(dataframe: pd.DataFrame) -> dash.Dash:
        """
        주어진 데이터프레임으로 Dash 앱과 레이아웃을 생성하여 반환합니다.
        """
        app = dash.Dash(__name__)

        # period 옵션은 데이터에서 동적으로 생성
        period_options = sorted(dataframe['period'].dropna().unique())
        period_options = [int(p) for p in period_options]

        app.layout = html.Div([
            # 제목
            html.H1("인터랙티브 테마 상대강도(RS) 대시보드"),

            # 컨트롤 패널
            html.Div([
                html.Div([
                    html.Label("시장 선택:"),
                    dcc.RadioItems(
                        id='market-radio',
                        options=[
                            {'label': 'KOSPI 대비', 'value': 'kospi_rs'},
                            {'label': 'KOSDAQ 대비', 'value': 'kosdaq_rs'}
                        ],
                        value='kospi_rs',
                        labelStyle={'display': 'inline-block', 'margin-right': '12px'}
                    )
                ], style={'margin-right': '40px'}),

                html.Div([
                    html.Label("기간 선택:"),
                    dcc.RadioItems(
                        id='period-radio',
                        options=[{'label': f"{p}일", 'value': p} for p in period_options],
                        value=period_options[0] if period_options else None,
                        labelStyle={'display': 'inline-block', 'margin-right': '12px'}
                    )
                ])
            ], style={'display': 'flex', 'alignItems': 'center', 'marginBottom': '20px'}),

            # 그래프
            dcc.Graph(id='tornado-graph'),

            # 에러/정보 영역
            html.Div(id='message-area', style={'color': 'red', 'marginTop': '10px'})
        ], style={'padding': '20px', 'font-family': 'Arial, Helvetica, sans-serif'})

        # 색상 매핑 헬퍼: 값의 절대값에 따라 색 농도 계산
        def _value_to_color(val: float, max_abs: float) -> str:
            """
            val > 0: 그린 계열, val < 0: 레드 계열
            max_abs: 정규화 기준(0이 아닌 최대 절대값)
            반환값은 'rgb(r,g,b)'
            """
            if max_abs <= 0 or np.isnan(val):
                return 'lightgray'
            norm = min(abs(val) / max_abs, 1.0)
            intensity = int(80 + norm * 175)  # 80 ~ 255 범위
            if val >= 0:
                # 녹색 계열: rgb( r, g, b ) -> r 작게, g 크게
                return f'rgb({int(30*(1-norm))},{int(intensity)},{int(30*(1-norm))})'
            else:
                # 빨강 계열: r 크게, g/b 작게
                return f'rgb({int(intensity)},{int(30*(1-norm))},{int(40*(1-norm))})'

        # 차트 생성 함수
        def _make_tornado_figure(filtered_df: pd.DataFrame, rs_column: str) -> go.Figure:
            """
            필터링된 df와 rs 컬럼 이름을 받아 토네이도(수평 막대) Figure를 반환합니다.
            """
            if filtered_df.empty:
                fig_empty = go.Figure()
                fig_empty.update_layout(
                    xaxis={'visible': False},
                    yaxis={'visible': False},
                    annotations=[{
                        'text': '선택한 기간/시장에 대한 데이터가 없습니다.',
                        'xref': 'paper', 'yref': 'paper', 'showarrow': False,
                        'font': {'size': 16}
                    }]
                )
                return fig_empty

            # RS 값으로 내림차순 정렬 (높은 RS가 위에 나오도록 y축 autorange 역전)
            df_sorted = filtered_df.sort_values(by=rs_column, ascending=False).copy()

            # 색상 매핑 기준(절대값의 최대)
            max_abs_rs = max(df_sorted[rs_column].abs().max(), 0)

            colors = [
                _value_to_color(v, max_abs_rs) for v in df_sorted[rs_column].fillna(0).tolist()
            ]

            # customdata로 theme_return 제공 (툴팁에서 사용)
            customdata = df_sorted[['theme_return']].values

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=df_sorted[rs_column],
                y=df_sorted['thema_nm'],
                orientation='h',
                marker=dict(color=colors),
                hovertemplate='테마: %{y}<br>RS: %{x:.2f}%<br>테마수익률: %{customdata[0]:.2f}%',
                customdata=customdata
            ))

            # 0 기준선 추가
            fig.add_vline(x=0, line_width=2, line_dash='dash', line_color='black', opacity=0.8)

            # 그래프 높이를 데이터 개수에 따라 동적으로 조절 (bar_height px per row)
            n_rows = len(df_sorted)
            bar_height = 18
            computed_height = max(600, int(bar_height * n_rows))

            # 모든 Y 라벨을 명시적으로 표시하도록 tickmode 설정
            fig.update_layout(
                margin={'l': 260, 'r': 40, 't': 40, 'b': 40},
                yaxis={
                    'autorange': 'reversed',  # 정렬한 순서가 위에서 아래로 표시되도록
                    'tickmode': 'array',
                    'tickvals': df_sorted['thema_nm'].tolist(),
                    'ticktext': df_sorted['thema_nm'].tolist(),
                    'automargin': True
                },
                xaxis_title='상대강도 (RS, %)',
                template='simple_white',
                hoverlabel=dict(font_size=12),
                height=computed_height
            )

            return fig

        # Dash 콜백: 라디오 변경 시 차트 업데이트
        @app.callback(
            Output('tornado-graph', 'figure'),
            Output('message-area', 'children'),
            Input('market-radio', 'value'),
            Input('period-radio', 'value')
        )
        def _update_graph(selected_market: str, selected_period: int):
            try:
                if selected_period is None:
                    return go.Figure(), '기간을 선택해주세요.'

                df_filtered = dataframe[dataframe['period'] == int(selected_period)].copy()
                if df_filtered.empty:
                    return _make_tornado_figure(df_filtered, selected_market), ''

                fig = _make_tornado_figure(df_filtered, selected_market)
                return fig, ''
            except Exception as e:
                logging.exception('그래프 업데이트 중 오류')
                return go.Figure(), f'오류 발생: {e}'

        return app

    # 실행 흐름 제어
    data_dir = os.path.join(current_dir, 'data')
    latest_csv = _find_latest_csv(data_dir)

    # 실행 방식 변경: 인자 없이 실행하면 대시보드가 뜨도록 기본 동작을 바꿨습니다.
    # 기존 동작(분석만 수행)을 원하면 'analyze' 인자를 사용하세요:
    #   python thema_rs_analyzer_v2.py analyze
    if len(sys.argv) > 1 and sys.argv[1].lower() == 'analyze':
        # 명시적으로 분석만 수행
        analyze_thema_relative_strength()
    else:
        # 기본: 대시보드 실행 (또는 'dash' 인자 명시 시에도 실행)
        if not latest_csv:
            print('데이터 파일이 없습니다: data/thema_relative_strength_*.csv')
            sys.exit(1)
        try:
            df_app = _load_and_prepare_dataframe(latest_csv)
        except Exception as e:
            print(f'CSV 로드 오류: {e}')
            sys.exit(1)

        dash_app = _create_dash_app(df_app)
        # 개발용: 127.0.0.1:8050 으로 접속
        # 최신 Dash 버전에서는 run_server 대신 run을 사용합니다.
        # 기본적으로 127.0.0.1로 바인딩하지만 WSL 환경에서는 '0.0.0.0'을 사용할 수도 있습니다.
        
        dash_app.run(host='127.0.0.1', port=8053, debug=False, use_reloader=False)
