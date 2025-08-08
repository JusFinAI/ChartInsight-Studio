"""데이터 다운로드 유틸리티"""

import numpy as np
import pandas as pd
import logging
import time
import sys
import os
from datetime import datetime

from app.utils.cache import data_cache
from app.utils.logger_config import get_logger

# 로거 설정
logger = get_logger("chartinsight-api.data_loader", "data_loader")

# 타임프레임별 최대 다운로드 가능 기간 (일 수)
INTERVAL_MAX_DAYS = {
    "1m": 7,       # 1분봉은 최대 7일
    "2m": 60,      # 2분봉은 최대 60일
    "3m": 60,      # 3분봉은 최대 60일 (대체 옵션으로 2m 사용)
    "5m": 60,      # 5분봉은 최대 60일
    "15m": 60,     # 15분봉은 최대 60일
    "30m": 60,     # 30분봉은 최대 60일
    "60m": 730,    # 1시간봉은 최대 730일
    "90m": 730,    # 90분봉은 최대 730일
    "1h": 730,     # 1시간봉은 최대 730일
    "1d": 7300,    # 일봉은 최대 7300일
    "5d": 7300,    # 5일봉은 최대 7300일
    "1wk": 7300,   # 주봉은 최대 7300일
    "1mo": 7300,   # 월봉은 최대 7300일
    "3mo": 7300    # 3개월봉은 최대 7300일
}

def get_optimal_period(interval):
    """
    타임프레임에 맞는 최적화된 기간을 반환
    
    Args:
        interval (str): 데이터 간격 (예: "1m", "30m", "1d")
        
    Returns:
        str: 최적화된 기간 (예: "7d", "60d", "max")
    """
    if interval in ["1m"]:
        return "7d"  # 1분봉은 최대 7일
    elif interval in ["2m", "5m", "15m", "30m"]:
        return "60d"  # 다른 분봉은 최대 60일
    elif interval in ["60m", "90m", "1h"]:
        return "730d"  # 시간봉은 최대 730일
    else:
        return "max"  # 일봉 이상은 최대 기간

def normalize_ticker(ticker):
    """
    티커 심볼을 Yahoo Finance 형식으로 변환
    
    Args:
        ticker (str): 원래 티커 심볼 (예: "BTC/USD", "ETH/USD")
        
    Returns:
        str: 변환된 티커 심볼 (예: "BTC-USD", "ETH-USD")
    """
    # '/'를 '-'로 변환 (암호화폐 티커에서 필요)
    normalized = ticker.replace('/', '-')
    logger.info(f"티커 변환: {ticker} -> {normalized}")
    return normalized

