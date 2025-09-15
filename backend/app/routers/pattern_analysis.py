"""패턴 분석 API 라우터"""

from fastapi import APIRouter, HTTPException, Query, Response, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
from datetime import datetime, timedelta, timezone
import pandas as pd
import random
import logging
import numpy as np
from app.utils.data_loader import download_data, get_optimal_period
from app.database import SessionLocal, get_db
from app.models import Stock, Candle
from app.crud import get_latest_candles, get_candles, normalize_timeframe
from app.services.data_loader import load_candles_from_db
from zoneinfo import ZoneInfo
from app.utils.logger_config import get_logger
from sqlalchemy.orm import Session

# 통합 분석 엔진 및 응답 스키마

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
        today = datetime.now(timezone.utc)
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
    patterns: Optional[List[Dict[str, Any]]] = None
    zigzag_points: Optional[List[Dict[str, Any]]] = None

# /analyze endpoint removed: analysis moved to engine_impl and trading-radar-data.

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

# TrendInfoResponse removed: endpoint deprecated and frontend updated to use trading-radar-data

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
        # If Korean stock code (6 digits), run engine on DB candles and extract patterns
        if _is_korean_stock_code(symbol):
            db = SessionLocal()
            try:
                df = load_candles_from_db(db, stock_code=symbol, timeframe=timeframe, period=None, limit=None, tz='Asia/Seoul')
            finally:
                try:
                    db.close()
                except Exception:
                    pass

            if df is None or df.empty:
                logger.warning(f"패턴: DB에 캔들 데이터 없음: {symbol}, {timeframe}")
                # fallback to sample
                patterns = get_sample_patterns(symbol, timeframe)
                return patterns

            # Run analysis engine to get patterns
            try:
                from app.analysis.engine_impl import run_full_analysis as run_full_analysis_impl
                ref_res = run_full_analysis_impl(df, ticker=symbol, period=period or "MAX", interval=timeframe)
            except Exception as e:
                logger.error(f"패턴 엔진 실행 실패: {e}")
                # fallback to sample
                patterns = get_sample_patterns(symbol, timeframe)
                return patterns

            patterns_raw = ref_res.get("patterns", {}) or {}
            patterns_list = []
            # helper to convert to epoch seconds
            def _to_epoch(obj):
                if obj is None:
                    return None
                try:
                    if isinstance(obj, dict):
                        dt = obj.get("date") or obj.get("actual_date") or obj.get("detected_date")
                    else:
                        dt = obj
                    if dt is None:
                        return None
                    parsed = pd.to_datetime(dt)
                    return int(parsed.timestamp())
                except Exception:
                    return None

            type_map = {
                "completed_hs": ("HS", "Head & Shoulders"),
                "completed_ihs": ("IHS", "Inverse H&S"),
                "completed_dt": ("DT", "Double Top"),
                "completed_db": ("DB", "Double Bottom"),
            }

            for key, (ptype, pname) in type_map.items():
                for idx, pat in enumerate(patterns_raw.get(key, [])):
                    pid = pat.get("id") or f"{ptype}-{idx}"
                    # Prefer explicit epoch fields if engine provided them
                    start_epoch = pat.get('startTimeEpoch') if pat.get('startTimeEpoch') is not None else None
                    end_epoch = pat.get('endTimeEpoch') if pat.get('endTimeEpoch') is not None else None
                    # If epochs absent, fall back to nested fields
                    if start_epoch is None or end_epoch is None:
                        start_time = pat.get("start") or pat.get("P1") or pat.get("V1") or pat.get("date")
                        end_time = pat.get("date") or pat.get("end")
                        start_epoch = start_epoch if start_epoch is not None else _to_epoch(start_time)
                        end_epoch = end_epoch if end_epoch is not None else _to_epoch(end_time)

                    # normalize to date string for response_model compatibility
                    try:
                        start_str = pd.to_datetime(start_epoch, unit='s').strftime('%Y-%m-%d') if start_epoch is not None else None
                    except Exception:
                        start_str = str(start_epoch) if start_epoch is not None else None
                    try:
                        end_str = pd.to_datetime(end_epoch, unit='s').strftime('%Y-%m-%d') if end_epoch is not None else None
                    except Exception:
                        end_str = str(end_epoch) if end_epoch is not None else None

                    patterns_list.append({
                        "id": str(pid),
                        "name": pname,
                        "description": pat.get("description", ""),
                        "confidence": float(pat.get("confidence", 0.0)) if pat.get("confidence") is not None else 0.0,
                        # return date strings to match PatternResponse schema
                        "startTime": start_str,
                        "startTimeEpoch": start_epoch,
                        "startTimeISO": pat.get('startTimeISO') if pat.get('startTimeISO') is not None else (pd.to_datetime(start_epoch, unit='s').isoformat() if start_epoch is not None else None),
                        "endTime": end_str,
                        "endTimeEpoch": end_epoch,
                        "endTimeISO": pat.get('endTimeISO') if pat.get('endTimeISO') is not None else (pd.to_datetime(end_epoch, unit='s').isoformat() if end_epoch is not None else None),
                        "direction": pat.get("direction", ""),
                        "status": pat.get("status", "completed"),
                        "completion": float(pat.get("completion", 100.0)) if pat.get("completion") is not None else 100.0,
                        "pattern_type": ptype,
                        "meta": pat,
                    })

            logger.info(f"패턴 응답(engine): {len(patterns_list)}개 패턴 반환")
            return patterns_list

        # Non-Korean symbols: return sample (or could implement external engine call)
        patterns = get_sample_patterns(symbol, timeframe)
        logger.info(f"패턴 응답(sample): {len(patterns)}개 패턴 반환")
        return patterns

    except Exception as e:
        # Log full traceback and write to temporary file for debugging
        import traceback, pathlib
        tb = traceback.format_exc()
        logger.error(tb)
        try:
            pathlib.Path('/tmp/patterns_trace.log').write_text(tb)
        except Exception as _write_err:
            logger.warning(f"Failed writing trace file: {_write_err}")
        # Return generic 500 but guide to trace file location for developer
        raise HTTPException(status_code=500, detail="Internal server error. Server traceback written to /tmp/patterns_trace.log")

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

