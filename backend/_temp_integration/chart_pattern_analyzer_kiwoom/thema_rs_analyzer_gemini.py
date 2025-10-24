import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, List

# --- Plotly Dash 관련 라이브러리 추가 ---
import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go

from test_ka90001_테마그룹별요청 import fn_ka90001
from test_ka20006 import fn_ka20006  # ✅ 구현 완료

from kiwoom_data_loader import KiwoomDataLoader


def get_index_data(loader: KiwoomDataLoader, index_code: str, base_date: str) -> List[Dict]:
    """지수 일봉 데이터 조회 (ka20006)"""
    print(f"📊 지수 데이터 조회 중: {index_code} ({base_date})")
    params = {'inds_cd': index_code, 'base_dt': base_date, 'num_candles': 130}
    api_result, _, _ = fn_ka20006(loader, params)
    
    # ✅ 수정: return_code == 0 (숫자 0으로 비교)
    if api_result and api_result.get('return_code') == 0 and 'inds_dt_pole_qry' in api_result:
        return api_result['inds_dt_pole_qry']
    
    print(f"❌ {index_code} 지수 데이터 조회 실패")
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
    """다양한 기간별 테마 수익률 조회 (ka90001)"""
    thema_returns = []
    for period in periods:
        print(f"🔍 {period}일 테마 수익률 조회 중...")
        params = {'qry_tp': '0', 'date_tp': str(period), 'flu_pl_amt_tp': '1', 'stex_tp': '1'}
        result = fn_ka90001(loader, params)
        if result and 'thema_grp' in result:
            for theme in result['thema_grp']:
                try:
                    theme_return = float(theme['dt_prft_rt'].rstrip('%'))
                    thema_returns.append({
                        'thema_grp_cd': theme['thema_grp_cd'],
                        'thema_nm': theme['thema_nm'],
                        'period': period,
                        'return_rate': theme_return
                    })
                except (ValueError, TypeError):
                    continue
    return thema_returns

def calculate_relative_strength(thema_return: float, index_return: float) -> float:
    """
    상대강도 계산: (테마수익률 - 지수수익률) / |지수수익률| × 100
    분모에 절대값을 사용하여 지수 하락 시에도 정확한 비교 가능
    """
        
    if index_return == 0:
       return 0.0
    return ((thema_return - index_return) / abs(index_return)) * 100

def analyze_thema_relative_strength(base_date: str = None):
    """테마 상대강도 분석 메인 함수"""
    print("🚀 테마 상대강도 분석 시작")
    if not base_date: base_date = datetime.now().strftime('%Y%m%d')
    print(f"📅 기준일자: {base_date}")
    
    periods = [5, 10, 20, 30]
    data_loader = KiwoomDataLoader()
    
    print("\n📈 지수 데이터 수집 중...")
    index_returns = {}
    for index_code in ['001', '101']:
        index_data = get_index_data(data_loader, index_code, base_date)
        index_returns[index_code] = calculate_index_returns(index_data, periods)
        print(f"   {index_code} 수익률: {index_returns[index_code]}")
    
    print("\n🎯 테마 수익률 조회 중...")
    thema_returns = get_thema_returns(data_loader, periods)
    
    print("\n📊 상대강도 계산 중...")
    rs_results = []
    for theme_data in thema_returns:
        theme_return = theme_data['return_rate']
        period = theme_data['period']
        
        kospi_rs = calculate_relative_strength(theme_return, index_returns['001'].get(period, 0))
        kosdaq_rs = calculate_relative_strength(theme_return, index_returns['101'].get(period, 0))
        
        rs_results.append({
            'thema_nm': theme_data['thema_nm'],
            'period': period,
            'theme_return': round(theme_return, 2),
            'kospi_rs': round(kospi_rs, 2),
            'kosdaq_rs': round(kosdaq_rs, 2)
        })
    
    if not rs_results:
        print("❌ 분석 결과 데이터가 없습니다.")
        return None

    df = pd.DataFrame(rs_results)
    csv_filename = os.path.join(os.path.dirname(os.path.abspath(__file__)), f'thema_excess_return_{base_date}.csv')
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
    print(f"✅ 분석 완료! 파일 저장: {csv_filename}")
    return df

# ==============================================================================
# --- DASHBOARD CREATION PART ---
# ==============================================================================

