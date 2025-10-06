import requests
import json
import sys
import os
from datetime import datetime
import time
import logging

# 현재 디렉토리를 Python 경로에 추가하여 kiwoom_data_loader를 임포트
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# 로그 설정
log_folder = os.path.join(current_dir, 'log_ka20003')
os.makedirs(log_folder, exist_ok=True)

# 로그 파일명에 타임스탬프 추가
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = os.path.join(log_folder, f'ka20003_{timestamp}.log')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()  # 콘솔에도 출력
    ]
)
logger = logging.getLogger(__name__)

from kiwoom_data_loader import KiwoomDataLoader

def fn_ka20003(loader: KiwoomDataLoader, data: dict):
    """
    전업종지수요청 (ka20003) API를 호출합니다.
    """
    try:
        # 1. 유효한 토큰 획득
        token = loader._get_token()
        if not token:
            logger.error("❌ 토큰 발급에 실패했습니다.")
            print("❌ 토큰 발급에 실패했습니다.")
            return None

        # 2. 요청 URL 설정
        host = 'https://api.kiwoom.com'  # 실전투자 서버
        endpoint = '/api/dostk/sect'
        url = host + endpoint

        # 3. Header 데이터 구성
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'api-id': 'ka20003', # API ID
        }

        # 4. HTTP POST 요청
        logger.info(f"🔍 요청 URL: {url}")
        logger.info(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")
        print(f"\n🔍 요청 URL: {url}")
        print(f"📄 요청 데이터: {json.dumps(data, indent=2, ensure_ascii=False)}")

        response = requests.post(url, headers=headers, json=data, timeout=15)

        # 5. 응답 처리
        logger.info(f"📊 응답 상태 코드: {response.status_code}")
        print(f"\n📊 응답 상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            logger.info("✅ 성공! 응답 데이터:")
            logger.info(json.dumps(result, indent=4, ensure_ascii=False))
            print("✅ 성공! 응답 데이터:")
            print(json.dumps(result, indent=4, ensure_ascii=False))
            return result
        else:
            logger.error(f"❌ 요청 실패: {response.status_code}")
            print(f"❌ 요청 실패: {response.status_code}")
            try:
                error_data = response.json()
                logger.error(f"🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
                print(f"🔍 에러 내용: {json.dumps(error_data, indent=4, ensure_ascii=False)}")
            except json.JSONDecodeError:
                logger.error(f"🔍 에러 텍스트: {response.text}")
                print(f"🔍 에러 텍스트: {response.text}")
            return None

    except Exception as e:
        logger.error(f"❌ 요청 중 예외 발생: {e}")
        print(f"❌ 요청 중 예외 발생: {e}")
        return None

# --- 메인 실행 로직 ---
if __name__ == '__main__':
    logger.info("🚀 키움증권 전업종지수 요청 (ka20003)")
    logger.info(f"🕐 실행 시간: {datetime.now()}")
    print("🚀 키움증권 전업종지수 요청 (ka20003)")
    print(f"🕐 실행 시간: {datetime.now()}")
    print("="*60)

    # KiwoomDataLoader 인스턴스를 한 번만 생성
    data_loader = KiwoomDataLoader()

    # 1. KOSPI 업종 지수 조회
    logger.info("[1/2] KOSPI 업종 지수 조회 시작")
    print("\n--- [1/2] KOSPI 업종 지수 조회 시작 ---")
    kospi_params = {
        'inds_cd': '001', # 업종코드 001:종합(KOSPI)
    }
    kospi_result = fn_ka20003(loader=data_loader, data=kospi_params)

    # API 호출 간격
    logger.info("API 호출 간격 대기 (1초)")
    time.sleep(1)

    # 2. KOSDAQ 업종 지수 조회
    logger.info("[2/2] KOSDAQ 업종 지수 조회 시작")
    print("\n--- [2/2] KOSDAQ 업종 지수 조회 시작 ---")
    kosdaq_params = {
        'inds_cd': '101', # 업종코드 101:종합(KOSDAQ)
    }
    kosdaq_result = fn_ka20003(loader=data_loader, data=kosdaq_params)

    logger.info("모든 요청 완료")
    print("\n" + "="*60)
    print("🎉 모든 요청 완료!")

    # 로그 파일 정보 출력
    logger.info(f"로그 파일이 저장되었습니다: {log_file}")
    print(f"\n📋 로그 파일이 저장되었습니다: {log_file}")
    print(f"📁 로그 폴더: {log_folder}")