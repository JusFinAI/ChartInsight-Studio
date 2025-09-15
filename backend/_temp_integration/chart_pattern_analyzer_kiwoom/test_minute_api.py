"""
분봉 API 500 에러 테스트 스크립트
"""

import sys
import os
import requests
import json
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def test_minute_api_directly():
    """분봉 API를 직접 호출하여 500 에러 확인"""
    
    print("🔍 분봉 API (ka10080) 직접 테스트")
    print("="*60)
    
    try:
        # 1. 토큰 발급
        loader = KiwoomDataLoader()
        token = loader._get_token()
        
        if not token:
            print("❌ 토큰 발급 실패")
            return False
            
        print(f"✅ 토큰: {token[:20]}...")
        
        # 2. 분봉 API 직접 호출
        host = "https://api.kiwoom.com"
        
        # 분봉 API 정보 (올바른 엔드포인트 사용)
        minute_tests = [
            {
                "name": "5분봉 (ka10080)",
                "endpoint": "/api/dostk/chart",  # 올바른 엔드포인트
                "api_id": "ka10080",
                "data": {
                    'stk_cd': '005930',
                    'tic_scope': '5',  # 5분
                    'upd_stkpc_tp': '1'
                }
            },
            {
                "name": "30분봉 (ka10080)", 
                "endpoint": "/api/dostk/chart",  # 올바른 엔드포인트
                "api_id": "ka10080",
                "data": {
                    'stk_cd': '005930',
                    'tic_scope': '30',  # 30분
                    'upd_stkpc_tp': '1'
                }
            },
            {
                "name": "60분봉 (ka10080)",
                "endpoint": "/api/dostk/chart",  # 올바른 엔드포인트
                "api_id": "ka10080",
                "data": {
                    'stk_cd': '005930',
                    'tic_scope': '60',  # 60분
                    'upd_stkpc_tp': '1'
                }
            }
        ]
        
        for test in minute_tests:
            print(f"\n📊 {test['name']} 테스트...")
            
            url = host + test['endpoint']
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'authorization': f'Bearer {token}',
                'cont-yn': 'N',
                'next-key': '',
                'api-id': test['api_id'],
            }
            
            print(f"   URL: {url}")
            print(f"   API-ID: {test['api_id']}")
            print(f"   Data: {test['data']}")
            
            try:
                response = requests.post(url, headers=headers, json=test['data'], timeout=15)
                print(f"   ✅ 상태 코드: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   📊 응답 키: {list(result.keys())}")
                elif response.status_code == 500:
                    print(f"   ❌ 500 에러 발생!")
                    try:
                        error_data = response.json()
                        print(f"   🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
                    except:
                        print(f"   🔍 에러 텍스트: {response.text}")
                else:
                    print(f"   ⚠️ 기타 에러: {response.status_code}")
                    print(f"   📄 응답: {response.text[:200]}...")
                    
            except Exception as e:
                print(f"   ❌ 예외 발생: {e}")
                
        return True
        
    except Exception as e:
        print(f"❌ 테스트 실패: {e}")
        return False

def test_other_chart_apis():
    """다른 차트 API들 테스트 (일봉/주봉)"""
    
    print("\n🔍 다른 차트 API 테스트 (일봉/주봉)")
    print("="*60)
    
    try:
        loader = KiwoomDataLoader()
        token = loader._get_token()
        
        # 올바른 차트 API들
        chart_apis = [
            {
                "name": "일봉 차트 (ka10081)",
                "endpoint": "/api/dostk/chart",
                "api_id": "ka10081",
                "data": {
                    'stk_cd': '005930',
                    'base_dt': '20250819',
                    'upd_stkpc_tp': '1'
                }
            },
            {
                "name": "주봉 차트 (ka10082)", 
                "endpoint": "/api/dostk/chart",
                "api_id": "ka10082",
                "data": {
                    'stk_cd': '005930',
                    'base_dt': '20250819',
                    'upd_stkpc_tp': '1'
                }
            }
        ]
        
        host = "https://api.kiwoom.com"
        
        for api in chart_apis:
            print(f"\n📡 {api['name']} 테스트...")
            
            url = host + api['endpoint']
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'authorization': f'Bearer {token}',
                'cont-yn': 'N',
                'next-key': '',
                'api-id': api['api_id'],
            }
            
            try:
                response = requests.post(url, headers=headers, json=api['data'], timeout=10)
                print(f"   상태: {response.status_code}")
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"   ✅ 성공! 응답 키: {list(result.keys())}")
                elif response.status_code == 500:
                    print(f"   ❌ 500 에러")
                else:
                    print(f"   ⚠️ 기타 에러: {response.status_code}")
                    
            except Exception as e:
                print(f"   ❌ 예외: {e}")
                
    except Exception as e:
        print(f"❌ 차트 API 테스트 실패: {e}")

if __name__ == "__main__":
    print("🚀 분봉 API 500 에러 진단")
    print(f"🕐 테스트 시간: {datetime.now()}")
    print("="*80)
    
    # 1. 분봉 API 직접 테스트
    success = test_minute_api_directly()
    
    # 2. 일봉/주봉 API 테스트 (정상 작동 확인용)
    test_other_chart_apis()
    
    print("\n" + "="*80)
    print("💡 분석 결과:")
    if success:
        print("✅ 분봉 API가 정상 작동합니다.")
        print("🎯 이제 메인 대시보드를 실행해보세요!")
        print("   python main_dashboard.py")
    else:
        print("❌ 분봉 API에서 여전히 500 에러가 발생합니다.")
        print("\n🔧 해결 방안:")
        print("1. 키움증권 계정의 분봉 데이터 권한 확인")
        print("2. 키움증권 고객센터 문의 (1544-5000)")
        print("3. 임시로 일봉/주봉만 사용")
