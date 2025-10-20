"""
dag_financials_update.py의 단위 테스트

dag_financials_update.py의 _analyze_and_store_financials 함수가
올바르게 재무 데이터를 수집하고 DB에 저장하는지 검증합니다.

NOTE: SQLite는 PostgreSQL schema를 지원하지 않으므로,
      이 테스트들은 실제 통합 테스트 환경(PostgreSQL)에서 검증됩니다.
      단위 테스트는 financial_engine.py의 개별 클래스들로 충분히 커버됩니다.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import date

from DataPipeline.dags.dag_financials_update import _analyze_and_store_financials
from DataPipeline.src.database import Base, engine, FinancialAnalysisResult, SessionLocal


@unittest.skip("SQLite schema 미지원: 통합 테스트(PostgreSQL)에서 검증")
class TestDagFinancialsUpdate(unittest.TestCase):
    """dag_financials_update의 Task 함수 테스트"""
    
    def setUp(self):
        """각 테스트 전에 DB 테이블 생성 및 세션 오픈"""
        self.engine = engine
        Base.metadata.create_all(bind=self.engine)
        self.db = SessionLocal(bind=self.engine)
    
    def tearDown(self):
        """각 테스트 후 DB 정리"""
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
    
    @patch('DataPipeline.dags.dag_financials_update.SessionLocal')
    @patch('DataPipeline.dags.dag_financials_update.get_managed_stocks_from_db')
    @patch('DataPipeline.dags.dag_financials_update.get_corp_code_from_dart_api')
    @patch('DataPipeline.dags.dag_financials_update.fetch_live_financial_data')
    def test_analyze_and_store_financials_success(
        self, 
        mock_fetch_data,
        mock_get_corp_code,
        mock_get_stocks,
        mock_session_local
    ):
        """재무 분석 및 저장 Task가 정상 동작하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        mock_get_stocks.return_value = ['005930', '000660']
        mock_get_corp_code.side_effect = ['00126380', '00164779']  # 삼성전자, SK하이닉스
        
        # Mock DART API 응답
        mock_financials_raw = [
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11011',  # Q4
                'thstrm_amount': '1000000000000'
            },
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2022',
                'reprt_code': '11011',  # Q4
                'thstrm_amount': '800000000000'
            },
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2021',
                'reprt_code': '11011',  # Q4
                'thstrm_amount': '600000000000'
            }
        ]
        
        mock_shares_raw = [
            {
                'se': '보통주',
                'bsns_year': '2023',
                'distb_stock_co': '50000000000'  # 500억 주
            }
        ]
        
        mock_fetch_data.return_value = (mock_financials_raw, mock_shares_raw)
        
        # Mock kwargs
        mock_kwargs = {
            'params': {'stock_limit': 0}
        }
        
        # Act
        _analyze_and_store_financials(**mock_kwargs)
        
        # Assert
        # DB에 2개 종목의 분석 결과가 저장되었는지 확인
        results = self.db.query(FinancialAnalysisResult).all()
        self.assertEqual(len(results), 2, "2개 종목의 분석 결과가 저장되어야 함")
        
        # 첫 번째 종목 검증
        result_005930 = self.db.query(FinancialAnalysisResult).filter_by(stock_code='005930').first()
        self.assertIsNotNone(result_005930, "삼성전자 분석 결과가 존재해야 함")
        self.assertEqual(result_005930.analysis_date, date.today())
        self.assertIsNotNone(result_005930.financial_grade, "재무 등급이 할당되어야 함")
    
    @patch('DataPipeline.dags.dag_financials_update.SessionLocal')
    @patch('DataPipeline.dags.dag_financials_update.get_managed_stocks_from_db')
    @patch('DataPipeline.dags.dag_financials_update.get_corp_code_from_dart_api')
    def test_analyze_and_store_financials_with_stock_limit(
        self, 
        mock_get_corp_code,
        mock_get_stocks,
        mock_session_local
    ):
        """stock_limit 파라미터가 올바르게 작동하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        mock_get_stocks.return_value = ['005930', '000660', '035720', '051910']
        mock_get_corp_code.return_value = None  # 모든 종목이 corp_code 조회 실패 (skip)
        
        # Mock kwargs with stock_limit=2
        mock_kwargs = {
            'params': {'stock_limit': 2}
        }
        
        # Act
        _analyze_and_store_financials(**mock_kwargs)
        
        # Assert
        # get_corp_code_from_dart_api가 2번만 호출되어야 함 (stock_limit=2)
        self.assertEqual(mock_get_corp_code.call_count, 2, "stock_limit=2이므로 2번만 호출되어야 함")
    
    @patch('DataPipeline.dags.dag_financials_update.SessionLocal')
    @patch('DataPipeline.dags.dag_financials_update.get_managed_stocks_from_db')
    @patch('DataPipeline.dags.dag_financials_update.get_corp_code_from_dart_api')
    @patch('DataPipeline.dags.dag_financials_update.fetch_live_financial_data')
    def test_analyze_and_store_financials_skip_on_no_data(
        self, 
        mock_fetch_data,
        mock_get_corp_code,
        mock_get_stocks,
        mock_session_local
    ):
        """재무 데이터가 없을 때 건너뛰는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        mock_get_stocks.return_value = ['005930']
        mock_get_corp_code.return_value = '00126380'
        mock_fetch_data.return_value = (None, None)  # 재무 데이터 없음
        
        # Mock kwargs
        mock_kwargs = {
            'params': {'stock_limit': 0}
        }
        
        # Act
        _analyze_and_store_financials(**mock_kwargs)
        
        # Assert
        # DB에 저장된 결과가 없어야 함
        results = self.db.query(FinancialAnalysisResult).all()
        self.assertEqual(len(results), 0, "재무 데이터가 없으면 저장되지 않아야 함")
    
    @patch('DataPipeline.dags.dag_financials_update.SessionLocal')
    @patch('DataPipeline.dags.dag_financials_update.get_managed_stocks_from_db')
    @patch('DataPipeline.dags.dag_financials_update.get_corp_code_from_dart_api')
    @patch('DataPipeline.dags.dag_financials_update.fetch_live_financial_data')
    def test_analyze_and_store_financials_upsert_on_conflict(
        self, 
        mock_fetch_data,
        mock_get_corp_code,
        mock_get_stocks,
        mock_session_local
    ):
        """동일 종목/날짜에 대한 UPSERT가 올바르게 동작하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        mock_get_stocks.return_value = ['005930']
        mock_get_corp_code.return_value = '00126380'
        
        mock_financials_raw = [
            {
                'account_id': 'ifrs-full_ProfitLossAttributableToOwnersOfParent',
                'bsns_year': '2023',
                'reprt_code': '11011',
                'thstrm_amount': '1000000000000'
            }
        ]
        
        mock_shares_raw = [
            {
                'se': '보통주',
                'bsns_year': '2023',
                'distb_stock_co': '50000000000'
            }
        ]
        
        mock_fetch_data.return_value = (mock_financials_raw, mock_shares_raw)
        
        # Mock kwargs
        mock_kwargs = {
            'params': {'stock_limit': 0}
        }
        
        # Act: 첫 번째 실행
        _analyze_and_store_financials(**mock_kwargs)
        
        # Assert: 1개 레코드 존재
        results = self.db.query(FinancialAnalysisResult).all()
        self.assertEqual(len(results), 1, "첫 실행 후 1개 레코드가 존재해야 함")
        first_created_at = results[0].created_at
        
        # Act: 두 번째 실행 (UPSERT 테스트)
        _analyze_and_store_financials(**mock_kwargs)
        
        # Assert: 여전히 1개 레코드만 존재 (INSERT가 아닌 UPDATE)
        results = self.db.query(FinancialAnalysisResult).all()
        self.assertEqual(len(results), 1, "UPSERT이므로 여전히 1개 레코드만 존재해야 함")
        
        # created_at은 변경되지 않아야 함 (UPDATE는 기존 레코드 유지)
        # Note: SQLite의 on_conflict_do_update는 created_at을 건드리지 않음


if __name__ == '__main__':
    unittest.main()

