"""
analysis_engine.py의 수정된 download_data 함수 테스트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from analysis_engine import download_data

def test_download_data():
    """키움증권 API 기반 download_data 함수 테스트"""
    
    print("🔍 analysis_engine.download_data() 테스트")
    print("="*50)
    
    # 테스트 파라미터
    test_ticker = "005930"  # 삼성전자
    test_interval = "1d"    # 일봉
    
    print(f"📊 테스트 종목: {test_ticker}")
    print(f"⏰ 타임프레임: {test_interval}")
    
    # 데이터 다운로드 테스트
    data = download_data(test_ticker, period="2y", interval=test_interval)
    
    if data is not None and not data.empty:
        print(f"✅ 데이터 다운로드 성공!")
        print(f"📈 데이터 형태: {data.shape}")
        print(f"📊 컬럼: {list(data.columns)}")
        print(f"📅 인덱스 타입: {type(data.index)}")
        print(f"📅 기간: {data.index[0]} ~ {data.index[-1]}")
        
        print("\n🔍 최근 5개 데이터:")
        print(data.tail())
        
        # OHLCV 컬럼 확인
        required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if not missing_columns:
            print("✅ 모든 필수 컬럼 (OHLCV) 존재")
        else:
            print(f"❌ 누락된 컬럼: {missing_columns}")
        
        return True
        
    else:
        print("❌ 데이터 다운로드 실패")
        return False

if __name__ == "__main__":
    success = test_download_data()
    print(f"\n{'✅' if success else '❌'} 테스트 완료!")
