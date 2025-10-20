import logging
import datetime
from zoneinfo import ZoneInfo


def configure_kst_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a logger configured to emit timestamps in KST (Asia/Seoul).

    This helper ensures handlers are not duplicated and provides a standard
    format for module-level KST logs.
    """
    logger = logging.getLogger(name)
    # Avoid adding multiple handlers if already configured
    if not logger.handlers:
        kst = ZoneInfo("Asia/Seoul")
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S %Z")

        def _kst_converter(seconds):
            return datetime.datetime.fromtimestamp(seconds, tz=kst).timetuple()

        fmt.converter = _kst_converter
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        # Prevent double logging to root handlers when basicConfig/root handlers are present
        logger.propagate = True
        logger.setLevel(level)
    return logger


