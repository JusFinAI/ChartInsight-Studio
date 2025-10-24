import requests
import json
import sys
import os
import time
from datetime import datetime
import pandas as pd
from typing import List, Dict, Set

# 현재 디렉토리를 Python 경로에 추가하여 kiwoom_data_loader를 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def get_all_thema_groups(loader: KiwoomDataLoader) -> List[Dict]:
    """
    모든 테마 그룹 목록을 조회합니다 (ka90001)
    """
    print("🔍 모든 테마 그룹 조회 중...")
    
    thema_params = {
        'qry_tp': '0',           # 0:전체검색
        'stk_cd': '',            
        'date_tp': '10',         # 10일간
        'thema_nm': '',          
        'flu_pl_amt_tp': '1',    # 1:상위기간수익률, 2:하위기간수익률, 3:상위등락률, 4:하위등락률
        'stex_tp': '1'           # 1:KRX
    }
    
    result = fn_ka90001(loader=loader, data=thema_params)
    if result and 'thema_grp' in result:
        return result['thema_grp']
    return []

def get_thema_stocks(loader: KiwoomDataLoader, thema_grp_cd: str) -> List[Dict]:
    """
    특정 테마 그룹의 모든 종목을 조회합니다 (ka90002)
    """
    print(f"  📋 테마 {thema_grp_cd} 종목 조회 중...")
    
    thema_params = {
        'thema_grp_cd': thema_grp_cd,  # ✅ 필수! (함수 파라미터 값)
        'qry_tp': '0',           # 0:전체검색
        'stk_cd': '',            
        'date_tp': '10',         # 10일간
        'thema_nm': '',          
        'flu_pl_amt_tp': '1',    # 1:당일수익률
        'stex_tp': '1'           # 1:KRX
    }
    
    result = fn_ka90002(loader=loader, data=thema_params)
    if result and 'thema_comp_stk' in result:
        return result['thema_comp_stk']
    return []

def collect_all_thema_stocks():
    """
    모든 테마의 모든 종목을 수집하고 통계를 생성합니다
    """
    print("🚀 키움증권 모든 테마 종목 수집 시작")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)
    
    # KiwoomDataLoader 인스턴스 생성
    data_loader = KiwoomDataLoader()
    
    # 1. 모든 테마 그룹 조회
    thema_groups = get_all_thema_groups(loader=data_loader)
    
    if not thema_groups:
        print("❌ 테마 그룹 조회에 실패했습니다.")
        return
    
    print(f"✅ 총 {len(thema_groups)}개의 테마 그룹을 찾았습니다.")
    
    # 2. 각 테마별로 종목 수집
    all_stocks = []
    unique_stock_codes = set()
    thema_stock_counts = []
    
    for i, thema in enumerate(thema_groups, 1):
        thema_grp_cd = thema.get('thema_grp_cd')
        thema_nm = thema.get('thema_nm')
        
        if not thema_grp_cd:
            continue
            
        print(f"\n[{i}/{len(thema_groups)}] 테마: {thema_nm} ({thema_grp_cd})")
        
        # 테마 종목 조회
        stocks = get_thema_stocks(loader=data_loader, thema_grp_cd=thema_grp_cd)
        
        if stocks:
            # 종목에 테마 정보 추가
            for stock in stocks:
                stock['thema_grp_cd'] = thema_grp_cd
                stock['thema_nm'] = thema_nm
                
            all_stocks.extend(stocks)
            
            # 고유 종목코드 수집
            stock_codes = {stock.get('stk_cd') for stock in stocks if stock.get('stk_cd')}
            unique_stock_codes.update(stock_codes)
            
            # 테마별 종목 수 기록
            thema_stock_counts.append({
                'thema_grp_cd': thema_grp_cd,
                'thema_nm': thema_nm,
                'stock_count': len(stocks),
                'unique_stock_count': len(stock_codes)
            })
            
            print(f"   → {len(stocks)}개 종목 수집 완료")
        else:
            print(f"   → 종목 조회 실패")
        
        # API Rate Limiting
        time.sleep(0.5)
    
    # 3. 결과 통계 계산
    total_themas = len(thema_stock_counts)
    total_stocks_collected = len(all_stocks)
    total_unique_stocks = len(unique_stock_codes)
    
    print("\n" + "="*60)
    print("📊 최종 수집 결과")
    print("="*60)
    print(f"• 총 테마 그룹 수: {total_themas}개")
    print(f"• 수집된 종목 데이터: {total_stocks_collected}건")
    print(f"• 고유 종목 코드 수: {total_unique_stocks}개")
    print(f"• 평균 테마당 종목 수: {total_stocks_collected/total_themas:.1f}개")
    
    # 4. CSV 파일로 저장
    data_dir = os.path.join(current_dir, 'data')
    os.makedirs(data_dir, exist_ok=True)
    
    # 4-1. 모든 종목 데이터 저장
    if all_stocks:
        all_stocks_df = pd.DataFrame(all_stocks)
        all_stocks_csv = os.path.join(data_dir, 'all_thema_stocks.csv')
        all_stocks_df.to_csv(all_stocks_csv, index=False, encoding='utf-8-sig')
        print(f"\n💾 모든 종목 데이터 저장: {all_stocks_csv}")
    
    # 4-2. 테마별 통계 저장
    if thema_stock_counts:
        thema_stats_df = pd.DataFrame(thema_stock_counts)
        thema_stats_csv = os.path.join(data_dir, 'thema_statistics.csv')
        thema_stats_df.to_csv(thema_stats_csv, index=False, encoding='utf-8-sig')
        print(f"💾 테마 통계 데이터 저장: {thema_stats_csv}")
    
    # 4-3. 고유 종목 코드 리스트 저장
    if unique_stock_codes:
        unique_stocks_df = pd.DataFrame({'stk_cd': list(unique_stock_codes)})
        unique_stocks_csv = os.path.join(data_dir, 'unique_stock_codes.csv')
        unique_stocks_df.to_csv(unique_stocks_csv, index=False, encoding='utf-8-sig')
        print(f"💾 고유 종목 코드 저장: {unique_stocks_csv}")
    
    print("\n" + "="*60)
    print("🎉 모든 테마 종목 수집 완료!")

# 기존 ka90001, ka90002 함수 import
from test_ka90001_테마그룹별요청 import fn_ka90001
from test_ka90002_테마구성종목요청 import fn_ka90002

if __name__ == '__main__':
    collect_all_thema_stocks()
