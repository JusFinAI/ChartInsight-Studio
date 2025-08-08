"""패턴 분석 API 라우터"""

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta
import pandas as pd
import random
import logging
import numpy as np
from app.services.peak_valley_detector import TrendDetector
from app.utils.data_loader import download_data, get_optimal_period
from app.database import SessionLocal
from app.models import Stock, Candle
from app.crud import get_latest_candles, get_candles, normalize_timeframe
from zoneinfo import ZoneInfo
from app.utils.logger_config import get_logger

# 라우터 로거 설정
logger = get_logger("chartinsight-api.pattern-analysis", "pattern_analysis")

router = APIRouter(
    prefix="/pattern-analysis",
    tags=["Pattern Analysis"],
    responses={404: {"description": "Not found"}}
)


def _is_korean_stock_code(symbol: str) -> bool:
    """순수 6자리 숫자 코드는 한국 주식으로 간주."""
    return symbol.isdigit() and len(symbol) == 6


def _parse_period_to_days(period_value: str) -> int | None:
    """period 문자열을 일수로 변환. auto/max는 None 반환.

    지원 예: '1d', '7d', '1mo', '6mo', '1y', '2y', 'ytd', 'max', 'auto'
    """
    if not period_value:
        return None
    p = period_value.strip().lower()
    if p in {"auto", "max"}:
        return None
    if p == "ytd":
        today = datetime.utcnow()
        start_of_year = datetime(today.year, 1, 1)
        return max(1, (today - start_of_year).days)
    try:
        if p.endswith("mo"):
            val = int(p[:-2])
            return max(1, val * 30)
        if p.endswith("y"):
            val = int(p[:-1])
            return max(1, val * 365)
        if p.endswith("d"):
            val = int(p[:-1])
            return max(1, val)
    except ValueError:
        return None
    return None

class AnalysisRequest(BaseModel):
    """분석 요청 모델"""
    symbol: str
    period: str = "2y"  # 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max
    interval: str = "1d"  # 1m, 2m, 5m, 15m, 30m, 60m, 90m, 1h, 1d, 5d, 1wk, 1mo, 3mo

class PointData(BaseModel):
    """포인트(Peak/Valley) 데이터 모델"""
    index: int
    value: float
    date: datetime

class TrendPeriod(BaseModel):
    """추세 구간 데이터 모델"""
    start: datetime
    end: datetime
    type: str  # "Uptrend", "Downtrend", "Sideways"

class StateData(BaseModel):
    """상태 데이터 모델"""
    index: int
    date: datetime
    state: int
    trend: str
    count: int
    reference_high: Optional[float] = None
    reference_low: Optional[float] = None
    is_inside_bar: bool
    close: float

class PriceData(BaseModel):
    """가격 데이터 모델"""
    dates: List[datetime]
    open: List[float]
    high: List[float]
    low: List[float]
    close: List[float]
    volume: List[float]

class AnalysisResponse(BaseModel):
    """분석 응답 모델"""
    symbol: str
    js_peaks: List[Dict[str, Any]]
    js_valleys: List[Dict[str, Any]]
    secondary_peaks: List[Dict[str, Any]]
    secondary_valleys: List[Dict[str, Any]]
    trend_periods: List[Dict[str, Any]]
    price_data: Dict[str, List]

class MarketDataResponse(BaseModel):
    """24시간 시장 데이터 응답 모델"""
    change_24h: float
    volume_24h: float
    high_24h: float
    low_24h: float

class TradingRadarDataResponse(BaseModel):
    """통합 Trading Radar 데이터 응답 모델"""
    symbol: str
    chart_data: List[Dict[str, Any]]
    js_points: Dict[str, List[Dict[str, Any]]]
    trend_periods: List[Dict[str, Any]]
    price_levels: List[Dict[str, Any]]
    trend_info: Dict[str, Any]

@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_pattern(request: AnalysisRequest):
    """
    주식 차트 패턴 분석 API
    
    - **symbol**: 주식 티커 심볼 (예: "AAPL", "005930.KS")
    - **period**: 다운로드 기간 (기본값: 2y)
    - **interval**: 데이터 간격 (기본값: 1d)
    
    패턴 분석 결과를 반환합니다.
    """
    try:
        # 데이터 다운로드
        data = download_data(request.symbol, request.period, request.interval)
        
        if data is None or data.empty:
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for symbol: {request.symbol}"
            )
        
        # 패턴 분석 수행
        detector = TrendDetector(n_criteria=2, window_size=5)
        
        # 백엔드 환경에서도 디버깅 로그가 기록되도록 debug_range 설정
        # 로깅 방식 개선: debug_range를 None으로 설정하면 모든 날짜의 로그가 기록됨
        logger.info(f"분석 시작: {request.symbol}, 기간: {request.period}, 간격: {request.interval}")
        
        js_peaks, js_valleys, secondary_peaks, secondary_valleys, states, trend_periods = detector.detect_peaks_valleys(data)
        
        # 가격 데이터 변환 (JSON 직렬화 가능하도록)
        price_data = {
            "dates": data.index.strftime('%Y-%m-%d %H:%M:%S').tolist(),
            "open": data['Open'].tolist(),
            "high": data['High'].tolist(),
            "low": data['Low'].tolist(),
            "close": data['Close'].tolist(),
            "volume": data['Volume'].tolist() if 'Volume' in data.columns else []
        }
        
        # 각 포인트의 날짜를 문자열로 변환
        js_peaks_json = [
            {"index": p["index"], "value": p["value"], "date": p["date"].strftime('%Y-%m-%d %H:%M:%S')}
            for p in js_peaks
        ]
        
        js_valleys_json = [
            {"index": v["index"], "value": v["value"], "date": v["date"].strftime('%Y-%m-%d %H:%M:%S')}
            for v in js_valleys
        ]
        
        secondary_peaks_json = [
            {"index": p["index"], "value": p["value"], "date": p["date"].strftime('%Y-%m-%d %H:%M:%S')}
            for p in secondary_peaks
        ]
        
        secondary_valleys_json = [
            {"index": v["index"], "value": v["value"], "date": v["date"].strftime('%Y-%m-%d %H:%M:%S')}
            for v in secondary_valleys
        ]
        
        trend_periods_json = [
            {"start": p["start"].strftime('%Y-%m-%d %H:%M:%S'), "end": p["end"].strftime('%Y-%m-%d %H:%M:%S'), "type": p["type"]}
            for p in trend_periods
        ]
        
        return {
            "symbol": request.symbol,
            "js_peaks": js_peaks_json,
            "js_valleys": js_valleys_json,
            "secondary_peaks": secondary_peaks_json,
            "secondary_valleys": secondary_valleys_json,
            "trend_periods": trend_periods_json,
            "price_data": price_data
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error analyzing pattern: {str(e)}"
        )

