# DataPipeline/src/utils/helpers.py

import json
import os
from pathlib import Path
from typing import List
import logging

import os
import datetime

logger = logging.getLogger(__name__)

def ensure_directory_exists(directory_path):
    """
    디렉토리가 존재하지 않으면 생성합니다.
    
    Args:
        directory_path (str): 생성할 디렉토리 경로
    """
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
        return True
    return False 

def get_today_str(format='%Y%m%d'):
    """오늘 날짜를 지정된 포맷의 문자열로 반환합니다."""
    return datetime.datetime.now().strftime(format) 

def get_target_stocks(limit: int = 30) -> List[str]:
    """
    타겟 종목 리스트를 가져옵니다.
    
    Args:
        limit: 가져올 종목 수 (기본값: 30)
        
    Returns:
        종목 코드 리스트
    """
    stock_codes = []
    
    # 프로젝트 루트에서 JSON 파일 경로 찾기
    current_dir = Path(__file__).parent  # src/utils
    project_root = current_dir.parent.parent  # DataPipeline
    
    kospi_path = project_root / "data" / "kospi_code.json"
    kosdaq_path = project_root / "data" / "kosdaq_code.json"
    
    if not kospi_path.exists():
        logger.error(f"❌ KOSPI 파일을 찾을 수 없습니다: {kospi_path}")
        return []
        
    if not kosdaq_path.exists():
        logger.error(f"❌ KOSDAQ 파일을 찾을 수 없습니다: {kosdaq_path}")
        return []
    
    try:
        # KOSPI 데이터 로드
        with open(kospi_path, 'r', encoding='utf-8') as f:
            kospi_data = json.load(f)
            
        # KOSDAQ 데이터 로드
        with open(kosdaq_path, 'r', encoding='utf-8') as f:
            kosdaq_data = json.load(f)
            
        # 대형주 우선 선택을 위한 필터링
        target_stocks = []
        
        # KOSPI에서 대형주 우선 선택
        for code, info in kospi_data.items():
            if info.get('upSizeName') == '대형주':
                target_stocks.append(code)
                if len(target_stocks) >= limit // 2:  # 절반은 KOSPI 대형주
                    break
        
        # KOSPI 중형주 추가
        for code, info in kospi_data.items():
            if info.get('upSizeName') == '중형주' and code not in target_stocks:
                target_stocks.append(code)
                if len(target_stocks) >= limit * 3 // 4:  # 3/4은 KOSPI
                    break
        
        # KOSDAQ 대형주로 나머지 채우기
        for code, info in kosdaq_data.items():
            if info.get('upSizeName') == '대형주' and code not in target_stocks:
                target_stocks.append(code)
                if len(target_stocks) >= limit:
                    break
        
        # 로그 레벨을 debug로 낮춰서 DagBag 파싱 등 초기화 과정에서 불필요하게
        # INFO 로그가 출력되는 것을 방지합니다. 운영 시 필요하면 debug로 확인하세요.
        logger.debug(f"📊 선택된 타겟 종목 수: {len(target_stocks)}")
        return target_stocks[:limit]
        
    except Exception as e:
        logger.error(f"❌ 타겟 종목 로드 실패: {e}")
        return []

