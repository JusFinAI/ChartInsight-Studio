from typing import Tuple, Optional, Dict
from fuzzywuzzy import fuzz
import logging

logger = logging.getLogger(__name__)

# 수동으로 지정할 예외 케이스
MANUAL_SECTOR_MAP = {
    '부동산': '일반서비스',
    '금융업': '금융'
}

SIMILARITY_THRESHOLD = 85  # 유사도 매칭을 위한 최소 점수


def _find_sector_code(stock_code: str, industry_name: str, sector_map: Dict[str, str], manual_stock_map: Dict[str, str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Enhanced matching algorithm with three priority levels:
    0) Direct stock_code -> sector_code mapping (STOCK_CODE_TO_SECTOR_CODE_MAP provided by master_data_manager)
    1) Manual name corrections (MANUAL_SECTOR_MAP) and exact match
    2) Fuzzy matching using fuzzywuzzy.ratio with SIMILARITY_THRESHOLD

    Returns: (matched_sector_code or None, best_match_name or None)
    """
    # 0) Stock code direct mapping if provided via master_data_manager
    try:
        from src.master_data_manager import STOCK_CODE_TO_SECTOR_CODE_MAP
    except Exception:
        STOCK_CODE_TO_SECTOR_CODE_MAP = {}

    if stock_code and stock_code in STOCK_CODE_TO_SECTOR_CODE_MAP:
        return STOCK_CODE_TO_SECTOR_CODE_MAP[stock_code], None

    # 1) industry_name empty -> cannot match further
    if not industry_name:
        return None, None

    corrected_name = MANUAL_SECTOR_MAP.get(industry_name, industry_name)

    # exact match
    for name, code in sector_map.items():
        if corrected_name == name:
            return code, name

    # fuzzy match
    best_match_name = None
    highest_score = 0
    for name in sector_map.keys():
        try:
            score = fuzz.ratio(corrected_name, name)
        except Exception:
            score = 0
        if score > highest_score:
            highest_score = score
            best_match_name = name

    if highest_score >= SIMILARITY_THRESHOLD:
        return sector_map.get(best_match_name), best_match_name

    return None, best_match_name


