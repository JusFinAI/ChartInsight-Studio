import requests
import json
import sys
import os
import time
from datetime import datetime, timedelta
import pandas as pd
from typing import Dict, List, Any

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
    return ((thema_return - index_return) / index_return) * 100

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
    # 기준일자 파라미터로 전달 가능 (예: '20251023')
    analyze_thema_relative_strength()
