import numpy as np
import pandas as pd
import logging
from typing import Optional

# Use the central 'backend' logger so file-formatting is controlled centrally
logger = logging.getLogger('backend')

class PatternDetector:
    """DT/DB/HS/IHS 패턴 감지기 기본 클래스"""
    def __init__(self, first_extremum, data, creation_event_date: pd.Timestamp = None, peaks=None, valleys=None):
        # 패턴 메타
        if not hasattr(self, 'pattern_type') or not self.pattern_type:
            self.pattern_type = "Unknown"
        self.first_extremum = first_extremum

        # 감지기 생성 일자/ID
        self.detector_creation_date = creation_event_date if creation_event_date is not None else pd.Timestamp.now()
        start_date_str = self.first_extremum['actual_date'].strftime('%y%m%d') if self.first_extremum and 'actual_date' in self.first_extremum else 'NO_DATE'
        self.detector_id = f"[{self.pattern_type}-{start_date_str}]"

        # 상태
        self.expectation_mode = True
        self.stage = "Initial" # 초기 상태는 Initial로 통일
        self.data = data
        self.peaks = peaks if peaks is not None else [] # 전체 Peak 리스트 참조
        self.valleys = valleys if valleys is not None else [] # 전체 Valley 리스트 참조
        self.candle_history = [] # 캔들 기록 (필요시)

        # 각 패턴별 속성 초기화 (None으로)
        # H&S / IH&S
        self.P1 = None; self.V2 = None; self.P2 = None; self.V3 = None; self.P3 = None
        self.V1 = None; self.P2_ihs = None; self.V2_ihs = None; self.P3_ihs = None; self.V3_ihs = None
        self.neckline_level = None
        
        # DT / DB
        self.confirmation_candle = None; self.actual_candle = None; self.band = None
        self.straight_peak = None; self.straight_valley = None
        self.first_positive_candle = None; self.first_negative_candle = None
        self.second_valley = None; self.second_peak = None
        self.band_option = "option2" # 기본값 설정 (필요시 하위 클래스에서 변경)

    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None):
        raise NotImplementedError("Subclasses must implement this method")

    def reset(self, reason=""):
        self.expectation_mode = False
        self.stage = "Failed"
        self.log_event(f"감지기 리셋: 이유={reason}", "INFO")

    def is_complete(self):
        return self.stage == "Completed"


    def is_failed(self):
        return self.stage == "Failed"

    def log_event(self, message: str, level: str = "DEBUG", current_date: Optional[pd.Timestamp] = None):
        if current_date is None:
            # current_date가 없으면 이벤트 발생일을 감지기 생성일로 간주
            current_date = self.detector_creation_date

        creation_date_str = self.detector_creation_date.strftime('%Y-%m-%d')
        current_date_str = current_date.strftime('%Y-%m-%d') if isinstance(current_date, pd.Timestamp) else str(current_date)

        log_msg = f"[{current_date_str}] {self.detector_id} {message} (감지기생성일: {creation_date_str})"
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(log_msg)
