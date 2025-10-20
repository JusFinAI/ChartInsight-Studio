import unittest
from unittest.mock import patch, MagicMock

from DataPipeline.dags.dag_initial_loader import _run_stock_info_load_task, _run_initial_load_task
from DataPipeline.src.database import Base, engine, Stock, SessionLocal

class TestInitialLoaderTasks(unittest.TestCase):

    def setUp(self):
        """각 테스트 전에 DB 테이블을 생성하고 세션을 엽니다."""
        self.engine = engine
        Base.metadata.create_all(bind=self.engine)
        self.db = SessionLocal(bind=self.engine)

    def tearDown(self):
        """각 테스트 후에 DB 세션을 닫고 테이블을 삭제합니다."""
        self.db.close()
        Base.metadata.drop_all(bind=self.engine)

    @patch('DataPipeline.dags.dag_initial_loader.apply_filter_zero')
    @patch('DataPipeline.dags.dag_initial_loader.sync_stock_master_data')
    def test_01_run_stock_info_load_task(self, mock_sync_master, mock_apply_filter):
        """[Task 1] _run_stock_info_load_task가 필터링과 DB 저장을 올바르게 수행하는지 검증"""
        # 1. Mock 데이터 설정
        mock_api_results = [
            {'code': '005930', 'name': '삼성전자', 'marketName': 'KOSPI'},
            {'code': '000010', 'name': '대상 스팩', 'marketName': 'KOSPI'}, # 키워드 탈락
        ]
        mock_sync_master.return_value = mock_api_results
        mock_apply_filter.return_value = [mock_api_results[0]] # '삼성전자'만 통과

        # 2. 테스트 대상 함수 실행 (실제 DB 세션을 인자로 주입)
        _run_stock_info_load_task(db_session=self.db)

        # 3. 검증: 실제 DB에 데이터가 올바르게 저장되었는지 직접 확인
        stocks_in_db = self.db.query(Stock).all()
        self.assertEqual(len(stocks_in_db), 1)
        saved_stock = stocks_in_db[0]
        self.assertEqual(saved_stock.stock_code, '005930')
        self.assertTrue(saved_stock.is_active)
        self.assertTrue(saved_stock.backfill_needed)

    @patch('DataPipeline.dags.dag_initial_loader.load_initial_history')
    def test_02_run_initial_load_task_auto_mode(self, mock_load_initial_history):
        """[Task 2] _run_initial_load_task의 자동 모드가 정상 동작하는지 검증"""
        # 1. Mock 데이터 설정: DB에 backfill_needed=True인 종목 2개 저장
        s1 = Stock(stock_code='AAA', stock_name='AAA', is_active=True, backfill_needed=True)
        s2 = Stock(stock_code='BBB', stock_name='BBB', is_active=True, backfill_needed=True)
        s3 = Stock(stock_code='CCC', stock_name='CCC', is_active=True, backfill_needed=False) # 이건 처리되면 안됨
        self.db.add_all([s1, s2, s3])
        self.db.commit()

        mock_load_initial_history.return_value = True

        # 2. 실행: dag_run.conf 없이 자동 모드로 실행
        # Airflow의 dag_run.conf를 모방하기 위한 간단한 객체 생성
        mock_dag_run = type('MockDagRun', (), {'conf': {}})()
        _run_initial_load_task(db_session=self.db, dag_run=mock_dag_run)

        # 3. 검증
        # a) load_initial_history가 2개 종목 × 5개 타임프레임 = 10번 호출되었는지 확인
        default_timeframes = ['5m', '30m', '1h', 'd', 'w']
        self.assertEqual(mock_load_initial_history.call_count, 2 * len(default_timeframes))

        # b) DB에서 backfill_needed가 False로 업데이트되었는지 확인
        refreshed_stocks = self.db.query(Stock).order_by(Stock.stock_code).all()
        self.assertFalse(refreshed_stocks[0].backfill_needed) # AAA
        self.assertFalse(refreshed_stocks[1].backfill_needed) # BBB
        self.assertFalse(refreshed_stocks[2].backfill_needed) # CCC는 원래 False였음

    @patch('DataPipeline.dags.dag_initial_loader.load_initial_history')
    def test_03_run_initial_load_task_manual_mode(self, mock_load_initial_history):
        """[Task 2] _run_initial_load_task의 수동 모드가 정상 동작하는지 검증"""
        # 1. Mock 데이터 설정
        mock_load_initial_history.return_value = True

        # 2. 실행: dag_run.conf에 stock_codes 전달
        mock_dag_run = type('MockDagRun', (), {'conf': {'stock_codes': '005930, 000660'}})()
        _run_initial_load_task(db_session=self.db, dag_run=mock_dag_run)

        # 3. 검증: load_initial_history가 2개 종목 × 5개 타임프레임 = 10번 호출되었는지 확인
        default_timeframes = ['5m', '30m', '1h', 'd', 'w']
        self.assertEqual(mock_load_initial_history.call_count, 2 * len(default_timeframes))

if __name__ == '__main__':
    unittest.main()