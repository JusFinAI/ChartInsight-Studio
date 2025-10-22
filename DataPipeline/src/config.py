"""Central configuration for DataPipeline.

This file centralizes FILTER_ZERO_CONFIG and other pipeline-wide
settings so they can be changed in one place.
"""

FILTER_ZERO_CONFIG = {
    # 기준 1: 최소 시가총액 (단위: 억 원)
    "MIN_MARKET_CAP_KRW": 1000,

    # 기준 2: 종목명(name)에 포함되면 제외할 키워드
    "NAME_EXCLUDE_KEYWORDS": [
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ],

    # 기준 3: 종목 상태(state)에 포함되면 제외할 키워드
    "STATE_EXCLUDE_KEYWORDS": [
        "관리종목", "거래정지", "증거금100"
    ],

    # 기준 4: 투자 유의(orderWarning) 필드가 '0'(정상)이 아니면 제외
    "FILTER_ON_ORDER_WARNING": True,
    # 기준 5: market_name에 포함되면 제외할 키워드 (예: ETF 등)
    "MARKET_EXCLUDE_KEYWORDS": [
        "ETF", "ETN", "KONEX"
    ]
}


