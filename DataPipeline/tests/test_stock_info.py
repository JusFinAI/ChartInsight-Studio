"""
DataPipeline/tests/test_stock_info.py

stock_info.py 모듈의 단위 테스트
"""
import unittest
from unittest.mock import Mock, patch, MagicMock

from src.kiwoom_api.stock_info import get_all_stock_list, _call_ka10099_api


class TestStockInfo(unittest.TestCase):
    """get_all_stock_list 함수 테스트"""
    
    def setUp(self):
        """테스트 준비"""
        self.mock_client = Mock()
    
    def test_get_all_stock_list_single_page(self):
        """단일 페이지 조회 테스트"""
        # Mock API 응답 (연속 조회 없음)
        mock_response = {
            'data': {
                'list': [
                    {'code': '005930', 'name': '삼성전자', 'marketName': 'KOSPI'},
                    {'code': '000660', 'name': 'SK하이닉스', 'marketName': 'KOSPI'}
                ],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'N',  # 더 이상 페이지 없음
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        self.mock_client.request = Mock(return_value=mock_response)
        
        # 실행
        result = get_all_stock_list(self.mock_client)
        
        # 검증
        self.assertEqual(len(result), 4)  # KOSPI 2개 + KOSDAQ 2개 (각각 동일한 mock 응답)
        
        # KOSPI 조회 확인
        self.mock_client.request.assert_any_call(
            '/api/dostk/stkinfo',
            'ka10099',
            {},
            'N',
            ''
        )
        
        # KOSDAQ 조회 확인
        self.mock_client.request.assert_any_call(
            '/api/dostk/stkinfo',
            'ka10099',
            {},
            'N',
            ''
        )
    
    def test_get_all_stock_list_multiple_pages(self):
        """연속 조회 (페이지네이션) 테스트"""
        # Mock API 응답 시나리오
        # 페이지 1: cont_yn='Y' (계속 조회)
        page1_response = {
            'data': {
                'list': [
                    {'code': '005930', 'name': '삼성전자', 'marketName': 'KOSPI'}
                ],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'Y',
                'next_key': 'NEXT_KEY_1',
                'api_id': 'ka10099'
            }
        }
        
        # 페이지 2: cont_yn='N' (마지막 페이지)
        page2_response = {
            'data': {
                'list': [
                    {'code': '000660', 'name': 'SK하이닉스', 'marketName': 'KOSPI'}
                ],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'N',
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        # Mock 설정: 호출 순서에 따라 다른 응답 반환
        self.mock_client.request = Mock(side_effect=[
            page1_response, page2_response,  # KOSPI: 페이지 1, 2
            page1_response, page2_response   # KOSDAQ: 페이지 1, 2
        ])
        
        # 실행
        result = get_all_stock_list(self.mock_client)
        
        # 검증
        self.assertEqual(len(result), 4)  # (1+1) KOSPI + (1+1) KOSDAQ
        self.assertEqual(self.mock_client.request.call_count, 4)
        
        # 두 번째 호출이 next_key를 사용했는지 확인
        second_call_args = self.mock_client.request.call_args_list[1]
        self.assertEqual(second_call_args[0][3], 'Y')  # cont_yn
        self.assertEqual(second_call_args[0][4], 'NEXT_KEY_1')  # next_key
    
    def test_get_all_stock_list_api_error(self):
        """API 오류 처리 테스트"""
        # Mock API 응답 (오류)
        error_response = {
            'data': {
                'list': [],
                'return_code': '99999',
                'return_msg': 'API 오류'
            },
            'headers': {
                'cont_yn': 'N',
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        self.mock_client.request = Mock(return_value=error_response)
        
        # 실행
        result = get_all_stock_list(self.mock_client)
        
        # 검증: 오류 발생 시 빈 리스트 반환
        self.assertEqual(len(result), 0)
    
    def test_get_all_stock_list_exception_handling(self):
        """예외 처리 테스트"""
        # Mock: 예외 발생
        self.mock_client.request = Mock(side_effect=Exception("Network error"))
        
        # 실행
        result = get_all_stock_list(self.mock_client)
        
        # 검증: 예외 발생 시 빈 리스트 반환
        self.assertEqual(len(result), 0)
    
    def test_call_ka10099_api_success(self):
        """_call_ka10099_api 성공 케이스 테스트"""
        # Mock API 응답
        mock_response = {
            'data': {
                'list': [{'code': '005930'}],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'Y',
                'next_key': 'KEY123',
                'api_id': 'ka10099'
            }
        }
        
        self.mock_client.request = Mock(return_value=mock_response)
        
        # 실행
        result = _call_ka10099_api(self.mock_client, '0', 'N', '')
        
        # 검증
        self.assertIsNotNone(result)
        self.assertEqual(result['cont_yn'], 'Y')
        self.assertEqual(result['next_key'], 'KEY123')
        self.assertEqual(len(result['list']), 1)
    
    def test_call_ka10099_api_failure(self):
        """_call_ka10099_api 실패 케이스 테스트"""
        # Mock API 응답 (return_code 오류)
        mock_response = {
            'data': {
                'list': [],
                'return_code': '99999',
                'return_msg': 'API 오류'
            },
            'headers': {
                'cont_yn': 'N',
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        self.mock_client.request = Mock(return_value=mock_response)
        
        # 실행
        result = _call_ka10099_api(self.mock_client, '0', 'N', '')
        
        # 검증: 오류 시 None 반환
        self.assertIsNone(result)
    
    def test_market_name_injection(self):
        """시장 정보 자동 주입 테스트"""
        # Mock API 응답 (marketName 없음)
        kospi_response = {
            'data': {
                'list': [
                    {'code': '005930', 'name': '삼성전자'}  # marketName 없음
                ],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'N',
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        kosdaq_response = {
            'data': {
                'list': [
                    {'code': '247540', 'name': '에코프로'}  # marketName 없음
                ],
                'return_code': '00000',
                'return_msg': '정상'
            },
            'headers': {
                'cont_yn': 'N',
                'next_key': '',
                'api_id': 'ka10099'
            }
        }
        
        # KOSPI 응답 후 KOSDAQ 응답
        self.mock_client.request = Mock(side_effect=[kospi_response, kosdaq_response])
        
        # 실행
        result = get_all_stock_list(self.mock_client)
        
        # 검증: marketName이 자동으로 추가되었는지 확인
        kospi_stocks = [s for s in result if s.get('marketName') == 'KOSPI']
        kosdaq_stocks = [s for s in result if s.get('marketName') == 'KOSDAQ']
        
        self.assertEqual(len(kospi_stocks), 1)
        self.assertEqual(len(kosdaq_stocks), 1)
        self.assertEqual(kospi_stocks[0]['code'], '005930')
        self.assertEqual(kosdaq_stocks[0]['code'], '247540')


if __name__ == '__main__':
    unittest.main()

