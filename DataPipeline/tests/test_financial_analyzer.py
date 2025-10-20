import unittest
import pandas as pd

from DataPipeline.src.analysis.financial_engine import _FinancialDataParser, _EpsCalculator, _FinancialGradeAnalyzer


class TestFinancialDataParser(unittest.TestCase):
    def setUp(self):
        self.parser = _FinancialDataParser()

    def test_parse_with_valid_data(self):
        """정상적인 재무제표와 주식총수 데이터를 파싱하는지 검증"""
        # Arrange: 가짜 API 응답 데이터
        financials_raw = [
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11011',  # Q4
                'thstrm_amount': '1000000000'
            },
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11014',  # Q3
                'thstrm_amount': '750000000'
            },
            {
                'account_id': 'ifrs-full_SomeOtherAccount',  # 다른 계정 (무시되어야 함)
                'bsns_year': '2023',
                'reprt_code': '11011',
                'thstrm_amount': '500000000'
            }
        ]
        
        annual_shares_raw = [
            {
                'se': '보통주',
                'bsns_year': '2023',
                'distb_stock_co': '50000000'
            },
            {
                'se': '우선주',  # 보통주가 아님 (무시되어야 함)
                'bsns_year': '2023',
                'distb_stock_co': '10000000'
            }
        ]
        
        # Act
        result_df = self.parser.parse(financials_raw, annual_shares_raw)
        
        # Assert
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertEqual(len(result_df), 3)  # 당기순이익 2개 + 주식총수 1개
        
        # 컬럼 검증
        expected_columns = ['year', 'quarter', 'account_id', 'amount']
        self.assertListEqual(list(result_df.columns), expected_columns)
        
        # 당기순이익 데이터 검증
        net_income = result_df[result_df['account_id'] == 'ifrs-full_ProfitLossAttributableToOwnersOfParent']
        self.assertEqual(len(net_income), 2)
        self.assertEqual(net_income[net_income['quarter'] == 'Q4'].iloc[0]['amount'], 1000000000)
        self.assertEqual(net_income[net_income['quarter'] == 'Q3'].iloc[0]['amount'], 750000000)
        
        # 주식총수 데이터 검증
        shares = result_df[result_df['account_id'] == 'SharesOutstanding']
        self.assertEqual(len(shares), 1)
        self.assertEqual(shares.iloc[0]['year'], 2023)
        self.assertEqual(shares.iloc[0]['quarter'], 'Q4')
        self.assertEqual(shares.iloc[0]['amount'], 50000000)

    def test_parse_with_empty_data(self):
        """빈 데이터를 파싱할 때 빈 DataFrame을 반환하는지 검증"""
        # Act
        result_df = self.parser.parse([], [])
        
        # Assert
        self.assertIsInstance(result_df, pd.DataFrame)
        self.assertTrue(result_df.empty)
        self.assertListEqual(list(result_df.columns), ['year', 'quarter', 'account_id', 'amount'])

    def test_parse_with_missing_fields(self):
        """필수 필드가 누락된 데이터는 건너뛰는지 검증"""
        # Arrange
        financials_raw = [
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                # 'bsns_year' 누락
                'reprt_code': '11011',
                'thstrm_amount': '1000000000'
            },
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11011',
                'thstrm_amount': '2000000000'  # 정상 데이터
            }
        ]
        
        annual_shares_raw = [
            {
                'se': '보통주',
                # 'bsns_year' 누락
                'distb_stock_co': '50000000'
            }
        ]
        
        # Act
        result_df = self.parser.parse(financials_raw, annual_shares_raw)
        
        # Assert
        self.assertEqual(len(result_df), 1)  # 정상 데이터 1개만
        self.assertEqual(result_df.iloc[0]['amount'], 2000000000)

    def test_parse_with_comma_in_amount(self):
        """금액에 콤마가 있어도 올바르게 파싱하는지 검증"""
        # Arrange
        financials_raw = [
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11011',
                'thstrm_amount': '1,000,000,000'
            }
        ]
        
        annual_shares_raw = [
            {
                'se': '보통주',
                'bsns_year': '2023',
                'distb_stock_co': '50,000,000'
            }
        ]
        
        # Act
        result_df = self.parser.parse(financials_raw, annual_shares_raw)
        
        # Assert
        self.assertEqual(result_df[result_df['account_id'] == 'ifrs-full_ProfitLossAttributableToOwnersOfParent'].iloc[0]['amount'], 1000000000)
        self.assertEqual(result_df[result_df['account_id'] == 'SharesOutstanding'].iloc[0]['amount'], 50000000)

    def test_report_code_to_quarter(self):
        """보고서 코드가 올바르게 분기로 변환되는지 검증"""
        self.assertEqual(self.parser._report_code_to_quarter('11013'), 'Q1')
        self.assertEqual(self.parser._report_code_to_quarter('11012'), 'Q2')
        self.assertEqual(self.parser._report_code_to_quarter('11014'), 'Q3')
        self.assertEqual(self.parser._report_code_to_quarter('11011'), 'Q4')
        self.assertEqual(self.parser._report_code_to_quarter('99999'), 'Unknown')

    def test_to_numeric(self):
        """_to_numeric 메서드가 올바르게 동작하는지 검증"""
        self.assertEqual(self.parser._to_numeric('1000'), 1000)
        self.assertEqual(self.parser._to_numeric('1,000,000'), 1000000)
        self.assertEqual(self.parser._to_numeric(''), 0)
        self.assertEqual(self.parser._to_numeric('invalid'), 0)
        self.assertEqual(self.parser._to_numeric(None), 0)


