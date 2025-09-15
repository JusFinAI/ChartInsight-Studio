"""
한국 주식 종목 데이터 로더
KOSPI/KOSDAQ JSON 파일에서 종목 정보를 로드하고 Dash 드롭다운 형태로 변환
"""

import json
import os
from typing import Dict, List, Tuple

def load_stock_codes() -> Tuple[Dict, Dict]:
    """
    선정된 30개 종목 데이터 로드 (KOSPI, KOSDAQ 분리)
    
    Returns:
        tuple: (kospi_data, kosdaq_data) 딕셔너리
    """
    current_dir = os.path.dirname(os.path.abspath(__file__))
    selected_stocks_path = os.path.join(current_dir, 'data', 'selected_stocks.json')
    
    # selected_stocks.json 파일 로드
    with open(selected_stocks_path, 'r', encoding='utf-8') as f:
        selected_data = json.load(f)
    
    # KOSPI와 KOSDAQ으로 분리
    kospi_data = {}
    kosdaq_data = {}
    
    for code, info in selected_data.items():
        if info.get('market') == 'KOSPI':
            kospi_data[code] = info
        elif info.get('market') == 'KOSDAQ':
            kosdaq_data[code] = info
    
    return kospi_data, kosdaq_data

def create_dropdown_options(stock_data: Dict) -> List[Dict]:
    """
    주식 데이터를 Dash 드롭다운 옵션 형태로 변환
    
    Args:
        stock_data: 주식 종목 딕셔너리
        
    Returns:
        list: [{'label': '종목명 (종목코드)', 'value': '종목코드'}, ...]
    """
    options = []
    
    for code, info in stock_data.items():
        # 정상 거래 종목만 포함 (감리/관리/정지 제외)
        if info.get('auditInfo', '') == '정상':
            label = f"{info['name']} ({code})"
            options.append({
                'label': label,
                'value': code
            })
    
    # 삼성전자(005930)를 맨 앞에, 나머지는 종목코드 순으로 정렬
    samsung_options = [opt for opt in options if opt['value'] == '005930']
    other_options = [opt for opt in options if opt['value'] != '005930']
    other_options.sort(key=lambda x: x['value'])
    
    options = samsung_options + other_options
    
    return options

def get_category_options() -> List[Dict]:
    """
    카테고리 드롭다운 옵션 반환
    
    Returns:
        list: [{'label': 'KOSPI', 'value': 'KOSPI'}, ...]
    """
    return [
        {'label': 'KOSPI', 'value': 'KOSPI'},
        {'label': 'KOSDAQ', 'value': 'KOSDAQ'}
    ]

def get_symbols_by_category() -> Dict[str, List[Dict]]:
    """
    카테고리별 종목 옵션 딕셔너리 반환
    
    Returns:
        dict: {'KOSPI': [...], 'KOSDAQ': [...]}
    """
    kospi_data, kosdaq_data = load_stock_codes()
    
    return {
        'KOSPI': create_dropdown_options(kospi_data),
        'KOSDAQ': create_dropdown_options(kosdaq_data)
    }

def get_interval_options() -> List[Dict]:
    """
    타임프레임 드롭다운 옵션 반환 (올바른 API 정보로 분봉 재활성화)
    
    Returns:
        list: 타임프레임 옵션 리스트
    """
    return [
        {"value": "5m", "label": "5 Minutes"},
        {"value": "30m", "label": "30 Minutes"},
        {"value": "1h", "label": "1 Hour"},
        {"value": "1d", "label": "1 Day"},
        {"value": "1wk", "label": "1 Week"}
    ]

def get_default_values() -> Tuple[str, str, str]:
    """
    기본값 반환
    
    Returns:
        tuple: (default_category, default_ticker, default_interval)
    """
    # 삼성전자를 기본값으로 설정
    default_category = 'KOSPI'
    default_ticker = '005930'  # 삼성전자
    default_interval = '1d'     # 일봉
    
    return default_category, default_ticker, default_interval

def get_stock_name(ticker: str) -> str:
    """
    종목 코드로 종목명 조회
    
    Args:
        ticker: 6자리 종목 코드
        
    Returns:
        str: 종목명 (없으면 종목코드 반환)
    """
    kospi_data, kosdaq_data = load_stock_codes()
    
    # KOSPI에서 먼저 찾기
    if ticker in kospi_data:
        return kospi_data[ticker]['name']
    
    # KOSDAQ에서 찾기
    if ticker in kosdaq_data:
        return kosdaq_data[ticker]['name']
    
    # 없으면 코드 그대로 반환
    return ticker

# 테스트용 메인 함수
if __name__ == "__main__":
    print("🔍 한국 주식 종목 로더 테스트")
    print("="*50)
    
    # 1. 카테고리 옵션 테스트
    categories = get_category_options()
    print(f"📂 카테고리 수: {len(categories)}")
    for cat in categories:
        print(f"   - {cat['label']}")
    
    # 2. 종목 수 확인
    symbols_by_category = get_symbols_by_category()
    for category, symbols in symbols_by_category.items():
        print(f"📈 {category} 종목 수: {len(symbols)}")
        
        # 첫 3개 종목 출력
        print("   상위 3개 종목:")
        for i, symbol in enumerate(symbols[:3]):
            print(f"   {i+1}. {symbol['label']}")
    
    # 3. 타임프레임 옵션 테스트
    intervals = get_interval_options()
    print(f"⏰ 타임프레임 수: {len(intervals)}")
    for interval in intervals:
        print(f"   - {interval['label']} ({interval['value']})")
    
    # 4. 기본값 테스트
    default_cat, default_ticker, default_interval = get_default_values()
    print(f"🎯 기본값:")
    print(f"   카테고리: {default_cat}")
    print(f"   종목: {get_stock_name(default_ticker)} ({default_ticker})")
    print(f"   타임프레임: {default_interval}")
    
    print("\n✅ 테스트 완료!")
