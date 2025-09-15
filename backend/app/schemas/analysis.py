from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel


class ExtremumPoint(BaseModel):
    type: str
    index: int
    value: float
    actual_date: Optional[datetime] = None
    detected_date: Optional[datetime] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None


class TrendPeriod(BaseModel):
    start: datetime
    end: datetime
    type: str


class DetectedPattern(BaseModel):
    date: datetime
    price: float
    pattern_type: str  # e.g., "DT", "DB", "HS", "IHS"
    meta: Dict[str, Any]


# FullAnalysisResponse 및 관련 스키마는 더 이상 사용되지 않아 제거되었습니다.


