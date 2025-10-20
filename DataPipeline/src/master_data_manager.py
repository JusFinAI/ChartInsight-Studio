"""
DataPipeline/src/master_data_manager.py

DB 동기화(종목 마스터) 관련 유틸리티
Kiwoom API를 통해 전체 종목 정보를 조회하고 DB와 동기화합니다.
"""
import logging
from typing import List, Dict

from sqlalchemy.dialects.postgresql import insert

from .database import SessionLocal, Stock
from .kiwoom_api.core.client import client as kiwoom_client
from .kiwoom_api.stock_info import get_all_stock_list
from src.utils.filters import apply_filter_zero
from src.utils.logging_kst import configure_kst_logger

logger = configure_kst_logger(__name__)


def _fetch_all_stock_codes_from_api() -> List[Dict]:
    """
    Kiwoom API ka10099를 호출하여 전체 종목 정보를 조회합니다.
    
    Returns:
        List[Dict]: 전체 종목 정보 리스트 (Stock 모델 컬럼명으로 매핑됨)
        
    Note:
        - API 응답 필드명을 Stock 모델 컬럼명으로 변환합니다
        - KOSPI와 KOSDAQ 전체 종목을 조회합니다
    """
    logger.info("Kiwoom API ka10099를 통해 전체 종목 목록을 조회합니다.")
    
    # API 호출하여 원본 데이터 가져오기
    raw_stocks = get_all_stock_list(kiwoom_client)
    
    logger.info(f"API로부터 총 {len(raw_stocks)}개 종목을 조회했습니다.")
    
    # API 응답 필드명 → Stock 모델 컬럼명 매핑
    mapped_stocks = []
    for raw_stock in raw_stocks:
        mapped_stock = _map_api_response_to_stock_model(raw_stock)
        mapped_stocks.append(mapped_stock)
    
    logger.info(f"필드 매핑 완료: {len(mapped_stocks)}개 종목")
    return mapped_stocks


def _map_api_response_to_stock_model(api_data: Dict) -> Dict:
    """
    ka10099 API 응답 데이터를 Stock 모델 컬럼명으로 매핑합니다.
    
    Args:
        api_data (Dict): API 원본 응답 데이터
        
    Returns:
        Dict: Stock 모델 컬럼명으로 매핑된 데이터
        
    Example:
        API 응답:
        {
            'code': '005930',
            'name': '삼성전자',
            'listCount': '5969782550',
            'marketName': 'KOSPI',
            ...
        }
        
        매핑 결과:
        {
            'code': '005930',           # filter.py가 사용
            'name': '삼성전자',          # filter.py가 사용
            'stock_name': '삼성전자',     # Stock 모델 컬럼
            'list_count': '5969782550',
            'marketName': 'KOSPI',      # filter.py가 사용
            'market_name': 'KOSPI',     # Stock 모델 컬럼
            ...
        }
    """
    return {
        # filter.py가 사용하는 필드 (원본 유지)
        'code': api_data.get('code'),
        'name': api_data.get('name'),
        'marketName': api_data.get('marketName'),
        'marketCode': api_data.get('marketCode'),
        'listCount': api_data.get('listCount'),
        'auditInfo': api_data.get('auditInfo'),
        'state': api_data.get('state'),
        
        # Stock 모델 컬럼명 (추가 매핑)
        'stock_name': api_data.get('name'),
        'market_name': api_data.get('marketName'),
        'list_count': api_data.get('listCount'),
        'audit_info': api_data.get('auditInfo'),
        'reg_day': api_data.get('regDay'),
        'last_price': api_data.get('lastPrice'),
        'market_code': api_data.get('marketCode'),
        'industry_name': api_data.get('upName'),
        'company_size_name': api_data.get('upSizeName'),
        'company_class_name': api_data.get('companyClassName'),
        'order_warning': api_data.get('orderWarning'),
        'nxt_enable': api_data.get('nxtEnable'),
    }


def sync_stock_master_data() -> List[Dict]:
    """
    API(또는 목업)로부터 종목 정보를 가져와 반환합니다.

    Returns:
        List[Dict]: API로부터 조회된 모든 종목 정보 리스트
    """
    logger.info("종목 마스터 데이터 동기화 작업을 시작합니다.")
    latest_stocks = _fetch_all_stock_codes_from_api()
    return latest_stocks


def get_managed_stocks_from_db(db_session) -> List[str]:
    """
    주입된 DB 세션을 사용하여 is_active=True인 관리 종목의 stock_code 리스트를 반환합니다.
    """
    print("--- DEBUGGING: INSIDE get_managed_stocks_from_db ---")
    try:
        # --- START: 디버깅 코드 v4 ---
        print("DEBUG PRINT: About to query ALL Stock codes and their is_active status...")
        all_stocks_with_active_status = db_session.query(Stock.stock_code, Stock.is_active).all()
        print(f"DEBUG PRINT: Found {len(all_stocks_with_active_status)} total stocks.")

        # is_active 값들의 분포를 확인 (최대 10개 샘플)
        sample_active_values = [s.is_active for s in all_stocks_with_active_status[:10]]
        print(f"DEBUG PRINT: Sample is_active values: {sample_active_values}")

        # is_active=True인 종목이 몇 개인지 직접 세어보기
        count_true_active = sum(1 for s in all_stocks_with_active_status if s.is_active == True)
        print(f"DEBUG PRINT: Count of stocks where is_active == True: {count_true_active}")
        # --- END: 디버깅 코드 v4 ---

        print("DEBUG PRINT: About to query Stock table with filter is_active=True...")
        query = db_session.query(Stock.stock_code).filter(Stock.is_active == True)
        rows = query.all()
        print(f"DEBUG PRINT: Query finished. Found {len(rows)} rows with is_active=True.")

        codes = [r.stock_code for r in rows]
        print(f"DEBUG PRINT: Returning {len(codes)} stock codes.")
        return codes
    except Exception as e:
        print(f"DEBUG PRINT: Exception in get_managed_stocks_from_db: {e}")
        return []