@router.get("/symbols/popular")
async def get_popular_symbols():
    """인기 주식 심볼 목록을 반환합니다."""
    return {
        "us_stocks": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA"],
        # 한국 주식은 6자리 코드로 통일
        "kr_stocks": ["005930", "000660", "035420", "035720", "051910"],
        "crypto": ["BTC-USD", "ETH-USD", "BNB-USD", "XRP-USD", "ADA-USD"],
        "indices": ["^GSPC", "^DJI", "^IXIC", "^KS11", "^KQ11"]
    }

@router.get("/symbols/kr-targets")
async def get_kr_target_symbols(limit: int = Query(30, ge=1, le=200)):
    """DataPipeline이 적재한 한국 주식 타겟(캔들 보유) 목록을 반환합니다.

    - live.candles에 존재하는 종목만 대상으로 하여 live.stocks와 조인해 코드/이름을 제공합니다.
    - 기본 30개, 코드 순 정렬.
    """
    db = SessionLocal()
    try:
        # candles에 존재하는 종목 코드만 선별
        subq = db.query(Candle.stock_code).distinct().subquery()
        rows = (
            db.query(Stock.stock_code, Stock.stock_name)
            .join(subq, Stock.stock_code == subq.c.stock_code)
            .order_by(Stock.stock_code.asc())
            .limit(limit)
            .all()
        )
        result = [
            {"value": code, "label": name or code}
            for code, name in rows
            if code and code.isdigit() and len(code) == 6
        ]
        return {"symbols": result}
    finally:
        db.close()

@router.get("/periods")
async def get_available_periods():
    """사용 가능한 데이터 기간 목록을 반환합니다."""
    return {
        "periods": [
            {"value": "1d", "label": "1 Day"},
            {"value": "5d", "label": "5 Days"},
            {"value": "1mo", "label": "1 Month"},
            {"value": "3mo", "label": "3 Months"},
            {"value": "6mo", "label": "6 Months"},
            {"value": "1y", "label": "1 Year"},
            {"value": "2y", "label": "2 Years"},
            {"value": "5y", "label": "5 Years"},
            {"value": "10y", "label": "10 Years"},
            {"value": "ytd", "label": "Year to Date"},
            {"value": "max", "label": "Maximum"}
        ]
    }

@router.get("/intervals")
async def get_available_intervals():
    """사용 가능한 데이터 간격 목록을 반환합니다."""
    return {
        "intervals": [
            {"value": "1m", "label": "1 Minute"},
            {"value": "5m", "label": "5 Minutes"},
            {"value": "15m", "label": "15 Minutes"},
            {"value": "30m", "label": "30 Minutes"},
            {"value": "1h", "label": "1 Hour"},
            {"value": "1d", "label": "1 Day"},
            {"value": "1wk", "label": "1 Week"},
            {"value": "1mo", "label": "1 Month"}
        ]
    }

# 프론트엔드 호환 추가 API 엔드포인트 -----------------------------------------------

class ChartDataResponse(BaseModel):
    """차트 데이터 응답 모델"""
    time: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    value: Optional[float] = None

class JSPointResponse(BaseModel):
    """JS 포인트 응답 모델"""
    time: str
    value: float
    type: str  # 'peak' 또는 'valley'

class PatternResponse(BaseModel):
    """패턴 응답 모델"""
    id: str
    name: str
    description: str
    confidence: float
    startTime: str
    endTime: str
    direction: str  # 'bullish', 'bearish', 또는 'neutral'
    status: str  # 'forming' 또는 'completed'
    completion: float

class PriceLevelResponse(BaseModel):
    """가격 레벨 응답 모델"""
    id: str
    price: float
    type: str  # 'support', 'resistance', 또는 'pivot'
    strength: float
    description: Optional[str] = None

class TrendInfoResponse(BaseModel):
    """추세 정보 응답 모델"""
    trend: str  # 'uptrend', 'downtrend', 'sideways', 또는 'neutral'
    startDate: str
    duration: int
    strength: float
    trend_periods: Optional[List[Dict[str, Any]]] = None

