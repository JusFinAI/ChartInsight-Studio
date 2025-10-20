from typing import Dict, List, Optional

# '필터 제로'를 위한 기본 설정값
# dag_daily_batch.py에 있던 설정을 중앙 관리용으로 이동
DEFAULT_FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000,  # 최소 시가총액 (단위: 억 원)
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}


def apply_filter_zero(
    stock_list: List[Dict],
    config: Optional[Dict] = None
) -> List[Dict]:
    """
    '필터 제로' 규칙을 적용하여 분석 대상 종목을 필터링하는 공통 함수.

    동작 요약:
    - config가 주어지지 않으면 `DEFAULT_FILTER_ZERO_CONFIG`를 사용합니다.
    - 키워드 기반 제외(EXCLUDE_KEYWORDS) 검사: 종목의 `name`, `state`, `auditInfo` 필드를
      소문자화하여 비교합니다(대소문자 무관).
    - 시가총액 계산: (lastPrice * listCount) / 100_000_000 로 계산하여 단위를 '억 원'으로 맞춥니다.
      계산 결과가 `MIN_MARKET_CAP_KRW`보다 작으면 탈락합니다.

    Args:
        stock_list (List[Dict]): 필터링을 적용할 전체 종목 정보 리스트.
            각 딕셔너리는 'name', 'state', 'lastPrice', 'listCount' 등의 키를 포함할 수 있습니다.
        config (Optional[Dict]): 필터링 규칙을 담은 딕셔너리.
            None일 경우, `DEFAULT_FILTER_ZERO_CONFIG`를 사용합니다.
            - MIN_MARKET_CAP_KRW (int): 최소 시가총액 (단위: 억 원)
            - EXCLUDE_KEYWORDS (List[str]): 종목명/상태에 포함될 경우 제외할 키워드 리스트

    Returns:
        List[Dict]: '필터 제로'를 통과한 종목 정보 딕셔너리의 리스트.
    """

    active_config = config if config is not None else DEFAULT_FILTER_ZERO_CONFIG
    min_market_cap_억 = active_config.get("MIN_MARKET_CAP_KRW", 0)
    exclude_keywords = [k.lower() for k in active_config.get("EXCLUDE_KEYWORDS", [])]

    def _safe_parse_number(value):
        if value is None:
            return None
        s = str(value).replace(',', '').strip()
        if s == '':
            return None
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    passed_stocks: List[Dict] = []
    for stock in stock_list:
        # 1) 키워드 필터 (대소문자 무시)
        name = (stock.get('name') or '')
        state = (stock.get('state') or '')
        audit_info = (stock.get('auditInfo') or stock.get('audit_info') or '')
        combined_text = f"{name} {state} {audit_info}".lower()
        if any(keyword in combined_text for keyword in exclude_keywords):
            continue

        # 2) 시가총액 필터
        try:
            last_price_raw = stock.get('lastPrice') or stock.get('last_price')
            list_count_raw = stock.get('listCount') or stock.get('list_count')

            last_price = _safe_parse_number(last_price_raw)
            list_count = _safe_parse_number(list_count_raw)

            if last_price is None or list_count is None:
                # 필요한 숫자 데이터가 없으면 탈락
                continue

            if last_price <= 0 or list_count <= 0:
                continue

            # 시가총액(억 원 단위)
            market_cap_억 = (last_price * list_count) / 100_000_000
            if market_cap_억 < min_market_cap_억:
                continue
        except Exception:
            # 안전을 위해 어떤 에러가 발생해도 탈락
            continue

        # 모두 통과
        passed_stocks.append(stock)

    return passed_stocks


