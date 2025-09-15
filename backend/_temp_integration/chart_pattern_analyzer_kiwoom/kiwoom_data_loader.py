"""
키움증권 API 데이터 로더
kiwoom_api 폴더의 정제된 모듈들을 사용하여 차트 데이터를 pandas DataFrame으로 변환
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from kiwoom_api.models.chart_data import ChartData
import json
import logging

# module logger
logger = logging.getLogger(__name__)

# 키움증권 API 모듈들 import (kiwoom_api 폴더 사용)
current_dir = os.path.dirname(os.path.abspath(__file__))
kiwoom_api_path = os.path.join(current_dir, 'kiwoom_api')

# sys.path에 kiwoom_api 경로 추가
if kiwoom_api_path not in sys.path:
    sys.path.insert(0, kiwoom_api_path)

logger.info(f"🔍 kiwoom_api 경로: {kiwoom_api_path}")

try:
    # 모듈별로 직접 import
    sys.path.insert(0, current_dir)
    
    # 서비스 모듈들을 직접 import
    from kiwoom_api.services.chart import ChartService
    from kiwoom_api.models.chart_data import ChartData
    from kiwoom_api.core.auth import Auth as AuthService
    
    logger.info("✅ 키움증권 API 모듈 import 성공")
    MODULES_LOADED = True
    
except ImportError as e:
    logger.error(f"❌ 키움증권 API 모듈 import 실패: {e}")
    logger.error(f"❌ kiwoom_api 경로: {kiwoom_api_path}")
    
    # 단계별 디버깅
    try:
        logger.info("🔍 단계별 import 테스트:")
        
        # 1단계: kiwoom_api 모듈 확인
        import kiwoom_api
        logger.info(f"   ✅ kiwoom_api 기본 모듈 로드 성공")
        logger.info(f"   📁 위치: {kiwoom_api.__file__}")
        
        # 2단계: 서브모듈 확인
        from kiwoom_api.services import chart
        logger.info(f"   ✅ chart 서비스 모듈 로드 성공")
        
        from kiwoom_api.models import chart_data
        logger.info(f"   ✅ chart_data 모델 모듈 로드 성공")
        
        from kiwoom_api.core import auth
        logger.info(f"   ✅ auth 코어 모듈 로드 성공")
        
    except Exception as debug_e:
        logger.error(f"   ❌ 디버깅 중 오류: {debug_e}")
    
    MODULES_LOADED = False

class KiwoomDataLoader:
    """키움증권 API를 통한 차트 데이터 로더 (kiwoom_api 모듈 사용)"""
    
    def __init__(self):
        """초기화"""
        # 모듈 로드 상태 확인
        if not MODULES_LOADED:
            raise ImportError("키움증권 API 모듈 로드에 실패했습니다.")
        
        # 키움증권 API 서비스 초기화
        self.auth_service = AuthService()
        self.chart_service = ChartService()
        
        logger.info("✅ 키움증권 API 서비스 초기화 완료")
    
    def _get_token(self) -> str:
        """OAuth 토큰 발급/갱신"""
        try:
            logger.info("🔑 OAuth 토큰 발급/갱신 중...")
            token = self.auth_service.get_token()
            if token:
                logger.info("✅ 토큰 발급/갱신 성공")
                return token
            else:
                logger.error("❌ 토큰 발급/갱신 실패")
                return None
        except Exception as e:
            logger.error(f"❌ 토큰 발급/갱신 오류: {e}")
            return None
    
    def _convert_chartdata_to_dataframe(self, chart_data: 'ChartData') -> Optional[pd.DataFrame]:
        """
        ChartData 객체를 pandas DataFrame으로 변환
        
        Args:
            chart_data: ChartData 객체
            
        Returns:
            pd.DataFrame: OHLCV 데이터프레임 (Date를 인덱스로 함)
        """
        try:
            if not chart_data or not chart_data.data:
                logger.error("❌ 차트 데이터가 없습니다.")
                return None

            logger.info(f"🔍 ChartData 변환 시작: {len(chart_data.data)}개 항목")
            logger.info(f"[DEBUG] chart_data.to_dataframe() 호출 직전! chart_type={getattr(chart_data, 'chart_type', 'Unknown')}")
            
            # ChartData의 내장 to_dataframe() 메서드 사용
            df = chart_data.to_dataframe()
            
            logger.info(f"[DEBUG] chart_data.to_dataframe() 호출 완료! df.shape={df.shape if df is not None else 'None'}")
            
            if df is None or df.empty:
                logger.error("❌ DataFrame 변환 결과가 비어있습니다.")
                return None

            logger.info(f"✅ DataFrame 변환 완료: {len(df)}개 캔들")
            logger.info(f"📊 컬럼: {list(df.columns)}")
            
            # Date 컬럼이 있으면 인덱스로 설정
            if 'Date' in df.columns:
                df.set_index('Date', inplace=True)
            elif 'date' in df.columns:
                df.set_index('date', inplace=True)
            
            # 키움증권 컬럼명을 표준 OHLCV로 매핑
            column_mapping = {
                'dt': 'Date',
                'open_pric': 'Open', 
                'high_pric': 'High',
                'low_pric': 'Low',
                'cur_prc': 'Close',
                'trde_qty': 'Volume',
                # 소문자 버전도 지원
                'open': 'Open',
                'high': 'High', 
                'low': 'Low',
                'close': 'Close',
                'volume': 'Volume'
            }
            df.rename(columns=column_mapping, inplace=True)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ DataFrame 변환 실패: {e}")
            logger.debug(f"🔍 ChartData 속성: {dir(chart_data)}")
            if hasattr(chart_data, 'data'):
                logger.debug(f"🔍 data 길이: {len(chart_data.data)}")
                if chart_data.data:
                    logger.debug(f"🔍 첫 번째 항목: {chart_data.data[0]}")
            return None
    
    def download_data(self, ticker: str, interval: str, count: int = 1000) -> Optional[pd.DataFrame]:
        """
        키움증권 API로 차트 데이터 다운로드 (kiwoom_api 서비스 사용)
        
        Args:
            ticker: 6자리 종목 코드 (예: '005930')
            interval: 타임프레임 ('5m', '30m', '1h', '1d', '1wk')
            count: 요청할 캔들 개수
            
        Returns:
            pd.DataFrame: OHLCV 데이터프레임 (Date를 인덱스로 함)
        """
        logger.info(f"📊 {ticker} {interval} 데이터 다운로드 시작...")
        
        # API 호출 전 잠시 대기 (과도한 요청 방지)
        import time
        time.sleep(1)
        
        try:
            chart_data = None
            
            if interval in ['5m', '30m', '1h']:
                # 분봉 데이터 요청
                tic_scope_map = {'5m': 5, '30m': 30, '1h': 60}
                tic_scope = tic_scope_map[interval]
                
                logger.info(f"🔄 분봉 API 호출 (tic_scope: {tic_scope}분)")
                chart_data = self.chart_service.get_minute_chart(
                    stock_code=ticker,
                    tic_scope=tic_scope,
                    num_candles=count
                )
                
            elif interval == '1d':
                # 일봉 데이터 요청
                logger.info("🔄 일봉 API 호출")
                chart_data = self.chart_service.get_daily_chart(
                    stock_code=ticker,
                    num_candles=count
                )
                
            elif interval == '1wk':
                # 주봉 데이터 요청
                logger.info("🔄 주봉 API 호출")
                chart_data = self.chart_service.get_weekly_chart(
                    stock_code=ticker,
                    num_candles=count
                )
                
            else:
                logger.error(f"❌ 지원하지 않는 interval: {interval}")
                return None
            
            # ChartData를 DataFrame으로 변환
            if chart_data:
                df = self._convert_chartdata_to_dataframe(chart_data)

                if df is not None and not df.empty:
                    logger.info(f"✅ 데이터 다운로드 완료: {len(df)}개 캔들")
                    logger.info(f"📅 기간: {df.index[0]} ~ {df.index[-1]}")
                    return df
                else:
                    logger.error("❌ DataFrame 변환 실패")
                    return None
            else:
                logger.error("❌ 차트 데이터 조회 실패")
                return None
                
        except Exception as e:
            logger.error(f"❌ 데이터 다운로드 오류: {e}")
            return None

# 테스트용 메인 함수
if __name__ == "__main__":
    print("🔍 키움증권 API 데이터 로더 테스트")
    print("="*50)
    
    # 데이터 로더 초기화
    loader = KiwoomDataLoader()
    
    # 테스트 파라미터
    test_ticker = "005930"  # 삼성전자
    test_intervals = ["1d"]  # 먼저 일봉만 테스트
    
    for interval in test_intervals:
        print(f"\n📊 {test_ticker} {interval} 테스트 시작...")
        
        # 데이터 다운로드
        df = loader.download_data(test_ticker, interval, count=100)
        
        if df is not None:
            print(f"✅ {interval} 성공!")
            print(f"📈 데이터 형태: {df.shape}")
            print(f"📊 컬럼: {list(df.columns)}")
            print("\n🔍 최근 5개 데이터:")
            print(df.tail())
        else:
            print(f"❌ {interval} 실패!")
        
        print("-" * 30)
    
    print("\n✅ 테스트 완료!")