# 차트 데이터 API
@router.get("/chart-data", response_model=List[Union[Dict[str, Any], ChartDataResponse]])
async def get_chart_data(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    chart_type: str = Query("candlestick", description="차트 타입 (line 또는 candlestick)"),
    period: str = Query("1y", description="데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
):
    """
    차트 데이터를 가져오는 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **chart_type**: 차트 타입 (line 또는 candlestick)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    logger.info(f"차트 데이터 요청: 심볼={symbol}, 시간틀={timeframe}, 타입={chart_type}, 기간={period}")
    
    try:
        # API 요청에 맞게 시간틀 변환
        interval_map = {
            "1m": "1m", "3m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "60m", "4h": "4h", "1d": "1d", "1wk": "1wk"
        }
        
        interval = interval_map.get(timeframe, "1d")
        
        # 데이터 다운로드
        data = download_data(symbol, period=period, interval=interval)
        
        if data is None or data.empty:
            logger.warning(f"데이터를 찾을 수 없음: {symbol}, {timeframe}")
            raise HTTPException(status_code=404, detail="데이터를 찾을 수 없습니다.")
        
        # 데이터가 충분한지 확인
        min_data_points = 30 if timeframe.endswith('m') else 10
        if len(data) < min_data_points:
            logger.warning(f"충분한 데이터가 없습니다: {len(data)}개 (최소 {min_data_points}개 필요)")
            raise HTTPException(
                status_code=400, 
                detail=f"충분한 데이터가 없습니다. {len(data)}개 데이터를 찾았으나, 최소 {min_data_points}개가 필요합니다."
            )
        
        # 작은 타임프레임 감지 (1m, 3m, 5m, 15m, 30m, 1h)
        is_minute_timeframe = timeframe.endswith('m') or timeframe.endswith('h')
        
        # 데이터 포맷 변환 (중복 시간 제거)
        result = []
        seen_times = set()  # 중복 시간 체크
        
        for idx, row in data.iterrows():
            # 타임스탬프 형식으로 통일
            timestamp = int(idx.timestamp())  # Unix timestamp(초 단위)
            
            # 중복 시간 건너뛰기 (로그 횟수 제한)
            if timestamp in seen_times:
                if len(seen_times) < 5 or len(seen_times) % 50 == 0:  # 처음 5개 또는 50개마다 로그
                    logger.warning(f"중복 시간 건너뛰기: {idx.strftime('%Y-%m-%d %H:%M:%S')} (타임스탬프: {timestamp})")
                continue
            
            seen_times.add(timestamp)
            
            if chart_type == "line":
                data_point = {
                    "time": timestamp,  # Unix timestamp(초 단위)
                    "value": float(row["Close"])
                }
            else:  # candlestick
                data_point = {
                    "time": timestamp,  # Unix timestamp(초 단위)
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"])
                }
            result.append(data_point)
        
        # 결과 정렬 (시간순)
        result.sort(key=lambda x: x["time"])
        
        if len(result) != len(data):
            logger.info(f"중복 시간 제거: 원본 {len(data)}개 → 결과 {len(result)}개 데이터 포인트")
        
        # 로그 출력
        if is_minute_timeframe and result:
            first_time = datetime.fromtimestamp(result[0]["time"]).strftime('%Y-%m-%d %H:%M:%S')
            last_time = datetime.fromtimestamp(result[-1]["time"]).strftime('%Y-%m-%d %H:%M:%S')
            logger.info(f"차트 데이터 응답: {len(result)}개 데이터 포인트 반환 (시간 범위: {first_time} ~ {last_time})")
        else:
            logger.info(f"차트 데이터 응답: {len(result)}개 데이터 포인트 반환")
        
        return result
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"차트 데이터 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"오류 발생: {str(e)}")

# JS 포인트 API
@router.get("/js-points", response_model=List[JSPointResponse])
async def get_js_points(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    period: str = Query("1y", description="데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
):
    """
    JS 포인트 (Peak/Valley) 데이터를 가져오는 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    logger.info(f"JS 포인트 요청: 심볼={symbol}, 시간틀={timeframe}, 기간={period}")
    
    try:
        # API 요청에 맞게 시간틀 변환
        interval_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "60m", "4h": "4h", "1d": "1d", "1wk": "1wk"
        }
        
        interval = interval_map.get(timeframe, "1d")
        
        # 데이터 다운로드
        data = download_data(symbol, period=period, interval=interval)
        
        if data is None or data.empty:
            logger.warning(f"데이터를 찾을 수 없음: {symbol}, {timeframe}")
            raise HTTPException(status_code=404, detail="데이터를 찾을 수 없습니다.")
        
        # JS 포인트 계산 (피크와 밸리)
        js_points = find_peaks_and_valleys(data)
        
        # 결과 포맷팅
        result = []
        for idx, point_type, price in js_points:
            result.append({
                "time": idx.strftime("%Y-%m-%d"),
                "value": price,
                "type": point_type
            })
        
        logger.info(f"JS 포인트 응답: {len(result)}개 포인트 반환 (피크: {sum(1 for p in result if p['type'] == 'peak')}, 밸리: {sum(1 for p in result if p['type'] == 'valley')})")
        return result
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"JS 포인트 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"오류 발생: {str(e)}")

