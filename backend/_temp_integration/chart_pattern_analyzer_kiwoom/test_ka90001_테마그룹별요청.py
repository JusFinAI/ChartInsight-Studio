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

def fn_ka90001(loader: KiwoomDataLoader, data: dict):
    """
    테마 그룹 조회 (ka90001) API를 호출합니다.
    """
    try:
        # 1. 유효한 토큰 획득
        token = loader._get_token()
        if not token:
            print("❌ 토큰 발급에 실패했습니다.")
            return None

        # 2. 요청 URL 설정
        host = 'https://api.kiwoom.com'  # 실전투자 서버
        endpoint = '/api/dostk/thme'
        url = host + endpoint

        # 3. Header 데이터 구성
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'api-id': 'ka90001', # API ID
        }

        # 4. HTTP POST 요청
        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        
        response = requests.post(url, headers=headers, json=data, timeout=15)

        # 5. 응답 처리
        print(f"\n📊 응답 상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            if result and result.get('return_code') == 0 and 'thema_grp' in result:
                thema_list = result['thema_grp']
                print(f"✅ 성공! 총 {len(thema_list)}개의 테마 그룹을 수신했습니다.")
                return result
            else:
                print("✅ 성공했으나, 응답 데이터에 'thema_grp' 키가 없습니다.")
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
    print("🚀 키움증권 테마 그룹 조회 요청 (ka90001)")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # KiwoomDataLoader 인스턴스를 한 번만 생성
    data_loader = KiwoomDataLoader()

    # 전체 테마 그룹 조회
    print("\n--- 전체 테마 그룹 조회 시작 ---")
    thema_params = {
        'qry_tp': '0',           # 0:전체검색, 1:테마검색, 2:종목검색
        'stk_cd': '',            # 종목코드 (종목검색 시 사용)
        'date_tp': '10',         # 10일간
        'thema_nm': '',          # 테마명 (테마검색 시 사용)
        'flu_pl_amt_tp': '1',    # 1:당일수익률
        'stex_tp': '1'           # 1:KRX
    }
    thema_result = fn_ka90001(loader=data_loader, data=thema_params)

    if thema_result and 'thema_grp' in thema_result:
        # 결과를 보기 좋게 Pandas DataFrame으로 변환하여 출력
        df = pd.DataFrame(thema_result['thema_grp'])
        print("\n--- 테마 그룹 리스트 (상위 10개) ---")
        print(df.head(10).to_string(index=False))
        
        # CSV 파일로 저장 (한글 인코딩)
        data_dir = os.path.join(current_dir, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        csv_filename = os.path.join(data_dir, 'thema_groups_ka90001.csv')
        df.to_csv(csv_filename, index=False, encoding='utf-8-sig')
        print(f"\n💾 CSV 파일 저장 완료: {csv_filename}")
        print(f"📊 저장된 데이터: {len(df)}개 테마 그룹")

    print("\n" + "="*60)
    print("🎉 요청 완료!")