def create_dashboard(df: pd.DataFrame):
    """분석 결과를 바탕으로 Plotly Dash 대시보드를 생성하고 실행합니다."""
    
    app = dash.Dash(__name__)

    available_periods = sorted(df['period'].unique())

    app.layout = html.Div(style={'fontFamily': 'Arial, sans-serif', 'padding': '20px'}, children=[
        html.H1(
            "🚀 인터랙티브 테마 상대강도(RS) 대시보드 (gemini)",
            style={'textAlign': 'center', 'color': '#333'}
        ),
        html.Div(f"분석 기준일: {datetime.now().strftime('%Y-%m-%d')}", style={'textAlign': 'center', 'color': '#666', 'marginBottom': '20px'}),
        
        # --- 컨트롤 패널 ---
        html.Div(style={'display': 'flex', 'justifyContent': 'center', 'alignItems': 'center', 'gap': '30px', 'padding': '20px', 'backgroundColor': '#f9f9f9', 'borderRadius': '10px'}, children=[
            html.Div(children=[
                html.Label("시장 선택:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.RadioItems(
                    id='market-selector',
                    options=[
                        {'label': ' KOSPI 대비', 'value': 'kospi_rs'},
                        {'label': ' KOSDAQ 대비', 'value': 'kosdaq_rs'},
                    ],
                    value='kospi_rs',
                    labelStyle={'display': 'inline-block', 'marginRight': '10px'},
                    inputStyle={"marginRight": "5px"}
                )
            ]),
            html.Div(children=[
                html.Label("기간 선택:", style={'fontWeight': 'bold', 'marginRight': '10px'}),
                dcc.RadioItems(
                    id='period-selector',
                    options=[{'label': f' {p}일', 'value': p} for p in available_periods],
                    value=available_periods[1] if len(available_periods) > 1 else available_periods[0],
                    labelStyle={'display': 'inline-block', 'marginRight': '10px'},
                    inputStyle={"marginRight": "5px"}
                )
            ]),
        ]),
        
        # --- 차트 표시 영역 ---
        dcc.Graph(id='rs-tornado-chart')
    ])

    @app.callback(
        Output('rs-tornado-chart', 'figure'),
        [Input('market-selector', 'value'),
         Input('period-selector', 'value')]
    )
    def update_chart(selected_market, selected_period):
        # 1. 데이터 필터링
        filtered_df = df[df['period'] == selected_period].copy()
        
        # 2. 정렬
        sorted_df = filtered_df.sort_values(by=selected_market, ascending=False)

        # 3. 색상 규칙 적용
        colors = ['#2ca02c' if val >= 0 else '#d62728' for val in sorted_df[selected_market]]

        # 4. 차트 생성
        fig = go.Figure(go.Bar(
            x=sorted_df[selected_market],
            y=sorted_df['thema_nm'],
            orientation='h',
            marker_color=colors,
            text=sorted_df[selected_market],
            textposition='outside',
            hoverinfo='y+x+text',
            hovertemplate=(
                '<b>%{y}</b><br>' +
                'RS Score: %{x:.2f}<br>' +
                '절대수익률: %{customdata:.2f}%<extra></extra>'
            ),
            customdata=sorted_df['theme_return']
        ))

        fig.update_layout(
            title=f'<b>{selected_period}일 기준 테마별 {selected_market.upper().replace("_RS","")} 대비 상대강도</b>',
            xaxis_title='상대강도(RS) 점수 (초과수익률 %p)',
            yaxis_title='테마',
            yaxis=dict(
                tickmode='array',
                tickvals=sorted_df['thema_nm'],
                ticktext=sorted_df['thema_nm'],
                autorange="reversed" # To have highest on top
            ),
            height=25 * len(sorted_df) + 200, # 막대 개수에 따라 차트 높이 동적 조절
            margin=dict(l=150, r=50, t=80, b=50),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#333')
        )
        
        # 5. 기준선(0) 추가
        fig.add_shape(
            type="line",
            x0=0, y0=-0.5, x1=0, y1=len(sorted_df)-0.5,
            line=dict(color="black", width=2, dash="dash")
        )
        fig.update_xaxes(gridcolor='#e5e5e5')
        fig.update_yaxes(showline=False)

        return fig

    return app

# ==============================================================================
# --- MAIN EXECUTION PART ---
# ==============================================================================

if __name__ == '__main__':
    # 1. 데이터 분석 실행
    results_df = analyze_thema_relative_strength()

    # 2. 분석 결과가 있을 경우 대시보드 실행
    if results_df is not None and not results_df.empty:
        print("\n\n--- 대시보드 서버를 시작합니다 ---")
        print("웹 브라우저에서 http://127.0.0.1:8050/ 를 열어주세요.")
        
        app = create_dashboard(results_df)
        # 명시적으로 호스트와 포트를 지정하고 reloader를 사용하지 않도록 설정합니다.
        # 이렇게 하면 다른 터미널에서 별도 프로세스로 실행했을 때 터미널 포커스가 뒤바뀌는 문제를 줄일 수 있습니다.
        app.run(host='127.0.0.1', port=8050, debug=False, use_reloader=False)
    else:
        print("\n대시보드를 실행할 데이터가 없습니다. 분석을 종료합니다.")