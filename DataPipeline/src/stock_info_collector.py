# DataPipeline/src/stock_info_collector.py

import os
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

# 현재 파일의 위치를 기준으로 src 폴더를 찾고, 그 안의 모듈을 임포트
# 이 스크립트가 DataPipeline/src/ 에 있다고 가정
from .database import SessionLocal, Stock, init_db # 같은 src 폴더 내 database.py
from .utils.common_helpers import load_stock_data_from_json_files # src/utils/helpers.py
    

def bulk_upsert_stocks_to_db(db: Session, stocks_data_list: list):
    """
    제공된 종목 데이터 리스트를 stocks 테이블에 UPSERT 합니다.
    """
    if not stocks_data_list:
        print("No stock data provided to upsert.")
        return

    # Stock 모델 객체로 변환 (데이터 유효성 검사 포함)
    records_to_insert = []
    for stock_data in stocks_data_list:
        # .get()을 사용하여 안전하게 키에 접근하고, 없는 경우 None 처리
        # String 타입이 아닌 경우 형 변환 필요 시 여기서 수행
        record = {
            "stock_code": stock_data.get('stock_code'),
            "stock_name": stock_data.get('stock_name'),
            "list_count": stock_data.get('list_count'),
            "audit_info": stock_data.get('audit_info'),
            "reg_day": stock_data.get('reg_day'),
            "last_price": stock_data.get('last_price'),
            "state": stock_data.get('state'),
            "market_code": stock_data.get('market_code'),
            "market_name": stock_data.get('market_name'),
            "industry_name": stock_data.get('industry_name'),
            "company_size_name": stock_data.get('company_size_name'),
            "company_class_name": stock_data.get('company_class_name'),
            "order_warning": stock_data.get('order_warning'),
            "nxt_enable": stock_data.get('nxt_enable')
        }
        # 필수 값 체크
        if record["stock_code"] and record["stock_name"]:
            records_to_insert.append(record)

    if not records_to_insert:
        print("No valid stock records to map for upsertion.")
        return

    print(f"Attempting to upsert {len(records_to_insert)} stock records...")

    # UPSERT 로직 (PostgreSQL 용)
    stmt = insert(Stock).values(records_to_insert)

    # 업데이트할 컬럼들을 명시적으로 지정 (PK인 stock_code는 제외)
    update_columns = {
        col.name: getattr(stmt.excluded, col.name)
        for col in Stock.__table__.columns
        if col.name != 'stock_code' # PK는 업데이트 대상에서 제외
    }

    stmt = stmt.on_conflict_do_update(
        index_elements=['stock_code'], # 충돌 감지 기준 (PK)
        set_=update_columns # 충돌 시 업데이트할 값들
    )

    try:
        db.execute(stmt)
        db.commit()
        print(f"{len(records_to_insert)} stock records successfully upserted to the database.")
    except Exception as e:
        db.rollback()
        print(f"Error during bulk upsert of stocks: {e}")
        print("Please check database connection, table schema, and data.")

def run_stock_info_collection():
    print("Starting stock information collection and database update...")
    # 1. DB 테이블 초기화 (Stock 모델 스키마에 맞게 테이블이 존재하는지 확인/생성)
    # 이 작업은 한 번만 수행하거나, 스키마 변경 시 수행
    # init_db() # database.py에 정의된 함수

    # 2. JSON 파일 경로 설정
    # 이 스크립트(stock_info_collector.py)가 DataPipeline/src/ 에 있다고 가정
    # JSON 파일은 DataPipeline/data/ 에 있다고 가정
    base_dir = os.path.dirname(os.path.abspath(__file__)) # 현재 파일이 있는 src 디렉토리
    project_root = os.path.dirname(base_dir) # src의 부모 디렉토리 (DataPipeline)
    data_dir = os.path.join(project_root, 'data')
    kospi_json_path = os.path.join(data_dir, 'kospi_code.json')
    kosdaq_json_path = os.path.join(data_dir, 'kosdaq_code.json')

    if not os.path.exists(kospi_json_path) or not os.path.exists(kosdaq_json_path):
        print(f"KOSPI/KOSDAQ JSON 파일({kospi_json_path}, {kosdaq_json_path})을 찾을 수 없습니다.")
        print("`getStockCodelist.py`를 실행하여 먼저 JSON 파일을 생성해야 합니다.")
        return

    # 3. JSON 파일에서 모든 종목 데이터 로드
    all_stocks_data = load_stock_data_from_json_files(kospi_json_path, kosdaq_json_path)

    if not all_stocks_data:
        print("No stock data loaded from JSON files. Exiting.")
        return

    # 4. DB 세션 생성 및 데이터 저장
    db_session = SessionLocal()
    try:
        bulk_upsert_stocks_to_db(db_session, all_stocks_data)
    finally:
        db_session.close()
        print("Database session closed.")
    print("Stock information collection process finished.")

if __name__ == "__main__":
    # 이 스크립트를 직접 실행하여 DB에 전 종목 정보를 저장 (초기 1회 또는 필요시)
    run_stock_info_collection()