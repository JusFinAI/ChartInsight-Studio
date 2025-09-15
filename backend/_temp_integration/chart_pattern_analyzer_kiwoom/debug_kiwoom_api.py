"""
키움증권 API 연결 상태 디버깅 스크립트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader
from datetime import datetime, timedelta

def debug_kiwoom_connection():
    """키움증권 API 연결 상태 및 설정 디버깅"""
    
    print("🔍 키움증권 API 연결 디버깅")
    print("="*50)
    
    try:
        # 1. 로더 초기화
        print("1️⃣ KiwoomDataLoader 초기화...")
        loader = KiwoomDataLoader()
        print("✅ 로더 초기화 성공")
        
        # 2. 토큰 상태 확인
        print("\n2️⃣ 토큰 상태 확인...")
        token = loader._get_token()
        if token:
            print("✅ 토큰 발급 성공")
            print(f"🔑 토큰 길이: {len(token)} 문자")
        else:
            print("❌ 토큰 발급 실패")
            return False
        
        # 3. 현재 시간 확인
        print("\n3️⃣ 시간 설정 확인...")
        now = datetime.now()
        print(f"🕐 현재 시간: {now}")
        print(f"🕐 UTC 시간: {datetime.utcnow()}")
        
        # 4. 간단한 데이터 요청 (소량)
        print("\n4️⃣ 소량 데이터 테스트...")
        print("📊 삼성전자 일봉 10개 요청...")
        
        data = loader.download_data(
            ticker="005930", 
            interval="1d", 
            count=10  # 소량으로 테스트
        )
        
        if data is not None and not data.empty:
            print("✅ 데이터 수신 성공!")
            print(f"📈 데이터 형태: {data.shape}")
            print(f"📊 컬럼: {list(data.columns)}")
            print(f"📅 최신 데이터:")
            print(data.head(3))
            return True
        else:
            print("❌ 데이터 수신 실패")
            return False
            
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        print(f"❌ 오류 타입: {type(e).__name__}")
        return False

def test_different_intervals():
    """다양한 타임프레임 테스트"""
    
    print("\n🔄 다양한 타임프레임 테스트")
    print("="*50)
    
    intervals = ["1d", "1wk"]  # 안전한 타임프레임만 테스트
    loader = KiwoomDataLoader()
    
    for interval in intervals:
        try:
            print(f"\n📊 {interval} 테스트 중...")
            data = loader.download_data("005930", interval, count=5)
            
            if data is not None and not data.empty:
                print(f"✅ {interval} 성공: {len(data)}개")
            else:
                print(f"❌ {interval} 실패")
                
        except Exception as e:
            print(f"❌ {interval} 오류: {e}")

if __name__ == "__main__":
    print("🚀 키움증권 API 디버깅 시작")
    
    # 기본 연결 테스트
    connection_ok = debug_kiwoom_connection()
    
    if connection_ok:
        # 추가 테스트
        test_different_intervals()
        print("\n✅ 디버깅 완료: API 연결 정상")
    else:
        print("\n❌ 디버깅 완료: API 연결 문제 발견")
        
    print("\n💡 해결책:")
    print("1. 토큰이 만료된 경우: 몇 분 후 재시도")
    print("2. 요청 한도 초과: 10-15분 후 재시도") 
    print("3. 서버 문제: 키움증권 고객센터 문의")
    print("4. 환경 설정: settings.yaml 실투자/모의투자 확인")
