from typing import Tuple, Optional, Dict, List, Set
from fuzzywuzzy import fuzz
import logging
from sqlalchemy.orm import Session
from src.database import Stock

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


def get_necessary_sector_codes(db: Session, user_stock_codes: List[str]) -> Set[str]:
    """
    주어진 종목 코드 리스트가 속한 모든 업종 코드를 조회하여 중복 없이 반환합니다.
    """
    if not user_stock_codes:
        return set()

    try:
        # 배치 처리를 통해 대량의 종목 코드도 효율적으로 조회
        sector_codes = set()
        batch_size = 500
        for i in range(0, len(user_stock_codes), batch_size):
            batch = user_stock_codes[i:i+batch_size]

            # Stock 테이블에서 sector_code만 조회
            sectors_in_batch = db.query(Stock.sector_code).filter(
                Stock.stock_code.in_(batch),
                Stock.sector_code.isnot(None)
            ).distinct().all()

            sector_codes.update({sector_code for (sector_code,) in sectors_in_batch})

        logger.info(f"{len(user_stock_codes)}개 종목으로부터 {len(sector_codes)}개의 관련 업종 코드를 추출했습니다.")
        return sector_codes

    except Exception as e:
        logger.error(f"필요 업종 코드 조회 중 오류 발생: {e}", exc_info=True)
        # 오류 발생 시 안전하게 빈 Set 반환
        return set()


