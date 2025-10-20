import unittest
import sys
import os

# Ensure project src is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.insert(0, project_root)

from src.kiwoom_api.services import chart


class TestChartServiceLiveFetch(unittest.TestCase):
    """Live integration tests for ChartService fetching monthly data.

    These tests call the real API and therefore require network access and
    valid credentials. They are intended to demonstrate that the service
    functions return non-empty data.
    """

    def test_get_monthly_inds_chart_kospi(self):
        res = chart.get_monthly_inds_chart('001', num_candles=5)
        self.assertTrue(hasattr(res, 'data'))
        self.assertTrue(len(res.data) > 0, 'Expected non-empty monthly data for KOSPI (001)')

    def test_get_monthly_stock_chart_samsung(self):
        res = chart.get_monthly_stock_chart('005930', num_candles=5)
        self.assertTrue(hasattr(res, 'data'))
        self.assertTrue(len(res.data) > 0, 'Expected non-empty monthly data for 005930')


if __name__ == '__main__':    unittest.main()


