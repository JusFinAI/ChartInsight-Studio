"""
키움증권 API 500 에러 상세 디버깅 스크립트
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

def test_api_directly():
    """키움증권 API를 직접 호출하여 에러 상세 정보 확인"""
    
    print("🔍 키움증권 API 직접 호출 테스트")
    print("="*60)
    
    try:
        # 1. 토큰 발급 테스트
        print("1️⃣ 토큰 발급 테스트...")
        loader = KiwoomDataLoader()
        token = loader._get_token()
        
        if not token:
            print("❌ 토큰 발급 실패 - 중단")
            return False
            
        print(f"✅ 토큰 발급 성공: {token[:20]}...")
        
        # 2. API 직접 호출
        print("\n2️⃣ API 직접 호출 테스트...")
        
        # 키움증권 일봉 API 엔드포인트
        host = "https://api.kiwoom.com"
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-price"
        url = host + endpoint
        
        # 요청 헤더
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': 'N',
            'next-key': '',
            'api-id': 'ka10081',
        }
        
        # 요청 데이터 (최소한의 데이터로 테스트)
        data = {
            'stk_cd': '005930',      # 삼성전자
            'base_dt': '20250819',   # 기준일
            'upd_stkpc_tp': '1'      # 수정주가구분
        }
        
        print(f"📡 요청 URL: {url}")
        print(f"📋 요청 헤더: {json.dumps(headers, indent=2, ensure_ascii=False)}")
        print(f"📊 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        # API 호출
        print("\n🚀 API 호출 중...")
        response = requests.post(url, headers=headers, json=data, timeout=30)
        
        print(f"📈 응답 상태 코드: {response.status_code}")
        print(f"📋 응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ API 호출 성공!")
            print(f"📊 응답 데이터 키: {list(result.keys())}")
            return True
        else:
            print(f"❌ API 호출 실패: {response.status_code}")
            print(f"📄 응답 내용: {response.text}")
            
            # 추가 분석
            try:
                error_data = response.json()
                print(f"🔍 에러 JSON: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
            except:
                print("🔍 응답이 JSON 형식이 아닙니다.")
            
            return False
            
    except Exception as e:
        print(f"❌ 예외 발생: {type(e).__name__}: {e}")
        return False

def test_different_endpoints():
    """다른 API 엔드포인트들 테스트"""
    
    print("\n🔍 다른 API 엔드포인트 테스트")
    print("="*60)
    
    # 테스트할 엔드포인트들
    endpoints = [
        {
            "name": "일봉 차트 (기본)",
            "endpoint": "/uapi/domestic-stock/v1/quotations/inquire-daily-price",
            "api_id": "ka10081"
        },
        {
            "name": "현재가 조회",
            "endpoint": "/uapi/domestic-stock/v1/quotations/inquire-price",
            "api_id": "FHKST01010100"
        }
    ]
    
    try:
        loader = KiwoomDataLoader()
        token = loader._get_token()
        
        for endpoint_info in endpoints:
            print(f"\n📡 테스트: {endpoint_info['name']}")
            
            url = f"https://api.kiwoom.com{endpoint_info['endpoint']}"
            headers = {
                'Content-Type': 'application/json;charset=UTF-8',
                'authorization': f'Bearer {token}',
                'cont-yn': 'N',
                'next-key': '',
                'api-id': endpoint_info['api_id'],
            }
            
            data = {
                'stk_cd': '005930',
                'base_dt': '20250819',
                'upd_stkpc_tp': '1'
            }
            
            try:
                response = requests.post(url, headers=headers, json=data, timeout=10)
                print(f"   상태: {response.status_code}")
                
                if response.status_code != 200:
                    print(f"   에러: {response.text[:200]}...")
                    
            except Exception as e:
                print(f"   예외: {e}")
                
    except Exception as e:
        print(f"❌ 엔드포인트 테스트 실패: {e}")

def test_network_connectivity():
    """네트워크 연결 상태 테스트"""
    
    print("\n🌐 네트워크 연결 상태 테스트")
    print("="*60)
    
    test_urls = [
        "https://api.kiwoom.com",
        "https://google.com",
        "https://mockapi.kiwoom.com"
    ]
    
    for url in test_urls:
        try:
            response = requests.get(url, timeout=5)
            print(f"✅ {url}: {response.status_code}")
        except Exception as e:
            print(f"❌ {url}: {e}")

if __name__ == "__main__":
    print("🚀 키움증권 API 500 에러 상세 디버깅")
    print(f"🕐 테스트 시간: {datetime.now()}")
    print("="*80)
    
    # 1. 네트워크 연결 테스트
    test_network_connectivity()
    
    # 2. API 직접 호출 테스트
    success = test_api_directly()
    
    # 3. 다른 엔드포인트 테스트
    if not success:
        test_different_endpoints()
    
    print("\n" + "="*80)
    print("💡 분석 결과:")
    if success:
        print("✅ API 호출이 성공했습니다. 문제는 다른 부분에 있을 수 있습니다.")
    else:
        print("❌ API 호출이 실패했습니다.")
        print("🔍 가능한 원인:")
        print("   1. 키움증권 서버 장애")
        print("   2. API 키/시크릿 문제")
        print("   3. 요청 형식 문제")
        print("   4. 네트워크 제한")
        print("   5. 계정 권한 문제")
    
    print("\n📞 추가 지원이 필요한 경우:")
    print("   - 키움증권 고객센터: 1544-5000")
    print("   - 개발자 문의: https://apiportal.kiwoom.com")
