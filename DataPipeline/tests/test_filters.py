import unittest

from DataPipeline.src.utils.filters import apply_filter_zero
from unittest.mock import patch, MagicMock
from DataPipeline.src.database import Stock


class TestApplyFilterZero(unittest.TestCase):
    def test_normal_pass(self):
        # 시가총액 2000억(=MIN 1000억을 초과) -> 통과
        stock = {
            'name': 'GOOD CO',
            'state': '',
            'lastPrice': '10000',
            'listCount': '20000000'  # 2000만주 * 10000원 = 2000억
        }
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 1)

    def test_filter_by_keyword(self):
        stock = {'name': 'SOME 스팩 CO', 'state': '', 'lastPrice': '10000', 'listCount': '2000000'}
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 0)

    def test_case_insensitive_keyword(self):
        stock = {'name': 'lowercase etf co', 'state': '', 'lastPrice': '10000', 'listCount': '2000000'}
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 0)

    def test_market_cap_below_threshold(self):
        # 시가총액 500억 -> 기본 MIN 1000억이면 탈락
        stock = {'name': 'SMALL CO', 'state': '', 'lastPrice': '5000', 'listCount': '1000000'}
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 0)

    def test_missing_listcount(self):
        stock = {'name': 'NOCOUNT CO', 'state': '', 'lastPrice': '10000'}
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 0)

    def test_comma_in_price(self):
        stock = {'name': 'COMMA CO', 'state': '', 'lastPrice': '87,500', 'listCount': '3000000'}
        res = apply_filter_zero([stock])
        self.assertEqual(len(res), 1)

    def test_config_override_min_market_cap(self):
        # 시가총액 500억인데 MIN_MARKET_CAP_KRW를 400으로 낮추면 통과
        stock = {'name': 'MEDIUM CO', 'state': '', 'lastPrice': '5000', 'listCount': '10000000'}  # 1000만주 * 5000원 = 500억
        res = apply_filter_zero([stock], config={'MIN_MARKET_CAP_KRW': 400, 'EXCLUDE_KEYWORDS': []})
        self.assertEqual(len(res), 1)

    # 추가 테스트: _run_stock_info_load_task와의 통합 동작을 모킹하여 검증할 수 있도록
    # 간단한 목업 기반 테스트를 추가할 수 있지만, 실제 DB session/insert 동작은
    # 별도의 테스트 파일(test_initial_loader.py)에서 mock으로 처리하는 것을 권장합니다.


if __name__ == '__main__':
    unittest.main()


