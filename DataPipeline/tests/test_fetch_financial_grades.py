"""
dag_daily_batch.py의 _fetch_financial_grades_from_db 함수 단위 테스트

financial_analysis_results 테이블에서 각 종목별 최신 재무 분석 결과를
올바르게 조회하는지 검증합니다.

NOTE: SQLite는 PostgreSQL schema를 지원하지 않으므로,
      이 테스트들은 실제 통합 테스트 환경(PostgreSQL)에서 검증됩니다.
"""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from DataPipeline.dags.dag_daily_batch import _fetch_financial_grades_from_db
from DataPipeline.src.database import Base, engine, FinancialAnalysisResult, SessionLocal


@unittest.skip("SQLite schema 미지원: 통합 테스트(PostgreSQL)에서 검증")
class TestFetchFinancialGrades(unittest.TestCase):
    """_fetch_financial_grades_from_db 함수 테스트"""
    
    def setUp(self):
        """각 테스트 전에 DB 테이블 생성 및 세션 오픈"""
        self.engine = engine
        Base.metadata.create_all(bind=self.engine)
        self.db = SessionLocal(bind=self.engine)
    
    def tearDown(self):
        """각 테스트 후 DB 정리"""
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)
    
    @patch('DataPipeline.dags.dag_daily_batch.SessionLocal')
    def test_fetch_latest_financial_grades(self, mock_session_local):
        """각 종목별 가장 최신 재무 등급을 조회하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        
        # 테스트 데이터 준비: 2개 종목, 각각 2개의 분석 날짜
        today = date.today()
        yesterday = today - timedelta(days=1)
        
        # 종목 1: 005930 (최신: today, 이전: yesterday)
        self.db.add(FinancialAnalysisResult(
            stock_code='005930',
            analysis_date=yesterday,
            eps_growth_yoy=20.0,
            eps_annual_growth_avg=15.0,
            financial_grade='Loose'
        ))
        self.db.add(FinancialAnalysisResult(
            stock_code='005930',
            analysis_date=today,
            eps_growth_yoy=30.0,
            eps_annual_growth_avg=25.0,
            financial_grade='Strict'
        ))
        
        # 종목 2: 000660 (최신: today만 존재)
        self.db.add(FinancialAnalysisResult(
            stock_code='000660',
            analysis_date=today,
            eps_growth_yoy=18.0,
            eps_annual_growth_avg=12.0,
            financial_grade='Loose'
        ))
        
        self.db.commit()
        
        # Mock kwargs
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = ['005930', '000660']
        mock_kwargs = {'ti': mock_ti}
        
        # Act
        result = _fetch_financial_grades_from_db(**mock_kwargs)
        
        # Assert
        self.assertEqual(len(result), 2, "2개 종목의 결과가 반환되어야 함")
        
        # 종목 1: 최신 날짜(today)의 데이터만 반환되어야 함
        self.assertIn('005930', result)
        self.assertEqual(result['005930']['eps_growth_yoy'], 30.0)
        self.assertEqual(result['005930']['eps_annual_growth_avg'], 25.0)
        self.assertEqual(result['005930']['financial_grade'], 'Strict')
        
        # 종목 2: today 데이터 반환
        self.assertIn('000660', result)
        self.assertEqual(result['000660']['eps_growth_yoy'], 18.0)
        self.assertEqual(result['000660']['financial_grade'], 'Loose')
    
    @patch('DataPipeline.dags.dag_daily_batch.SessionLocal')
    def test_fetch_with_no_data(self, mock_session_local):
        """재무 데이터가 없을 때 빈 딕셔너리를 반환하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = ['005930', '000660']
        mock_kwargs = {'ti': mock_ti}
        
        # Act (DB에 데이터 없음)
        result = _fetch_financial_grades_from_db(**mock_kwargs)
        
        # Assert
        self.assertEqual(result, {}, "데이터가 없으면 빈 딕셔너리를 반환해야 함")
    
    @patch('DataPipeline.dags.dag_daily_batch.SessionLocal')
    def test_fetch_with_partial_data(self, mock_session_local):
        """일부 종목만 재무 데이터가 있을 때 올바르게 처리하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        
        # 종목 1만 데이터 존재
        self.db.add(FinancialAnalysisResult(
            stock_code='005930',
            analysis_date=date.today(),
            eps_growth_yoy=25.0,
            eps_annual_growth_avg=20.0,
            financial_grade='Strict'
        ))
        self.db.commit()
        
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = ['005930', '000660', '035720']  # 3개 종목
        mock_kwargs = {'ti': mock_ti}
        
        # Act
        result = _fetch_financial_grades_from_db(**mock_kwargs)
        
        # Assert
        self.assertEqual(len(result), 1, "데이터가 있는 1개 종목만 반환되어야 함")
        self.assertIn('005930', result)
        self.assertNotIn('000660', result)
        self.assertNotIn('035720', result)
    
    @patch('DataPipeline.dags.dag_daily_batch.SessionLocal')
    def test_fetch_with_no_stock_codes(self, mock_session_local):
        """XCom에서 종목 리스트를 받지 못했을 때 빈 딕셔너리를 반환하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = None  # XCom에서 데이터 없음
        mock_kwargs = {'ti': mock_ti}
        
        # Act
        result = _fetch_financial_grades_from_db(**mock_kwargs)
        
        # Assert
        self.assertEqual(result, {}, "종목 리스트가 없으면 빈 딕셔너리를 반환해야 함")
    
    @patch('DataPipeline.dags.dag_daily_batch.SessionLocal')
    def test_fetch_handles_null_values(self, mock_session_local):
        """NULL 값을 포함한 재무 데이터를 올바르게 처리하는지 검증"""
        # Arrange
        mock_session_local.return_value = self.db
        
        # NULL 값 포함 데이터
        self.db.add(FinancialAnalysisResult(
            stock_code='005930',
            analysis_date=date.today(),
            eps_growth_yoy=None,  # NULL
            eps_annual_growth_avg=None,  # NULL
            financial_grade='Fail'
        ))
        self.db.commit()
        
        mock_ti = MagicMock()
        mock_ti.xcom_pull.return_value = ['005930']
        mock_kwargs = {'ti': mock_ti}
        
        # Act
        result = _fetch_financial_grades_from_db(**mock_kwargs)
        
        # Assert
        self.assertIn('005930', result)
        self.assertIsNone(result['005930']['eps_growth_yoy'])
        self.assertIsNone(result['005930']['eps_annual_growth_avg'])
        self.assertEqual(result['005930']['financial_grade'], 'Fail')


if __name__ == '__main__':
    unittest.main()

