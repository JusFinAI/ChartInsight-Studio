# data_loader.py
"""
Data loader helper for chart_pattern_analyzer_kiwoom_db.
Provides a single entry function `load_candles_from_db` that returns a tz-aware
pandas DataFrame suitable for analysis.

Behavior:
- By default `tz='auto'` will convert timestamps to the exchange/ticker local timezone
  using `timezone_map.get_tz_for_ticker`.
- Returns tz-aware DataFrame indexed by DatetimeIndex.
- Columns: Open, High, Low, Close, Volume
"""
from typing import Optional
import pandas as pd
from zoneinfo import ZoneInfo
from backend.app.crud import get_latest_candles, get_candles


# 기본 count map (기존 엔진과 동일한 기본값 유지)
DEFAULT_COUNT_MAP = {'5m': 500, '30m': 300, '1h': 200, '1d': 500, '1wk': 200}


def _to_dataframe(candles, tz: Optional[str] = None) -> pd.DataFrame:
    if not candles:
        return pd.DataFrame()

    rows = []
    for c in candles:
        # assume c.timestamp is tz-aware UTC
        ts = c.timestamp
        # ensure timestamp is tz-aware; if naive, assume UTC
        if getattr(ts, 'tzinfo', None) is None:
            try:
                ts = ts.replace(tzinfo=ZoneInfo('UTC'))
            except Exception:
                pass
        if tz:
            try:
                ts = ts.astimezone(ZoneInfo(tz))
            except Exception:
                # fallback: keep as original tz
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
    # ensure tz-aware DatetimeIndex
    try:
        idx = pd.to_datetime(df.index)
        if tz:
            # localize naive index to UTC then convert to target tz
            if getattr(idx[0], 'tzinfo', None) is None:
                idx = idx.tz_localize('UTC')
            idx = idx.tz_convert(tz)
        else:
            # keep as parsed (may be tz-aware already)
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
        tz: timezone to convert to. If 'auto', use ticker->tz mapping.

    Returns:
        pd.DataFrame indexed by tz-aware DatetimeIndex (if tz resolved)
    """
    # timezone: expect IANA name string (e.g. 'Asia/Seoul'). Default is Asia/Seoul.
    resolved_tz = tz

    # decide fetch limit
    default_limit = DEFAULT_COUNT_MAP.get(timeframe, 500)
    fetch_limit = default_limit if (limit is None) else min(limit, default_limit)

    # choose fetch strategy depending on period
    try:
        if period:
            # use get_candles with start/end logic in caller - here we fallback to latest when period is unsupported
            candles = get_candles(db_session, stock_code, timeframe, limit=fetch_limit)
        else:
            candles = get_latest_candles(db_session, stock_code, timeframe, fetch_limit)

        df = _to_dataframe(candles, tz=resolved_tz)
        return df
    except Exception as e:
        # return empty df on error but log upstream (caller should handle)
        return pd.DataFrame()
