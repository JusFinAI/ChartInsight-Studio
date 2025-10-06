import requests
import json
import sys
import os
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

# 주식연간실적정보요청 (개선된 인증 방식 적용)
def fn_ka10094(data):
    """개선된 인증 방식으로 주식연간실적정보 요청"""

    try:
        # 1. KiwoomDataLoader를 통해 토큰 획득
        loader = KiwoomDataLoader()
        token = loader._get_token()

        if not token:
            print("❌ 토큰 발급 실패")
            return None

        print(f"✅ 토큰 발급 성공: {token[:20]}...")

        # 2. 요청할 API URL
        host = 'https://api.kiwoom.com'  # 실전투자
        endpoint = '/api/dostk/chart'
        url = host + endpoint

        # 3. header 데이터
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',  # 컨텐츠타입
            'authorization': f'Bearer {token}',  # 접근토큰
            'api-id': 'ka10094',  # TR명
        }

        # 4. http POST 요청
        print(f"🔍 요청 URL: {url}")
        print(f"📊 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data, timeout=15)

        # 5. 응답 상태 코드와 데이터 출력
        print(f"\n📊 응답 상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ 성공! 응답 데이터:")
            print(json.dumps(result, indent=4, ensure_ascii=False))
            return result
        elif response.status_code == 500:
            print("❌ 서버 내부 오류 (500)")
            try:
                error_data = response.json()
                print(f"🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
            except:
                print(f"🔍 에러 텍스트: {response.text}")
            return None
        else:
            print(f"⚠️ 기타 오류: {response.status_code}")
            print(f"📄 응답: {response.text[:200]}...")
            return None

    except Exception as e:
        print(f"❌ 요청 중 오류 발생: {e}")
        return None

# 실행 구간
if __name__ == '__main__':
    print("🚀 키움증권 EPS 정보 조회")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # 1. 요청 데이터 설정
    params = {
        'stk_cd': '005930',  # 종목코드 (삼성전자)
        'base_dt': '20250905',  # 기준일자 YYYYMMDD
        'upd_stkpc_tp': '1',  # 수정주가구분 0 or 1
    }

    # 2. API 실행 (개선된 인증 방식 사용)
    result = fn_ka10094(data=params)

    print("\n" + "="*60)
    if result:
        print("✅ EPS 정보 조회 성공!")
    else:
        print("❌ EPS 정보 조회 실패")
        print("\n🔧 해결 방안:")
        print("1. 키움증권 계정 인증 정보 확인")
        print("2. KiwoomDataLoader 클래스의 토큰 발급 로직 확인")
        print("3. 키움증권 고객센터 문의 (1544-5000)")