# 추세 정보 API 및 샘플 생성 함수는 완전 제거되었습니다.
# 관련 프론트엔드 호출 및 스키마도 함께 제거되어 더 이상 필요하지 않습니다.

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

            # 'period' 파라미터는 무시합니다. 항상 최신 N개 캔들을 반환하도록 변경.
            db = SessionLocal()
            try:
                # 기본 개수는 원본 엔진의 count_map과 일치시킵니다.
                count_map = {
                    '5m': 500,
                    '30m': 300,
                    '1h': 200,
                    '1d': 500,
                    '1wk': 200,
                }
                default_limit = count_map.get(timeframe, 500)
                # limit 파라미터가 있으면 상한으로 적용
                fetch_limit = default_limit if (limit is None) else min(limit, default_limit)
                df = load_candles_from_db(db, stock_code=symbol, timeframe=timeframe, period=None, limit=fetch_limit, tz='Asia/Seoul')
            finally:
                try:
                    db.close()
                except Exception:
                    pass

            if df is None or df.empty:
                raise HTTPException(status_code=404, detail=f"DB에 데이터가 없습니다: {symbol}, {timeframe}")

            # 차트 데이터(이미 KST tz-aware 인덱스) -> Unix timestamp 초 단위
            chart_data = []
            for idx, row in df.iterrows():
                ts = int(idx.timestamp())
                # volume may be present under 'Volume' or 'volume' depending on source
                try:
                    if 'Volume' in row.index:
                        vol = float(row['Volume'])
                    elif 'volume' in row.index:
                        vol = float(row['volume'])
                    else:
                        vol = 0.0
                except Exception:
                    vol = 0.0

                if chart_type == "line":
                    chart_data.append({"time": ts, "value": float(row['Close'])})
                else:
                    chart_data.append({
                        "time": ts,
                        "open": float(row['Open']),
                        "high": float(row['High']),
                        "low": float(row['Low']),
                        "close": float(row['Close']),
                        "volume": vol,
                    })

            js_peaks_json = []
            js_valleys_json = []
            secondary_peaks_json = []
            secondary_valleys_json = []
            trend_periods_json = []
            trend_info = {}

            # 항상 V3 엔진에 위임하여 결과를 사용합니다. (폴백 로직 제거)
            from app.analysis.engine_impl import run_full_analysis as run_full_analysis_impl

            # Call engine_impl and extract fields
            ref_res = run_full_analysis_impl(df, ticker=symbol, period=period or "MAX", interval=timeframe)
            pv = ref_res.get("peaks_valleys", {})
            js_peaks = pv.get("js_peaks", [])
            js_valleys = pv.get("js_valleys", [])
            secondary_peaks = pv.get("sec_peaks", [])
            secondary_valleys = pv.get("sec_valleys", [])
            trend_periods = ref_res.get("trend_info", {}).get("periods", [])

            # Include patterns and zigzag_points in response for frontend consumption
            patterns_raw = ref_res.get("patterns", {}) or {}
            patterns_list = []

            # helper: convert various date representations to epoch seconds
            def _to_epoch(obj):
                if obj is None:
                    return None
                try:
                    if isinstance(obj, dict):
                        dt = obj.get("date") or obj.get("actual_date") or obj.get("detected_date")
                    else:
                        dt = obj
                    if dt is None:
                        return None
                    parsed = pd.to_datetime(dt)
                    # pandas Timestamp.timestamp() returns float seconds
                    return int(parsed.timestamp())
                except Exception:
                    return None
            type_map = {
                "completed_hs": ("HS", "Head & Shoulders"),
                "completed_ihs": ("IHS", "Inverse H&S"),
                "completed_dt": ("DT", "Double Top"),
                "completed_db": ("DB", "Double Bottom"),
            }
            for key, (ptype, pname) in type_map.items():
                for idx, pat in enumerate(patterns_raw.get(key, [])):
                    # normalize pattern object for frontend
                    pid = pat.get("id") or f"{ptype}-{idx}"
                    # Prefer explicit normalized fields from engine/meta; fall back to structural points
                    # Check top-level epoch/iso fields first, then nested start_peak/start_valley, then generic start/date
                    start_field_candidates = [pat.get('startTimeEpoch'), pat.get('startTimeISO'), pat.get('startTime'), pat.get('start'), pat.get('start_valley'), pat.get('start_peak'), pat.get('P1'), pat.get('V1'), pat.get('date')]
                    end_field_candidates = [pat.get('endTimeEpoch'), pat.get('endTimeISO'), pat.get('endTime'), pat.get('date'), pat.get('end')]

                    # pick first non-null candidate
                    def _first_non_null(lst):
                        for x in lst:
                            if x is not None:
                                return x
                        return None

                    start_time = _first_non_null(start_field_candidates)
                    end_time = _first_non_null(end_field_candidates)

                    # if engine already provided epoch seconds at top-level, use them directly
                    start_ts = pat.get('startTimeEpoch') if pat.get('startTimeEpoch') is not None else _to_epoch(start_time)
                    end_ts = pat.get('endTimeEpoch') if pat.get('endTimeEpoch') is not None else _to_epoch(end_time)
                    patterns_list.append({
                        "id": str(pid),
                        "name": pname,
                        "description": pat.get("description", ""),
                        "confidence": float(pat.get("confidence", 0.0)) if pat.get("confidence") is not None else 0.0,
                        # normalized as epoch seconds (front will convert to ms)
                        "startTime": start_ts,
                        "endTime": end_ts,
                        "direction": pat.get("direction", ""),
                        "status": pat.get("status", "completed"),
                        "completion": float(pat.get("completion", 100.0)) if pat.get("completion") is not None else 100.0,
                        "pattern_type": ptype,
                        "meta": pat,
                    })

            zigzag_points = ref_res.get("trend_info", {}).get("zigzag_points", [])

            def _ts(obj):
                dt = obj.get("date") or obj.get("actual_date") or obj.get("detected_date")
                return int(dt.timestamp()) if dt is not None else None

            js_peaks_json = [{"time": _ts(p), "value": p.get("value"), "type": "peak"} for p in js_peaks if _ts(p) is not None]
            js_valleys_json = [{"time": _ts(v), "value": v.get("value"), "type": "valley"} for v in js_valleys if _ts(v) is not None]
            secondary_peaks_json = [{"time": _ts(p), "value": p.get("value"), "type": "secondary_peak"} for p in secondary_peaks if _ts(p) is not None]
            secondary_valleys_json = [{"time": _ts(v), "value": v.get("value"), "type": "secondary_valley"} for v in secondary_valleys if _ts(v) is not None]

            if trend_periods:
                # normalize trend periods to unix timestamps
                trend_periods_json = [{"start": int(p["start"].timestamp()), "end": int(p["end"].timestamp()), "type": p.get("type", "")} for p in trend_periods]
                latest = trend_periods[-1]
                try:
                    start_ts = int(latest["start"].timestamp())
                    duration = (latest["end"] - latest["start"]).days or 1
                    trend_type = latest.get("type", "").lower()
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
                    trend_info = {"trend": trend_type, "startDate": start_ts, "duration": duration, "strength": float(strength), "trend_periods": trend_periods_json}
                except Exception:
                    trend_info = {}
            else:
                trend_periods_json = []
                trend_info = {}

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
                # 추가: 프론트에서 패턴 및 ZigZag 데이터를 즉시 사용할 수 있도록 포함
                "patterns": patterns_list,
                "zigzag_points": zigzag_points,
            }

            # 분 단위일 때 로그
            # is_minute_timeframe는 위에서 정의되므로 안전하게 사용합니다.
            if timeframe.endswith('m') or timeframe.endswith('h') and chart_data:
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

        # 비한국 심볼: 현재 Trading Radar는 한국주식(6자리 코드)만 지원합니다.
        # 프론트엔드를 한국주식 전용으로 고정했으므로, 비한국 심볼 요청은 명시적 오류로 처리합니다.
        logger.info(f"비한국 심볼 요청 차단: {symbol}")
        raise HTTPException(status_code=400, detail="Trading Radar API는 현재 한국주식(6자리 종목 코드)만 지원합니다.")
        
    except HTTPException as e:
        logger.error(f"Trading Radar HTTP 예외: {e.status_code} - {e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Trading Radar 데이터 오류: {str(e)}")
        import traceback
        logger.error(f"스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"오류 발생: {str(e)}") 


# /analysis/full-report 엔드포인트는 완전 제거되었습니다.
# 관련 코드와 스키마는 더 이상 사용되지 않으므로 삭제되었습니다.