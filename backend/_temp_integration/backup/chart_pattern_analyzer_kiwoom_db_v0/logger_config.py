"""로컬(모듈)용 로깅 유틸리티

이 파일은 `chart_pattern_analyzer_kiwoom_db` 폴더 내에서만 사용하도록
경량화된 로깅 구성 함수를 제공합니다. 전체 프로젝트의 중앙 로거와
충돌하지 않도록 import 시점에 핸들러를 추가하지 않고 호출자가
명시적으로 설정하도록 설계되었습니다.
"""
from pathlib import Path
import logging
import os
from datetime import datetime


from typing import Optional

# Note: automatic project-root discovery has been removed from this module.
# Callers MUST provide an explicit `logs_dir` to `configure_logger`.


def configure_logger(logger_name: str, log_file_prefix: str = None, logs_dir: Optional[str | Path] = None, level=logging.INFO):
    """간단한 모듈 전용 로거 구성 함수.

    호출자가 반드시 `logs_dir`을 명시해야 하며, 이 함수는 해당 디렉터리를 생성합니다.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    # 중복 핸들러 제거
    for h in list(logger.handlers):
        logger.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass

    # 파일 핸들러 생성은 선택적입니다. logs_dir이 주어지면 파일 핸들러를 추가합니다.
    file_handler_created = False
    if logs_dir:
        target_dir = Path(logs_dir)
        # Ensure directory exists (safe even if called concurrently)
        target_dir.mkdir(parents=True, exist_ok=True)

        prefix = log_file_prefix if log_file_prefix else logger_name.split('.')[-1]
        fname = target_dir / f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        fh = logging.FileHandler(str(fname), mode='w', encoding='utf-8')
        fh.setLevel(level)
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        fh.setFormatter(fmt)
        logger.addHandler(fh)
        file_handler_created = True

    # console handler (개발용) - 항상 추가
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(levelname)s - %(message)s'))
    logger.addHandler(ch)

    logger.propagate = False
    if file_handler_created:
        logger.info(f"{logger_name} logger configured (file={fname})")
    else:
        logger.info(f"{logger_name} logger configured (console only)")
    return logger


