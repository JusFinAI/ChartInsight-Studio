from typing import Dict, List
from src.config import FILTER_ZERO_CONFIG


def apply_filter_zero(stock_list: List[Dict]) -> List[Dict]:
    """
    '필터 제로' 규칙을 적용하여 분석 대상 종목을 필터링하는 공통 함수.

    동작 요약:
    - 이 함수는 중앙 설정(`FILTER_ZERO_CONFIG`)을 사용합니다.
    - 키워드 기반 제외 검사: 종목의 `name`, `state`, `auditInfo` 필드를 소문자화하여 비교합니다.
    - 시가총액 계산: (lastPrice * listCount) / 100_000_000 로 계산하여 단위를 '억 원'으로 맞춥니다.
      계산 결과가 `MIN_MARKET_CAP_KRW`보다 작으면 탈락합니다.

    Args:
        stock_list (List[Dict]): 필터링을 적용할 전체 종목 정보 리스트.
            각 딕셔너리는 'name', 'state', 'lastPrice', 'listCount' 등의 키를 포함할 수 있습니다.

    Returns:
        List[Dict]: '필터 제로'를 통과한 종목 정보 딕셔너리의 리스트.
    """

    # 중앙 설정 사용
    min_market_cap_억 = FILTER_ZERO_CONFIG.get("MIN_MARKET_CAP_KRW", 0)
    name_exclude_keywords = FILTER_ZERO_CONFIG.get("NAME_EXCLUDE_KEYWORDS", [])
    state_exclude_keywords = FILTER_ZERO_CONFIG.get("STATE_EXCLUDE_KEYWORDS", [])
    filter_on_warning = FILTER_ZERO_CONFIG.get("FILTER_ON_ORDER_WARNING", False)

    # 사전(루프 외부)에서 키워드 소문자화하여 반복 시 비용 절감
    name_exclude_keywords_lower = [k.lower() for k in name_exclude_keywords]
    state_exclude_keywords_lower = [k.lower() for k in state_exclude_keywords]
    market_exclude_keywords = FILTER_ZERO_CONFIG.get("MARKET_EXCLUDE_KEYWORDS", [])
    market_exclude_keywords_lower = [k.lower() for k in market_exclude_keywords]

    passed_stocks: List[Dict] = []
    for stock in stock_list:
        # 1) 종목명 키워드 필터 (대소문자 무시)
        name = (stock.get('name') or '').lower()
        if any(keyword in name for keyword in name_exclude_keywords_lower):
            continue

        # 2) 종목 상태 키워드 필터 (대소문자 무시)
        state = (stock.get('state') or '').lower()
        if any(keyword in state for keyword in state_exclude_keywords_lower):
            continue

        # 2-1b) market_name 기반 필터링 추가
        market_name = (stock.get('marketName') or stock.get('market_name') or '').lower()
        if any(keyword in market_name for keyword in market_exclude_keywords_lower):
            # 시장명이 ETF/ETN 등으로 표기된 경우 분석 대상에서 제외
            continue

        # 2-1) auditInfo도 상태와 유사한 정보로 간주하여 검사 (대소문자 무시)
        audit_info_raw = (stock.get('auditInfo') or stock.get('audit_info') or '')
        audit_info = audit_info_raw.lower()
        if any(keyword in audit_info for keyword in state_exclude_keywords_lower):
            continue

        # 3) 투자 유의(orderWarning) 필드 검사 - 단순화
        if filter_on_warning:
            order_warning = str(stock.get('orderWarning', stock.get('order_warning', '0'))).strip()
            if order_warning != '0':
                continue


        # 4) 시가총액 필터 (입력은 이미 정규화되어 숫자형이어야 함)
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
        except (ValueError, TypeError):
            # 타입 문제 등이 발생하면 탈락
            continue

        # 모두 통과
        passed_stocks.append(stock)

    return passed_stocks


