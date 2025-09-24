# timezone_map.py
"""
Ticker -> Exchange timezone mapping helper.
This module provides a simple mapping from ticker (or exchange code) to IANA timezone strings.
It is intentionally small and editable; for production it can read from a configuration file.
"""
from typing import Optional

# 기본 매핑 예시. 필요 시 확장/파일로 분리 가능.
TICKER_TZ_MAP = {
    # Korean example
    "005930": "Asia/Seoul",  # 삼성전자
    "000660": "Asia/Seoul",  # SK하이닉스
    # US examples
    "AAPL": "America/New_York",
    "SPY": "America/New_York",
}


def get_tz_for_ticker(ticker: str) -> Optional[str]:
    """Return IANA timezone name for given ticker or None if unknown."""
    if ticker is None:
        return None
    # direct match
    tz = TICKER_TZ_MAP.get(ticker)
    if tz:
        return tz
    # fallback: simple heuristic - if ticker looks like numeric (KRX), assume KST
    if ticker.isdigit() and len(ticker) == 6:
        return "Asia/Seoul"
    return None
