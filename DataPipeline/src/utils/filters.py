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

    # apply_filter_zero는 이제 master_data_manager에서 숫자 타입으로 정규화된 값을 전달받음을 기대합니다.
    # 따라서 문자열 파싱 로직은 제거하고 None/0 체크만 수행합니다.

    passed_stocks: List[Dict] = []
    for stock in stock_list:
        # 1) 키워드 필터 (대소문자 무시)
        name = (stock.get('name') or '')
        state = (stock.get('state') or '')
        audit_info = (stock.get('auditInfo') or stock.get('audit_info') or '')
        combined_text = f"{name} {state} {audit_info}".lower()
        if any(keyword in combined_text for keyword in exclude_keywords):
            continue

        # 2) 시가총액 필터 (입력은 이미 숫자형이어야 함)
        last_price = stock.get('lastPrice') if 'lastPrice' in stock else stock.get('last_price')
        list_count = stock.get('listCount') if 'listCount' in stock else stock.get('list_count')

        if last_price is None or list_count is None:
            # 필요한 숫자 데이터가 없으면 탈락
            continue

        try:
            # 이미 숫자 타입일 것을 가정 (master_data_manager에서 정규화)
            if last_price <= 0 or list_count <= 0:
                continue

            market_cap_억 = (float(last_price) * float(list_count)) / 100_000_000
            if market_cap_억 < min_market_cap_억:
                continue
        except Exception:
            # 타입 문제 등이 발생하면 탈락
            continue

        # 모두 통과
        passed_stocks.append(stock)

    return passed_stocks


