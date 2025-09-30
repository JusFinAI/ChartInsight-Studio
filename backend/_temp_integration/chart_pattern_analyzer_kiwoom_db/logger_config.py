"""차트 패턴 분석기용 로깅 시스템 (개선된 버전)

이 모듈은 chart_pattern_analyzer_kiwoom_db 프로젝트의 로깅을 담당합니다.

🎯 주요 개선사항:
1. 충돌 방지: 같은 로거에 대해 여러 번 설정해도 안전합니다
2. 설정 완료 표시: _fully_configured 속성으로 중복 설정 방지
3. 헬퍼 함수 제공: 로거 레벨 변경, 추가 핸들러 연결 등 편의 기능
4. 명확한 메시지: 이모지와 함께 직관적인 로그 메시지

📝 사용법:
1. configure_logger()로 로거 초기 설정
2. get_logger()로 이미 설정된 로거 가져오기
3. set_logger_level()로 동적 레벨 변경
4. add_file_handler()로 추가 로그 파일 연결

🔧 로그 레벨:
- DEBUG: 매우 자세한 내부 동작 (개발 시)
- INFO: 일반적인 정보 (운영 시 기본)
- WARNING: 주의사항
- ERROR: 오류
- CRITICAL: 심각한 오류
"""
from pathlib import Path
import logging
import os
from datetime import datetime


from typing import Optional

# Note: automatic project-root discovery has been removed from this module.
# Callers MUST provide an explicit `logs_dir` to `configure_logger`.


def configure_logger(logger_name: str, log_file_prefix: str = None, logs_dir: Optional[str | Path] = None, level=logging.INFO):
    """개선된 모듈 전용 로거 구성 함수.

    충돌 방지를 위해 기존 핸들러를 안전하게 관리하고,
    같은 로거에 대해 여러 번 호출해도 설정이 누적되지 않도록 합니다.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # 이미 완전히 설정된 로거인지 확인
    if hasattr(logger, '_fully_configured'):
        return logger

    # 중복 핸들러 제거 (안전하게)
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # 파일 핸들러 생성 (선택적)
    file_handler_created = False
    if logs_dir:
        target_dir = Path(logs_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        prefix = log_file_prefix if log_file_prefix else logger_name.split('.')[-1]
        fname = target_dir / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(str(fname), mode='w', encoding='utf-8')
        fh.setLevel(level)
        fmt = logging.Formatter('%(message)s')
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        file_handler_created = True

    # 콘솔 핸들러 (항상 추가)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(ch)

    logger.propagate = False
    logger._fully_configured = True  # 설정 완료 표시

    if file_handler_created:
        logger.info(f"✅ {logger_name} logger configured (file={fname})")
    else:
        logger.info(f"✅ {logger_name} logger configured (console only)")
    return logger


# ===== 추가 헬퍼 함수들 =====

def get_logger(name: str) -> logging.Logger:
    """이미 설정된 로거를 안전하게 가져오는 함수.

    Args:
        name: 로거 이름

    Returns:
        logging.Logger: 설정된 로거 인스턴스
    """
    return logging.getLogger(name)


def set_logger_level(logger_name: str, level: int):
    """기존 로거의 레벨을 동적으로 변경하는 함수.

    Args:
        logger_name: 로거 이름
        level: 새로운 로깅 레벨 (logging.INFO, logging.DEBUG 등)
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.info(f"🔧 Logger '{logger_name}' level changed to {logging.getLevelName(level)}")


def add_file_handler(logger_name: str, log_file_prefix: str, logs_dir: str | Path):
    """기존 로거에 파일 핸들러를 추가로 연결하는 함수.

    Args:
        logger_name: 로거 이름
        log_file_prefix: 로그 파일 접두사
        logs_dir: 로그 디렉토리
    """
    logger = logging.getLogger(logger_name)
    target_dir = Path(logs_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    fname = target_dir / f"{log_file_prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    fh = logging.FileHandler(str(fname), mode='w', encoding='utf-8')
    fh.setLevel(logger.level)
    fmt = logging.Formatter('%(asctime)s - %(message)s')
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    logger.info(f"📁 Additional file handler added: {fname}")


