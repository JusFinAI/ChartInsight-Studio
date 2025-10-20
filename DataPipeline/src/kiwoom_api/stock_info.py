"""
DataPipeline/src/kiwoom_api/stock_info.py

Kiwoom API를 통한 종목 정보 조회 기능을 제공합니다.
"""
import time
import logging
from typing import List, Dict, Optional

from .core.client import KiwoomClient

logger = logging.getLogger(__name__)


def get_all_stock_list(client: KiwoomClient) -> List[Dict]:
    """
    Kiwoom API ka10099를 호출하여 KOSPI와 KOSDAQ 전체 종목 리스트를 조회합니다.
    연속 조회를 통해 모든 페이지의 데이터를 가져옵니다.
    
    Args:
        client (KiwoomClient): Kiwoom API 클라이언트 인스턴스
        
    Returns:
        List[Dict]: 전체 종목 정보 리스트
        
    Example:
        >>> from .core.client import client
        >>> stocks = get_all_stock_list(client)
        >>> print(f"총 {len(stocks)}개 종목 조회")
    """
    logger.info("Kiwoom API를 통한 전체 종목 리스트 조회를 시작합니다.")
    
    all_stocks = []
    
    # KOSPI(0)와 KOSDAQ(10) 순서로 조회
    for market_tp in ['0', '10']:
        cont_yn = 'N'
        next_key = ''
        page = 1
        market_name = 'KOSPI' if market_tp == '0' else 'KOSDAQ'
        
        logger.info(f"--- {market_name} 종목 조회 시작 ---")
        
        while True:
            try:
                # API 호출
                response = _call_ka10099_api(client, market_tp, cont_yn, next_key)
                
                if response is None:
                    logger.error(f"{market_name} API 호출 실패. 조회를 중단합니다.")
                    break
                
                # 데이터 추출
                stock_list = response.get('list', [])
                
                if not stock_list:
                    logger.warning(f"{market_name} 페이지 {page}: 데이터가 없습니다.")
                    break
                
                # 시장 정보 추가 (API 응답에 없을 경우 대비)
                for stock in stock_list:
                    if 'marketName' not in stock or not stock['marketName']:
                        stock['marketName'] = market_name
                    if 'marketCode' not in stock or not stock['marketCode']:
                        stock['marketCode'] = market_tp
                
                all_stocks.extend(stock_list)
                
                # 연속 조회 정보 확인
                cont_yn = response.get('cont_yn', 'N')
                next_key = response.get('next_key', '')
                
                logger.info(f"페이지 {page}: {market_name} {len(stock_list)}개 조회 (전체: {len(all_stocks)}개)")
                
                # 연속 조회 여부 확인
                if cont_yn != 'Y':
                    logger.info(f"{market_name} 조회 완료. 마지막 페이지: {page}")
                    break
                
                page += 1
                
                # API 부하 방지를 위한 대기
                time.sleep(0.3)
                
            except Exception as e:
                logger.error(f"{market_name} 페이지 {page} 조회 중 오류 발생: {e}")
                break
        
        logger.info(f"--- {market_name} 조회 완료: 총 {sum(1 for s in all_stocks if s.get('marketName') == market_name)}개 ---")
    
    logger.info(f"전체 종목 조회 완료: 총 {len(all_stocks)}개 (KOSPI + KOSDAQ)")
    return all_stocks


def _call_ka10099_api(
    client: KiwoomClient, 
    market_tp: str, 
    cont_yn: str, 
    next_key: str
) -> Optional[Dict]:
    """
    ka10099 API를 호출하는 저수준 헬퍼 함수.
    
    Args:
        client (KiwoomClient): Kiwoom API 클라이언트
        market_tp (str): 시장 구분 ('0': KOSPI, '10': KOSDAQ)
        cont_yn (str): 연속 조회 여부 ('Y' 또는 'N')
        next_key (str): 연속 조회 키
        
    Returns:
        Optional[Dict]: API 응답 데이터 (실패 시 None)
        
    Response Format:
        {
            'list': [...],           # 종목 리스트
            'cont_yn': 'Y' or 'N',   # 연속 조회 여부
            'next_key': '...',       # 연속 조회 키
            'return_code': '00000',  # 응답 코드
            'return_msg': '정상'      # 응답 메시지
        }
    """
    endpoint = '/api/dostk/stkinfo'
    api_id = 'ka10099'
    
    # request body - mrkt_tp는 필수 파라미터!
    data = {'mrkt_tp': market_tp}
    
    try:
        # KiwoomClient.request() 호출
        result = client.request(endpoint, api_id, data, cont_yn, next_key)
        
        # 응답 구조 분해
        response_data = result.get('data', {})
        response_headers = result.get('headers', {})
        
        # return_code 확인 (정수 또는 문자열 모두 허용)
        return_code = response_data.get('return_code', '')
        return_msg = response_data.get('return_msg', '')
        
        # return_code가 0, '0', 또는 '00000'이면 정상
        # API가 정수 또는 문자열로 반환할 수 있음
        if return_code not in [0, '0', '00000']:
            logger.error(f"API 응답 오류: {return_code} - {return_msg}")
            return None
        
        # getStockCodelist.py 형식으로 변환하여 반환
        return {
            'list': response_data.get('list', []),
            'cont_yn': response_headers.get('cont_yn', 'N'),
            'next_key': response_headers.get('next_key', ''),
            'return_code': return_code,
            'return_msg': return_msg
        }
        
    except Exception as e:
        logger.error(f"ka10099 API 호출 중 예외 발생: {e}")
        return None

