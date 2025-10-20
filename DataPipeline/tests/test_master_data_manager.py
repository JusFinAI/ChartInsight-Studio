import unittest
from unittest.mock import patch

from DataPipeline.src.master_data_manager import get_managed_stocks_from_db, sync_stock_master_to_db
from DataPipeline.src.database import Base, engine, Stock, SessionLocal


class TestMasterDataManager(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal(bind=engine)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_get_managed_stocks_from_db(self):
        # Arrange: insert 2 active and 1 inactive stocks
        s1 = Stock(stock_code='AAA', stock_name='AAA', is_active=True, backfill_needed=False)
        s2 = Stock(stock_code='BBB', stock_name='BBB', is_active=True, backfill_needed=False)
        s3 = Stock(stock_code='CCC', stock_name='CCC', is_active=False, backfill_needed=False)
        self.db.add_all([s1, s2, s3])
        self.db.commit()

        # Act
        codes = get_managed_stocks_from_db(self.db)

        # Assert
        self.assertEqual(len(codes), 2)
        self.assertCountEqual(codes, ['AAA', 'BBB'])

    def test_sync_stock_master_to_db_new_stocks(self):
        # Arrange: mock API to return new stocks, DB is empty
        mock_api_filtered = [
            {'code': 'NEW1', 'name': 'New Stock 1', 'marketName': 'KOSPI'},
            {'code': 'NEW2', 'name': 'New Stock 2', 'marketName': 'KOSDAQ'}
        ]
        with patch('DataPipeline.src.master_data_manager.sync_stock_master_data') as mock_sync, \
             patch('DataPipeline.src.master_data_manager.apply_filter_zero') as mock_filter:
            mock_sync.return_value = []  # Doesn't matter since we mock filtered
            mock_filter.return_value = mock_api_filtered

            # Act
            result = sync_stock_master_to_db(self.db)

            # Assert
            self.assertEqual(result['new_count'], 2)
            self.assertEqual(result['delisted_count'], 0)
            self.assertEqual(result['updated_count'], 0)

            db_stocks = self.db.query(Stock).all()
            self.assertEqual(len(db_stocks), 2)
            codes = {s.stock_code for s in db_stocks}
            self.assertEqual(codes, {'NEW1', 'NEW2'})
            for s in db_stocks:
                self.assertTrue(s.is_active)
                self.assertTrue(s.backfill_needed)

    def test_sync_stock_master_to_db_delisted(self):
        # Arrange: DB has active stocks, API returns none of them
        s1 = Stock(stock_code='DEL1', stock_name='Delisted 1', is_active=True)
        s2 = Stock(stock_code='DEL2', stock_name='Delisted 2', is_active=True)
        self.db.add_all([s1, s2])
        self.db.commit()

        with patch('DataPipeline.src.master_data_manager.sync_stock_master_data') as mock_sync, \
             patch('DataPipeline.src.master_data_manager.apply_filter_zero') as mock_filter:
            mock_sync.return_value = []
            mock_filter.return_value = []

            # Act
            result = sync_stock_master_to_db(self.db)

            # Assert
            self.assertEqual(result['new_count'], 0)
            self.assertEqual(result['delisted_count'], 2)
            self.assertEqual(result['updated_count'], 0)

            db_stocks = self.db.query(Stock).all()
            self.assertEqual(len(db_stocks), 2)
            for s in db_stocks:
                self.assertFalse(s.is_active)

    def test_sync_stock_master_to_db_reactivate_and_update(self):
        # Arrange: DB has inactive stock and one with outdated name
        s1 = Stock(stock_code='REACT1', stock_name='Old Name', market_name='OLD', is_active=False)
        s2 = Stock(stock_code='UPD2', stock_name='Outdated', market_name='OLD', is_active=True)
        self.db.add_all([s1, s2])
        self.db.commit()

        mock_api_filtered = [
            {'code': 'REACT1', 'name': 'Reactivated', 'marketName': 'KOSPI'},
            {'code': 'UPD2', 'name': 'Updated Name', 'marketName': 'KOSDAQ'}
        ]

        with patch('DataPipeline.src.master_data_manager.sync_stock_master_data') as mock_sync, \
             patch('DataPipeline.src.master_data_manager.apply_filter_zero') as mock_filter:
            mock_sync.return_value = []
            mock_filter.return_value = mock_api_filtered

            # Act
            result = sync_stock_master_to_db(self.db)

            # Assert
            self.assertEqual(result['new_count'], 0)
            self.assertEqual(result['delisted_count'], 0)
            self.assertEqual(result['updated_count'], 2)  # reactivation and update both count as updated

            db_stocks = self.db.query(Stock).all()
            react = next(s for s in db_stocks if s.stock_code == 'REACT1')
            self.assertTrue(react.is_active)
            self.assertTrue(react.backfill_needed)
            self.assertEqual(react.stock_name, 'Reactivated')
            self.assertEqual(react.market_name, 'KOSPI')

            upd = next(s for s in db_stocks if s.stock_code == 'UPD2')
            self.assertEqual(upd.stock_name, 'Updated Name')
            self.assertEqual(upd.market_name, 'KOSDAQ')


if __name__ == '__main__':
    unittest.main()