class TestEpsCalculator(unittest.TestCase):
    def setUp(self):
        self.calculator = _EpsCalculator()
    
    def test_calculate_eps_with_valid_data(self):
        """정상 데이터로 EPS가 올바르게 계산되는지 검증"""
        # Arrange
        df = pd.DataFrame([
            {'year': 2023, 'quarter': 'Q4', 'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent', 'amount': 1000000000},
            {'year': 2023, 'quarter': 'Q4', 'account_id': 'SharesOutstanding', 'amount': 50000000},
            {'year': 2022, 'quarter': 'Q4', 'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent', 'amount': 800000000},
            {'year': 2022, 'quarter': 'Q4', 'account_id': 'SharesOutstanding', 'amount': 50000000},
        ])
        
        # Act
        result = self.calculator.calculate(df, current_list_count=50000000)
        
        # Assert
        self.assertIsInstance(result, pd.DataFrame)
        self.assertFalse(result.empty)
        self.assertIn('EPS', result.columns)
        
        # 2023년 EPS 검증: 1000000000 / 50000000 = 20
        eps_2023 = result[result['year'] == 2023]['EPS'].iloc[0]
        self.assertAlmostEqual(eps_2023, 20.0, places=2)
    
    def test_calculate_eps_without_shares_data(self):
        """주식수 데이터가 없어도 current_list_count로 계산되는지 검증"""
        # Arrange
        df = pd.DataFrame([
            {'year': 2023, 'quarter': 'Q4', 'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent', 'amount': 500000000},
        ])
        
        # Act
        result = self.calculator.calculate(df, current_list_count=25000000)
        
        # Assert
        self.assertIsInstance(result, pd.DataFrame)
        self.assertFalse(result.empty)
        
        # EPS 검증: 500000000 / 25000000 = 20
        eps = result['EPS'].iloc[0]
        self.assertAlmostEqual(eps, 20.0, places=2)


class TestFinancialGradeAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = _FinancialGradeAnalyzer()
    
    def test_analyze_strict_grade(self):
        """Strict 등급 판정이 올바르게 동작하는지 검증"""
        # Arrange: 3년간 높은 성장률 + 최근 분기 YoY 25% 이상
        eps_df = pd.DataFrame([
            {'year': 2020, 'quarter': 'Q4', 'EPS': 10.0},
            {'year': 2021, 'quarter': 'Q4', 'EPS': 14.0},  # 40% 성장
            {'year': 2022, 'quarter': 'Q4', 'EPS': 18.0},  # 28.6% 성장
            {'year': 2023, 'quarter': 'Q4', 'EPS': 24.0},  # 33.3% 성장
            {'year': 2022, 'quarter': 'Q3', 'EPS': 4.0},
            {'year': 2023, 'quarter': 'Q3', 'EPS': 6.0},   # 50% YoY 성장
        ])
        
        # Act
        result = self.analyzer.analyze(eps_df)
        
        # Assert
        self.assertEqual(result['financial_grade'], 'Strict')
        self.assertGreater(result['eps_growth_yoy'], 25)
        self.assertGreater(result['eps_annual_growth_avg'], 25)
    
    def test_analyze_loose_grade(self):
        """Loose 등급 판정이 올바르게 동작하는지 검증"""
        # Arrange: 성장은 있지만 Strict 기준에는 미달 (연평균 15% 이상, YoY 25% 미만)
        eps_df = pd.DataFrame([
            {'year': 2021, 'quarter': 'Q4', 'EPS': 10.0},
            {'year': 2022, 'quarter': 'Q4', 'EPS': 12.5},  # 25% 성장
            {'year': 2023, 'quarter': 'Q4', 'EPS': 15.0},  # 20% 성장 (CAGR = 22.5% > 15%)
            {'year': 2022, 'quarter': 'Q3', 'EPS': 3.0},
            {'year': 2023, 'quarter': 'Q3', 'EPS': 3.5},  # 16.7% YoY (< 25%, Strict 미달)
        ])
        
        # Act
        result = self.analyzer.analyze(eps_df)
        
        # Assert
        self.assertEqual(result['financial_grade'], 'Loose')
    
    def test_analyze_fail_grade(self):
        """Fail 등급 판정이 올바르게 동작하는지 검증"""
        # Arrange: 역성장 또는 적자
        eps_df = pd.DataFrame([
            {'year': 2021, 'quarter': 'Q4', 'EPS': 10.0},
            {'year': 2022, 'quarter': 'Q4', 'EPS': 8.0},
            {'year': 2023, 'quarter': 'Q4', 'EPS': 6.0},
            {'year': 2022, 'quarter': 'Q3', 'EPS': 4.0},
            {'year': 2023, 'quarter': 'Q3', 'EPS': 3.0},  # 역성장
        ])
        
        # Act
        result = self.analyzer.analyze(eps_df)
        
        # Assert
        self.assertEqual(result['financial_grade'], 'Fail')


if __name__ == '__main__':
    unittest.main()

