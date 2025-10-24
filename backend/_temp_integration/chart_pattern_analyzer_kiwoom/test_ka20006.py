import requests
import json
import sys
import os
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def fn_ka20006(loader: KiwoomDataLoader, data: dict, cont_yn='N', next_key=''):
    """
    업종일봉조회 (ka20006) API를 호출합니다.
    """
    try:
        token = loader._get_token()
        if not token:
            print("❌ 토큰 발급에 실패했습니다.")
            return None, 'N', ''

        host = 'https://api.kiwoom.com'
        endpoint = '/api/dostk/chart'
        url = host + endpoint

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka20006',  # ✅ API ID 변경
        }

        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data, timeout=15)
        print(f"\n📊 응답 상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            cont_yn_res = response.headers.get('cont-yn', 'N')
            next_key_res = response.headers.get('next-key', '')
            
            # ✅ return_code 체크 추가
            if result.get('return_code') == 0:
                print("✅ 업종일봉 데이터 조회 성공")
                return result, cont_yn_res, next_key_res
            else:
                print(f"❌ API 실패: {result.get('return_msg')}")
                return None, 'N', ''
        else:
            print(f"❌ HTTP 실패: {response.status_code}")
            return None, 'N', ''

    except Exception as e:
        print(f"❌ 요청 중 예외 발생: {e}")
        return None, 'N', ''

# 테스트 함수
def test_ka20006():
    """
    ka20006 API 테스트
    """
    print("🚀 업종 일봉 차트 데이터 조회 (ka20006)")
    print(f"🕐 실행 시간: {datetime.now()}")
    
    loader = KiwoomDataLoader()
    
    # KOSPI 지수(001) 테스트
    params = {
        'inds_cd': '001',  # KOSPI 지수
        'base_dt': datetime.now().strftime('%Y%m%d'),
    }
    
    result, cont_yn, next_key = fn_ka20006(loader, params)
    
    if result and 'inds_dt_pole_qry' in result:
        chart_data = result['inds_dt_pole_qry']
        print(f"✅ 총 {len(chart_data)}개 일봉 데이터 수신")
        return chart_data
    else:
        print("❌ 데이터 조회 실패")
        return None

if __name__ == '__main__':
    test_ka20006()