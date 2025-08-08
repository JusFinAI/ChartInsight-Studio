import yaml
import os

def load_settings():
    """settings.yaml 파일에서 설정을 로드합니다."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(current_dir, 'settings.yaml')
    
    with open(settings_path, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)
    
    # 환경 설정
    environment = settings.get('environment', 'paper')
    env_config = settings['api'][environment]
    
    # API 설정
    host = env_config['host']
    app_key = env_config['app_key']
    secret_key = env_config['secret_key']
    
    print(f"설정 로드 완료: 환경={environment}, 호스트={host}")
    
    return {
        'environment': environment,
        'host': host,
        'app_key': app_key,
        'secret_key': secret_key
    } 