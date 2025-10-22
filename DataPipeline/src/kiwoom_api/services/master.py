from typing import List, Dict
import logging

from src.kiwoom_api.core.client import client as kiwoom_client

logger = logging.getLogger(__name__)


def get_sector_list() -> List[Dict]:
    """
    Kiwoom API(ka10101)를 호출하여 KOSPI와 KOSDAQ의 전체 업종 목록을 가져옵니다.

    Returns:
        List[Dict]: [{'sector_code': '001', 'sector_name': '종합(KOSPI)', 'market_name': 'KOSPI'}, ...]
    """
    all_sectors: List[Dict] = []

    # 시장 구분: '0' (KOSPI), '10' (KOSDAQ)
    for market_code, market_name in [('0', 'KOSPI'), ('10', 'KOSDAQ')]:
        tried_codes = [market_code]
        # KOSDAQ ambiguity in docs: try both '10' and '1' if initial attempt returns nothing
        if market_code == '10':
            tried_codes.append('1')

        items = []
        for try_code in tried_codes:
            try:
                logger.info(f"ka10101 호출 시도: market_code={try_code} ({market_name})")
                res = kiwoom_client.request('/api/dostk/stkinfo', 'ka10101', {'mrkt_tp': try_code})
                data = res.get('data') if isinstance(res, dict) else None
                if data and isinstance(data, dict):
                    items = data.get('list') or data.get('result') or []
                if items:
                    logger.info(f"ka10101 응답 수신: market_code={try_code}, items={len(items)}")
                    break
                else:
                    logger.warning(f"ka10101 응답 빈 리스트: market_code={try_code}")
            except Exception as e:
                logger.error(f"업종 목록 조회 실패(market_code={try_code}): {e}")
                # try next code if available
                continue

        if not items:
            logger.warning(f"ka10101 API 응답 없음 또는 형식 불일치: market_codes={tried_codes}")
            continue

        for item in items:
            code = item.get('code')
            name = item.get('name') or item.get('inds_nm') or item.get('upName') or ''
            if not code:
                continue
            all_sectors.append({
                'sector_code': code,
                'sector_name': name.strip(),
                'market_name': market_name
            })

    return all_sectors


