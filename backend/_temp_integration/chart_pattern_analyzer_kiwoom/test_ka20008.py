import requests
import json
import sys
import os
from datetime import datetime

# 현재 디렉토리를 Python 경로에 추가하여 kiwoom_data_loader를 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

def fn_ka20008(data, cont_yn='N', next_key=''):
    """
    업종월봉조회요청 (ka20008) API를 호출합니다.
    """
    try:
        loader = KiwoomDataLoader()
        token = loader._get_token()
        if not token:
            print("❌ 토큰 발급에 실패했습니다. kiwoom_data_loader.py를 확인해주세요.")
            return None, 'N', ''

        host = 'https://api.kiwoom.com'
        endpoint = '/api/dostk/chart'
        url = host + endpoint

        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': 'ka20008',
        }

        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data, timeout=15)
        print(f"\n📊 응답 상태 코드: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            cont_yn_res = response.headers.get('cont-yn', 'N')
            next_key_res = response.headers.get('next-key', '')
            print(f"\n🔄 연속 조회 정보: cont-yn='{cont_yn_res}', next-key='{next_key_res}'")
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

if __name__ == '__main__':
    print("🚀 업종 월봉 차트 데이터 조회 (ka20008)")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # 기본 파라미터: inds_cd=029 (서비스업) 기준일은 최근 예제와 맞추어 오늘 날짜 사용
    params = {
        'inds_cd': '129',
        'base_dt': datetime.now().strftime('%Y%m%d'),
        
    }

    result, cont_yn, next_key = fn_ka20008(data=params)

    print("\n" + "="*60)
    if result:
        print("✅ 업종 월봉 첫 조회 응답 확인")
        # 핵심 필드 검사
        if 'inds_mth_pole_qry' in result:
            chart_data = result['inds_mth_pole_qry']
            print(f"총 데이터 개수: {len(chart_data)}개")
            if len(chart_data) > 0:
                #print('첫 항목 샘플:', json.dumps(chart_data[0], ensure_ascii=False, indent=2))
                #print('마지막 항목 샘플:', json.dumps(chart_data[-1], ensure_ascii=False, indent=2))
                print('전체 샘플:', json.dumps(chart_data, ensure_ascii=False, indent=2))
                
        else:
            print("⚠️ 응답에 'inds_mth_pole_qry' 필드가 없습니다.")

        if cont_yn == 'Y':
            print("\n--- 연속 조회(다음 페이지) 시도 ---")
            result_next, cont2, key2 = fn_ka20008(data=params, cont_yn='Y', next_key=next_key)
            if result_next:
                print("연속 조회 응답 확인")
            else:
                print("연속 조회 실패")
    else:
        print("❌ 업종 월봉 데이터 조회 실패")