def load_stock_data_from_json_files(kospi_json_path: str, kosdaq_json_path: str) -> list:
    """
    KOSPI 및 KOSDAQ 종목 정보 JSON 파일들을 읽어와 통합된 리스트로 반환합니다.
    리스트의 각 요소는 DB 저장을 위한 딕셔너리 형태입니다.
    """
    all_stocks_list = []

    def _parse_json_file(file_path: str) -> list:
        parsed_list = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f) # 전체 JSON 객체 로드

                for stock_code, info_dict in data.items():
                    # Stock 모델의 컬럼명과 일치하도록 키 이름을 매핑
                    stock_data = {
                        'stock_code': info_dict.get('code'),
                        'stock_name': info_dict.get('name'),
                        'list_count': info_dict.get('listCount'),
                        'audit_info': info_dict.get('auditInfo'),
                        'reg_day': info_dict.get('regDay'),
                        'last_price': info_dict.get('lastPrice'),
                        'state': info_dict.get('state'),
                        'market_code': info_dict.get('marketCode'),
                        'market_name': info_dict.get('marketName'), # getStockCodelist.py에서 추가했던 marketName 필드
                        'industry_name': info_dict.get('upName'),
                        'company_size_name': info_dict.get('upSizeName'),
                        'company_class_name': info_dict.get('companyClassName'), # getStockCodelist.py에서 추가했던 필드
                        'order_warning': info_dict.get('orderWarning'),
                        'nxt_enable': info_dict.get('nxtEnable')
                    }
                    # 필수 값 체크 (예: stock_code, stock_name)
                    if stock_data['stock_code'] and stock_data['stock_name']:
                        parsed_list.append(stock_data)
                    else:
                        print(f"Skipping stock in {os.path.basename(file_path)} due to missing code or name: {info_dict}")
        except FileNotFoundError:
            print(f"Error: File not found at {file_path}")
        except json.JSONDecodeError:
            print(f"Error: Could not decode JSON from {file_path}")
        return parsed_list

    # KOSPI 데이터 로드
    print(f"Loading KOSPI stock data from: {kospi_json_path}")
    all_stocks_list.extend(_parse_json_file(kospi_json_path))

    # KOSDAQ 데이터 로드
    print(f"Loading KOSDAQ stock data from: {kosdaq_json_path}")
    all_stocks_list.extend(_parse_json_file(kosdaq_json_path))

    print(f"Total stocks loaded from JSON files: {len(all_stocks_list)}")
    return all_stocks_list


def get_all_filtered_stocks() -> List[str]:
    """
    Kiwoom API를 통해 전체 종목 정보를 가져온 후, '필터 제로'를 적용하여
    분석 대상이 되는 유효 종목 코드 리스트를 반환합니다.

    Returns:
        List[str]: 필터링된 종목 코드 리스트.
    """
    # 이 함수는 나중에 market_sector_rs_calcurator_all_final.py의
    # get_all_stock_codes와 _apply_filter_and_enrich 로직을 기반으로 구현될 것입니다.
    # 지금은 구조를 잡기 위해 목업 데이터를 반환합니다.

    print("🔥 '필터 제로'를 적용하여 전체 유효 종목 리스트를 가져옵니다... (현재는 목업)")

    # 약 1,300개가 반환된다고 가정하고, 테스트를 위해 10개만 목업으로 생성
    mock_filtered_codes = [str(i).zfill(6) for i in range(10)]

    print(f"✅ 필터링된 종목 수 (목업): {len(mock_filtered_codes)}개")
    return mock_filtered_codes

if __name__ == '__main__':
    # 테스트용 코드
    # 이 스크립트 파일(helpers.py)이 DataPipeline/src/utils/ 에 있다고 가정
    # JSON 파일은 DataPipeline/src/utils/ 에 있다고 가정
    current_dir = os.path.dirname(os.path.abspath(__file__))
    kospi_path = os.path.join(current_dir, 'kospi_code.json')
    kosdaq_path = os.path.join(current_dir, 'kosdaq_code.json')

    if not os.path.exists(kospi_path) or not os.path.exists(kosdaq_path):
        print(f"JSON 파일 ({kospi_path}, {kosdaq_path})을 찾을 수 없습니다. getStockCodelist.py를 먼저 실행하여 생성하세요.")
    else:
        test_stocks = load_stock_data_from_json_files(kospi_path, kosdaq_path)
        if test_stocks:
            print(f"Successfully loaded {len(test_stocks)} stocks. First 3 items:")
            for i, stock in enumerate(test_stocks[:3]):
                print(f"Stock {i+1}: {stock}")
        else:
            print("No stocks were loaded.")