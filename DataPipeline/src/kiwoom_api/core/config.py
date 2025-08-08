import os
import yaml
from pathlib import Path


class Config:
    """설정 관리 클래스"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self.base_dir = Path(__file__).parent.parent
        self.config_dir = self.base_dir / 'config'
        self.output_dir = self.base_dir / 'out_csv'
        
        # 설정 파일 로드
        self.load_settings()
        
        self._initialized = True
    
    def load_settings(self):
        """설정 파일을 로드합니다."""
        settings_path = self.config_dir / 'settings.yaml'
        
        with open(settings_path, 'r', encoding='utf-8') as f:
            self.settings = yaml.safe_load(f)
        
        # 환경 설정
        self.environment = self.settings.get('environment', 'paper')
        env_config = self.settings['api'][self.environment]
        
        # API 설정
        self.host = env_config['host']
        self.websocket_url = env_config['websocket']
        self.app_key = env_config['app_key']
        self.api_secret_key = env_config['secret_key']
        
        print(f"설정 로드 완료: 환경={self.environment}, 호스트={self.host}")


# 싱글톤 인스턴스 생성
config = Config() 