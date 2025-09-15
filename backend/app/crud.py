"""CRUD utilities for ChartInsight Backend.

This module provides read-focused helpers to query the existing
tables managed by the DataPipeline:
 - live.stocks
 - live.candles

Write operations are intentionally omitted for safety.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Tuple

from sqlalchemy import and_, select
from sqlalchemy.orm import Session

from app.models import Stock, Candle


# ------------------------------
# Timeframe normalization
# ------------------------------
_FRONTEND_TO_DB_TIMEFRAME = {
    # minutes
    "5m": "M5",
    "30m": "M30",
    # hours
    "1h": "H1",
    "60m": "H1",
    # days/weeks
    "1d": "D",
    "1w": "W",
    "1wk": "W",
}


def normalize_timeframe(input_timeframe: str) -> str:
    """Normalize various timeframe inputs to DB format.

    Examples:
      - '5m' -> 'M5'
      - '30m' -> 'M30'
      - '1h' -> 'H1'
      - '1d' -> 'D'
      - '1w' -> 'W'
      - already-normalized returns as-is (e.g., 'M5', 'D')
    """
    if not input_timeframe:
        return input_timeframe
    tf = input_timeframe.strip()
    if tf in _FRONTEND_TO_DB_TIMEFRAME:
        return _FRONTEND_TO_DB_TIMEFRAME[tf]
    return tf.upper()


# ------------------------------
# Stocks
# ------------------------------
def list_stocks(db: Session, limit: Optional[int] = None) -> List[Stock]:
    stmt = select(Stock).order_by(Stock.stock_code)
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_stock(db: Session, stock_code: str) -> Optional[Stock]:
    stmt = select(Stock).where(Stock.stock_code == stock_code)
    return db.execute(stmt).scalars().first()


# ------------------------------
# Candles
# ------------------------------
def get_candles(
    db: Session,
    stock_code: str,
    timeframe: str,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: Optional[int] = None,
    sort_asc: bool = True,
) -> List[Candle]:
    """Fetch candles by filters.

    - stock_code: 6-digit code (e.g., '005930')
    - timeframe: accepts either frontend format ('5m', '1d', ...) or DB format ('M5', 'D', ...)
    - start_time/end_time are inclusive bounds if provided
    - limit: optional row cap; applied after ordering
    - sort_asc: True for oldest->newest, False for newest->oldest
    """
    tf = normalize_timeframe(timeframe)

    conditions = [
        Candle.stock_code == stock_code,
        Candle.timeframe == tf,
    ]
    if start_time is not None:
        conditions.append(Candle.timestamp >= start_time)
    if end_time is not None:
        conditions.append(Candle.timestamp <= end_time)

    stmt = select(Candle).where(and_(*conditions))
    if sort_asc:
        stmt = stmt.order_by(Candle.timestamp.asc())
    else:
        stmt = stmt.order_by(Candle.timestamp.desc())
    if limit is not None and limit > 0:
        stmt = stmt.limit(limit)

    return list(db.execute(stmt).scalars().all())


def get_latest_candles(
    db: Session,
    stock_code: str,
    timeframe: str,
    limit: int,
) -> List[Candle]:
    """Fetch latest N candles sorted from oldest to newest (stable for charting)."""
    tf = normalize_timeframe(timeframe)

    stmt = (
        select(Candle)
        .where(
            and_(
                Candle.stock_code == stock_code,
                Candle.timeframe == tf,
            )
        )
        .order_by(Candle.timestamp.desc())
        .limit(max(1, limit))
    )

    rows = list(db.execute(stmt).scalars().all())
    rows.reverse()  # ensure ascending time for plotting
    return rows


def get_time_range(
    db: Session,
    stock_code: str,
    timeframe: str,
) -> Optional[Tuple[datetime, datetime]]:
    """Return (min_timestamp, max_timestamp) available for the given series."""
    tf = normalize_timeframe(timeframe)

    # min
    stmt_min = (
        select(Candle.timestamp)
        .where(and_(Candle.stock_code == stock_code, Candle.timeframe == tf))
        .order_by(Candle.timestamp.asc())
        .limit(1)
    )
    # max
    stmt_max = (
        select(Candle.timestamp)
        .where(and_(Candle.stock_code == stock_code, Candle.timeframe == tf))
        .order_by(Candle.timestamp.desc())
        .limit(1)
    )

    min_row = db.execute(stmt_min).scalar()
    max_row = db.execute(stmt_max).scalar()

    if min_row is None or max_row is None:
        return None
    return (min_row, max_row)


