"""로깅 시스템 중앙 설정 모듈"""

import os
import sys
import logging
from datetime import datetime
import atexit
import traceback

# 로그 디렉토리 생성
logs_dir = "logs"
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir)

# 모든 파일 핸들러를 추적하기 위한 리스트
all_handlers = []

# 종료 시 모든 핸들러 플러시 및 닫기
def close_handlers():
    for handler in all_handlers:
        if isinstance(handler, logging.FileHandler):
            handler.flush()
            handler.close()

# 프로그램 종료 시 핸들러 정리 등록
atexit.register(close_handlers)

class ImmediateFileHandler(logging.FileHandler):
    def __init__(self, filename, mode='a', encoding=None, delay=False):
        super().__init__(filename, mode, encoding, delay)
    
    def emit(self, record):
        try:
            super().emit(record)
            self.flush()  # 매 로그 기록마다 즉시 파일에 플러시
            print(f"파일에 기록 완료: {record.msg}")  # 디버깅용 출력
        except Exception as e:
            print(f"파일 핸들러 오류: {e}")  # 오류 출력 구체화

# 로깅 설정 함수
def setup_logger(logger_name, log_file_prefix):
    """
    로거 설정 함수
    
    Args:
        logger_name (str): 로거 이름
        log_file_prefix (str): 로그 파일 접두사
        
    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    # 현재 날짜와 시간으로 로그 파일명 생성
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{logs_dir}/{log_file_prefix}_{current_time}.log"
    
    # 로거 가져오기 (이미 존재하면 기존 로거 사용)
    logger = logging.getLogger(logger_name)
    
    # 기존 핸들러 제거 (중복 방지)
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # 로거 레벨 설정
    logger.setLevel(logging.DEBUG)
    
    # 커스텀 파일 핸들러 사용 (매 로그마다 플러시)
    file_handler = ImmediateFileHandler(log_filename, mode='w')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    
    # 콘솔 핸들러 설정
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # 콘솔에는 INFO 레벨 이상만 출력
    console_formatter = logging.Formatter('%(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    
    # 핸들러 추가
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    # 중요: 핸들러가 자동으로 플러시되도록 설정
    logger.propagate = False  # 상위 로거로 로그 전파 방지
    
    # 전역 핸들러 목록에 추가
    all_handlers.append(file_handler)
    all_handlers.append(console_handler)
    
    # 초기화 로그
    logger.info(f"{logger_name} 로거 초기화 완료 (로그 파일: {log_filename})")
    
    # 파일에 즉시 기록되도록 플러시
    file_handler.flush()
    
    # 디버그 로그로 로거 상태 기록
    logger.debug(f"로거 상태: 이름={logger_name}, 레벨={logger.level}, 핸들러 수={len(logger.handlers)}")
    
    return logger

# 로거 인스턴스 가져오기 (이미 설정된 경우 기존 로거 반환)
def get_logger(logger_name, log_file_prefix=None):
    """
    로거 인스턴스 가져오기
    
    Args:
        logger_name (str): 로거 이름
        log_file_prefix (str, optional): 로그 파일 접두사. None이면 logger_name 사용
        
    Returns:
        logging.Logger: 로거 인스턴스
    """
    logger = logging.getLogger(logger_name)
    
    # 로거가 이미 설정되어 있는지 확인
    if not logger.handlers:
        # 접두사 설정
        prefix = log_file_prefix if log_file_prefix else logger_name.split('.')[-1]
        # 로거 설정
        logger = setup_logger(logger_name, prefix)
    
    return logger

# 로깅 레벨 변환 함수
def get_log_level(level_str):
    """
    문자열 로그 레벨을 logging 모듈 레벨로 변환
    
    Args:
        level_str (str): 로그 레벨 문자열 ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        
    Returns:
        int: logging 모듈 로그 레벨
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }
    return level_map.get(level_str.upper(), logging.INFO) 