def download_data(ticker, period="2y", interval="1d", retries=3, delay=5, use_cache=True):
    """
    키움 API 또는 더미 데이터를 사용한 주식 데이터 다운로드 (캐싱 기능 추가)
    
    Args:
        ticker (str): 주식 티커 심볼 (예: "AAPL", "005930.KS")
        period (str): 다운로드 기간 (예: "1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y", "ytd", "max")
        interval (str): 데이터 간격 (예: "1m", "2m", "5m", "15m", "30m", "60m", "90m", "1h", "1d", "5d", "1wk", "1mo", "3mo")
        retries (int): 재시도 횟수 (사용하지 않음, 호환성 유지)
        delay (int): 재시도 간 지연 시간(초) (사용하지 않음, 호환성 유지)
        use_cache (bool): 캐시 사용 여부
        
    Returns:
        pandas.DataFrame: OHLC 데이터 프레임, 실패시 None
    """
    # 티커 심볼 정규화
    normalized_ticker = normalize_ticker(ticker)
    
    # 캐시 키 생성
    cache_key = f"{normalized_ticker}_{period}_{interval}"
    
    # 캐시 확인 (캐시 사용 설정시)
    if use_cache:
        cached_data = data_cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"캐시에서 데이터 로드: {normalized_ticker}, 기간: {period}, 간격: {interval}, 데이터 크기: {len(cached_data)}")
            
            # 캐시된 데이터 유효성 검증
            if len(cached_data) > 0:
                return cached_data
            logger.warning("캐시된 데이터가 비어 있어 무시하고 새로 다운로드합니다.")
    
    # 한국 주식 여부 판별
    if is_korean_stock(normalized_ticker):
        logger.info(f"한국 주식 감지: {normalized_ticker} - 키움 API 사용")
        data = download_korean_stock_data(normalized_ticker, period, interval)
    else:
        logger.info(f"해외 주식 감지: {normalized_ticker} - 더미 데이터 생성")
        data = generate_dummy_data_for_foreign_stock(normalized_ticker, period, interval)
    
    # 데이터 검증 및 캐시 저장
    if data is not None and not data.empty:
        # 결과 로그
        start_date = data.index[0].strftime("%Y-%m-%d %H:%M:%S")
        end_date = data.index[-1].strftime("%Y-%m-%d %H:%M:%S")
        logger.info(f"데이터 로드 완료: {len(data)}개 ({start_date} ~ {end_date})")
        
        # 캐시에 저장 (캐시 사용 설정시)
        if use_cache:
            data_cache.set(cache_key, data)
            logger.info(f"데이터 캐싱 완료: {cache_key}")
        
        return data
    else:
        logger.error(f"데이터 로드 실패: {normalized_ticker}")
        return None
                
def generate_dummy_data(days=30):
    """
    테스트용 더미 데이터 생성
    
    Args:
        days (int): 생성할 데이터 일수
        
    Returns:
        pandas.DataFrame: 더미 OHLC 데이터 프레임
    """
    logger.info(f"더미 데이터 생성 ({days}일)")
    end_date = pd.Timestamp.now()
    start_date = end_date - pd.Timedelta(days=days)
    date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    
    # 시작 가격
    base_price = 50000 + np.random.randn() * 5000
    
    data = {
        'Open': [],
        'High': [],
        'Low': [],
        'Close': [],
        'Volume': []
    }
    
    prev_close = base_price
    for _ in range(len(date_range)):
        # 난수로 변동성 설정
        volatility = np.random.uniform(0.01, 0.03)  
        direction = np.random.choice([-1, 1], p=[0.4, 0.6])  # 60% 확률로 상승
        change = prev_close * volatility * direction
        
        # OHLC 생성
        open_price = prev_close
        close_price = open_price + change
        high_price = max(open_price, close_price) + abs(change) * np.random.uniform(0.1, 0.5)
        low_price = min(open_price, close_price) - abs(change) * np.random.uniform(0.1, 0.5)
        
        # 볼륨 생성 (1백만~5백만)
        volume = np.random.randint(1000000, 5000000)
        
        # 데이터 추가
        data['Open'].append(open_price)
        data['High'].append(high_price)
        data['Low'].append(low_price)
        data['Close'].append(close_price)
        data['Volume'].append(volume)
        
        # 다음 날을 위해 종가 저장
        prev_close = close_price
    
    # DataFrame 생성
    dummy_data = pd.DataFrame(data, index=date_range)
    logger.info(f"더미 데이터 생성 완료: {len(dummy_data)}일")
    
    return dummy_data


def is_korean_stock(symbol):
    """
    한국 주식 여부 판별
    
    Args:
        symbol (str): 주식 심볼
        
    Returns:
        bool: 한국 주식이면 True, 아니면 False
    """
    # .KS로 끝나는 경우 (예: 005930.KS)
    if symbol.endswith('.KS'):
        return True
    
    # 6자리 숫자로만 구성된 경우 (예: 005930)
    if len(symbol) == 6 and symbol.isdigit():
        return True
    
    return False