def sync_stock_master_to_db(db_session) -> dict:
    """
    API로부터 최신 종목 정보를 가져와 DB의 `Stock` 테이블과 차이를 동기화합니다.

    Args:
        db_session: SQLAlchemy session (주입)

    Returns:
        dict: 요약 통계 (new_count, delisted_count, updated_count)
    """
    logger.info("외부 API로부터 종목 정보를 조회하여 DB와 동기화합니다.")

    api_all = sync_stock_master_data()
    # NOTE: 필터 제로 호출은 동기화 단계에서 제거합니다. 분석 대상 필터링은 DAG 실행 중 별도 Task에서 수행됩니다.

    api_codes = {s.get('code') for s in api_all if s.get('code')}

    db_stocks = db_session.query(Stock).all()
    db_map = {s.stock_code: s for s in db_stocks}
    db_codes = set(db_map.keys())

    new_codes = api_codes - db_codes
    delisted_codes = db_codes - api_codes
    existing_codes = api_codes & db_codes

    new_count = 0
    delisted_count = 0
    updated_count = 0

    # 4a. 신규 종목 추가
    if new_codes:
        for code in new_codes:
            src = next((s for s in api_all if s.get('code') == code), None)
            if not src:
                continue
            stock_obj = Stock(
                stock_code=code,
                stock_name=src.get('name') or src.get('stock_name') or None,
                market_name=src.get('marketName') or src.get('market_name') or None,
                is_active=True,
                backfill_needed=True,
            )
            db_session.add(stock_obj)
            new_count += 1

    # 4b. 상장폐지/비활성 종목 처리
    if delisted_codes:
        for code in delisted_codes:
            s = db_map.get(code)
            if s and s.is_active:
                s.is_active = False
                delisted_count += 1

    # 4c. 기존 종목 정보 업데이트 및 재활성화
    if existing_codes:
        for code in existing_codes:
            src = next((s for s in api_all if s.get('code') == code), None)
            db_obj = db_map.get(code)
            if not src or not db_obj:
                continue
            changed = False
            new_name = src.get('name') or src.get('stock_name')
            new_market = src.get('marketName') or src.get('market_name')
            if new_name and new_name != db_obj.stock_name:
                db_obj.stock_name = new_name
                changed = True
            if new_market and new_market != db_obj.market_name:
                db_obj.market_name = new_market
                changed = True
            # 재활성화: DB에서 비활성화되어 있었으나 다시 API에 나타난 경우
            if not db_obj.is_active:
                db_obj.is_active = True
                db_obj.backfill_needed = True
                changed = True
            if changed:
                updated_count += 1

    db_session.commit()
    summary = {"new_count": new_count, "delisted_count": delisted_count, "updated_count": updated_count}
    logger.info(f"동기화 완료: {summary}")

    # 후속 Task에 전달할, 현재 DB에 저장된 최종 활성 종목 리스트를 조회하여 반환
    logger.info("DB에서 최종 활성 종목 리스트를 조회하여 반환합니다.")
    active_stocks = db_session.query(Stock.stock_code).filter(Stock.is_active == True).all()
    return [code for code, in active_stocks]


def update_analysis_target_flags(db_session, stock_codes: List[str]) -> int:
    """
    주어진 stock_codes 리스트에 해당하는 종목들을 대상으로 '필터 제로'를 적용하여,
    is_analysis_target 플래그를 업데이트하고, 변경된 레코드의 개수를 반환합니다.
    """
    logger.info(f"총 {len(stock_codes)}개 종목에 대해 is_analysis_target 플래그 업데이트를 시작합니다.")

    try:
        # 1. 주어진 stock_codes에 해당하는 Stock 객체들을 조회
        target_stocks = db_session.query(Stock).filter(Stock.stock_code.in_(stock_codes)).all()
        if not target_stocks:
            logger.warning("플래그를 업데이트할 종목이 DB에 없습니다.")
            return 0

        # 2. 필터링을 위해 필요한 최소 정보만 메모리에 로드
        stock_info_for_filter = [{
            'code': s.stock_code, 'name': s.stock_name, 'state': s.state,
            'auditInfo': s.audit_info, 'lastPrice': s.last_price, 'listCount': s.list_count
        } for s in target_stocks]

        # 3. '필터 제로' 적용
        filtered_stocks_info = apply_filter_zero(stock_info_for_filter)
        analysis_target_codes = {s['code'] for s in filtered_stocks_info}

        logger.info(f"{len(target_stocks)}개 종목 중 {len(analysis_target_codes)}개가 분석 대상으로 선정되었습니다.")

        # 4. 플래그 업데이트
        update_count = 0
        for stock in target_stocks:
            should_be_target = stock.stock_code in analysis_target_codes
            if stock.is_analysis_target != should_be_target:
                stock.is_analysis_target = should_be_target
                update_count += 1

        if update_count > 0:
            logger.info(f"{update_count}개 종목의 플래그가 변경되었습니다. DB에 커밋합니다.")
            db_session.commit()
        else:
            logger.info("is_analysis_target 플래그에 변경 사항이 없습니다.")

        return update_count

    except Exception as e:
        logger.error(f"is_analysis_target 플래그 업데이트 중 오류 발생: {e}", exc_info=True)
        try:
            db_session.rollback()
        except Exception:
            logger.exception("롤백 중 오류 발생")
        raise