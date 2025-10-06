import requests
import json
import sys
import os
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가하여 kiwoom_data_loader를 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def fn_ka10083(data, cont_yn='N', next_key=''):
    """
    주식월봉차트조회요청 (ka10083) API를 호출합니다.
    test_ka10094.py와 동일한 인증 방식을 사용합니다.
    """
    try:
        # 1. KiwoomDataLoader를 통해 유효한 토큰 획득
        loader = KiwoomDataLoader()
        token = loader._get_token()

        if not token:
            print("❌ 토큰 발급에 실패했습니다. kiwoom_data_loader.py를 확인해주세요.")
            return None

        print(f"✅ 토큰 발급 성공: {token[:20]}...")

        # 2. 요청할 API URL 설정
        host = 'https://api.kiwoom.com'  # 실전투자 서버
        endpoint = '/api/dostk/chart'
        url = host + endpoint

        # 3. Header 데이터 구성
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'api-id': 'ka10083',  # API ID를 ka10083으로 변경
            'cont-yn': cont_yn,   # 연속 조회 여부
            'next-key': next_key, # 연속 조회 키
        }

        # 4. HTTP POST 요청
        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, headers=headers, json=data, timeout=15)

        # 5. 응답 처리
        print(f"\n📊 응답 상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            # 전체 응답 데이터를 출력하지 않음 (너무 길어서)

            # 연속 조회 정보 출력
            cont_yn_res = response.headers.get('cont-yn', 'N')
            next_key_res = response.headers.get('next-key', '')
            print(f"\n🔄 연속 조회 정보: cont-yn='{cont_yn_res}', next-key='{next_key_res}'")

            if cont_yn_res == 'Y':
                print("\n💡 추가 데이터가 있습니다. 반환된 next-key로 다음 요청을 보낼 수 있습니다.")

            return result, cont_yn_res, next_key_res
        else:
            print(f"❌ 요청 실패: {response.status_code}")
            try:
                error_data = response.json()
                print(f"🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
            except json.JSONDecodeError:
                print(f"🔍 에러 텍스트: {response.text}")
            return None, 'N', ''

    except Exception as e:
        print(f"❌ 요청 중 예외 발생: {e}")
        return None, 'N', ''

# --- 메인 실행 로직 ---
if __name__ == '__main__':
    print("🚀 키움증권 월봉 차트 데이터 조회 (ka10083)")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # 1. 요청 파라미터 설정
    params = {
        'stk_cd': '005930',        # 종목코드 (삼성전자)
        'base_dt': '20250930',    # 기준일자 (YYYYMMDD) - 오늘 날짜 또는 과거 날짜
        'upd_stkpc_tp': '1',      # 수정주가구분 (1: 수정주가 적용)
    }

    # 2. API 실행
    result, cont_yn, next_key = fn_ka10083(data=params)

    print("\n" + "="*60)
    if result:
        print("✅ 월봉 데이터 첫 조회 성공!")

        # 월봉 데이터 분석 및 출력
        if 'stk_mth_pole_chart_qry' in result:
            chart_data = result['stk_mth_pole_chart_qry']
            data_count = len(chart_data)

            print(f"\n📊 월봉 데이터 분석 결과:")
            print(f"   • 총 데이터 개수: {data_count}개")

            if data_count > 0:
                first_data = chart_data[0]
                last_data = chart_data[-1]

                print(f"   • 첫 번째 데이터 ({first_data.get('dt', 'N/A')}):")
                print(f"     - 종가: {first_data.get('cur_prc', 'N/A')}원")
                print(f"     - 거래량: {first_data.get('trde_qty', 'N/A')}주")
                print(f"     - 시가: {first_data.get('open_pric', 'N/A')}원")
                print(f"     - 고가: {first_data.get('high_pric', 'N/A')}원")
                print(f"     - 저가: {first_data.get('low_pric', 'N/A')}원")

                print(f"\n   • 마지막 데이터 ({last_data.get('dt', 'N/A')}):")
                print(f"     - 종가: {last_data.get('cur_prc', 'N/A')}원")
                print(f"     - 거래량: {last_data.get('trde_qty', 'N/A')}주")
                print(f"     - 시가: {last_data.get('open_pric', 'N/A')}원")
                print(f"     - 고가: {last_data.get('high_pric', 'N/A')}원")
                print(f"     - 저가: {last_data.get('low_pric', 'N/A')}원")

                # 날짜 범위 정보
                if data_count > 1:
                    first_date = first_data.get('dt', 'N/A')
                    last_date = last_data.get('dt', 'N/A')
                    print(f"\n📅 데이터 기간: {last_date} ~ {first_date}")
            else:
                print("   ⚠️  데이터가 없습니다.")
        else:
            print("⚠️  'stk_mth_pole_chart_qry' 필드가 응답에 없습니다.")

        # 연속 조회
        if cont_yn == 'Y':
            print("\n" + "--- 연속 조회 (2번째 페이지) 시작 ---")
            # next_key를 사용하여 다음 데이터 요청
            result_next, _, _ = fn_ka10083(data=params, cont_yn='Y', next_key=next_key)
            if result_next:
                print("\n✅ 연속 조회 성공!")
            else:
                print("\n❌ 연속 조회 실패.")

    else:
        print("❌ 월봉 데이터 조회 실패")
        print("\n🔧 해결 방안:")
        print("1. KiwoomDataLoader의 인증 정보가 올바른지 확인하세요.")
        print("2. 요청 파라미터('stk_cd', 'base_dt')가 유효한지 확인하세요.")
        print("3. API 서버 상태를 확인하거나 잠시 후 다시 시도해보세요.")