import requests
import time
from datetime import datetime, timedelta
from .config import config


class Auth:
    """키움증권 API 인증 관리 클래스"""
    
    def __init__(self):
        self.token = None
        self.token_expiry = None
        self.host = config.host
        self.app_key = config.app_key
        self.api_secret_key = config.api_secret_key
    
    def get_token(self, force_refresh=False):
        """
        토큰을 얻어옵니다. 만료되었거나 force_refresh가 True면 새로 발급받습니다.
        
        Args:
            force_refresh (bool): 강제로 토큰을 재발급 받을지 여부
            
        Returns:
            str: 액세스 토큰
        """
        # 토큰이 없거나 만료되었거나 강제 갱신이면 토큰 발급
        if (self.token is None or 
            self.token_expiry is None or 
            datetime.now() >= self.token_expiry or 
            force_refresh):
            self._refresh_token()
        
        return self.token
    
    def _refresh_token(self):
        """토큰을 새로 발급받습니다."""
        print("토큰을 새로 발급받습니다")
        
        endpoint = '/oauth2/token'
        url = self.host + endpoint
        
        # 요청 데이터
        params = {
            'grant_type': 'client_credentials',
            'appkey': self.app_key,
            'secretkey': self.api_secret_key
        }
        
        # 헤더 데이터
        headers = {
            'Content-Type': 'application/json;charset=UTF-8'
        }
        
        try:
            # 요청 전송
            response = requests.post(url, headers=headers, json=params)
            response.raise_for_status()
            
            # 응답 처리
            result = response.json()
            self.token = result['token']
            
            # 만료 시간 설정 (현재 시간 + 유효기간)
            # 실제 만료 시간보다 5분 일찍 만료되는 것으로 설정
            expires_in = result.get('expires_in', 86400)  # 기본값: 1일
            self.token_expiry = datetime.now() + timedelta(seconds=expires_in - 300)
            
            print(f"토큰이 발급되었습니다. 만료 시간: {self.token_expiry}")
            
        except requests.exceptions.RequestException as e:
            print(f"토큰 발급 중 오류 발생: {e}")
            raise


# 싱글톤 인스턴스 생성
auth = Auth() 