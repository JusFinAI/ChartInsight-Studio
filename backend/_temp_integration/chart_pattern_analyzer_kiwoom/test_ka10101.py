import requests
import json
import sys
import os
from datetime import datetime
import pandas as pd

# 현재 디렉토리를 Python 경로에 추가하여 kiwoom_data_loader를 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def fn_ka10101(loader: KiwoomDataLoader, data: dict):
    """
    업종코드 리스트 (ka10101) API를 호출합니다.
    """
    try:
        # 1. 유효한 토큰 획득
        token = loader._get_token()
        if not token:
            print("❌ 토큰 발급에 실패했습니다.")
            return None

        # 2. 요청 URL 설정
        host = 'https://api.kiwoom.com'  # 실전투자 서버
        endpoint = '/api/dostk/stkinfo'
        url = host + endpoint

        # 3. Header 데이터 구성
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'api-id': 'ka10101', # API ID
        }

        # 4. HTTP POST 요청
        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, headers=headers, json=data, timeout=15)

        # 5. 응답 처리
        print(f"\n📊 응답 상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            # 응답 데이터의 양이 많으므로 전체를 출력하는 대신 요약 정보를 보여줍니다.
            if result and 'stk_ix_info' in result:
                stk_list = result['stk_ix_info']
                print(f"✅ 성공! 총 {len(stk_list)}개의 업종코드 리스트를 수신했습니다.")
                return result
            else:
                print("✅ 성공했으나, 응답 데이터에 'stk_ix_info' 키가 없습니다.")
                print(json.dumps(result, indent=4, ensure_ascii=False))
                return None
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            try:
                error_data = response.json()
                print(f"🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
            except json.JSONDecodeError:
                print(f"🔍 에러 텍스트: {response.text}")
            return None

    except Exception as e:
        print(f"❌ 요청 중 예외 발생: {e}")
        return None

# --- 메인 실행 로직 ---
if __name__ == '__main__':
    print("🚀 키움증권 업종코드 리스트 요청 (ka10101)")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # KiwoomDataLoader 인스턴스를 한 번만 생성
    data_loader = KiwoomDataLoader()

    # KOSPI 업종 코드 리스트 조회
    print("\n--- KOSPI 업종 코드 리스트 조회 시작 ---")
    kospi_params = {
        'mrkt_tp': '0', # 시장구분 0:코스피(거래소)
    }
    kospi_result = fn_ka10101(loader=data_loader, data=kospi_params)

    if kospi_result and 'stk_ix_info' in kospi_result:
        # 결과를 보기 좋게 Pandas DataFrame으로 변환하여 출력
        df = pd.DataFrame(kospi_result['stk_ix_info'])
        print("\n--- KOSPI 업종코드 리스트 (상위 10개) ---")
        print(df.head(10).to_string(index=False))

    print("\n" + "="*60)
    print("🎉 요청 완료!")