"""
로깅 시스템 중앙 설정 모듈

이 모듈은 ChartInsight 백엔드의 모든 로깅을 중앙에서 관리합니다.
초보 개발자도 쉽게 이해하고 유지보수할 수 있도록 단순하게 설계되었습니다.

주요 기능:
1. 중앙 집중식 로깅 설정 (main.py에서 한 번만 호출)
2. 자동 로그 파일 로테이션 (크기 기반)
3. 표준 예외 처리 지원

사용법:
- 앱 시작 시: setup_logging()을 한 번만 호출
- 각 모듈에서: logger = logging.getLogger(__name__)로 사용
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from datetime import datetime

# 프로젝트 루트 기준 로그 디렉토리 경로
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_LOGS_DIR = PROJECT_ROOT / "logs"


class SmartFormatter(logging.Formatter):
    """
    스마트 포맷터: 로그의 종류에 따라 다른 포맷을 적용합니다.
    
    - 알고리즘 로직 로그 (analysis 모듈): 실행 시각 제거, 모듈명만 표시
    - 시스템 로그 (main, routers 등): 실행 시각 포함
    
    이렇게 하면 알고리즘 디버깅 시 캔들 날짜 흐름에 집중할 수 있고,
    시스템 디버깅 시 실행 타이밍을 추적할 수 있습니다.
    """
    
    def __init__(self):
        # 기본 포맷 (시스템 로그용)
        self.default_fmt = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        # 알고리즘 로직 로그용 포맷 (실행 시각 제외)
        self.algorithm_fmt = logging.Formatter(
            '%(name)s - %(levelname)s - %(message)s'
        )
    
    def format(self, record):
        """
        로그 레코드의 로거 이름을 보고 적절한 포맷을 선택합니다.
        
        알고리즘 관련 모듈:
        - app.analysis.*  (분석 엔진, 추세 감지, 패턴 감지 등)
        
        시스템 관련 모듈:
        - app.main, app.routers.*, app.utils.*, root 등
        """
        # 알고리즘 로직 로그인 경우 (analysis 모듈)
        if 'app.analysis' in record.name:
            return self.algorithm_fmt.format(record)
        else:
            # 시스템 로그인 경우 (API 요청, 초기화 등)
            return self.default_fmt.format(record)


def setup_logging(
    logs_dir: str = None,
    log_level: str = "INFO",
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
):
    """
    애플리케이션 전체의 로깅을 중앙에서 설정합니다.
    
    이 함수는 main.py에서 앱 시작 시 **딱 한 번만** 호출되어야 합니다.
    설정 후 모든 모듈에서 logging.getLogger(__name__)로 로거를 사용하면 됩니다.
    
    Args:
        logs_dir (str, optional): 로그 파일을 저장할 디렉토리 경로. 
            기본값은 프로젝트 루트의 'logs' 폴더입니다.
        log_level (str, optional): 로그 레벨 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL").
            기본값은 "INFO"입니다.
        max_bytes (int, optional): 로그 파일 최대 크기 (바이트 단위).
            이 크기를 초과하면 자동으로 새 파일로 로테이션됩니다. 기본값은 10MB입니다.
        backup_count (int, optional): 보관할 이전 로그 파일 개수.
            기본값은 5개입니다. (예: app.log, app.log.1, app.log.2, ...)
    
    Returns:
        None
    
    예시:
        # main.py에서
        from app.utils.logger_config import setup_logging
        
        setup_logging(log_level="INFO")  # 앱 시작 시 한 번만 호출
        
        # 다른 모듈에서
        import logging
        logger = logging.getLogger(__name__)  # 모듈명이 자동으로 로거 이름이 됨
        logger.info("로그 메시지")
    """
    # 로그 디렉토리 생성
    target_logs_dir = Path(logs_dir) if logs_dir else DEFAULT_LOGS_DIR
    target_logs_dir.mkdir(parents=True, exist_ok=True)
    
    # 로그 파일명 (날짜 포함하여 식별 용이)
    log_filename = target_logs_dir / f"chartinsight_{datetime.now().strftime('%Y%m%d')}.log"
    
    # 루트 로거 가져오기 (모든 로거의 부모)
    root_logger = logging.getLogger()
    
    # 기존 핸들러가 있으면 제거 (중복 방지)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # 루트 로거 레벨 설정 (DEBUG로 설정하여 모든 레벨 허용, 필터링은 핸들러에서)
    root_logger.setLevel(logging.DEBUG)
    
    # === 1. 파일 핸들러 설정 (자동 로테이션) ===
    # RotatingFileHandler: 파일 크기가 max_bytes를 초과하면 자동으로 .1, .2, ... 로 백업
    file_handler = RotatingFileHandler(
        filename=log_filename,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(get_log_level(log_level))
    
    # 스마트 포맷터 적용 (알고리즘 로그는 실행 시각 제거)
    file_handler.setFormatter(SmartFormatter())
    
    # === 2. 콘솔 핸들러 설정 (터미널 출력) ===
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(get_log_level(log_level))
    
    # 콘솔 로그 포맷: 간단하게 레벨과 메시지만
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # === 3. 루트 로거에 핸들러 등록 ===
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # 초기화 완료 로그
    root_logger.info(f"로깅 시스템 초기화 완료 - 로그 파일: {log_filename}")
    root_logger.info(f"로그 레벨: {log_level}, 최대 파일 크기: {max_bytes / (1024*1024):.1f}MB, 백업 개수: {backup_count}")


def get_log_level(level_str: str) -> int:
    """
    문자열 로그 레벨을 logging 모듈의 상수로 변환합니다.
    
    Args:
        level_str (str): 로그 레벨 문자열 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        
    Returns:
        int: logging 모듈의 로그 레벨 상수
        
    예시:
        >>> get_log_level("INFO")
        20
        >>> get_log_level("ERROR")
        40
    """
    level_map = {
        "DEBUG": logging.DEBUG,      # 10 - 상세한 디버깅 정보
        "INFO": logging.INFO,        # 20 - 일반 정보 메시지
        "WARNING": logging.WARNING,  # 30 - 경고 메시지
        "ERROR": logging.ERROR,      # 40 - 에러 메시지
        "CRITICAL": logging.CRITICAL # 50 - 치명적 에러
    }
    return level_map.get(level_str.upper(), logging.INFO) 