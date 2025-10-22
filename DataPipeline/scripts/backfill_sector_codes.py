#!/usr/bin/env python3
"""백필 스크립트: 기존 Stock 레코드의 industry_name(upName)을 바탕으로 sector_code를 채웁니다.

사용법:
    python DataPipeline/scripts/backfill_sector_codes.py
"""
import logging
from sqlalchemy import and_, or_, not_
from src.database import SessionLocal, Sector, Stock
from src.utils.sector_mapper import _find_sector_code
from src.config import FILTER_ZERO_CONFIG

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def main(batch_size: int = 500):
    db = SessionLocal()
    try:
        # load sectors into map {name: code}
        sectors = db.query(Sector.sector_code, Sector.sector_name).all()
        sector_map = {name: code for code, name in ((s.sector_code, s.sector_name) for s in sectors)}

        # 2. [수정] 'Filter Zero' 통과 종목 중 sector_code가 NULL인 대상만 조회
        name_exclude_conditions = [Stock.stock_name.ilike(f"%{keyword}%") for keyword in FILTER_ZERO_CONFIG['NAME_EXCLUDE_KEYWORDS']]
        state_exclude_conditions = [Stock.state.ilike(f"%{keyword}%") for keyword in FILTER_ZERO_CONFIG['STATE_EXCLUDE_KEYWORDS']]

        # market cap 계산식: (last_price * list_count) / 100_000_000 >= MIN_MARKET_CAP_KRW
        market_cap_expr = (Stock.list_count * Stock.last_price) / 100000000

        market_exclude_conditions = [Stock.market_name.ilike(f"%{keyword}%") for keyword in FILTER_ZERO_CONFIG.get('MARKET_EXCLUDE_KEYWORDS', [])]

        stocks_to_update = db.query(Stock).filter(
            and_(
                Stock.sector_code.is_(None),
                market_cap_expr >= FILTER_ZERO_CONFIG['MIN_MARKET_CAP_KRW'],
                not_(or_(*name_exclude_conditions)),
                not_(or_(*state_exclude_conditions)),
                not_(or_(*market_exclude_conditions)),
                Stock.order_warning == '0'
            )
        ).all()

        logger.info(f"총 {len(stocks_to_update)}개의 '분석 대상' 종목에 대해 백필을 시도합니다.")

        updated_count = 0
        for stock in stocks_to_update:
            # call _find_sector_code with stock_code and industry_name
            found_code, best_guess = _find_sector_code(stock.stock_code, stock.industry_name, sector_map)
            if found_code:
                stock.sector_code = found_code
                updated_count += 1
            else:
                logger.warning(f"[{stock.stock_code}] '{stock.industry_name}' 매칭 실패. 가장 유사한 업종: '{best_guess}'")

        if updated_count > 0:
            db.commit()
            logger.info(f"Updated sector_code for {updated_count} stocks.")
        else:
            logger.info("No sector_code updates performed.")

    finally:
        db.close()


if __name__ == '__main__':
    main()