def download_korean_stock_data(symbol, period, interval):
    """
    키움 API를 사용하여 한국 주식 데이터 다운로드
    
    Args:
        symbol (str): 한국 주식 심볼 (예: '005930.KS' 또는 '005930')
        period (str): 조회 기간 (예: '1y', '2y')
        interval (str): 데이터 간격 (예: '1d', '1h', '5m')
        
    Returns:
        pandas.DataFrame: OHLCV 데이터, 실패시 None
    """
    try:
        # .KS 제거하여 순수 종목코드 추출
        stock_code = symbol.replace('.KS', '')
        
        # 키움 API 함수들 import
        if interval == '1d':
            from app.kiwoom.daily_chart import get_daily_chart
            logger.info(f"키움 일봉 API 호출: {stock_code}, 기간: {period}")
            return get_daily_chart(stock_code, period)
            
        elif interval in ['1m', '3m', '5m', '15m', '30m', '60m']:
            from app.kiwoom.minute_chart import get_minute_chart
            # interval을 분 단위 숫자로 변환 (예: '5m' -> 5)
            minute_interval = int(interval.replace('m', ''))
            logger.info(f"키움 분봉 API 호출: {stock_code}, 간격: {minute_interval}분, 기간: {period}")
            return get_minute_chart(stock_code, time_interval=minute_interval, period=period)
            
        elif interval in ['1w', '1wk']:
            from app.kiwoom.weekly_chart import get_weekly_chart
            logger.info(f"키움 주봉 API 호출: {stock_code}, 기간: {period}")
            return get_weekly_chart(stock_code, period)
            
        else:
            logger.warning(f"지원하지 않는 간격: {interval}, 일봉으로 대체")
            from app.kiwoom.daily_chart import get_daily_chart
            return get_daily_chart(stock_code, period)
            
    except Exception as e:
        logger.error(f"키움 API 호출 실패: {symbol}, {str(e)}")
        return None


def generate_dummy_data_for_foreign_stock(symbol, period, interval, seed=None):
    """
    해외 주식용 더미 데이터 생성 (심볼별 고유 패턴)
    
    Args:
        symbol (str): 주식 심볼 (예: 'AAPL', 'TSLA')
        period (str): 기간 (예: '1y', '2y')
        interval (str): 간격 (예: '1d', '1h')
        seed (int, optional): 난수 시드 (심볼 기반 자동 생성)
        
    Returns:
        pandas.DataFrame: 더미 OHLCV 데이터
    """
    # 심볼 기반 시드 생성으로 일관된 데이터 제공
    if seed is None:
        import hashlib
        seed = int(hashlib.md5(symbol.encode()).hexdigest()[:8], 16)
    
    np.random.seed(seed)
    
    # 기간을 일수로 변환
    period_days = parse_period_to_days(period)
    
    # 간격에 따른 데이터 포인트 수 계산
    if interval == '1d':
        data_points = period_days
        freq = 'D'
    elif interval == '1h':
        data_points = period_days * 24
        freq = 'H'
    elif interval.endswith('m'):
        minutes = int(interval.replace('m', ''))
        data_points = period_days * 24 * 60 // minutes
        freq = f'{minutes}T'
    else:
        data_points = period_days
        freq = 'D'
    
    # 심볼별 고유 특성 반영
    base_price = get_symbol_base_price(symbol)
    volatility = get_symbol_volatility(symbol)
    
    logger.info(f"해외 주식 더미 데이터 생성: {symbol}, 기간: {period} ({period_days}일), 간격: {interval}")
    
    # 날짜 범위 생성
    end_date = pd.Timestamp.now()
    if freq == 'D':
        start_date = end_date - pd.Timedelta(days=period_days)
        date_range = pd.date_range(start=start_date, end=end_date, freq='D')
    else:
        start_date = end_date - pd.Timedelta(days=period_days)
        date_range = pd.date_range(start=start_date, end=end_date, freq=freq)
    
    # 실제 data_points만큼만 사용
    if len(date_range) > data_points:
        date_range = date_range[-data_points:]
    
    # 가격 데이터 생성
    prices = generate_realistic_price_series(len(date_range), base_price, volatility)
    
    # OHLCV 데이터 생성
    data = []
    for i, price in enumerate(prices):
        # 일일 변동성 적용
        daily_range = price * (volatility / 100) * np.random.uniform(0.5, 2.0)
        
        high = price + daily_range * np.random.uniform(0, 1)
        low = price - daily_range * np.random.uniform(0, 1)
        
        # Open과 Close는 High-Low 범위 내에서 결정
        open_price = low + (high - low) * np.random.uniform(0.2, 0.8)
        close_price = low + (high - low) * np.random.uniform(0.2, 0.8)
        
        # 볼륨 생성 (심볼별 특성 반영)
        base_volume = get_symbol_base_volume(symbol)
        volume = int(base_volume * np.random.uniform(0.5, 2.0))
        
        data.append({
            'Open': round(open_price, 2),
            'High': round(high, 2),
            'Low': round(low, 2),
            'Close': round(close_price, 2),
            'Adj Close': round(close_price, 2),
            'Volume': volume
        })
    
    dummy_data = pd.DataFrame(data, index=date_range)
    logger.info(f"해외 주식 더미 데이터 생성 완료: {symbol}, {len(dummy_data)}개 포인트")
    
    return dummy_data


