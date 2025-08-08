"""ChartInsight API 테스트 스크립트"""

import requests
import json
from pprint import pprint

# API 기본 URL
BASE_URL = "http://localhost:8000/api/v1"

def test_root():
    """루트 엔드포인트 테스트"""
    response = requests.get("http://localhost:8000/")
    print("=== 루트 엔드포인트 테스트 ===")
    pprint(response.json())
    print()

def test_pattern_analysis():
    """패턴 분석 API 테스트"""
    url = f"{BASE_URL}/pattern-analysis/analyze"
    payload = {
        "symbol": "AAPL",
        "period": "6mo",
        "interval": "1d"
    }
    
    print(f"=== 패턴 분석 테스트: {payload['symbol']} ===")
    print(f"요청 URL: {url}")
    print(f"요청 데이터: {payload}")
    
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        data = response.json()
        
        # 요약 정보만 출력
        print(f"상태 코드: {response.status_code}")
        print(f"분석된 심볼: {data['symbol']}")
        print(f"JS Peaks: {len(data['js_peaks'])}")
        print(f"JS Valleys: {len(data['js_valleys'])}")
        print(f"Secondary Peaks: {len(data['secondary_peaks'])}")
        print(f"Secondary Valleys: {len(data['secondary_valleys'])}")
        print(f"추세 구간: {len(data['trend_periods'])}")
        print(f"가격 데이터 길이: {len(data['price_data']['dates'])}")
        
        # 첫 번째 JS Peak과 Valley 출력
        if data['js_peaks']:
            print("\n첫 번째 JS Peak:")
            pprint(data['js_peaks'][0])
        
        if data['js_valleys']:
            print("\n첫 번째 JS Valley:")
            pprint(data['js_valleys'][0])
        
        # 첫 번째 추세 구간 출력
        if data['trend_periods']:
            print("\n첫 번째 추세 구간:")
            pprint(data['trend_periods'][0])
        
    except requests.exceptions.RequestException as e:
        print(f"오류 발생: {e}")
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_detail = e.response.json()
                print(f"API 오류 메시지: {error_detail.get('detail', '알 수 없는 오류')}")
            except:
                print(f"응답 내용: {e.response.text}")

def test_popular_symbols():
    """인기 심볼 목록 API 테스트"""
    url = f"{BASE_URL}/pattern-analysis/symbols/popular"
    
    print("=== 인기 심볼 목록 테스트 ===")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print(f"상태 코드: {response.status_code}")
        pprint(data)
        
    except requests.exceptions.RequestException as e:
        print(f"오류 발생: {e}")

def test_periods_and_intervals():
    """기간 및 간격 목록 API 테스트"""
    periods_url = f"{BASE_URL}/pattern-analysis/periods"
    intervals_url = f"{BASE_URL}/pattern-analysis/intervals"
    
    print("=== 기간 목록 테스트 ===")
    try:
        response = requests.get(periods_url)
        response.raise_for_status()
        data = response.json()
        
        print(f"상태 코드: {response.status_code}")
        pprint(data)
        
    except requests.exceptions.RequestException as e:
        print(f"오류 발생: {e}")
    
    print("\n=== 간격 목록 테스트 ===")
    try:
        response = requests.get(intervals_url)
        response.raise_for_status()
        data = response.json()
        
        print(f"상태 코드: {response.status_code}")
        pprint(data)
        
    except requests.exceptions.RequestException as e:
        print(f"오류 발생: {e}")

if __name__ == "__main__":
    print("ChartInsight API 테스트 시작\n")
    
    test_root()
    test_popular_symbols()
    test_periods_and_intervals()
    test_pattern_analysis()
    
    print("\nChartInsight API 테스트 완료") 