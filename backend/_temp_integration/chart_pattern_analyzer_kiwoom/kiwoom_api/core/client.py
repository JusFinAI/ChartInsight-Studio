import requests
import json
from .auth import auth
from .config import config


class KiwoomClient:
    """키움증권 API 호출 클라이언트"""
    
    def __init__(self):
        self.host = config.host
    
    def request(self, endpoint, api_id, data, cont_yn='N', next_key=''):
        """
        API 요청을 보냅니다.
        
        Args:
            endpoint (str): API 엔드포인트
            api_id (str): API ID (예: ka10081)
            data (dict): 요청 데이터
            cont_yn (str): 연속조회 여부 ('Y' 또는 'N')
            next_key (str): 연속조회 키
            
        Returns:
            dict: 응답 데이터
        """
        print(f"API 요청: {api_id}, 데이터: {data}")
        
        # URL 구성
        url = self.host + endpoint
        
        # 토큰 가져오기
        token = auth.get_token()
        
        # 헤더 구성
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'cont-yn': cont_yn,
            'next-key': next_key,
            'api-id': api_id,
        }
        
        try:
            # 요청 전송
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            # 응답 헤더 로깅
            important_headers = {
                key: response.headers.get(key) 
                for key in ['next-key', 'cont-yn', 'api-id'] 
                if response.headers.get(key)
            }
            
            if important_headers:
                print(f"응답 헤더: {json.dumps(important_headers)}")
            
            # 응답 결과 반환
            result = {
                'data': response.json(),
                'headers': {
                    'next_key': response.headers.get('next-key', ''),
                    'cont_yn': response.headers.get('cont-yn', 'N'),
                    'api_id': response.headers.get('api-id', '')
                }
            }
            
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"API 요청 중 오류 발생: {e}")
            raise


# 싱글톤 인스턴스 생성
client = KiwoomClient() 