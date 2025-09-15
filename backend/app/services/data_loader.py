"""
Central data loader for backend production use.
This file is a port of the v3 data_loader into the backend services package.
"""
from typing import Optional
import pandas as pd
from zoneinfo import ZoneInfo
from app.crud import get_latest_candles, get_candles


# 기본 count map (원본 엔진과 동일한 기본값 유지)
DEFAULT_COUNT_MAP = {'5m': 500, '30m': 300, '1h': 200, '1d': 500, '1wk': 200}


def _to_dataframe(candles, tz: Optional[str] = None) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()

    rows = []
    for c in candles:
        ts = c.timestamp
        if getattr(ts, 'tzinfo', None) is None:
            try:
                ts = ts.replace(tzinfo=ZoneInfo('UTC'))
            except Exception:
                pass
        if tz:
            try:
                ts = ts.astimezone(ZoneInfo(tz))
            except Exception:
                pass
        rows.append({
            "Date": ts,
            "Open": float(c.open),
            "High": float(c.high),
            "Low": float(c.low),
            "Close": float(c.close),
            "Volume": int(getattr(c, 'volume', 0)),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df.set_index('Date', inplace=True)
    try:
        idx = pd.to_datetime(df.index)
        if tz:
            if getattr(idx[0], 'tzinfo', None) is None:
                idx = idx.tz_localize('UTC')
            idx = idx.tz_convert(tz)
        else:
            if getattr(idx[0], 'tzinfo', None) is None:
                idx = idx.tz_localize('UTC')
        df.index = idx
    except Exception:
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            df.index = df.index

    df = df.sort_index()
    df = df[~df.index.duplicated(keep='first')]
    return df


def load_candles_from_db(db_session, stock_code: str, timeframe: str, period: Optional[str] = None, limit: Optional[int] = None, tz: Optional[str] = 'Asia/Seoul') -> pd.DataFrame:
    """Load candles from DB and return tz-aware DataFrame.

    Args:
        db_session: SQLAlchemy session
        stock_code: ticker string
        timeframe: '5m','30m','1h','1d','1wk'
        period: optional period string (e.g., '30d')
        limit: max candles to fetch (overrides default upper bound)
        tz: timezone to convert to (IANA string). Default 'Asia/Seoul'.
    """
    default_limit = DEFAULT_COUNT_MAP.get(timeframe, 500)
    fetch_limit = default_limit if (limit is None) else min(limit, default_limit)
    try:
        if period:
            candles = get_candles(db_session, stock_code, timeframe, limit=fetch_limit)
        else:
            candles = get_latest_candles(db_session, stock_code, timeframe, fetch_limit)
        df = _to_dataframe(candles, tz=tz)
        return df
    except Exception:
        return pd.DataFrame()