# 패턴 API
@router.get("/patterns", response_model=List[PatternResponse])
async def get_patterns(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    period: str = Query("1y", description="데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
):
    """
    패턴 정보를 가져오는 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    logger.info(f"패턴 요청: 심볼={symbol}, 시간틀={timeframe}, 기간={period}")
    
    try:
        # 샘플 패턴 데이터
        patterns = get_sample_patterns(symbol, timeframe)
        logger.info(f"패턴 응답: {len(patterns)}개 패턴 반환")
        return patterns
    
    except Exception as e:
        logger.error(f"패턴 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"오류 발생: {str(e)}")

# 가격 레벨 API 수정
@router.get("/price-levels", response_model=List[PriceLevelResponse])
async def get_price_levels(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    period: str = Query("1y", description="데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
):
    """
    중요 가격 레벨 정보를 가져오는 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    logger.info(f"가격 레벨 요청: 심볼={symbol}, 시간틀={timeframe}, 기간={period}")
    
    try:
        # 불필요한 데이터 다운로드 제거 - 바로 샘플 데이터 반환
        support_resistance = get_sample_price_levels(symbol, timeframe)
        
        logger.info(f"가격 레벨 응답: {len(support_resistance)}개 레벨 반환 (지지: {sum(1 for p in support_resistance if p['type'] == 'support')}, 저항: {sum(1 for p in support_resistance if p['type'] == 'resistance')})")
        return support_resistance
    
    except Exception as e:
        logger.error(f"가격 레벨 오류: {str(e)}")
        return get_sample_price_levels(symbol, timeframe)

# 샘플 가격 레벨 데이터 생성 함수 수정
def get_sample_price_levels(symbol, timeframe):
    """
    샘플 가격 레벨 데이터를 반환합니다. (불필요한 데이터 다운로드 제거)
    
    Args:
        symbol (str): 거래 심볼
        timeframe (str): 시간틀
        
    Returns:
        List[Dict]: 가격 레벨 목록
    """
    logger.info(f"샘플 가격 레벨 생성: 심볼={symbol}, 시간틀={timeframe}")
    
    # 더이상 실제 데이터를 사용하지 않고 직접 샘플 데이터 생성
    base_price = 50000 + random.random() * 10000  # 무작위 기본가
    
    levels = []
    
    # 지지선 2개
    for i in range(2):
        supportPrice = base_price * (0.95 - (i * 0.03))
        levels.append({
            "id": f"support-{i+1}",
            "value": float(supportPrice),
            "type": "support",
            "strength": 0.7 - (i * 0.2)
        })
    
    # 저항선 2개
    for i in range(2):
        resistancePrice = base_price * (1.05 + (i * 0.03))
        levels.append({
            "id": f"resistance-{i+1}",
            "value": float(resistancePrice),
            "type": "resistance",
            "strength": 0.7 - (i * 0.2)
        })
    
    return levels

# 추세 정보 API
@router.get("/trend-info", response_model=TrendInfoResponse)
async def get_trend_info(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    period: str = Query("1y", description="데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)")
):
    """
    현재 추세 정보를 가져오는 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    logger.info(f"추세 정보 요청: 심볼={symbol}, 시간틀={timeframe}, 기간={period}")
    
    try:
        # 1d와 같이 너무 짧은 기간에 대한 처리
        if period == "1d":
            logger.warning("1일 기간은 추세 계산에 부적합, 7d로 확장합니다")
            period = "7d"
            
        # API 요청에 맞게 시간틀 변환
        interval_mapping = {
            "5m": "5m",
            "15m": "15m", 
            "30m": "30m",
            "1h": "60m",
            "4h": "4h", 
            "1d": "1d",
            "3m": "2m"
        }
        interval = interval_mapping.get(timeframe, "1d")
        
        data = download_data(symbol, period, interval)
        
        if data is None or data.empty:
            logger.warning(f"데이터를 찾을 수 없음: {symbol}, {timeframe}, {period}")
            return get_sample_trend_info(symbol, timeframe)
        
        # 데이터가 너무 적을 경우 샘플 데이터 반환
        if len(data) < 5:
            logger.warning(f"데이터가 너무 적음: {len(data)}개 행. 샘플 추세 정보 반환")
            return get_sample_trend_info(symbol, timeframe)
        
        # TrendDetector 클래스 사용하여 추세 분석
        detector = TrendDetector(n_criteria=2, window_size=5)
        js_peaks, js_valleys, secondary_peaks, secondary_valleys, states, trend_periods = detector.detect_peaks_valleys(data)
        
        # 추세 구간 정보 포맷팅
        formatted_trend_periods = []
        for period in trend_periods:
            formatted_trend_periods.append({
                "start": period["start"].strftime("%Y-%m-%d"),
                "end": period["end"].strftime("%Y-%m-%d"),
                "type": period["type"].lower()  # 'Uptrend'/'Downtrend' -> 'uptrend'/'downtrend'
            })
        
        # 현재 추세 결정 (최근 구간 기준)
        current_trend = "neutral"
        start_date = datetime.now() - timedelta(days=7)
        duration = 7
        strength = 50.0
        
        if trend_periods:
            latest_period = trend_periods[-1]
            current_trend = latest_period["type"].lower()
            start_date = latest_period["start"]
            end_date = latest_period["end"]
            duration = (end_date - start_date).days if hasattr(end_date, 'days') else 1
            
            # 추세 강도 계산
            recent_data_length = min(5, len(data))
            recent_closes = data['Close'].values[-recent_data_length:]
            if current_trend == "uptrend":
                strength = min(100, (recent_closes[-1] / recent_closes[0] - 1) * 100 * 3)  # 배수 조정
            elif current_trend == "downtrend":
                strength = min(100, (1 - recent_closes[-1] / recent_closes[0]) * 100 * 3)  # 배수 조정
            else:
                strength = 50.0
        
        # 추세 정보 생성
        trend_periods_json = formatted_trend_periods
        trend_info = {
            "trend": current_trend,
            "startDate": start_date.strftime("%Y-%m-%d") if isinstance(start_date, pd.Timestamp) else start_date.strftime("%Y-%m-%d"),
            "duration": duration if duration > 0 else 1,
            "strength": float(strength),
            "trend_periods": trend_periods_json
        }
        
        logger.info(f"추세 정보 응답: {current_trend}, 기간: {len(formatted_trend_periods)}개")
        return trend_info
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"추세 정보 오류: {str(e)}")
        # 오류 발생시 샘플 추세 정보 반환
        return get_sample_trend_info(symbol, timeframe)

# 샘플 추세 정보 생성
def get_sample_trend_info(symbol, timeframe):
    """
    샘플 추세 정보를 반환합니다.
    
    Args:
        symbol (str): 거래 심볼
        timeframe (str): 시간틀
        
    Returns:
        Dict: 추세 정보
    """
    logger.info(f"샘플 추세 정보 생성: 심볼={symbol}, 시간틀={timeframe}")
    
    # 무작위 추세 방향 선택
    trend_options = ["uptrend", "downtrend", "sideways"]
    trend = random.choice(trend_options)
    
    # 현재 날짜
    today = datetime.now()
    
    # 샘플 트렌드 기간 생성
    sample_trend_periods = []
    end_date = today
    
    # 3-5개의 기간 생성
    for i in range(random.randint(3, 5)):
        # 각 기간은 10-30일
        period_days = random.randint(10, 30)
        start_date = end_date - timedelta(days=period_days)
        
        # 번갈아가며 상승/하락/횡보 추세 할당
        period_trend = trend_options[i % 3]
        
        sample_trend_periods.append({
            "start": int(start_date.timestamp()),  # Unix timestamp로 변환
            "end": int(end_date.timestamp()),      # Unix timestamp로 변환
            "type": period_trend
        })
        
        # 다음 기간의 종료일 = 현재 기간의 시작일
        end_date = start_date
    
    # 리스트 순서 뒤집기 (오래된 것부터 정렬)
    sample_trend_periods.reverse()
    
    # 가장 최근 기간의 정보를 현재 추세로 사용
    latest_period = sample_trend_periods[-1]
    current_trend = latest_period["type"]
    start_date = latest_period["start"]
    
    # 시작일부터 현재까지의 기간 계산
    start_datetime = datetime.fromtimestamp(start_date)
    duration = (today - start_datetime).days
    
    return {
        "trend": current_trend,
        "startDate": start_date,  # Unix timestamp
        "duration": duration if duration > 0 else 1,
        "strength": random.uniform(50, 90),
        "trend_periods": sample_trend_periods
    }

# 24시간 시장 데이터 API 수정 (불필요한 다운로드 제거)
@router.get("/market-data", response_model=MarketDataResponse)
async def get_market_data(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)")
):
    """24시간 시장 데이터를 가져옵니다."""
    try:
        logger.info(f"시장 데이터 요청: {symbol}")
        
        # 더이상 실제 데이터를 다운로드하지 않고 샘플 데이터 반환
        market_data = MarketDataResponse(
            change_24h=round(random.uniform(-5.0, 5.0), 2),  # -5%~+5% 변동
            volume_24h=random.randint(1000000, 10000000),    # 적절한 볼륨 값
            high_24h=100 + random.uniform(0, 5),             # 임의의 값
            low_24h=100 - random.uniform(0, 5)               # 임의의 값
        )
        
        logger.info(f"시장 데이터 응답: {market_data}")
        return market_data
        
    except Exception as e:
        logger.error(f"시장 데이터 가져오기 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# === 유틸리티 함수 ===

def find_peaks_and_valleys(df, window=5):
    """
    주어진 시계열 데이터에서 피크와 밸리 포인트를 찾습니다.
    
    Args:
        df (pandas.DataFrame): OHLC 데이터프레임
        window (int): 피크와 밸리 감지를 위한 윈도우 크기
        
    Returns:
        List: (인덱스, 포인트 타입, 가격) 튜플 목록
    """
    logger.info(f"피크와 밸리 포인트 계산 시작: 윈도우 크기={window}")
    
    result = []
    for i in range(window, len(df) - window):
        # 피크 확인
        is_peak = True
        for j in range(1, window + 1):
            if df['High'].iloc[i] <= df['High'].iloc[i - j] or df['High'].iloc[i] <= df['High'].iloc[i + j]:
                is_peak = False
                break
        
        if is_peak:
            result.append((df.index[i], 'peak', df['High'].iloc[i]))
            continue
        
        # 밸리 확인
        is_valley = True
        for j in range(1, window + 1):
            if df['Low'].iloc[i] >= df['Low'].iloc[i - j] or df['Low'].iloc[i] >= df['Low'].iloc[i + j]:
                is_valley = False
                break
        
        if is_valley:
            result.append((df.index[i], 'valley', df['Low'].iloc[i]))
    
    logger.info(f"피크와 밸리 포인트 계산 완료: {len(result)}개 포인트 발견")
    return result

def calculate_support_resistance(df, num_levels=4):
    """
    지지/저항 레벨을 계산합니다.
    
    Args:
        df (pandas.DataFrame): OHLC 데이터프레임
        num_levels (int): 반환할 레벨 개수
        
    Returns:
        List[Dict]: 지지/저항 레벨 목록
    """
    logger.info(f"지지/저항 레벨 계산 시작: 레벨 수={num_levels}")
    
    # 데이터 검증
    if df is None or len(df) < 10:
        logger.warning(f"지지/저항 레벨 계산에 충분한 데이터가 없습니다. 데이터 길이: {len(df) if df is not None else 0}")
        # 데이터가 너무 적을 경우 빈 결과 반환
        return []
    
    # 중복 인덱스 제거 (오류 방지)
    df = df[~df.index.duplicated(keep='first')]
    
    # 피크와 밸리 찾기
    points = find_peaks_and_valleys(df)
    
    # 가격대별 빈도 계산 (히스토그램)
    price_range = df['High'].max() - df['Low'].min()
    
    # 가격 범위가 너무 작은 경우 처리
    if price_range <= 0:
        logger.warning("가격 범위가 0 이하입니다. 유효한 지지/저항 레벨을 계산할 수 없습니다.")
        return []
    
    # 빈 크기 계산 (최소 20개의 빈이 생성되도록 조정)
    bin_size = max(price_range / 20, 0.01)
    
    highs = df['High'].values
    lows = df['Low'].values
    
    # 빈 생성
    try:
        bins = np.arange(df['Low'].min(), df['High'].max() + bin_size, bin_size)
        
        # 빈이 너무 적으면 처리
        if len(bins) <= 1:
            logger.warning("유효한 빈 생성 실패. 지지/저항 레벨을 계산할 수 없습니다.")
            return []
        
        hist_high, _ = np.histogram(highs, bins=bins)
        hist_low, _ = np.histogram(lows, bins=bins)
        
        # 반환할 레벨 수 조정 (빈 수가 적을 경우)
        actual_num_levels = min(num_levels, len(hist_high) // 2)
        if actual_num_levels < 1:
            actual_num_levels = 1
        
        # 가장 빈도가 높은 빈 찾기
        support_indices = np.argsort(hist_low)[-actual_num_levels:]
        resistance_indices = np.argsort(hist_high)[-actual_num_levels:]
        
        # 결과 포맷팅
        result = []
        
        for i, idx in enumerate(resistance_indices):
            if idx < len(bins) - 1:  # 인덱스 범위 검증
                level_value = (bins[idx] + bins[idx + 1]) / 2
                strength = float(hist_high[idx] / hist_high.max()) if hist_high.max() > 0 else 0.5
                result.append({
                    "id": f"resistance-{i+1}",
                    "value": float(level_value),
                    "type": "resistance",
                    "strength": strength
                })
        
        for i, idx in enumerate(support_indices):
            if idx < len(bins) - 1:  # 인덱스 범위 검증
                level_value = (bins[idx] + bins[idx + 1]) / 2
                strength = float(hist_low[idx] / hist_low.max()) if hist_low.max() > 0 else 0.5
                result.append({
                    "id": f"support-{i+1}",
                    "value": float(level_value),
                    "type": "support",
                    "strength": strength
                })
        
        logger.info(f"지지/저항 레벨 계산 완료: {len(result)}개 레벨 발견")
        return result
        
    except Exception as e:
        logger.error(f"지지/저항 레벨 계산 중 오류 발생: {str(e)}")
        return []

def get_sample_patterns(symbol, timeframe):
    """
    샘플 패턴 데이터를 반환합니다.
    
    Args:
        symbol (str): 거래 심볼
        timeframe (str): 시간틀
        
    Returns:
        List[Dict]: 패턴 목록
    """
    logger.info(f"샘플 패턴 생성: 심볼={symbol}, 시간틀={timeframe}")
    
    now = datetime.now()
    patterns = [
        {
            "id": "1",
            "name": "헤드앤숄더", 
            "description": "약세 반전 패턴",
            "confidence": 0.85,
            "startTime": (now - timedelta(days=30)).strftime("%Y-%m-%d"),
            "endTime": (now - timedelta(days=10)).strftime("%Y-%m-%d"),
            "direction": "bearish",
            "status": "completed",
            "completion": 1.0
        },
        {
            "id": "2",
            "name": "이중 바닥",
            "description": "강세 반전 패턴",
            "confidence": 0.75,
            "startTime": (now - timedelta(days=15)).strftime("%Y-%m-%d"),
            "endTime": now.strftime("%Y-%m-%d"),
            "direction": "bullish",
            "status": "completed",
            "completion": 0.9
        }
    ]
    
    return patterns

@router.get("/trading-radar-data", response_model=TradingRadarDataResponse)
async def get_trading_radar_data(
    symbol: str = Query(..., description="거래 심볼 (예: BTC-USD)"),
    timeframe: str = Query("1d", description="시간 프레임 (예: 5m, 15m, 1h, 1d)"),
    chart_type: str = Query("candlestick", description="차트 타입 (line 또는 candlestick)"),
    period: str = Query("1y", description="데이터 기간"),
    limit: int = Query(None, ge=1, description="반환할 캔들 최대 개수(선택)"),
    response: Response = None,
):
    """
    Trading Radar 페이지에 필요한 모든 데이터를 한 번에 가져오는 통합 API
    
    - **symbol**: 거래 심볼 (예: BTC-USD, AAPL)
    - **timeframe**: 시간 프레임 (예: 5m, 15m, 1h, 1d)
    - **chart_type**: 차트 타입 (line 또는 candlestick)
    - **period**: 데이터 기간 (예: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)
    """
    try:
        logger.info(f"Trading Radar 데이터 요청: 심볼={symbol}, 시간틀={timeframe}, 타입={chart_type}, 기간={period}")

        # 한국 주식(6자리 코드)은 DB에서 조회하여 반환
        if _is_korean_stock_code(symbol):
            kst = ZoneInfo("Asia/Seoul")

            # 최신 N개만 조회(차트에 충분한 양). 분/시간봉은 500, 일/주봉은 400으로 제한
            is_minute_timeframe = timeframe.endswith('m') or timeframe.endswith('h')
            default_limit = 500 if is_minute_timeframe else 400
            period_days = _parse_period_to_days(period) if period else None

            db = SessionLocal()
            try:
                if period_days is not None:
                    # 기간 기반 조회 (UTC)
                    end_utc = datetime.utcnow()
                    start_utc = end_utc - timedelta(days=period_days)
                    candles = get_candles(
                        db,
                        stock_code=symbol,
                        timeframe=timeframe,
                        start_time=start_utc,
                        end_time=end_utc,
                        limit=limit or None,
                        sort_asc=True,
                    )
                else:
                    # auto/max → 최신 N개
                    fetch_limit = default_limit if (limit is None) else min(limit, default_limit)
                    candles = get_latest_candles(db, symbol, timeframe, fetch_limit)
            finally:
                db.close()

            if not candles:
                raise HTTPException(status_code=404, detail=f"DB에 데이터가 없습니다: {symbol}, {timeframe}")

            # 차트 데이터(KST 변환 후 Unix timestamp 초 단위)
            chart_data = []
            for c in candles:
                kst_ts = c.timestamp.astimezone(kst)
                ts = int(kst_ts.timestamp())
                if chart_type == "line":
                    chart_data.append({"time": ts, "value": float(c.close)})
                else:
                    chart_data.append({
                        "time": ts,
                        "open": float(c.open),
                        "high": float(c.high),
                        "low": float(c.low),
                        "close": float(c.close),
                    })

            # TrendDetector 실행을 위해 DataFrame 구성
            df = pd.DataFrame([
                {
                    "Date": c.timestamp.astimezone(kst),
                    "Open": float(c.open),
                    "High": float(c.high),
                    "Low": float(c.low),
                    "Close": float(c.close),
                    "Volume": int(c.volume),
                }
                for c in candles
            ])
            df.set_index("Date", inplace=True)

            js_peaks_json = []
            js_valleys_json = []
            secondary_peaks_json = []
            secondary_valleys_json = []
            trend_periods_json = []
            trend_info = {}

            if len(df) >= 30:
                detector = TrendDetector(n_criteria=2, window_size=5)
                js_peaks, js_valleys, secondary_peaks, secondary_valleys, states, trend_periods = detector.detect_peaks_valleys(df)

                js_peaks_json = [
                    {"time": int(p["date"].timestamp()), "value": p["value"], "type": "peak"}
                    for p in js_peaks
                ]
                js_valleys_json = [
                    {"time": int(v["date"].timestamp()), "value": v["value"], "type": "valley"}
                    for v in js_valleys
                ]
                secondary_peaks_json = [
                    {"time": int(p["date"].timestamp()), "value": p["value"], "type": "secondary_peak"}
                    for p in secondary_peaks
                ]
                secondary_valleys_json = [
                    {"time": int(v["date"].timestamp()), "value": v["value"], "type": "secondary_valley"}
                    for v in secondary_valleys
                ]
                trend_periods_json = [
                    {"start": int(p["start"].timestamp()), "end": int(p["end"].timestamp()), "type": p["type"]}
                    for p in trend_periods
                ]

                # 간단 추세 정보 추출
                if trend_periods:
                    latest = trend_periods[-1]
                    start_ts = int(latest["start"].timestamp())
                    duration = (latest["end"] - latest["start"]).days or 1
                    trend_type = latest["type"].lower()
                    try:
                        start_price = df.loc[latest["start"]]["Close"]
                        end_price = df.loc[latest["end"]]["Close"]
                        if trend_type == "uptrend":
                            strength = min(100.0, ((end_price / start_price) - 1) * 100)
                        elif trend_type == "downtrend":
                            strength = min(100.0, ((start_price / end_price) - 1) * 100)
                        else:
                            strength = 50.0
                    except Exception:
                        strength = 50.0

                    trend_info = {
                        "trend": trend_type,
                        "startDate": start_ts,
                        "duration": duration,
                        "strength": float(strength),
                        "trend_periods": trend_periods_json,
                    }

            # 응답 구성(+ 데이터 소스 명시)
            response_data = {
                "symbol": symbol,
                "chart_data": chart_data,
                "js_points": {
                    "peaks": js_peaks_json,
                    "valleys": js_valleys_json,
                    "secondary_peaks": secondary_peaks_json,
                    "secondary_valleys": secondary_valleys_json,
                },
                "trend_periods": trend_periods_json,
                "price_levels": get_sample_price_levels(symbol, timeframe),
                "trend_info": trend_info,
            }

            # 분 단위일 때 로그
            if is_minute_timeframe and chart_data:
                first_time = datetime.fromtimestamp(chart_data[0]["time"]).strftime('%Y-%m-%d %H:%M:%S')
                last_time = datetime.fromtimestamp(chart_data[-1]["time"]).strftime('%Y-%m-%d %H:%M:%S')
                logger.info(f"Trading Radar(DB) 응답: {symbol}, {len(chart_data)}개 (범위: {first_time} ~ {last_time})")
            else:
                logger.info(f"Trading Radar(DB) 응답: {symbol}, {len(chart_data)}개 포인트")

            # 데이터 소스 표기 추가
            response_data["source"] = "db"
            if response is not None:
                response.headers["X-Data-Source"] = "db"
            return response_data

        # 비한국 심볼: 기존 경로 유지(download_data)
        # API 요청에 맞게 시간틀 변환
        interval_map = {
            "1m": "1m", "3m": "2m", "5m": "5m", "15m": "15m", "30m": "30m",
            "1h": "60m", "4h": "4h", "1d": "1d", "1wk": "1wk"
        }
        interval = interval_map.get(timeframe, "1d")

        if not period or period == "auto":
            period = get_optimal_period(interval)

        data = download_data(symbol, period=period, interval=interval, use_cache=True)
        if data is None or data.empty:
            logger.warning(f"데이터를 찾을 수 없음: {symbol}, {timeframe}")
            raise HTTPException(status_code=404, detail=f"{symbol} 심볼에 대한 데이터를 찾을 수 없습니다. 다른 심볼이나 타임프레임을 선택해보세요.")

        min_data_points = 30 if timeframe.endswith('m') else 10
        if len(data) < min_data_points:
            logger.warning(f"충분한 데이터가 없습니다: {len(data)}개 (최소 {min_data_points}개 필요)")
            raise HTTPException(status_code=404, detail=f"충분한 데이터가 없습니다. {symbol}에 대해 {min_data_points}개 이상의 데이터 포인트가 필요합니다.")

        is_minute_timeframe = timeframe.endswith('m') or timeframe.endswith('h')
        chart_data = []
        seen_times = set()
        for idx, row in data.iterrows():
            timestamp = int(idx.timestamp())
            if timestamp in seen_times:
                continue
            seen_times.add(timestamp)
            if chart_type == "line":
                chart_data.append({"time": timestamp, "value": float(row["Close"])})
            else:
                chart_data.append({
                    "time": timestamp,
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                })
        chart_data.sort(key=lambda x: x["time"])

        detector = TrendDetector(n_criteria=2, window_size=5)
        js_peaks, js_valleys, secondary_peaks, secondary_valleys, states, trend_periods = detector.detect_peaks_valleys(data)
        js_peaks_json = [{"time": int(p["date"].timestamp()), "value": p["value"], "type": "peak"} for p in js_peaks]
        js_valleys_json = [{"time": int(v["date"].timestamp()), "value": v["value"], "type": "valley"} for v in js_valleys]
        secondary_peaks_json = [{"time": int(p["date"].timestamp()), "value": p["value"], "type": "secondary_peak"} for p in secondary_peaks]
        secondary_valleys_json = [{"time": int(v["date"].timestamp()), "value": v["value"], "type": "secondary_valley"} for v in secondary_valleys]
        trend_periods_json = [{"start": int(p["start"].timestamp()), "end": int(p["end"].timestamp()), "type": p["type"]} for p in trend_periods]

        price_levels = get_sample_price_levels(symbol, timeframe)

        trend_info = {}
        if trend_periods:
            latest_trend = trend_periods[-1]
            trend_type = latest_trend["type"].lower()
            start_timestamp = int(latest_trend["start"].timestamp())
            duration_delta = latest_trend["end"] - latest_trend["start"]
            duration = duration_delta.days if hasattr(duration_delta, 'days') else 1
            if duration < 1:
                duration = 1
            try:
                if trend_type == "uptrend":
                    start_price = data.loc[latest_trend["start"]]["Close"]
                    end_price = data.loc[latest_trend["end"]]["Close"]
                    strength = min(100.0, ((end_price / start_price) - 1) * 100)
                elif trend_type == "downtrend":
                    start_price = data.loc[latest_trend["start"]]["Close"]
                    end_price = data.loc[latest_trend["end"]]["Close"]
                    strength = min(100.0, ((start_price / end_price) - 1) * 100)
                else:
                    strength = 50.0
            except (KeyError, TypeError):
                strength = 50.0
            trend_info = {
                "trend": trend_type,
                "startDate": start_timestamp,
                "duration": duration,
                "strength": float(strength),
                "trend_periods": trend_periods_json,
            }

        response_data = {
            "symbol": symbol,
            "chart_data": chart_data,
            "js_points": {
                "peaks": js_peaks_json,
                "valleys": js_valleys_json,
                "secondary_peaks": secondary_peaks_json,
                "secondary_valleys": secondary_valleys_json,
            },
            "trend_periods": trend_periods_json,
            "price_levels": price_levels,
            "trend_info": trend_info,
        }

        # 비한국 심볼도 헤더 표기
        if response is not None:
            response.headers["X-Data-Source"] = "api"
        return response_data
        
    except HTTPException as e:
        logger.error(f"Trading Radar HTTP 예외: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Trading Radar 데이터 오류: {str(e)}")
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"오류 발생: {str(e)}") 