def parse_period_to_days(period):
    """기간 문자열을 일수로 변환"""
    if period == 'max':
        return 365 * 10  # 10년
    elif period.endswith('y'):
        return int(period[:-1]) * 365
    elif period.endswith('mo'):
        return int(period[:-2]) * 30
    elif period.endswith('d'):
        return int(period[:-1])
    else:
        return 365  # 기본값 1년


def get_symbol_base_price(symbol):
    """심볼별 기본 가격 설정"""
    symbol_prices = {
        'AAPL': 150.0,
        'TSLA': 800.0,
        'MSFT': 300.0,
        'GOOGL': 2500.0,
        'AMZN': 3000.0,
        'NVDA': 500.0,
        'META': 250.0,
        'NFLX': 400.0,
        'BTC-USD': 45000.0,
        'ETH-USD': 3000.0,
    }
    return symbol_prices.get(symbol, 100.0)  # 기본값


def get_symbol_volatility(symbol):
    """심볼별 변동성 설정 (%)"""
    symbol_volatilities = {
        'AAPL': 2.5,
        'TSLA': 5.0,
        'MSFT': 2.0,
        'GOOGL': 3.0,
        'AMZN': 3.5,
        'NVDA': 4.0,
        'META': 3.5,
        'NFLX': 4.0,
        'BTC-USD': 8.0,
        'ETH-USD': 10.0,
    }
    return symbol_volatilities.get(symbol, 3.0)  # 기본값


def get_symbol_base_volume(symbol):
    """심볼별 기본 거래량 설정"""
    symbol_volumes = {
        'AAPL': 50000000,
        'TSLA': 30000000,
        'MSFT': 25000000,
        'GOOGL': 1500000,
        'AMZN': 3000000,
        'NVDA': 40000000,
        'META': 20000000,
        'NFLX': 5000000,
        'BTC-USD': 1000000,
        'ETH-USD': 500000,
    }
    return symbol_volumes.get(symbol, 10000000)  # 기본값


def generate_realistic_price_series(length, base_price, volatility):
    """현실적인 가격 시계열 생성"""
    prices = [base_price]
    
    for i in range(1, length):
        # 이전 가격 기반 변동
        prev_price = prices[-1]
        
        # 랜덤워크 + 평균회귀 경향
        drift = np.random.normal(0, volatility/100 * prev_price)
        mean_revert = (base_price - prev_price) * 0.001  # 약한 평균회귀
        
        new_price = prev_price + drift + mean_revert
        
        # 최소값 제한 (0보다 커야 함)
        new_price = max(new_price, base_price * 0.1)
        
        prices.append(new_price)
    
    return prices 