import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time
import logging
import sys
# yfinance 429 오류 해결을 위한 추가 import
try:
    from curl_cffi import requests
    CURL_CFFI_AVAILABLE = True
except ImportError:
    CURL_CFFI_AVAILABLE = False
    print("⚠️ curl_cffi가 설치되지 않았습니다. 429 오류 발생 시 'pip install curl_cffi' 실행하세요.")
from dataclasses import dataclass, field
from typing import List, Dict, Any,Optional, Tuple # 타입 힌팅 추가
import os
from datetime import datetime

# logs 디렉토리가 없으면 생성
os.makedirs('logs', exist_ok=True)

# 현재 날짜를 기반으로 로그 파일 이름 생성
current_date = datetime.now().strftime('%Y%m%d%H%M')
log_filename = f'logs/dttb_strategy_grok_{current_date}.log'

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
# --- 파일 핸들러 경로 수정 ---
file_handler = logging.FileHandler(log_filename, mode='w') # 날짜 기반 로그 파일 이름 사용
# --------------------------
file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.DEBUG)
console_formatter = logging.Formatter('%(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)
# --- 로거 핸들러 중복 추가 방지 ---
if not logger.handlers:
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
@dataclass
class MarketTrendInfo:
    """최종 시장 추세 관련 정보를 관리하는 데이터 클래스"""
    market_trend: str = "Sideways"           # 최종 추세 상태 ("Uptrend", "Downtrend", "Sideways")
    start_index: Optional[int] = None       # 추세 시작 인덱스
    periods: List[Dict] = field(default_factory=list) # 추세 구간 기록 리스트
    

class TrendDetector:
    def __init__(self, n_criteria=2):
        # ... (기존 V020의 변수들, MarketTrendInfo 사용 확인) ...
        self.state: int = 0
        self.state_direction: Optional[str] = None
        self.trend_count: int = -1
        self.reference_high: Optional[float] = None
        self.reference_low: Optional[float] = None
        self.reference_index: Optional[int] = None
        self.reset_high: Optional[float] = None
        self.reset_low: Optional[float] = None
        self.is_reset_state: bool = False
        self.highest_high: Optional[float] = None
        self.highest_high_index: Optional[int] = None
        self.lowest_low: Optional[float] = None
        self.lowest_low_index: Optional[int] = None
        self.js_peaks: List[Dict] = []
        self.js_valleys: List[Dict] = []
        self.secondary_peaks: List[Dict] = []
        self.secondary_valleys: List[Dict] = []
        self.states: List[Dict] = [] # states 리스트 초기화 확인
        self.trend_info = MarketTrendInfo() # 수정된 dataclass 사용
        self.n_criteria: int = n_criteria
        self.debug_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None
        self.data: Optional[pd.DataFrame] = None
        self.newly_registered_peak: Optional[Dict] = None
        self.newly_registered_valley: Optional[Dict] = None
        self.previous_state_direction: Optional[str] = None

    def is_inside_bar(self, high: float, low: float, ref_high: Optional[float], ref_low: Optional[float]) -> bool:
        """내부봉(Inside Bar) 여부 확인"""
        if ref_high is None or ref_low is None:
            return False
        return high <= ref_high and low >= ref_low

    def update_reference_band(self, high: float, low: float, index: int):
        """기준 고점/저점 (외부봉 기준) 업데이트"""
        self.reference_high = high
        self.reference_low = low
        self.reference_index = index

    def is_in_debug_range(self, date: pd.Timestamp) -> bool:
        """현재 날짜가 디버그 범위 내에 있는지 확인"""
        return self.debug_range is None or (self.debug_range[0] <= date <= self.debug_range[1])

    def log_event(self, date: pd.Timestamp, message: str, level: str = "DEBUG"):
        """로그 기록 (디버그 범위 내에서만 출력되도록 수정)"""
        log_date_str = date.strftime('%Y-%m-%d') if isinstance(date, pd.Timestamp) else str(date)
        if self.is_in_debug_range(date):
             getattr(logger, level.lower())(f"[{log_date_str}] {message}")

    # --- Helper 함수: 이전 마지막 극점 찾기 ---
    def _get_last_extremum_before(self, target_index: int, extremum_type: str) -> Optional[Dict]:
        """주어진 인덱스 이전에 발생한 가장 마지막 극점(JS+Secondary 통합)을 찾음"""
        if extremum_type == 'peak':
            all_extremums = self.js_peaks + self.secondary_peaks
        elif extremum_type == 'valley':
            all_extremums = self.js_valleys + self.secondary_valleys
        else:
            return None

        # target_index보다 작은 인덱스를 가진 극점들 필터링
        prior_extremums = [e for e in all_extremums if e['index'] < target_index]

        if not prior_extremums:
            return None

        # 인덱스가 가장 큰 (가장 최근) 극점 반환
        return max(prior_extremums, key=lambda x: x['index'])
    # -----------------------------------------
    def register_js_peak(self, index: int, value: float, actual_date: pd.Timestamp, detected_date: pd.Timestamp, data: pd.DataFrame):
        """JS Peak 등록 (OHLC 정보 포함) 및 기존 방식 Secondary Valley 검증"""
        try:
            actual_candle = data.loc[actual_date]
        except KeyError:
            self.log_event(detected_date, f"오류: JS Peak 등록 시 실제 캔들({actual_date})을 찾을 수 없음", "ERROR")
            return

        new_peak = {
            'type': 'js_peak', # 타입 명시
            'index': index, 'value': value, # value는 High 값
            'actual_date': actual_date, 'detected_date': detected_date,
            'open': actual_candle['Open'], 'high': actual_candle['High'],
            'low': actual_candle['Low'], 'close': actual_candle['Close']
        }
        if not any(p['index'] == index for p in self.js_peaks):
            self.js_peaks.append(new_peak)
            self.newly_registered_peak = new_peak # DTDB 및 H&S 매니저 트리거용
            self.log_event(detected_date, f"JS Peak 등록: Idx={index}, Val={value:.2f}, Actual={actual_date.strftime('%y%m%d')}", "INFO")

            # 기존 방식 Secondary Valley 검증 (JS Peak 2개 이상일 때)
            if len(self.js_peaks) >= 2:
                prev_peak = self._get_extremum_before(new_peak['index'], 'peak')
                if prev_peak and prev_peak['index'] < new_peak['index']:
                    start_index = prev_peak['index']
                    end_index = new_peak['index']
                    window_data = data.iloc[start_index : end_index + 1]
                    if not window_data.empty:
                        valley_value = window_data['Low'].min()
                        valley_actual_date = window_data['Low'].idxmin()
                        valley_index_relative = data.index.get_loc(valley_actual_date)
                        # 조건: 양쪽 JS Peak 값보다 낮아야 함
                        if valley_value < prev_peak['value'] and valley_value < new_peak['value']:
                            sec_valley_indices = {v['index'] for v in self.secondary_valleys}
                            js_valley_indices = {v['index'] for v in self.js_valleys}
                            if valley_index_relative not in sec_valley_indices and valley_index_relative not in js_valley_indices:
                                try:
                                    sec_valley_candle = data.loc[valley_actual_date]
                                    sec_valley = {
                                        'type': 'sec_valley', # 타입 명시
                                        'index': valley_index_relative, 'value': valley_value,
                                        'actual_date': valley_actual_date, 'detected_date': detected_date, # JS 등록 시 검출
                                        'open': sec_valley_candle['Open'], 'high': sec_valley_candle['High'],
                                        'low': sec_valley_candle['Low'], 'close': sec_valley_candle['Close']
                                    }
                                    self.secondary_valleys.append(sec_valley)
                                    self.newly_registered_valley = sec_valley # <<< 이 줄 추가 제안
                                    self.log_event(detected_date, f"  -> Sec Valley (JS등록시) 등록: Idx={sec_valley['index']}, Val={sec_valley['value']:.2f}", "DEBUG")
                                except KeyError:
                                    self.log_event(detected_date, f"오류: Sec Valley(JS등록시) 등록 시 실제 캔들({valley_actual_date}) 찾기 실패", "ERROR")

    def register_js_valley(self, index: int, value: float, actual_date: pd.Timestamp, detected_date: pd.Timestamp, data: pd.DataFrame):
        """JS Valley 등록 (OHLC 정보 포함) 및 기존 방식 Secondary Peak 검증"""
        try:
            actual_candle = data.loc[actual_date]
        except KeyError:
            self.log_event(detected_date, f"오류: JS Valley 등록 시 실제 캔들({actual_date})을 찾을 수 없음", "ERROR")
            return

        new_valley = {
            'type': 'js_valley', # 타입 명시
            'index': index, 'value': value, # value는 Low 값
            'actual_date': actual_date, 'detected_date': detected_date,
            'open': actual_candle['Open'], 'high': actual_candle['High'],
            'low': actual_candle['Low'], 'close': actual_candle['Close']
        }
        if not any(v['index'] == index for v in self.js_valleys):
            self.js_valleys.append(new_valley)
            self.newly_registered_valley = new_valley # DTDB 및 H&S 매니저 트리거용
            self.log_event(detected_date, f"JS Valley 등록: Idx={index}, Val={value:.2f}, Actual={actual_date.strftime('%y%m%d')}", "INFO")

            # 기존 방식 Secondary Peak 검증 (JS Valley 2개 이상일 때)
            if len(self.js_valleys) >= 2:
                prev_valley = self._get_extremum_before(new_valley['index'], 'valley')
                if prev_valley and prev_valley['index'] < new_valley['index']:
                    start_index = prev_valley['index']
                    end_index = new_valley['index']
                    window_data = data.iloc[start_index : end_index + 1]
                    if not window_data.empty:
                        peak_value = window_data['High'].max()
                        peak_actual_date = window_data['High'].idxmax()
                        peak_index_relative = data.index.get_loc(peak_actual_date)
                        # 조건: 양쪽 JS Valley 값보다 높아야 함
                        if peak_value > prev_valley['value'] and peak_value > new_valley['value']:
                            sec_peak_indices = {p['index'] for p in self.secondary_peaks}
                            js_peak_indices = {p['index'] for p in self.js_peaks}
                            if peak_index_relative not in sec_peak_indices and peak_index_relative not in js_peak_indices:
                                try:
                                    sec_peak_candle = data.loc[peak_actual_date]
                                    sec_peak = {
                                        'type': 'sec_peak', # 타입 명시
                                        'index': peak_index_relative, 'value': peak_value,
                                        'actual_date': peak_actual_date, 'detected_date': detected_date, # JS 등록 시 검출
                                        'open': sec_peak_candle['Open'], 'high': sec_peak_candle['High'],
                                        'low': sec_peak_candle['Low'], 'close': sec_peak_candle['Close']
                                    }
                                    self.secondary_peaks.append(sec_peak)
                                    self.newly_registered_peak = sec_peak # <<< 이 줄 추가 제안
                                    self.log_event(detected_date, f"  -> Sec Peak (JS등록시) 등록: Idx={sec_peak['index']}, Val={sec_peak['value']:.2f}", "DEBUG")
                                except KeyError:
                                    self.log_event(detected_date, f"오류: Sec Peak(JS등록시) 등록 시 실제 캔들({peak_actual_date}) 찾기 실패", "ERROR")


    def handle_state_0(self, current: pd.Series, prev: pd.Series, i: int, date: pd.Timestamp):
        self.is_reset_state = False
        self.previous_state_direction = self.state_direction # 변수명 변경
        if i == 1:
            if current['Close'] < current['Open']:
                self.state = 1
                self.state_direction = 'down' # 변수명 변경
                self.trend_count = 0
                self.log_event(date, f"State 0 -> 1 (하락 가설 시작, 첫 캔들 이후 음봉)", "INFO")
            elif current['Close'] > current['Open']:
                self.state = 1
                self.state_direction = 'up' # 변수명 변경
                self.trend_count = 0
                self.log_event(date, f"State 0 -> 1 (상승 가설 시작, 첫 캔들 이후 양봉)", "INFO")
        else:
            if not self.is_inside_bar(current['High'], current['Low'], self.reference_high, self.reference_low):
                if current['Low'] < self.reference_low:
                    self.state = 1
                    self.state_direction = 'down' # 변수명 변경
                    self.trend_count = 0
                    self.log_event(date, f"State 0 -> 1 (하락 가설 시작, Low < RefLow)", "INFO")
                elif current['High'] > self.reference_high:
                    self.state = 1
                    self.state_direction = 'up' # 변수명 변경
                    self.trend_count = 0
                    self.log_event(date, f"State 0 -> 1 (상승 가설 시작, High > RefHigh)", "INFO")

    def handle_state_1(self, current: pd.Series, prev: pd.Series, i: int, date: pd.Timestamp):
        # 강한 움직임 검출 로직 (V015와 동일)
        previous_candle_range = prev['High'] - prev['Low']
        close_to_close_move = abs(current['Close'] - prev['Close'])
        is_bullish_candle = current['Close'] > current['Open']
        is_bearish_candle = current['Close'] < current['Open']
        is_bullish_move = current['Close'] > prev['Close']
        is_bearish_move = current['Close'] < prev['Close']
        is_strong_move = close_to_close_move > previous_candle_range if previous_candle_range > 0 else False # 0으로 나누기 방지
        direction_match = ((self.state_direction == 'up' and is_bullish_candle and is_bullish_move) or
                        (self.state_direction == 'down' and is_bearish_candle and is_bearish_move))

        if is_strong_move and direction_match:
            self.state = 3
            self.trend_count = self.n_criteria
            if self.state_direction == 'up':
                self.highest_high = current['High']
                self.highest_high_index = i
            else:
                self.lowest_low = current['Low']
                self.lowest_low_index = i
            self.log_event(date, f"State 1({self.state_direction}) -> State 3 (즉시 추세 확정)", "INFO")
            return

        
        if self.state_direction == 'up':
            if current['High'] > self.reference_high and current.get('Close', float('-inf')) > prev.get('Close', float('-inf')):
                self.state = 2
                self.trend_count = 1
                self.log_event(date, f"State 1(up) -> State 2(up) (상승 추세 형성 시작)", "INFO")
            elif current['Low'] < self.reference_low:
                if current['Close'] < prev['Open']: # 강한 반전
                    self.state = 1
                    self.state_direction = 'down'
                    self.trend_count = 0
                    self.log_event(date, f"State 1(up) -> State 1(down) (방향 전환)", "INFO")
                else: # 단순 이탈
                    self.state = 0
                    self.state_direction = None
                    self.trend_count = -1
                    self.log_event(date, f"State 1(up) -> State 0 (추세 가설 취소)", "INFO")
            else:
                self.log_event(date, f"State 1(up) 유지", "DEBUG")
        elif self.state_direction == 'down':
            if current['Low'] < self.reference_low and current.get('Close', float('inf')) < prev.get('Close', float('inf')):
                self.state = 2
                self.trend_count = 1
                self.log_event(date, f"State 1(down) -> State 2(down) (하락 추세 형성 시작)", "INFO")
            elif current['High'] > self.reference_high:
                if current['Close'] > prev['Open']: # 강한 반전
                    self.state = 1
                    self.state_direction = 'up'
                    self.trend_count = 0
                    self.log_event(date, f"State 1(down) -> State 1(up) (방향 전환)", "INFO")
                else: # 단순 이탈
                    self.state = 0
                    self.state_direction = None
                    self.trend_count = -1
                    self.log_event(date, f"State 1(down) -> State 0 (추세 가설 취소)", "INFO")
            else:
                self.log_event(date, f"State 1(down) 유지", "DEBUG")

    def handle_state_2(self, current: pd.Series, prev: pd.Series, i: int, date: pd.Timestamp):
        # State 3 전환 또는 리셋/방향 전환 로직 (V015와 동일, state_direction 사용)
        if self.state_direction == 'up':
            if current['High'] > self.reference_high and current.get('Close', float('-inf')) > prev.get('Close', float('-inf')):
                self.trend_count += 1
                self.log_event(date, f"State 2(up) 유지 (Count={self.trend_count})", "DEBUG")
                if self.trend_count >= self.n_criteria:
                    self.state = 3
                    self.highest_high = current['High']
                    self.highest_high_index = i
                    self.log_event(date, f"State 2(up) -> State 3(up) (상승 추세 확정)", "INFO")
            elif current['Low'] < self.reference_low:
                 if current['Close'] < prev['Open']: # 강한 반전
                    self.state = 1
                    self.state_direction = 'down'
                    self.trend_count = 0
                    self.log_event(date, f"State 2(up) -> State 1(down) (방향 전환)", "INFO")
                 else: # 단순 이탈
                    self.state = 0
                    self.state_direction = None
                    self.trend_count = -1
                    self.reset_low = current['Low']
                    self.is_reset_state = True
                    self.log_event(date, f"State 2(up) -> State 0 (리셋)", "INFO")
            else:
                 self.log_event(date, f"State 2(up) 유지 (추세 약화/조정)", "DEBUG")
        elif self.state_direction == 'down':
            if current['Low'] < self.reference_low and current.get('Close', float('inf')) < prev.get('Close', float('inf')):
                self.trend_count += 1
                self.log_event(date, f"State 2(down) 유지 (Count={self.trend_count})", "DEBUG")
                if self.trend_count >= self.n_criteria:
                    self.state = 3
                    self.lowest_low = current['Low']
                    self.lowest_low_index = i
                    self.log_event(date, f"State 2(down) -> State 3(down) (하락 추세 확정)", "INFO")
            elif current['High'] > self.reference_high:
                 if current['Close'] > prev['Open']: # 강한 반전
                    self.state = 1
                    self.state_direction = 'up'
                    self.trend_count = 0
                    self.log_event(date, f"State 2(down) -> State 1(up) (방향 전환)", "INFO")
                 else: # 단순 이탈
                    self.state = 0
                    self.state_direction = None
                    self.trend_count = -1
                    self.reset_high = current['High']
                    self.is_reset_state = True
                    self.log_event(date, f"State 2(down) -> State 0 (리셋)", "INFO")
            else:
                 self.log_event(date, f"State 2(down) 유지 (추세 약화/조정)", "DEBUG")

    def handle_state_3(self, current: pd.Series, prev: pd.Series, i: int, date: pd.Timestamp, data: pd.DataFrame):
        """State 3 처리: JS Peak/Valley 등록 조건 확인 및 등록"""
        detected_date = date # 확정일 = 현재 캔들 날짜

        if self.state_direction == 'up':
            # JS Peak 등록 조건 (V015와 동일)
            if current['Close'] < self.reference_low and current['Close'] < current['Open']:
                # 최고점 갱신 확인 (V015와 동일)
                if self.highest_high is None or current['High'] > self.highest_high:
                    self.highest_high = current['High']
                    self.highest_high_index = i
                    self.log_event(date, f"State 3(up) Peak 등록 전 최고점 갱신: {self.highest_high:.2f} at index {i}", "DEBUG")

                # 정확한 Peak 찾기 (V015와 동일)
                # --- 최고점 인덱스 None 체크 추가 ---
                if self.highest_high_index is not None:
                    window_data = data.iloc[self.highest_high_index : i + 1]
                    if not window_data.empty:
                        peak_value = window_data['High'].max()
                        peak_actual_date = window_data['High'].idxmax()
                        peak_index_relative = data.index.get_loc(peak_actual_date)
                        # JS Peak 등록 함수 호출
                        self.register_js_peak(peak_index_relative, peak_value, peak_actual_date, detected_date, data)
                        # 상태 전환
                        self.state = 1
                        self.state_direction = 'down'
                        self.trend_count = 0
                        self.log_event(date, f"State 3(up) -> State 1(down) (JS Peak 등록 조건 충족)", "INFO") # register 함수에서 로그 기록
                    else:
                        self.log_event(date, f"State 3(up) Peak 등록 위한 window_data 비어있음 (Index: {self.highest_high_index} ~ {i})", "WARNING")
                else:
                    self.log_event(date, f"State 3(up) Peak 등록 시 highest_high_index가 None임", "ERROR")
                # ---------------------------------

            # 최고점 갱신 (V015와 동일)
            elif self.highest_high is None or current['High'] > self.highest_high:
                self.highest_high = current['High']
                self.highest_high_index = i
                self.log_event(date, f"State 3(up) 최고점 갱신: {self.highest_high:.2f} at index {i}", "DEBUG")
            else:
                self.log_event(date, f"State 3(up) 유지", "DEBUG")

        elif self.state_direction == 'down':
            # JS Valley 등록 조건 (V015와 동일)
            if current['Close'] > self.reference_high and current['Close'] > current['Open']:
                # 최저점 갱신 확인 (V015와 동일)
                if self.lowest_low is None or current['Low'] < self.lowest_low:
                    self.lowest_low = current['Low']
                    self.lowest_low_index = i
                    self.log_event(date, f"State 3(down) Valley 등록 전 최저점 갱신: {self.lowest_low:.2f} at index {i}", "DEBUG")

                # 정확한 Valley 찾기 (V015와 동일)
                # --- 최저점 인덱스 None 체크 추가 ---
                if self.lowest_low_index is not None:
                    window_data = data.iloc[self.lowest_low_index : i + 1]
                    if not window_data.empty:
                        valley_value = window_data['Low'].min()
                        valley_actual_date = window_data['Low'].idxmin()
                        valley_index_relative = data.index.get_loc(valley_actual_date)
                        # JS Valley 등록 함수 호출
                        self.register_js_valley(valley_index_relative, valley_value, valley_actual_date, detected_date, data)
                        # 상태 전환
                        self.state = 1
                        self.state_direction = 'up'
                        self.trend_count = 0
                        self.log_event(date, f"State 3(down) -> State 1(up) (JS Valley 등록 조건 충족)", "INFO") # register 함수에서 로그 기록
                    else:
                        self.log_event(date, f"State 3(down) Valley 등록 위한 window_data 비어있음 (Index: {self.lowest_low_index} ~ {i})", "WARNING")
                else:
                    self.log_event(date, f"State 3(down) Valley 등록 시 lowest_low_index가 None임", "ERROR")
                # ---------------------------------

            # 최저점 갱신 (V015와 동일)
            elif self.lowest_low is None or current['Low'] < self.lowest_low:
                self.lowest_low = current['Low']
                self.lowest_low_index = i
                self.log_event(date, f"State 3(down) 최저점 갱신: {self.lowest_low:.2f} at index {i}", "DEBUG")
            else:
                self.log_event(date, f"State 3(down) 유지", "DEBUG")
    # --- 상태 머신 핸들러 끝 ---
    
    # --- 메인 처리 함수: process_candle (V020 최종 수정 2) ---
    # --- Helper 함수들 (수정 및 추가) ---
    def _get_last_extremum(self, extremum_type: str) -> Optional[Dict]:
        """가장 마지막(최신) 극점(JS+Secondary 통합)을 찾음"""
        if extremum_type == 'peak':
            all_extremums = self.js_peaks + self.secondary_peaks
        elif extremum_type == 'valley':
            all_extremums = self.js_valleys + self.secondary_valleys
        else:
            return None
        if not all_extremums:
            return None
        # 인덱스가 가장 큰 (가장 최근) 극점 반환
        return max(all_extremums, key=lambda x: x['index'])

    def _get_extremum_before(self, target_index: int, extremum_type: str) -> Optional[Dict]:
        """주어진 인덱스 이전에 발생한 가장 마지막 극점(JS+Secondary 통합)을 찾음 (기존 _get_last_extremum_before와 동일 기능, 이름 변경)"""
        if extremum_type == 'peak':
            all_extremums = self.js_peaks + self.secondary_peaks
        elif extremum_type == 'valley':
            all_extremums = self.js_valleys + self.secondary_valleys
        else:
            return None
        prior_extremums = [e for e in all_extremums if e['index'] < target_index]
        if not prior_extremums:
            return None
        return max(prior_extremums, key=lambda x: x['index'])
    # --- Helper 함수들 끝 ---

    # --- 메인 처리 함수: process_candle (V020 최종 수정 3) ---
    def process_candle(self, current: pd.Series, prev: pd.Series, i: int, date: pd.Timestamp, data: pd.DataFrame):
        """개별 캔들 처리 메인 로직 (V021 최종)"""
        # --- 추가: 현재 캔들 OHLC 로그 기록 ---
        self.log_event(date, f"Candle OHLC: O={current['Open']:.2f} H={current['High']:.2f} L={current['Low']:.2f} C={current['Close']:.2f}", "DEBUG")
        # -----------------------------------
        self.newly_registered_peak = None
        self.newly_registered_valley = None
        is_inside = self.is_inside_bar(current['High'], current['Low'], self.reference_high, self.reference_low)

        # --- 1. 실시간 돌파 감지 및 Secondary 탐색/등록 (항상 양방향 체크) ---
        # 1-1. 상승 돌파 이벤트 확인 및 처리
        latest_peak = self._get_last_extremum('peak')
        if latest_peak:
            is_up_breakout = current['Close'] > current['Open'] and current['Close'] > latest_peak['value']
            if is_up_breakout:
                self.log_event(date, f"^^^ 상승 돌파 이벤트 감지 (Close {current['Close']:.2f} > Latest Peak {latest_peak['value']:.2f}) ^^^", "INFO")
                window_data = data.iloc[latest_peak['index'] : i + 1]
                if not window_data.empty:
                    sec_valley_value = window_data['Low'].min()
                    sec_valley_actual_date = window_data['Low'].idxmin()
                    sec_valley_index = data.index.get_loc(sec_valley_actual_date)
                    prev_valley_before_peak = self._get_extremum_before(latest_peak['index'], 'valley')
                    
                    # 최소 조건 추가: 이전 밸리가 존재하고, 현재 밸리가 이전 밸리보다 크거나 같아야 함
                    if prev_valley_before_peak and sec_valley_value > prev_valley_before_peak['value']: # HL 조건 만족
                        self.log_event(date, f"  -> HL 조건 만족 (Sec Valley {sec_valley_value:.2f} > Prev Valley {prev_valley_before_peak['value']:.2f})", "INFO")
                        sec_valley_indices = {v['index'] for v in self.secondary_valleys}
                        js_valley_indices = {v['index'] for v in self.js_valleys}
                        if sec_valley_index not in sec_valley_indices and sec_valley_index not in js_valley_indices:
                            try:
                                sec_valley_candle = data.loc[sec_valley_actual_date]
                                sec_valley = {
                                    'type': 'sec_valley', # 타입 명시
                                    'index': sec_valley_index, 'value': sec_valley_value,
                                    'actual_date': sec_valley_actual_date, 'detected_date': date,
                                    'open': sec_valley_candle['Open'], 'high': sec_valley_candle['High'],
                                    'low': sec_valley_candle['Low'], 'close': sec_valley_candle['Close']
                                }
                                self.secondary_valleys.append(sec_valley)
                                self.newly_registered_valley = sec_valley # <<< 이 줄 추가 제안
                                self.log_event(date, f"  -> Sec Valley (돌파탐색) 등록: Idx={sec_valley_index}, Val={sec_valley_value:.2f}", "INFO")
                            except KeyError:
                                self.log_event(date, f"오류: Sec Valley(돌파) 등록 시 실제 캔들({sec_valley_actual_date}) 찾기 실패", "ERROR")
                    # else: # HL 불만족 로그
                    #    self.log_event(date, f"  -> HL 조건 불충족...", "DEBUG")
                # else: # window 비어있음 로그
                #    self.log_event(date, f"  -> Sec Valley 탐색 위한 window_data 비어있음...", "WARNING")

        # 1-2. 하락 돌파 이벤트 확인 및 처리
        latest_valley = self._get_last_extremum('valley')
        if latest_valley:
            is_down_breakout = current['Close'] < current['Open'] and current['Close'] < latest_valley['value']
            if is_down_breakout:
                self.log_event(date, f"vvv 하락 돌파 이벤트 감지 (Close {current['Close']:.2f} < Latest Valley {latest_valley['value']:.2f}) vvv", "INFO")
                window_data = data.iloc[latest_valley['index'] : i + 1]
                if not window_data.empty:
                    sec_peak_value = window_data['High'].max()
                    sec_peak_actual_date = window_data['High'].idxmax()
                    sec_peak_index = data.index.get_loc(sec_peak_actual_date)
                    prev_peak_before_valley = self._get_extremum_before(latest_valley['index'], 'peak')
                    if prev_peak_before_valley and sec_peak_value < prev_peak_before_valley['value']: # LH 조건 만족
                        self.log_event(date, f"  -> LH 조건 만족 (Sec Peak {sec_peak_value:.2f} < Prev Peak {prev_peak_before_valley['value']:.2f})", "INFO")
                        sec_peak_indices = {p['index'] for p in self.secondary_peaks}
                        js_peak_indices = {p['index'] for p in self.js_peaks}
                        if sec_peak_index not in sec_peak_indices and sec_peak_index not in js_peak_indices:
                            try:
                                sec_peak_candle = data.loc[sec_peak_actual_date]
                                sec_peak = {
                                    'type': 'sec_peak', # 타입 명시
                                    'index': sec_peak_index, 'value': sec_peak_value,
                                    'actual_date': sec_peak_actual_date, 'detected_date': date,
                                    'open': sec_peak_candle['Open'], 'high': sec_peak_candle['High'],
                                    'low': sec_peak_candle['Low'], 'close': sec_peak_candle['Close']
                                }
                                self.secondary_peaks.append(sec_peak)
                                self.newly_registered_peak = sec_peak # <<< 이 줄 추가 제안
                                self.log_event(date, f"  -> Sec Peak (돌파탐색) 등록: Idx={sec_peak_index}, Val={sec_peak_value:.2f}", "INFO")
                            except KeyError:
                                self.log_event(date, f"오류: Sec Peak(돌파) 등록 시 실제 캔들({sec_peak_actual_date}) 찾기 실패", "ERROR")
                    # else: # LH 불만족 로그
                    #      self.log_event(date, f"  -> LH 조건 불충족...", "DEBUG")
                # else: # window 비어있음 로그
                #     self.log_event(date, f"  -> Sec Peak 탐색 위한 window_data 비어있음...", "WARNING")
        # --- 실시간 돌파 감지 끝 ---

        # --- 2. (기존) 상태 머신 로직 실행 ---
        if self.state == 0: self.handle_state_0(current, prev, i, date)
        elif self.state == 1:
            if is_inside: pass
            else: self.handle_state_1(current, prev, i, date)
        elif self.state == 2:
            if is_inside: pass
            else: self.handle_state_2(current, prev, i, date)
        elif self.state == 3:
            if is_inside: pass
            else: self.handle_state_3(current, prev, i, date, data)
        # --- 상태 머신 로직 끝 ---

        # --- 3. (기존) 기준 band 업데이트 ---
        if not is_inside: self.update_reference_band(current['High'], current['Low'], i)
        # -------------------------------

        # --- 4. (기존-단순화된) 최종 추세 판단 로직 실행 ---
        if self.trend_info.market_trend == "Sideways":
            if self.check_downtrend_start(current, i, date): pass
            elif self.check_uptrend_start(current, i, date): pass
        elif self.trend_info.market_trend == "Downtrend":
            if not self.check_downtrend_continuation(current, i, date): pass
        elif self.trend_info.market_trend == "Uptrend":
            if not self.check_uptrend_continuation(current, i, date): pass
        # --- 최종 추세 판단 로직 끝 ---

        # 상태 정보 기록
        self.states.append({
            'index': i, 'date': date, 'state': self.state, 'market_trend': self.trend_info.market_trend,
            'count': self.trend_count, 'reference_high': self.reference_high,
            'reference_low': self.reference_low, 'is_inside_bar': is_inside,
            'close': current['Close']
        })
    # --- 추세 판단 함수 (check_...trend...) 수정 ---
    def check_downtrend_start(self, current: pd.Series, i: int, date: pd.Timestamp) -> bool:
        # ... (V020 최종 수정 3 코드와 동일) ...
        if self.trend_info.market_trend != "Sideways": return False
        all_peaks = sorted(self.js_peaks + self.secondary_peaks, key=lambda x: x['index'], reverse=True)
        all_valleys = sorted(self.js_valleys + self.secondary_valleys, key=lambda x: x['index'], reverse=True)
        if len(all_peaks) < 2 or len(all_valleys) < 1: return False
        last_peak = all_peaks[0]; prev_peak = all_peaks[1]; last_valley = all_valleys[0]
        is_lower_high = last_peak['value'] < prev_peak['value']
        is_valley_broken = last_valley['index'] < i and current['Close'] < last_valley['value']
        if is_lower_high and is_valley_broken:
             self.log_event(date, f"*** 하락 추세 시작 (CheckStart) ***: LH({last_peak['value']:.2f}<{prev_peak['value']:.2f}) + Valley 돌파({current['Close']:.2f}<{last_valley['value']:.2f})", "INFO")
             self.trend_info.market_trend = "Downtrend"; self.trend_info.start_index = i
             return True
        return False

    def check_uptrend_start(self, current: pd.Series, i: int, date: pd.Timestamp) -> bool:
        # ... (V020 최종 수정 3 코드와 동일) ...
        if self.trend_info.market_trend != "Sideways": return False
        all_peaks = sorted(self.js_peaks + self.secondary_peaks, key=lambda x: x['index'], reverse=True)
        all_valleys = sorted(self.js_valleys + self.secondary_valleys, key=lambda x: x['index'], reverse=True)
        if len(all_valleys) < 2 or len(all_peaks) < 1: return False
        last_valley = all_valleys[0]; prev_valley = all_valleys[1]; last_peak = all_peaks[0]
        is_higher_low = last_valley['value'] > prev_valley['value']
        is_peak_broken = last_peak['index'] < i and current['Close'] > last_peak['value']
        if is_higher_low and is_peak_broken:
            self.log_event(date, f"*** 상승 추세 시작 (CheckStart) ***: HL({last_valley['value']:.2f}>{prev_valley['value']:.2f}) + Peak 돌파({current['Close']:.2f}>{last_peak['value']:.2f})", "INFO")
            self.trend_info.market_trend = "Uptrend"; self.trend_info.start_index = i
            return True
        return False

    def check_uptrend_continuation(self, current: pd.Series, i: int, date: pd.Timestamp) -> bool:
        # ... (V020 최종 수정 3 코드와 동일 - breakout_signal 초기화 없음) ...
        if self.trend_info.market_trend == "Uptrend":
            all_valleys = sorted(self.js_valleys + self.secondary_valleys, key=lambda x: x['index'], reverse=True)
            if not all_valleys: return True
            last_valley = all_valleys[0]
            if current['Close'] < last_valley['value']:
                self.log_event(date, f"--- 상승 추세 종료 ---> Sideways (Close {current['Close']:.2f} < Last Valley {last_valley['value']:.2f})", "INFO")
                if self.trend_info.start_index is not None:
                    if self.trend_info.start_index < len(self.data.index):
                        self.trend_info.periods.append({'start': self.data.index[self.trend_info.start_index], 'end': date, 'type': "Uptrend"})
                    else: self.log_event(date, f"오류: 추세 기간 기록 시 start_index ({self.trend_info.start_index})가 데이터 길이를 벗어남", "ERROR")
                self.trend_info.market_trend = "Sideways"; self.trend_info.start_index = None
                return False
            else: return True
        return True

    def check_downtrend_continuation(self, current: pd.Series, i: int, date: pd.Timestamp) -> bool:
        # ... (V020 최종 수정 3 코드와 동일 - breakout_signal 초기화 없음) ...
        if self.trend_info.market_trend == "Downtrend":
            all_peaks = sorted(self.js_peaks + self.secondary_peaks, key=lambda x: x['index'], reverse=True)
            if not all_peaks: return True
            last_peak = all_peaks[0]
            if current['Close'] > last_peak['value']:
                self.log_event(date, f"--- 하락 추세 종료 ---> Sideways (Close {current['Close']:.2f} > Last Peak {last_peak['value']:.2f})", "INFO")
                if self.trend_info.start_index is not None:
                    if self.trend_info.start_index < len(self.data.index):
                        self.trend_info.periods.append({'start': self.data.index[self.trend_info.start_index], 'end': date, 'type': "Downtrend"})
                    else: self.log_event(date, f"오류: 추세 기간 기록 시 start_index ({self.trend_info.start_index})가 데이터 길이를 벗어남", "ERROR")
                self.trend_info.market_trend = "Sideways"; self.trend_info.start_index = None
                return False
            else: return True
        return True

    def finalize(self, data: pd.DataFrame):
        """데이터 처리 루프 종료 후 마지막 추세 및 극점 처리 (V015 기반)"""
        last_date = data.index[-1]
        # 마지막 추세 구간 마무리
        if self.trend_info.market_trend in ["Uptrend", "Downtrend"] and self.trend_info.start_index is not None:
            self.trend_info.periods.append({
                'start': data.index[self.trend_info.start_index],
                'end': last_date,
                'type': self.trend_info.market_trend
            })
            self.log_event(last_date, f"마지막 추세 구간 기록: {self.trend_info.market_trend} ({data.index[self.trend_info.start_index].strftime('%y%m%d')} ~ {last_date.strftime('%y%m%d')})", "INFO")

        # 마지막 State 3 처리 (데이터 끝까지 추세 확정 상태인 경우 JS 등록 시도)
        # 주의: 마지막 캔들이 등록 조건을 만족해야 실제 등록됨
        if self.state == 3:
            if self.state_direction == 'up' and self.highest_high_index is not None:
                 # 마지막 캔들 정보로 handle_state_3을 호출하여 등록 조건 확인 및 처리
                 if len(data) > 1:
                      self.handle_state_3(data.iloc[-1], data.iloc[-2], len(data)-1, last_date, data)
                      self.log_event(last_date, f"데이터 끝 State 3(up) 처리 시도", "DEBUG")
                 else:
                      self.log_event(last_date, f"데이터가 1개뿐이라 마지막 State 3 처리 불가", "WARNING")

            elif self.state_direction == 'down' and self.lowest_low_index is not None:
                 if len(data) > 1:
                      self.handle_state_3(data.iloc[-1], data.iloc[-2], len(data)-1, last_date, data)
                      self.log_event(last_date, f"데이터 끝 State 3(down) 처리 시도", "DEBUG")
                 else:
                      self.log_event(last_date, f"데이터가 1개뿐이라 마지막 State 3 처리 불가", "WARNING")


    def detect_peaks_valleys(self, data: pd.DataFrame, debug_range: Optional[Tuple[pd.Timestamp, pd.Timestamp]] = None):
        """Peak/Valley 및 추세 감지 메인 함수"""
        self.debug_range = debug_range
        self.data = data # 데이터 저장 (내부 참조용)
        # --- 리스트 초기화 ---
        self.js_peaks, self.js_valleys = [], []
        self.secondary_peaks, self.secondary_valleys = [], []
        self.states = []
        self.trend_info = MarketTrendInfo() # 추세 정보 객체 초기화
        self.state = 0 # 상태 초기화
        self.state_direction = None
        self.trend_count = -1
        # -------------------

        if len(data) < 2:
            logger.warning("데이터 길이가 너무 짧아 Peak/Valley 분석을 수행할 수 없습니다.")
            return [], [], [], [], [], [] # 빈 리스트 반환

        # 첫 캔들 처리
        first = data.iloc[0]
        self.update_reference_band(first['High'], first['Low'], 0)
        self.states.append({ # 첫 캔들 상태 기록
            'index': 0, 'date': data.index[0], 'state': self.state,
            'market_trend': self.trend_info.market_trend, 'count': self.trend_count,
            'reference_high': self.reference_high, 'reference_low': self.reference_low,
            'is_inside_bar': False, 'close': first['Close']
        })
        self.log_event(data.index[0], f"초기화: State={self.state}, Trend={self.trend_info.market_trend}", "INFO")

        # 나머지 캔들 처리 루프
        for i in range(1, len(data)):
            current_date = data.index[i]
            current_candle = data.iloc[i]
            prev_candle = data.iloc[i-1]
            self.process_candle(current_candle, prev_candle, i, current_date, data)

        # 데이터 처리 완료 후 최종 정리
        self.finalize(data)

        # 최종 결과 반환
        return self.js_peaks, self.js_valleys, self.secondary_peaks, self.secondary_valleys, self.states, self.trend_info.periods

class PatternDetector:
    """DT/DB/HS/IHS 패턴 감지기 기본 클래스"""
    def __init__(self, first_extremum, data, peaks=None, valleys=None): # 기본 생성자 단순화
        self.expectation_mode = True
        self.stage = "Initial" # 초기 상태는 Initial로 통일
        self.first_extremum = first_extremum # 패턴 시작 극점 (P1 또는 V1)
        self.pattern_type = "Unknown"
        self.data = data
        self.peaks = peaks if peaks is not None else [] # 전체 Peak 리스트 참조
        self.valleys = valleys if valleys is not None else [] # 전체 Valley 리스트 참조
        self.candle_history = [] # 캔들 기록 (필요시)

        # 각 패턴별 속성 초기화 (None으로)
        # H&S / IH&S
        self.P1 = None; self.V2 = None; self.P2 = None; self.V3 = None; self.P3 = None
        self.V1 = None; self.P2_ihs = None; self.V2_ihs = None; self.P3_ihs = None; self.V3_ihs = None
        self.neckline_level = None
        self.p1_close_level_reached = False
        self.v1_close_level_reached = False
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
        # 로그 출력 시점에 first_extremum이 있는지 확인
        current_date = pd.Timestamp.now()
        if self.first_extremum and 'detected_date' in self.first_extremum:
            actual_date_str = self.first_extremum['actual_date'].strftime('%Y-%m-%d') if 'actual_date' in self.first_extremum else 'N/A'
            logger.info(
                f"[{current_date.strftime('%Y-%m-%d')}] [{self.pattern_type}-{self.first_extremum['actual_date'].strftime('%y%m%d')}] 감지기 리셋: 이유={reason} (감지기생성일: {self.first_extremum['detected_date'].strftime('%Y-%m-%d')})"
            )
        else:
            logger.info(f"[{current_date.strftime('%Y-%m-%d')}] [{self.pattern_type}] 감지기 리셋: 이유={reason}")

    def is_complete(self):
        return self.stage == "Completed"

    def is_failed(self):
        return self.stage == "Failed"

    def log_event(self, message, level="DEBUG", current_date=None): # 현재 처리 중인 날짜 파라미터 추가
        if current_date is None:
            # 현재 날짜 정보가 없으면 패턴 감지기 생성 날짜 사용
            if self.candle_history and 'date' in self.candle_history[-1]:
                current_date = self.candle_history[-1]['date']
            else:
                current_date = pd.Timestamp.now()
                
        if self.first_extremum and 'detected_date' in self.first_extremum and 'actual_date' in self.first_extremum:
            pattern_start_date = self.first_extremum['actual_date'].strftime('%y%m%d') if isinstance(self.first_extremum['actual_date'], pd.Timestamp) else 'N/A'
            detector_creation_date = self.first_extremum['detected_date'].strftime('%Y-%m-%d')
            
            # 현재 날짜를 맨 앞에 표시하고 패턴 정보와 감지기 생성일 추가
            log_msg = f"[{current_date.strftime('%Y-%m-%d')}] [{self.pattern_type}-{pattern_start_date}] {message} (감지기생성일: {detector_creation_date})"
            logger.log(getattr(logging, level.upper()), log_msg)
        else:
            # 기본 정보가 없는 경우 간단한 형식 사용
            current_date_str = current_date.strftime('%Y-%m-%d') if isinstance(current_date, pd.Timestamp) else str(current_date)
            logger.log(getattr(logging, level.upper()), f"[{current_date_str}] [{self.pattern_type}] {message}")

class HeadAndShouldersDetector(PatternDetector):
    """Head and Shoulders 패턴 감지기 (수정 V4 - 규칙 변경 및 옵션 추가)"""
    def __init__(self, p1, data, peaks=None, valleys=None, completion_mode='aggressive'): # completion_mode 파라미터 추가
        super().__init__(p1, data, peaks, valleys)
        self.pattern_type = "HS"
        self.P1 = p1 # Left Shoulder Peak
        self.completion_mode = completion_mode # 옵션 저장
        self.stage = "LeftShoulderPeakDetected" # Stage 1
        
# HeadAndShouldersDetector 클래스 내
    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None):
        """H&S 패턴 상태 업데이트 (수정 V4 - 검증 규칙 변경 및 완성 옵션 적용)"""
        if not self.expectation_mode: return

        current_date = candle['date']
        current_close = candle['Close']
        current_high = candle['High']
        current_low = candle['Low']

        # --- 리셋 조건 확인 (스테이지 이름 조정) ---
        if self.P1 and current_high > self.P1['value'] and self.stage == "LeftShoulderPeakDetected": # Stage 1 Reset
            self.log_event(f"리셋 (Stage 1): 현재 High({current_high:.0f}) > P1({self.P1['value']:.0f})", "INFO"); self.reset("P1 고점 상회"); return
        if self.V2 and current_close < self.V2['value'] and self.stage == "LeftNecklineValleyDetected": # Stage 2 Reset
            self.log_event(f"리셋 (Stage 2): 현재 Close({current_close:.0f}) < V2({self.V2['value']:.0f})", "INFO"); self.reset("V2 저점 하회"); return
        # P2(머리) 고점 돌파 리셋: P2 형성 후 ~ 완성 전까지 모든 단계에서 확인
        if self.P2 and current_high > self.P2['value'] and self.stage in ["HeadPeakDetected", "RightNecklineValleyDetected", "AwaitingCompletion"]:
            self.log_event(f"리셋 (Stage {self.stage}): 현재 High({current_high:.0f}) > P2({self.P2['value']:.0f})", "INFO"); self.reset("머리 고점 상회"); return
        # V2(왼쪽 넥라인) 저점 돌파 리셋: V3/P3 형성 중 또는 완성 대기 중
        if self.V2 and current_close < self.V2['value'] and self.stage in ["RightNecklineValleyDetected", "AwaitingCompletion"]:
            self.log_event(f"리셋 (Stage {self.stage}): 현재 Close({current_close:.0f}) < V2({self.V2['value']:.0f})", "INFO"); self.reset("V3/P3 형성 또는 완성 대기 중 V2 하회"); return
        # P3(오른쪽 어깨) 고점 돌파 리셋: P3 형성 후 완성 대기 중
        if self.P3 and current_close > self.P3['value'] and self.stage == "AwaitingCompletion":
            self.log_event(f"리셋 (Stage AwaitingCompletion): 현재 Close({current_close:.0f}) > P3({self.P3['value']:.0f})", "INFO"); self.reset("완성 전 P3 상회"); return
        # ---------------------

        # --- 상태별 로직 진행 ---
        if self.stage == "LeftShoulderPeakDetected": # Stage 1: V2 찾기
            if newly_registered_valley and newly_registered_valley['index'] > self.P1['index']:
                self.V2 = newly_registered_valley
                self.stage = "LeftNecklineValleyDetected" # Stage 2
                # self.log_event(f"Stage 1 -> 2: V2 감지 {self.V2['actual_date'].strftime('%y%m%d')}({self.V2['value']:.0f})")

        elif self.stage == "LeftNecklineValleyDetected": # Stage 2: P2 찾기
            if newly_registered_peak and newly_registered_peak['index'] > self.V2['index']:
                # P2 > P1 조건은 Manager에서 검증했지만, 여기서 다시 확인 가능 (선택사항)
                if newly_registered_peak['value'] > self.P1['value']:
                    self.P2 = newly_registered_peak
                    self.stage = "HeadPeakDetected" # Stage 3
                    # self.log_event(f"Stage 2 -> 3: P2(머리) 감지 {self.P2['actual_date'].strftime('%y%m%d')}({self.P2['value']:.0f})")
                # else: self.reset("Internal Error: P2 <= P1"); return # 필요시 리셋

        elif self.stage == "HeadPeakDetected": # Stage 3: V3 찾기
            if newly_registered_valley and newly_registered_valley['index'] > self.P2['index']:
                self.V3 = newly_registered_valley
                self.stage = "RightNecklineValleyDetected" # Stage 4
                # self.log_event(f"Stage 3 -> 4: V3 감지 {self.V3['actual_date'].strftime('%y%m%d')}({self.V3['value']:.0f})")
                # V3 vs V2 몸통 검증 제거됨

        elif self.stage == "RightNecklineValleyDetected": # Stage 4: P3 찾기 및 검증 (균형/대칭 규칙 적용)
            if newly_registered_peak and newly_registered_peak['index'] > self.V3['index']:
                potential_p3 = newly_registered_peak
                self.log_event(f"Stage 4: P3 후보 발견 {potential_p3['actual_date'].strftime('%y%m%d')}({potential_p3['value']:.0f}). 검증 시작.", "DEBUG")

                # --- 검증 규칙 적용 ---
                p3_valid = True # 검증 통과 여부 플래그

                # 검증 0: P3 < P2 (기본 조건)
                if not (potential_p3.get('value', np.inf) < self.P2.get('value', -np.inf)):
                    p3_valid = False; self.log_event(f"  - P3 후보 검증 실패: P3({potential_p3.get('value'):.0f}) >= P2({self.P2.get('value'):.0f})", "DEBUG")

                # 필요한 데이터 준비 (종가 기준)
                if p3_valid: # 기본 조건 통과 시에만 추가 검증
                    try:
                        p1_val = self.data.loc[self.P1['actual_date'], 'High']
                        v2_val = self.data.loc[self.V2['actual_date'], 'Low']
                        p2_val = self.data.loc[self.P2['actual_date'], 'High']
                        v3_val = self.data.loc[self.V3['actual_date'], 'Low']
                        p3_val = self.data.loc[potential_p3['actual_date'], 'High'] # P3 값은 후보 캔들의 종가 사용
                        p3_idx = potential_p3['index']; p2_idx = self.P2['index']; p1_idx = self.P1['index']
                        v3_idx = self.V3['index']; v2_idx = self.V2['index'] # 균형 규칙 위해 추가

                    except KeyError as e:
                        self.log_event(f"오류: 검증 위한 가격 데이터 접근 실패 (날짜={e})", "ERROR"); self.reset("Data access error"); return
                    except Exception as e:
                        self.log_event(f"오류: 검증 데이터 준비 중 오류: {e}", "ERROR"); self.reset("Data prep error"); return

                    # 검증 1: 균형 규칙 (Balance Rule)
                    r_midpoint = 0.5 * (p3_val + v3_val)
                    l_midpoint = 0.5 * (p1_val + v2_val)
                    if p1_val < r_midpoint or p3_val < l_midpoint:
                        p3_valid = False
                        self.log_event(f"  - P3 후보 검증 실패: 균형 규칙 위반 (P1={p1_val:.0f} vs R_Mid={r_midpoint:.0f} or P3={p3_val:.0f} vs L_Mid={l_midpoint:.0f})", "DEBUG")

                    # 검증 2: 대칭 규칙 (Symmetry Rule)
                    if p3_valid and p3_idx > p2_idx and p2_idx > p1_idx: # 시간 순서 및 이전 검증 통과 확인
                        r_to_h_time = p3_idx - p2_idx
                        l_to_h_time = p2_idx - p1_idx
                        if r_to_h_time <= 0 or l_to_h_time <= 0: # 시간 차이가 0 이하인 경우 제외
                            p3_valid = False
                            self.log_event("  - P3 후보 검증 실패: 대칭 규칙 시간 계산 오류 (시간 차이 <= 0)", "WARNING")
                        elif r_to_h_time > 2.5 * l_to_h_time or l_to_h_time > 2.5 * r_to_h_time:
                            p3_valid = False
                            self.log_event(f"  - P3 후보 검증 실패: 대칭 규칙 위반 (L->H={l_to_h_time}, H->R={r_to_h_time})", "DEBUG")
                    elif p3_valid: # 시간 순서 오류
                        p3_valid = False
                        self.log_event("  - P3 후보 검증 실패: 대칭 규칙 시간 계산 오류 (인덱스 순서 오류)", "WARNING")


                # 모든 검증 통과 시 P3 확정 및 상태 변경
                if p3_valid:
                    self.P3 = potential_p3 # P3 확정
                    self.stage = "AwaitingCompletion" # Stage 5: 완성 조건 대기
                    self.log_event(f"Stage 4 -> 5: P3 감지 및 검증 통과 {self.P3['actual_date'].strftime('%y%m%d')}({self.P3['value']:.0f}). 완성 조건 확인 시작.", "INFO")
                # else: 검증 실패 시 아무것도 안하고 다음 Peak/Valley 이벤트 기다림

        elif self.stage == "AwaitingCompletion": # Stage 5: 완성 조건 확인
            # 현재 캔들의 인덱스 가져오기
            try:
                current_index_loc = self.data.index.get_loc(candle['date'])
            except KeyError:
                self.log_event(f"오류: 현재 캔들 날짜({candle['date']})를 self.data 인덱스에서 찾을 수 없음.", "ERROR")
                self.reset("Internal data index error")
                return

            if current_index_loc <= 0: # 첫 캔들에 대한 비교 불가
                self.log_event("경고: 직전 캔들 없어 완성 조건 확인 불가 (인덱스 0).", "WARNING"); return

            prev_candle = self.data.iloc[current_index_loc - 1] # 직전 캔들

            # 옵션별 완성 조건 확인
            if self.completion_mode == 'aggressive':
                # 조건: 음봉 마감 & 종가 < 직전 저점
                if candle['Close'] < candle['Open'] and candle['Close'] < prev_candle['Low']:
                    self.stage = "Completed"
                    self.expectation_mode = False
                    self.log_event(f"*** Head & Shoulders 패턴 완성! (Aggressive) *** Price={candle['Close']:.0f}, Prev Low={prev_candle['Low']:.0f}", "INFO")

            elif self.completion_mode == 'neckline':
                # 기울어진 넥라인 돌파 확인
                if self.V2 and self.V3: # V2, V3 정보 필요
                    try:
                        v2_idx = self.V2['index']; v3_idx = self.V3['index']
                        # 넥라인은 V2, V3의 Low 값을 기준으로 계산 (참고 코드와 약간 다름, Close 대신 Low 사용)
                        v2_val = self.V2.get('value') # V2 Low 값
                        v3_val = self.V3.get('value') # V3 Low 값

                        if v2_val is None or v3_val is None:
                             self.log_event("경고: 넥라인 계산 위한 V2 또는 V3 value 없음.", "WARNING"); return

                        if v3_idx > v2_idx: # 시간 순서 확인
                            neck_run = v3_idx - v2_idx
                            neck_rise = v3_val - v2_val
                            neck_slope = neck_rise / neck_run if neck_run != 0 else 0

                            # 현재 시점(i)에서의 넥라인 값 계산
                            current_i = current_index_loc
                            # neck_val = v2_val + (current_i - v2_idx) * neck_slope
                            # 좀 더 안정적인 계산을 위해 V3 기준에서 역산 또는 보간 사용 고려 가능
                            # 단순 직선 가정: V2 가격 + 경과시간 * 기울기
                            neck_val = v2_val + (current_i - v2_idx) * neck_slope


                            # 돌파 확인: 현재 종가 <= 넥라인 값
                            if candle['Close'] <= neck_val:
                                self.stage = "Completed"
                                self.expectation_mode = False
                                self.neckline_level = neck_val # 완성 시점 넥라인 값 저장
                                self.log_event(f"*** Head & Shoulders 패턴 완성! (Neckline Break) *** Price={candle['Close']:.0f}, Neckline={neck_val:.0f}, Slope={neck_slope:.2f}", "INFO")
                        else:
                            self.log_event("경고: 넥라인 계산 위한 V2/V3 인덱스 오류.", "WARNING")

                    except KeyError as e:
                        self.log_event(f"오류: 넥라인 완성 조건 확인 중 가격 데이터 접근 실패 (키={e})", "ERROR")
                    except TypeError as e:
                        self.log_event(f"오류: 넥라인 완성 조건 계산 중 타입 오류: {e}", "ERROR")
                    except Exception as e:
                        self.log_event(f"오류: 넥라인 완성 조건 확인 중 예외 발생: {e}", "ERROR")
                else:
                    self.log_event("경고: 넥라인 완성 조건 확인 위한 V2 또는 V3 정보 부족.", "WARNING")

# --- 신규: Inverse Head and Shoulders 감지기 클래스 ---
class InverseHeadAndShouldersDetector(PatternDetector):
    """Inverse Head and Shoulders 패턴 감지기 (수정 V4 - 규칙 변경 및 옵션 추가)"""
    def __init__(self, v1, data, peaks=None, valleys=None, completion_mode='neckline'): # completion_mode 추가
        super().__init__(v1, data, peaks, valleys)
        self.pattern_type = "IHS"
        self.V1 = v1 # Left Shoulder Valley
        self.completion_mode = completion_mode # 옵션 저장
        self.stage = "LeftShoulderValleyDetected" # Stage 1
        self.log_event(f"Stage 0 -> 1: 감지기 생성 (V1={v1['actual_date'].strftime('%y%m%d')}@ {v1['value']:.0f})", "INFO")

    def log_event(self, message, level="DEBUG"):
        log_date = self.V1['detected_date'].strftime('%Y-%m-%d')
        pattern_start_date = self.V1['actual_date'].strftime('%y%m%d')
        logger.log(getattr(logging, level.upper()), f"[{log_date} / {self.pattern_type}-{pattern_start_date}] {message}")

# InverseHeadAndShouldersDetector 클래스 내
    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None):
        """IH&S 패턴 상태 업데이트 (수정 V4 - 검증 규칙 변경 및 완성 옵션 적용)"""
        if not self.expectation_mode: return

        current_date = candle['date']
        current_close = candle['Close']
        current_high = candle['High']
        current_low = candle['Low']

        # --- 리셋 조건 확인 (대칭 및 스테이지 이름 조정) ---
        if self.V1 and current_low < self.V1['value'] and self.stage == "LeftShoulderValleyDetected":
            self.log_event(f"리셋 (Stage 1): 현재 Low({current_low:.0f}) < V1({self.V1['value']:.0f})", "INFO"); self.reset("V1 저점 하회"); return
        if self.P2_ihs and current_close > self.P2_ihs['value'] and self.stage == "LeftNecklinePeakDetected":
            self.log_event(f"리셋 (Stage 2): 현재 Close({current_close:.0f}) > P2({self.P2_ihs['value']:.0f})", "INFO"); self.reset("P2 고점 상회"); return
        # V2(머리) 저점 돌파 리셋: V2 형성 후 ~ 완성 전까지
        if self.V2_ihs and current_low < self.V2_ihs['value'] and self.stage in ["HeadValleyDetected", "RightNecklinePeakDetected", "AwaitingCompletion"]:
            self.log_event(f"리셋 (Stage {self.stage}): 현재 Low({current_low:.0f}) < V2({self.V2_ihs['value']:.0f})", "INFO"); self.reset("머리 저점 하회"); return
        # P3(오른쪽 넥라인) 형성 중 P2 고점 상회 시 리셋
        if self.P2_ihs and current_close > self.P2_ihs['value'] and self.stage in ["RightNecklinePeakDetected", "AwaitingCompletion"]:
            self.log_event(f"리셋 (Stage {self.stage}): 현재 Close({current_close:.0f}) > P2({self.P2_ihs['value']:.0f})", "INFO"); self.reset("V3/P3 형성 또는 완성 대기 중 P2 상회"); return
        # V3(오른쪽 어깨) 저점 돌파 리셋: V3 형성 후 완성 대기 중
        if self.V3_ihs and current_close < self.V3_ihs['value'] and self.stage == "AwaitingCompletion":
            self.log_event(f"리셋 (Stage AwaitingCompletion): 현재 Close({current_close:.0f}) < V3({self.V3_ihs['value']:.0f})", "INFO"); self.reset("완성 전 V3 하회"); return
        # ---------------------

        # --- 상태별 로직 진행 (대칭) ---
        if self.stage == "LeftShoulderValleyDetected": # Stage 1: P2 찾기
            if newly_registered_peak and newly_registered_peak['index'] > self.V1['index']:
                self.P2_ihs = newly_registered_peak
                self.stage = "LeftNecklinePeakDetected" # Stage 2
                # self.log_event(f"Stage 1 -> 2: P2 후보 감지 {self.P2_ihs['actual_date'].strftime('%y%m%d')}({self.P2_ihs['value']:.0f})")

        elif self.stage == "LeftNecklinePeakDetected": # Stage 2: V2 찾기
            if newly_registered_valley and newly_registered_valley['index'] > self.P2_ihs['index']:
                if newly_registered_valley['value'] < self.V1['value']:
                    self.V2_ihs = newly_registered_valley
                    self.stage = "HeadValleyDetected" # Stage 3
                    # self.log_event(f"Stage 2 -> 3: V2(머리) 감지 {self.V2_ihs['actual_date'].strftime('%y%m%d')}({self.V2_ihs['value']:.0f})")
                # else: self.reset("Internal Error: V2 >= V1"); return

        elif self.stage == "HeadValleyDetected": # Stage 3: P3 찾기
            if newly_registered_peak and newly_registered_peak['index'] > self.V2_ihs['index']:
                self.P3_ihs = newly_registered_peak
                self.stage = "RightNecklinePeakDetected" # Stage 4
                # self.log_event(f"Stage 3 -> 4: P3 감지 {self.P3_ihs['actual_date'].strftime('%y%m%d')}({self.P3_ihs['value']:.0f})")
                # P3 vs P2 몸통 검증 제거됨

        elif self.stage == "RightNecklinePeakDetected": # Stage 4: V3 찾기 및 검증 (균형/대칭 규칙 적용)
            if newly_registered_valley and newly_registered_valley['index'] > self.P3_ihs['index']:
                potential_v3 = newly_registered_valley
                self.log_event(f"Stage 4: V3 후보 발견 {potential_v3['actual_date'].strftime('%y%m%d')}({potential_v3['value']:.0f}). 검증 시작.", "DEBUG")

                # --- 검증 규칙 적용 ---
                v3_valid = True # 검증 통과 여부 플래그

                # 검증 0: V3 > V2 (기본 조건)
                if not (potential_v3.get('value', -np.inf) > self.V2_ihs.get('value', np.inf)):
                    v3_valid = False; self.log_event(f"  - V3 후보 검증 실패: V3({potential_v3.get('value'):.0f}) <= V2({self.V2_ihs.get('value'):.0f})", "DEBUG")

                # 필요한 데이터 준비 (종가 기준)
                if v3_valid:
                    try:
                        v1_val = self.data.loc[self.V1['actual_date'], 'Low']
                        p2_val = self.data.loc[self.P2_ihs['actual_date'], 'High']
                        v2_val = self.data.loc[self.V2_ihs['actual_date'], 'Low']
                        p3_val = self.data.loc[self.P3_ihs['actual_date'], 'High']
                        v3_val = self.data.loc[potential_v3['actual_date'], 'Low']
                        v3_idx = potential_v3['index']; v2_idx = self.V2_ihs['index']; v1_idx = self.V1['index']
                        p3_idx = self.P3_ihs['index']; p2_idx = self.P2_ihs['index'] # 균형 규칙 위해 추가

                    except KeyError as e:
                        self.log_event(f"오류: 검증 위한 가격 데이터 접근 실패 (날짜={e})", "ERROR"); self.reset("Data access error"); return
                    except Exception as e:
                        self.log_event(f"오류: 검증 데이터 준비 중 오류: {e}", "ERROR"); self.reset("Data prep error"); return

                    # 검증 1: 균형 규칙 (Balance Rule - 대칭)
                    r_midpoint = 0.5 * (v3_val + p3_val) # 오른쪽 어깨(V3)-겨드랑이(P3)
                    l_midpoint = 0.5 * (v1_val + p2_val) # 왼쪽 어깨(V1)-겨드랑이(P2)
                    if v1_val > r_midpoint or v3_val > l_midpoint:
                        v3_valid = False
                        self.log_event(f"  - V3 후보 검증 실패: 균형 규칙 위반 (V1={v1_val:.0f} vs R_Mid={r_midpoint:.0f} or V3={v3_val:.0f} vs L_Mid={l_midpoint:.0f})", "DEBUG")

                    # 검증 2: 대칭 규칙 (Symmetry Rule - 대칭)
                    if v3_valid and v3_idx > v2_idx and v2_idx > v1_idx:
                        r_to_h_time = v3_idx - v2_idx
                        l_to_h_time = v2_idx - v1_idx
                        if r_to_h_time <= 0 or l_to_h_time <= 0:
                            v3_valid = False
                            self.log_event("  - V3 후보 검증 실패: 대칭 규칙 시간 계산 오류 (시간 차이 <= 0)", "WARNING")
                        elif r_to_h_time > 2.5 * l_to_h_time or l_to_h_time > 2.5 * r_to_h_time:
                            v3_valid = False
                            self.log_event(f"  - V3 후보 검증 실패: 대칭 규칙 위반 (L->H={l_to_h_time}, H->R={r_to_h_time})", "DEBUG")
                    elif v3_valid:
                        v3_valid = False
                        self.log_event("  - V3 후보 검증 실패: 대칭 규칙 시간 계산 오류 (인덱스 순서 오류)", "WARNING")

                # 모든 검증 통과 시 V3 확정 및 상태 변경
                if v3_valid:
                    self.V3_ihs = potential_v3 # V3 확정
                    self.stage = "AwaitingCompletion" # Stage 5
                    self.log_event(f"Stage 4 -> 5: V3 감지 및 검증 통과 {self.V3_ihs['actual_date'].strftime('%y%m%d')}({self.V3_ihs['value']:.0f}). 완성 조건 확인 시작.", "INFO")
                # else: 검증 실패 시 다음 Valley 후보 기다림

        elif self.stage == "AwaitingCompletion": # Stage 5: 완성 조건 확인
            # 현재 캔들의 인덱스 가져오기
            try:
                current_index_loc = self.data.index.get_loc(candle['date'])
            except KeyError:
                self.log_event(f"오류: 현재 캔들 날짜({candle['date']})를 self.data 인덱스에서 찾을 수 없음.", "ERROR")
                self.reset("Internal data index error")
                return

            if current_index_loc <= 0:
                self.log_event("경고: 직전 캔들 없어 완성 조건 확인 불가 (인덱스 0).", "WARNING"); return

            prev_candle = self.data.iloc[current_index_loc - 1] # 직전 캔들

            # 옵션별 완성 조건 확인
            if self.completion_mode == 'aggressive':
                # 조건: 양봉 마감 & 종가 > 직전 고점
                if candle['Close'] > candle['Open'] and candle['Close'] > prev_candle['High']:
                    self.stage = "Completed"
                    self.expectation_mode = False
                    self.log_event(f"*** Inverse Head & Shoulders 패턴 완성! (Aggressive) *** Price={candle['Close']:.0f}, Prev High={prev_candle['High']:.0f}", "INFO")
            elif self.completion_mode == 'neckline':
                # 기울어진 넥라인 돌파 확인
                if self.P2_ihs and self.P3_ihs: # P2, P3 정보 필요
                    try:
                        p2_idx = self.P2_ihs['index']; p3_idx = self.P3_ihs['index']
                        # 넥라인은 P2, P3의 High 값을 기준으로 계산 (Close 대신 High 사용)
                        p2_val = self.P2_ihs.get('value') # P2 High 값
                        p3_val = self.P3_ihs.get('value') # P3 High 값

                        if p2_val is None or p3_val is None:
                            self.log_event("경고: 넥라인 계산 위한 P2 또는 P3 value 없음.", "WARNING"); return

                        if p3_idx > p2_idx:
                            neck_run = p3_idx - p2_idx
                            neck_rise = p3_val - p2_val
                            neck_slope = neck_rise / neck_run if neck_run != 0 else 0

                            current_i = current_index_loc
                            # neck_val = p2_val + (current_i - p2_idx) * neck_slope
                            # P3 기준 역산 또는 보간
                            neck_val = p2_val + (current_i - p2_idx) * neck_slope


                            # 돌파 확인: 현재 종가 >= 넥라인 값
                            if candle['Close'] >= neck_val:
                                self.stage = "Completed"
                                self.expectation_mode = False
                                self.neckline_level = neck_val
                                self.log_event(f"*** Inverse Head & Shoulders 패턴 완성! (Neckline Break) *** Price={candle['Close']:.0f}, Neckline={neck_val:.0f}, Slope={neck_slope:.2f}", "INFO")
                        else:
                            self.log_event("경고: 넥라인 계산 위한 P2/P3 인덱스 오류.", "WARNING")

                    except KeyError as e:
                        self.log_event(f"오류: 넥라인 완성 조건 확인 중 가격 데이터 접근 실패 (키={e})", "ERROR")
                    except TypeError as e:
                        self.log_event(f"오류: 넥라인 완성 조건 계산 중 타입 오류: {e}", "ERROR")
                    except Exception as e:
                        self.log_event(f"오류: 넥라인 완성 조건 확인 중 예외 발생: {e}", "ERROR")
                else:
                    self.log_event("경고: 넥라인 완성 조건 확인 위한 P2 또는 P3 정보 부족.", "WARNING")                
# --- DoubleBottomDetector 전체 코드 (수정된 __init__ 포함) ---
class DoubleBottomDetector(PatternDetector):
    """Double Bottom 패턴 감지기"""
    def __init__(self, valley, data, peaks=None, valleys=None): # band_option 파라미터 제거
        super().__init__(valley, data, peaks, valleys) # 기본 생성자 호출
        self.pattern_type = "DB"
        # band_option 변수 제거

        # --- 필요한 캔들 정보 조회 및 유효성 검사 ---
        try:
            # extremum 객체에 필요한 키가 모두 있는지, 타입이 맞는지 확인
            required_keys = ['detected_date', 'actual_date', 'open', 'high', 'low', 'close', 'value', 'index']
            if not all(k in self.first_extremum for k in required_keys):
                    raise ValueError("필요한 극점 정보(날짜, OHLC, 값, 인덱스)가 extremum 객체에 없습니다.")
            if not isinstance(self.first_extremum['detected_date'], pd.Timestamp) or \
                not isinstance(self.first_extremum['actual_date'], pd.Timestamp):
                    raise ValueError("극점 날짜 정보가 Timestamp 형식이 아닙니다.")

            # 확인 캔들 정보 조회
            self.confirmation_candle = data.loc[self.first_extremum['detected_date']].to_dict()
            self.confirmation_candle['date'] = self.first_extremum['detected_date']
            # 실제 캔들 정보 조회 (extremum 객체에서 직접 사용)
            self.actual_candle = {
                'date': self.first_extremum['actual_date'],
                'Open': self.first_extremum['open'], 'High': self.first_extremum['high'],
                'Low': self.first_extremum['low'], 'Close': self.first_extremum['close']
            }
            self.candle_history.append(self.confirmation_candle) # 히스토리 시작

            # 확정 캔들이 양봉인지 확인 (DB 시작 조건)
            if self.confirmation_candle['Close'] <= self.confirmation_candle['Open']:
                    self.log_event(f"경고: 확정 캔들({self.confirmation_candle['date'].strftime('%Y-%m-%d')})이 양봉 아님.", "WARNING", self.confirmation_candle['date'])
                    self.reset("초기 확정 캔들 조건 불충족"); return

        except KeyError as e:
            self.log_event(f"오류: DB 생성 시 캔들 데이터 접근 실패 - 날짜 {e}", "ERROR", pd.Timestamp.now()); self.reset(f"Candle data error ({e})"); return
        except ValueError as e:
            self.log_event(f"오류: DB 생성 시 극점 정보 부족 또는 타입 오류 - {e}", "ERROR", pd.Timestamp.now()); self.reset("Extremum data error"); return
        except Exception as e:
            self.log_event(f"오류: DB 생성 시 캔들 데이터 처리 중 오류: {e}", "ERROR", pd.Timestamp.now()); self.reset("Candle processing error"); return

        # --- DB 속성 초기화 ---
        # actual_candle이 양봉인지 음봉인지 확인
        is_actual_positive = self.actual_candle['Close'] > self.actual_candle['Open']
        
        # 밴드 계산 - band.high를 actual_candle의 '몸통 위'로 변경
        self.band = {
            'low': self.actual_candle['Low'],
            'high': self.actual_candle['Close'] if is_actual_positive else self.actual_candle['Open']
        }
        self.positive_candles = []
        self.second_valley = None
        self.straight_peak = self._get_straight_peak() # Straight Peak 계산

        # --- 양봉 기준 설정 (단순화) ---
        self.first_positive_candle = self.confirmation_candle  # 확정 캔들은 이미 양봉임이 확인됨

        # --- 초기 검증 ---
        if self.straight_peak is None: 
            self.log_event("경고: 직전 Peak 없음.", "WARNING")
            self.reset("직전 Peak 정보 없음")
            return

        # --- 두 캔들 모두 양봉이면 초기 stage를 Reentry로 설정 ---
        if is_actual_positive:
            self.stage = "Reentry"
            straight_peak_str = f"{self.straight_peak:.2f}" if self.straight_peak is not None else "N/A"
            self.log_event(f"Stage Initial -> Reentry: 두 캔들 모두 양봉이므로 Pullback 단계 건너뜀. Valley={valley['actual_date'].strftime('%y%m%d')}@ {valley['value']:.0f}, Band=[{self.band['low']:.0f},{self.band['high']:.0f}], StrPeak={straight_peak_str}", "INFO", valley['detected_date'])
        else:
            # --- 초기화 성공 후 Stage 설정 및 로그 ---
            self.stage = "Pullback"
            straight_peak_str = f"{self.straight_peak:.2f}" if self.straight_peak is not None else "N/A"
            self.log_event(f"Stage Initial -> Pullback: DB 감지기 생성. Valley={valley['actual_date'].strftime('%y%m%d')}@ {valley['value']:.0f}, Band=[{self.band['low']:.0f},{self.band['high']:.0f}], StrPeak={straight_peak_str}", "INFO", valley['detected_date'])

    def _get_straight_peak(self):
         # 1. 첫 번째 Valley의 시간적 위치(인덱스)를 가져옵니다.
        valley_index = self.first_extremum['index']
        # 2. Detector가 알고 있는 모든 Peak 목록(self.peaks)에서 조건을 만족하는 Peak들만 골라냅니다.
        #    조건 1: Peak의 시간적 위치(p['index'])가 첫 번째 Valley의 위치(valley_index)보다 '이전'이어야 합니다.
        #    조건 2: Peak의 타입(p.get('type'))이 반드시 'js_peak' (주요 고점)이어야 합니다. (Secondary Peak는 제외)
        prior_peaks = [p for p in self.peaks if p['index'] < valley_index and p.get('type') == 'js_peak']
        # 3. 조건을 만족하는 JS Peak들이 하나 이상 존재하는지 확인합니다.
        if prior_peaks: 
            # 4. 존재한다면, 그중에서 시간적으로 가장 마지막(가장 최근)에 발생한 JS Peak를 찾습니다.
            #    (max 함수의 key=lambda x: x['index']는 인덱스 값이 가장 큰 Peak, 즉 가장 최근 Peak를 찾으라는 의미입니다.)
            # 5. 찾은 가장 마지막 JS Peak의 가격 값('value')을 반환합니다. 이것이 straight_peak 값이 됩니다.
            return max(prior_peaks, key=lambda x: x['index'])['value']
        else: return None

    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None): # 시그니처 통일
        """DB 패턴 상태 업데이트 (V015 로직 기반)"""
        if not self.expectation_mode: return
        # straight_peak None 체크 강화
        if self.straight_peak is None:
            if not self.is_failed(): self.reset("Internal: Straight Peak is None")
            return

        # candle 딕셔너리 타입 및 키 확인
        if not isinstance(candle, dict) or not all(k in candle for k in ['date', 'Close', 'Open', 'Low']):
            # 필요한 정보가 없으면 업데이트 중단 또는 오류 처리
            self.log_event(f"오류: update 메서드에 전달된 candle 객체 정보 부족.", "ERROR")
            return

        self.candle_history.append(candle)
        current_date = candle['date']

        if self.stage == "Pullback":
            # 밴드 존재 여부 확인 추가
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                reason = f"Close({candle['Close']:.2f}) < Band Low({self.band.get('low', 'N/A'):.2f})" if self.band and candle['Close'] < self.band['low'] else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
            # first_positive_candle 존재 여부 확인 추가
            if candle['Close'] > candle['Open'] and self.first_positive_candle and candle['Close'] > self.first_positive_candle['Close']:
                self.stage = "Reentry"; self.log_event("Stage Pullback -> Reentry", "DEBUG", candle['date'])

        elif self.stage == "Reentry":
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                reason = f"Close({candle['Close']:.2f}) < Band Low({self.band.get('low', 'N/A'):.2f})" if self.band and candle['Close'] < self.band['low'] else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
            if self.band and candle['Low'] <= self.band['high']: # band None 체크
                self.second_valley = candle['Low']
                self.stage = "reentry_confirmation"; self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Valley Cand: {self.second_valley:.0f})", "DEBUG", candle['date'])
                if self.second_valley < self.band['low']:
                    self.log_event(f"Band Low 업데이트: {self.band['low']:.0f} -> {self.second_valley:.0f}", "DEBUG", candle['date']); self.band['low'] = self.second_valley

        elif self.stage == "reentry_confirmation":
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                reason = f"Close({candle['Close']:.2f}) < Band Low({self.band.get('low', 'N/A'):.2f})" if self.band and candle['Close'] < self.band['low'] else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
                
            # 완성 조건 수정: 양봉이고 윗꼬리 길이가 전체 캔들 길이의 20% 미만인 경우
            if candle['Close'] > candle['Open']:  # 양봉 확인
                self.stage = "Completed"
                self.expectation_mode = False
                self.log_event(f"*** Double Bottom 패턴 완성! *** Price={candle['Close']:.0f}", "INFO", candle['date'])
        

# --- DoubleTopDetector 전체 코드 (수정된 __init__ 포함) ---
class DoubleTopDetector(PatternDetector):
    """Double Top 패턴 감지기"""
    def __init__(self, peak, data, peaks=None, valleys=None): # band_option 파라미터 제거
        super().__init__(peak, data, peaks, valleys) # 기본 생성자 호출
        self.pattern_type = "DT"
        # band_option 변수 제거

        # --- 필요한 캔들 정보 조회 및 유효성 검사 ---
        try:
            required_keys = ['detected_date', 'actual_date', 'open', 'high', 'low', 'close', 'value', 'index']
            if not all(k in self.first_extremum for k in required_keys):
                raise ValueError("필요한 극점 정보(날짜, OHLC, 값, 인덱스)가 extremum 객체에 없습니다.")
            if not isinstance(self.first_extremum['detected_date'], pd.Timestamp) or \
                not isinstance(self.first_extremum['actual_date'], pd.Timestamp):
                raise ValueError("극점 날짜 정보가 Timestamp 형식이 아닙니다.")

            self.confirmation_candle = data.loc[self.first_extremum['detected_date']].to_dict()
            self.confirmation_candle['date'] = self.first_extremum['detected_date']
            self.actual_candle = {
                'date': self.first_extremum['actual_date'],
                'Open': self.first_extremum['open'], 'High': self.first_extremum['high'],
                'Low': self.first_extremum['low'], 'Close': self.first_extremum['close']
            }
            self.candle_history.append(self.confirmation_candle)

            # 확정 캔들이 음봉인지 확인 (DT 시작 조건)
            if self.confirmation_candle['Close'] >= self.confirmation_candle['Open']:
                self.log_event(f"경고: 확정 캔들({self.confirmation_candle['date'].strftime('%Y-%m-%d')})이 음봉 아님.", "WARNING", self.confirmation_candle['date'])
                self.reset("초기 확정 캔들 조건 불충족"); return

        except KeyError as e:
            self.log_event(f"오류: DT 생성 시 캔들 데이터 접근 실패 - 날짜 {e}", "ERROR", pd.Timestamp.now()); self.reset(f"Candle data error ({e})"); return
        except ValueError as e:
            self.log_event(f"오류: DT 생성 시 극점 정보 부족 또는 타입 오류 - {e}", "ERROR", pd.Timestamp.now()); self.reset("Extremum data error"); return
        except Exception as e:
            self.log_event(f"오류: DT 생성 시 캔들 데이터 처리 중 오류: {e}", "ERROR", pd.Timestamp.now()); self.reset("Candle processing error"); return

        # --- DT 속성 초기화 ---
        # actual_candle이 음봉인지 양봉인지 확인
        is_actual_negative = self.actual_candle['Close'] < self.actual_candle['Open']
        
        # 밴드 계산 - band.low를 actual_candle의 '몸통 밑'으로 변경
        self.band = {
            'high': self.actual_candle['High'],
            'low': self.actual_candle['Close'] if is_actual_negative else self.actual_candle['Open']
        }
        self.negative_candles = []
        self.second_peak = None
        self.straight_valley = self._get_straight_valley() # Straight Valley 계산

        # --- 음봉 기준 설정 (단순화) ---
        self.first_negative_candle = self.confirmation_candle  # 확정 캔들은 이미 음봉임이 확인됨

        # --- 초기 검증 ---
        if self.straight_valley is None: 
            self.log_event("경고: 직전 Valley 없음.", "WARNING")
            self.reset("직전 Valley 정보 없음")
            return

        # --- 두 캔들 모두 음봉이면 초기 stage를 Reentry로 설정 ---
        if is_actual_negative:
            self.stage = "Reentry"
            straight_valley_str = f"{self.straight_valley:.2f}" if self.straight_valley is not None else "N/A"
            self.log_event(f"Stage Initial -> Reentry: 두 캔들 모두 음봉이므로 Pullback 단계 건너뜀. Peak={peak['actual_date'].strftime('%y%m%d')}@ {peak['value']:.0f}, Band=[{self.band['low']:.0f},{self.band['high']:.0f}], StrValley={straight_valley_str}", "INFO", peak['detected_date'])
        else:
            # --- 초기화 성공 후 Stage 설정 및 로그 ---
            self.stage = "Pullback"
            straight_valley_str = f"{self.straight_valley:.2f}" if self.straight_valley is not None else "N/A"
            self.log_event(f"Stage Initial -> Pullback: DT 감지기 생성. Peak={peak['actual_date'].strftime('%y%m%d')}@ {peak['value']:.0f}, Band=[{self.band['low']:.0f},{self.band['high']:.0f}], StrValley={straight_valley_str}", "INFO", peak['detected_date'])

    def _get_straight_valley(self):
        """첫 번째 Peak 형성 직전의 마지막 JS Valley 값"""
        peak_index = self.first_extremum['index']
        # self.valleys에는 JS와 Secondary 포함. JS Valley만 필터링
        prior_valleys = [v for v in self.valleys if v['index'] < peak_index and v.get('type') == 'js_valley']
        if prior_valleys: return max(prior_valleys, key=lambda x: x['index'])['value']
        else: return None

    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None): # 시그니처 통일
        """DT 패턴 상태 업데이트"""
        if not self.expectation_mode: return
        if self.straight_valley is None:
            if not self.is_failed(): self.reset("Internal: Straight Valley is None")
            return

        # candle 딕셔너리 타입 및 키 확인
        if not isinstance(candle, dict) or not all(k in candle for k in ['date', 'Close', 'Open', 'High', 'Low']):
            self.log_event(f"오류: update 메서드에 전달된 candle 객체 정보 부족.", "ERROR")
            return

        self.candle_history.append(candle)
        current_date = candle['date']

        if self.stage == "Pullback":
            if (self.band and candle['Close'] > self.band['high']) or candle['Close'] < self.straight_valley:
                reason = f"Close({candle['Close']:.2f}) > Band High({self.band.get('high', 'N/A'):.2f})" if self.band and candle['Close'] > self.band['high'] else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
            if candle['Close'] < candle['Open']:
                # first_negative_candle 존재 여부 확인 추가
                if self.first_negative_candle and candle['Close'] < self.first_negative_candle['Close']:
                    self.stage = "Reentry"; self.log_event("Stage Pullback -> Reentry", "DEBUG", candle['date'])

        elif self.stage == "Reentry":
            if (self.band and candle['Close'] > self.band['high']) or candle['Close'] < self.straight_valley:
                reason = f"Close({candle['Close']:.2f}) > Band High({self.band.get('high', 'N/A'):.2f})" if self.band and candle['Close'] > self.band['high'] else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
            if self.band and candle['High'] >= self.band['low']: # band None 체크
                self.second_peak = candle['High']
                self.stage = "reentry_confirmation"; self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Peak Cand: {self.second_peak:.0f})", "DEBUG", candle['date'])
                if self.second_peak > self.band['high']:
                    self.log_event(f"Band High 업데이트: {self.band['high']:.0f} -> {self.second_peak:.0f}", "DEBUG", candle['date']); self.band['high'] = self.second_peak

        elif self.stage == "reentry_confirmation":
            if (self.band and candle['Close'] > self.band['high']) or candle['Close'] < self.straight_valley:
                reason = f"Close({candle['Close']:.2f}) > Band High({self.band.get('high', 'N/A'):.2f})" if self.band and candle['Close'] > self.band['high'] else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
                
            # 완성 조건 수정: 음봉이고 아래꼬리 길이가 전체 캔들 길이의 20% 미만인 경우
            if candle['Close'] < candle['Open']:  # 음봉 확인
                self.stage = "Completed"
                self.expectation_mode = False
                self.log_event(f"*** Double Top 패턴 완성! *** Price={candle['Close']:.0f}", "INFO", candle['date'])


class PatternManager:
    def __init__(self, data):
        """
        모든 패턴 감지기를 관리하는 클래스.

        Args:
            data (pd.DataFrame): 전체 가격 데이터.
        """
        self.data = data
        self.active_detectors: List[PatternDetector] = []  # 현재 활성화된 모든 패턴 감지기
        self.completed_dt: List[Dict] = []              # 완성된 Double Top 패턴 정보
        self.completed_db: List[Dict] = []              # 완성된 Double Bottom 패턴 정보
        self.completed_hs: List[Dict] = []              # 완성된 Head and Shoulders 패턴 정보
        self.completed_ihs: List[Dict] = []             # 완성된 Inverse H&S 패턴 정보
        self.failed_detectors: List[PatternDetector] = [] # 실패/리셋된 감지기 목록

    def _find_extremum_before(self, all_extremums: List[Dict], target_index: int, extremum_type_suffix: str) -> Optional[Dict]:
        """
        (매니저 내부 헬퍼) 정렬된 전체 극점 리스트에서
        주어진 target_index 이전에 발생한 가장 마지막 특정 타입 극점을 찾습니다.

        Args:
            all_extremums (List[Dict]): 시간순으로 정렬된 전체 극점 리스트 (JS + Sec). 각 딕셔너리는 'index', 'type' 키를 포함해야 함.
            target_index (int): 기준 인덱스.
            extremum_type_suffix (str): 찾고자 하는 극점 타입 접미사 ('peak' 또는 'valley').

        Returns:
            Optional[Dict]: 찾은 극점 딕셔너리 또는 None.
        """
        # extremum 딕셔너리에 'type' 키가 없을 경우를 대비하여 .get('',) 사용
        candidates = [e for e in all_extremums if e.get('index', -1) < target_index and e.get('type','').endswith(extremum_type_suffix)]
        return max(candidates, key=lambda x: x['index']) if candidates else None
    
    def _find_hs_ihs_structural_points(self, all_extremums: List[Dict], lookback_limit: int = 15) -> Optional[Dict[str, Dict]]:
        """
        (헬퍼 함수) 시간순 정렬된 전체 극점 리스트에서 H&S 또는 IH&S의
        구조적 극점(P1,V2,P2,V3 또는 V1,P2,V2,P3) 후보를 식별합니다.
        연속된 동일 타입 극점 중 가장 유의미한 값(최고 P, 최저 V)만 선택합니다.

        Args:
            all_extremums (List[Dict]): 시간순 정렬된 전체 극점 리스트.
            lookback_limit (int): 구조를 찾기 위해 최대 몇 개의 극점까지 거슬러 올라갈지 제한.

        Returns:
            Optional[Dict[str, Dict]]: 찾은 구조적 극점 딕셔너리 {'P1': {...}, 'V2': {...}, ...} 또는 None.
                                    H&S의 경우 'pattern_type': 'HS', IH&S의 경우 'pattern_type': 'IHS' 포함.
        """
        if len(all_extremums) < 4:
            return None

        structural_points = {}
        last_extremum = all_extremums[-1]
        current_index = len(all_extremums) - 1
        points_found = 0
        consecutive_buffer = [] # 연속된 동일 타입 극점 임시 저장

        # 패턴 타입 결정 및 목표 극점 설정
        if last_extremum.get('type', '').endswith('valley'):
            pattern_type = 'HS'
            target_sequence = ['V3', 'P2', 'V2', 'P1'] # 찾아야 할 순서 (V3는 이미 찾음)
            structural_points['V3'] = last_extremum
            current_target_role = 'P2'
            current_target_type = 'peak'
            points_found = 1
        elif last_extremum.get('type', '').endswith('peak'):
            pattern_type = 'IHS'
            target_sequence = ['P3', 'V2', 'P2', 'V1'] # 찾아야 할 순서 (P3는 이미 찾음)
            structural_points['P3'] = last_extremum
            current_target_role = 'V2'
            current_target_type = 'valley'
            points_found = 1
        else:
            return None # 마지막 극점 타입 불분명

        # 루프 시작점: 마지막 극점 바로 이전부터
        search_index = current_index - 1
        lookback_count = 0

        while search_index >= 0 and points_found < 4 and lookback_count < lookback_limit:
            current_point = all_extremums[search_index]
            current_type = 'peak' if current_point.get('type', '').endswith('peak') else 'valley'

            if current_type == current_target_type:
                # 목표 타입과 일치 -> 연속 버퍼에 추가
                consecutive_buffer.append(current_point)
            else:
                # 다른 타입 발견 -> 이전 버퍼 처리 및 새 타입 검색 시작
                if consecutive_buffer:
                    # 이전 버퍼에서 대표 극점 선택
                    representative_point = None
                    if current_target_type == 'peak':
                        representative_point = max(consecutive_buffer, key=lambda x: x.get('value', -np.inf))
                    else: # valley
                        representative_point = min(consecutive_buffer, key=lambda x: x.get('value', np.inf))

                    if representative_point:
                        structural_points[current_target_role] = representative_point
                        points_found += 1
                        if points_found == 4: break # 필요한 4개 다 찾음

                        # 다음 목표 설정
                        next_role_index = target_sequence.index(current_target_role) + 1
                        if next_role_index < len(target_sequence):
                            current_target_role = target_sequence[next_role_index]
                            current_target_type = 'peak' if current_target_role.startswith('P') else 'valley'
                        else: break # 예상치 못한 상황, 루프 종료

                # 새 타입 검색 준비
                consecutive_buffer = [current_point] # 새 버퍼 시작
                # current_target_type = current_type # 이미 위에서 설정됨

            search_index -= 1
            lookback_count += 1

        # 루프 종료 후 마지막 버퍼 처리
        if points_found < 4 and consecutive_buffer:
            representative_point = None
            if current_target_type == 'peak':
                representative_point = max(consecutive_buffer, key=lambda x: x.get('value', -np.inf))
            else: # valley
                representative_point = min(consecutive_buffer, key=lambda x: x.get('value', np.inf))

            if representative_point:
                structural_points[current_target_role] = representative_point
                points_found += 1

        # 최종 확인
        if points_found == 4:
            structural_points['pattern_type'] = pattern_type
            # 시간 순서 재확인 (P1/V1 index < V2/P2 index < P2/V2 index < V3/P3 index)
            indices = []
            roles = target_sequence[::-1] # P1, V2, P2, V3 순서 또는 V1, P2, V2, P3 순서
            valid_sequence = True
            for role in roles:
                if role not in structural_points:
                    valid_sequence = False; break
                indices.append(structural_points[role]['index'])

            if valid_sequence and all(indices[i] < indices[i+1] for i in range(len(indices)-1)):
                return structural_points
            else:
                #logger.debug(f"구조적 극점 시간 순서 오류: {indices}")
                logger.debug(f"Found structural points for {pattern_type}: P1/V1={structural_points.get(roles[0],{}).get('index')} V2/P2={structural_points.get(roles[1],{}).get('index')} P2/V2={structural_points.get(roles[2],{}).get('index')} V3/P3={structural_points.get(roles[3],{}).get('index')}")
                return None # 시간 순서가 맞지 않으면 유효하지 않음
        else:
            logger.debug(f"Could not find 4 structural points ({points_found} found).") # 로그 추가
            return None

    # PatternManager 클래스 내
# PatternManager 클래스 내
    def check_for_hs_ihs_start(self, peaks: List[Dict], valleys: List[Dict], completion_mode: str = 'neckline'): # completion_mode 추가 (기본값 'aggressive')
        """
        (수정 V4) 새로운 극점 발생 시 H&S 또는 IH&S 패턴의 시작 가능성을
        구조적 극점 식별 로직(연속 P/V 처리 포함) 및 기본 가격 조건 검증 후 감지기를 생성합니다.
        세부 검증(균형, 대칭) 및 완성 조건은 Detector 내부에서 처리합니다.

        Args:
            peaks (List[Dict]): 현재까지 등록된 모든 Peak (JS + Sec) 리스트.
            valleys (List[Dict]): 현재까지 등록된 모든 Valley (JS + Sec) 리스트.
            completion_mode (str): 패턴 완성 조건 옵션 ('aggressive' 또는 'neckline').
        """
        all_extremums = sorted(peaks + valleys, key=lambda x: x.get('index', -1))
        if len(all_extremums) < 4: return

        # 1. 구조적 극점 후보 찾기 (P1,V2,P2,V3 또는 V1,P2,V2,P3)
        structural_points = self._find_hs_ihs_structural_points(all_extremums)
        # logger.debug(f"Checking for H&S/IHS start: Structural points found: {'Yes' if structural_points else 'No'}") # 디버깅 필요 시 활성화

        if structural_points:
            pattern_type = structural_points.get('pattern_type')
            log_date = all_extremums[-1].get('detected_date', pd.Timestamp.now()).strftime('%Y-%m-%d')

            try: # 딕셔너리 키 접근 및 검증 로직 오류 방지
                if pattern_type == 'HS':
                    p1 = structural_points.get('P1')
                    v2 = structural_points.get('V2')
                    p2 = structural_points.get('P2')
                    v3 = structural_points.get('V3')

                    # logger.debug(f"[{log_date}] Checking H&S candidate: P1={p1.get('index')} V2={v2.get('index')} P2={p2.get('index')} V3={v3.get('index')}") # 디버깅 필요 시 활성화

                    if not all([p1, v2, p2, v3]):
                        # logger.warning(f"[{log_date}] H&S 구조적 포인트 식별 실패.") # 이미 헬퍼 함수에서 로깅됨
                        return

                    # 2. 기본 가격 조건 검증 (P2 > P1 만 확인)
                    is_valid = True
                    # 검증 1: P2 > P1
                    if not (p2.get('value', -np.inf) > p1.get('value', -np.inf)):
                        is_valid = False; logger.debug(f"[{log_date}] H&S Initial Rule Fail: P2({p2.get('value'):.0f}) <= P1({p1.get('value'):.0f})")
                    # --- V3 vs V2 몸통 검증 로직 제거됨 ---

                    # 3. 유효성 검증 통과 시 감지기 생성 시도
                    if is_valid:
                        # 동일한 P1으로 시작하는 활성 H&S 감지기가 없는지 확인
                        if not any(isinstance(d, HeadAndShouldersDetector) and d.P1 and d.P1.get('index') == p1.get('index') for d in self.active_detectors):
                            p1_date_str = p1.get('actual_date', pd.Timestamp('NaT')).strftime('%y%m%d') if isinstance(p1.get('actual_date'), pd.Timestamp) else 'N/A'
                            logger.info(f"[{log_date}] H&S 패턴 후보 감지. P1={p1_date_str}, Completion Mode='{completion_mode}'")

                            # Detector 생성 시 completion_mode 전달
                            detector = HeadAndShouldersDetector(p1, self.data, peaks, valleys, completion_mode='aggressive')
                            if not detector.is_failed():
                                detector.V2 = v2; detector.P2 = p2; detector.V3 = v3
                                detector.stage = "RightNecklineValleyDetected" # V3까지 찾음, P3 탐색 및 검증 단계
                                self.active_detectors.append(detector)
                            else:
                                if detector not in self.failed_detectors: self.failed_detectors.append(detector)

                elif pattern_type == 'IHS':
                    v1 = structural_points.get('V1')
                    p2 = structural_points.get('P2')
                    v2 = structural_points.get('V2')
                    p3 = structural_points.get('P3')

                    # logger.debug(f"[{log_date}] Checking IHS candidate: V1={v1.get('index')} P2={p2.get('index')} V2={v2.get('index')} P3={p3.get('index')}") # 디버깅 필요 시 활성화

                    if not all([v1, p2, v2, p3]):
                         # logger.warning(f"[{log_date}] IHS 구조적 포인트 식별 실패.")
                         return

                    # 2. 기본 가격 조건 검증 (V2 < V1 만 확인)
                    is_valid = True
                    # 검증 1: V2 < V1
                    if not (v2.get('value', np.inf) < v1.get('value', np.inf)):
                        is_valid = False; logger.debug(f"[{log_date}] IHS Initial Rule Fail: V2({v2.get('value'):.0f}) >= V1({v1.get('value'):.0f})")
                    # --- P3 vs P2 몸통 검증 로직 제거됨 ---

                    # 3. 유효성 검증 통과 시 감지기 생성 시도
                    if is_valid:
                        # 동일한 V1으로 시작하는 활성 IH&S 감지기가 없는지 확인
                        if not any(isinstance(d, InverseHeadAndShouldersDetector) and d.V1 and d.V1.get('index') == v1.get('index') for d in self.active_detectors):
                            v1_date_str = v1.get('actual_date', pd.Timestamp('NaT')).strftime('%y%m%d') if isinstance(v1.get('actual_date'), pd.Timestamp) else 'N/A'
                            logger.info(f"[{log_date}] IH&S 패턴 후보 감지. V1={v1_date_str}, Completion Mode='{completion_mode}'")

                            # Detector 생성 시 completion_mode 전달
                            detector = InverseHeadAndShouldersDetector(v1, self.data, peaks, valleys, completion_mode='aggressive')
                            if not detector.is_failed():
                                detector.P2_ihs = p2; detector.V2_ihs = v2; detector.P3_ihs = p3
                                detector.stage = "RightNecklinePeakDetected" # P3까지 찾음, V3 탐색 및 검증 단계
                                self.active_detectors.append(detector)
                            else:
                                if detector not in self.failed_detectors: self.failed_detectors.append(detector)

            except KeyError as e:
                logger.error(f"[{log_date}] H&S/IH&S 후보 검증 중 키 오류: {e}. 극점 정보 확인 필요.")
            except TypeError as e:
                logger.error(f"[{log_date}] H&S/IH&S 후보 검증 중 타입 오류: {e}. 극점 정보 확인 필요.")
            except Exception as e:
                logger.error(f"[{log_date}] H&S/IH&S 후보 검증 중 예외 발생: {e}")

    def add_detector(self, pattern_type: str, extremum: Dict, data: pd.DataFrame, js_peaks: List[Dict], js_valleys: List[Dict]):
        """DT/DB 감지기 추가 로직 (수정된 생성자 호출 방식)"""
        detector = None
        # DT/DB는 JS Peak/Valley만 사용
        peaks_arg = js_peaks
        valleys_arg = js_valleys

        try: # 감지기 생성 중 발생할 수 있는 오류 처리
            if pattern_type == "DB":
                detector = DoubleBottomDetector(extremum, self.data, peaks_arg, valleys_arg)
            elif pattern_type == "DT":
                detector = DoubleTopDetector(extremum, self.data, peaks_arg, valleys_arg)
            else:
                logger.error(f"PatternManager: 유효하지 않은 패턴 타입 - {pattern_type}")
                return
        except Exception as e:
            logger.error(f"PatternManager: {pattern_type} 감지기 생성 중 오류 발생 - {e}")
            # 실패 리스트에 추가하지 않고 생성 자체를 실패로 간주
            return

        # Detector 생성 및 초기 검증 후 실패 상태가 아닌 경우 활성 목록에 추가
        if detector and not detector.is_failed():
            # 동일 시작점 감지기 중복 추가 방지
            if not any(d.first_extremum.get('index') == extremum.get('index') and isinstance(d, type(detector)) for d in self.active_detectors):
                self.active_detectors.append(detector)
            else:
                log_date = extremum.get('detected_date', pd.Timestamp('NaT')).strftime('%Y-%m-%d')
                actual_date_str = extremum.get('actual_date', pd.Timestamp('NaT')).strftime('%y%m%d')
                logger.debug(f"[{log_date}] PatternManager: 동일 시작점({actual_date_str})의 {pattern_type} 감지기 이미 존재하여 추가 안 함.")
                # 이미 활성 감지기가 있으므로, 새로 생성된 것은 실패 처리
                if detector not in self.failed_detectors: self.failed_detectors.append(detector)
        elif detector and detector.is_failed():
            # 생성자에서 이미 실패한 경우
            if detector not in self.failed_detectors: self.failed_detectors.append(detector)

    def update_all(self, candle: Dict, newly_registered_peak: Optional[Dict], newly_registered_valley: Optional[Dict]):
        """모든 활성 감지기 업데이트 및 상태 처리"""
        # 입력 candle 유효성 검사
        if not isinstance(candle, dict) or 'date' not in candle:
            logger.error(f"PatternManager.update_all: 유효하지 않은 캔들 정보 수신 - {candle}")
            return
        # 날짜 타입 확인 및 변환
        if not isinstance(candle['date'], pd.Timestamp):
            try: candle['date'] = pd.Timestamp(candle['date'])
            except Exception: logger.error(f"PatternManager.update_all: 유효하지 않은 날짜 형식 - {candle['date']}"); return

        log_prefix = f"[{candle['date'].strftime('%Y-%m-%d')}] PatternManager:"

        # 1. 기존 활성 감지기 상태 업데이트 (리스트 복사본 순회)
        for detector in self.active_detectors[:]: # Note the [:] for safe removal while iterating
            try:
                # 모든 detector는 동일한 시그니처의 update 메서드를 가짐
                detector.update(candle, newly_registered_peak, newly_registered_valley)
            except Exception as e:
                # 개별 detector 업데이트 중 오류 발생 시 로깅 및 해당 detector 리셋
                start_date_str = detector.first_extremum.get('actual_date','N/A')
                if isinstance(start_date_str, pd.Timestamp): start_date_str = start_date_str.strftime('%y%m%d')
                logger.error(f"{log_prefix} {detector.pattern_type} Detector (시작 {start_date_str}) 업데이트 중 오류: {e}")
                detector.reset(f"Update error: {e}") # 오류 발생 시 강제 리셋

            # 2. 완성/실패 처리
            if detector.is_complete():
                completion_details = "" # 로그용 상세 정보
                start_date_str = detector.first_extremum.get('actual_date','N/A')
                if isinstance(start_date_str, pd.Timestamp): start_date_str = start_date_str.strftime('%y%m%d')

                # 패턴 타입별 처리
                if isinstance(detector, DoubleTopDetector):
                    self.completed_dt.append({'date': candle['date'], 'price': candle['Close'], 'start_peak': detector.first_extremum})
                    completion_details = f"DT 시작 Peak: {start_date_str}"
                    logger.info(f"{log_prefix} Double Top 완성! {completion_details}")
                elif isinstance(detector, DoubleBottomDetector):
                    self.completed_db.append({'date': candle['date'], 'price': candle['Close'], 'start_valley': detector.first_extremum})
                    completion_details = f"DB 시작 Valley: {start_date_str}"
                    logger.info(f"{log_prefix} Double Bottom 완성! {completion_details}")
                elif isinstance(detector, HeadAndShouldersDetector):
                    completion_info = { 'date': candle['date'], 'price': candle['Close'], 'neckline': detector.neckline_level,
                                        'P1': detector.P1, 'V2': detector.V2, 'P2': detector.P2, 'V3': detector.V3, 'P3': detector.P3 }
                    self.completed_hs.append(completion_info)
                    p1_date_str = detector.P1.get('actual_date','N/A').strftime('%y%m%d') if detector.P1 and isinstance(detector.P1.get('actual_date'), pd.Timestamp) else 'N/A'
                    completion_details = f"H&S 시작 P1: {p1_date_str}"
                    logger.info(f"{log_prefix} Head and Shoulders 완성! {completion_details}")
                elif isinstance(detector, InverseHeadAndShouldersDetector):
                    completion_info = { 'date': candle['date'], 'price': candle['Close'], 'neckline': detector.neckline_level,
                                        'V1': detector.V1, 'P2': detector.P2_ihs, 'V2': detector.V2_ihs, 'P3': detector.P3_ihs, 'V3': detector.V3_ihs }
                    self.completed_ihs.append(completion_info)
                    v1_date_str = detector.V1.get('actual_date','N/A').strftime('%y%m%d') if detector.V1 and isinstance(detector.V1.get('actual_date'), pd.Timestamp) else 'N/A'
                    completion_details = f"IH&S 시작 V1: {v1_date_str}"
                    logger.info(f"{log_prefix} Inverse Head and Shoulders 완성! {completion_details}")

                # 완성된 감지기는 활성 리스트에서 제거
                if detector in self.active_detectors:
                    self.active_detectors.remove(detector)

            elif detector.is_failed():
                # 실패한 감지기는 실패 리스트로 이동 (중복 방지)
                if detector not in self.failed_detectors:
                    self.failed_detectors.append(detector)
                # 활성 리스트에 여전히 있다면 제거 (안전장치)
                if detector in self.active_detectors:
                    self.active_detectors.remove(detector)


def download_data(ticker, period, interval, retries=3, delay=15):
    """
    yfinance를 이용한 주식 데이터 다운로드 (429 오류 해결 적용)
    
    Args:
        ticker (str): 종목 코드
        period (str): 기간 (예: '1y', '2y') 
        interval (str): 간격 (예: '1d', '1wk')
        retries (int): 재시도 횟수
        delay (int): 재시도 간격(초)
    
    Returns:
        pd.DataFrame: 주식 데이터 또는 None
    """
    # curl_cffi 세션 생성 (429 오류 해결)
    session = None
    if CURL_CFFI_AVAILABLE:
        try:
            session = requests.Session(impersonate="chrome")
            logger.info(f"curl_cffi 세션 생성 완료 - 429 오류 방지 모드 활성화")
        except Exception as e:
            logger.warning(f"curl_cffi 세션 생성 실패: {e}. 기본 모드로 진행합니다.")
            session = None
    else:
        logger.warning("curl_cffi 사용 불가. 429 오류 발생 시 'pip install curl_cffi' 실행하세요.")
    
    for attempt in range(retries):
        try:
            # yfinance Ticker 객체 생성 (세션 주입)
            if session:
                stock = yf.Ticker(ticker, session=session)
                logger.debug(f"curl_cffi 세션과 함께 {ticker} 데이터 요청 (시도 {attempt + 1})")
            else:
                stock = yf.Ticker(ticker)
                logger.debug(f"기본 세션으로 {ticker} 데이터 요청 (시도 {attempt + 1})")
                
            data = stock.history(period=period, interval=interval)
            
            if data.empty:
                raise ValueError("No data returned")
                
            data.index = data.index.tz_localize(None) # 시간대 정보 제거
            
            # 데이터 정수 변환 및 NaN 처리  
            data[['Open', 'High', 'Low', 'Close']] = data[['Open', 'High', 'Low', 'Close']].fillna(method='ffill').round(0)
            
            if 'Volume' in data.columns:
                data['Volume'] = data['Volume'].fillna(0).astype(np.int64) # Volume은 정수형으로
                # 볼륨 데이터 처리 - 0값 또는 이상치 처리
                median_volume = data[data['Volume'] > 0]['Volume'].median() # 0 제외 중간값
                zero_volume_count = (data['Volume'] == 0).sum()
                if zero_volume_count > 0:
                    # 0값을 중간값으로 대체, 중간값이 NaN일 경우(모든 거래량이 0) 0 유지
                    data['Volume'] = data['Volume'].replace(0, median_volume if not pd.isna(median_volume) else 0)

            # 결측치 재확인
            if data.isnull().values.any():
                logger.warning("데이터 다운로드 후에도 NaN 값이 존재합니다. ffill/bfill로 처리합니다.")
                data.fillna(method='ffill', inplace=True)
                data.fillna(method='bfill', inplace=True) # 혹시 모를 첫 행 NaN 처리

            logger.info(f"✅ {ticker} 데이터 다운로드 성공: {len(data)}개 캔들 (세션: {'curl_cffi' if session else 'default'})")
            return data
            
        except Exception as e:
            error_msg = str(e)
            # 429 오류 특별 처리
            if "429" in error_msg or "Too Many Requests" in error_msg:
                if not session and CURL_CFFI_AVAILABLE:
                    logger.warning("429 오류 감지! curl_cffi 세션으로 재시도합니다.")
                    try:
                        session = requests.Session(impersonate="chrome")
                        continue  # 즉시 재시도
                    except Exception as session_err:
                        logger.error(f"curl_cffi 세션 생성 실패: {session_err}")
                else:
                    logger.error(f"429 오류이지만 curl_cffi 사용 불가. 설치 명령: pip install curl_cffi")
            
            logger.error(f"데이터 다운로드 실패 (시도 {attempt + 1}/{retries}): {ticker} - {e}")
            if attempt < retries - 1:
                logger.info(f"{delay}초 후 재시도...")
                time.sleep(delay)
            else:
                logger.error(f"{ticker} 데이터 다운로드 최종 실패.")
                return None
            


def run_full_analysis(data: pd.DataFrame, ticker: str = None, period: str = None, interval: str = None) -> Dict[str, Any]:
    """
    주어진 데이터프레임에 대해 전체 분석(Peak/Valley, Trend, Patterns)을 수행하고
    구조화된 결과 딕셔너리를 반환합니다.

    Args:
        data (pd.DataFrame): OHLCV 데이터 (인덱스는 DatetimeIndex 여야 함)
        ticker (str, optional): 분석 중인 티커 심볼
        period (str, optional): 데이터 기간 (예: '1y', '2y')
        interval (str, optional): 데이터 타임프레임 (예: '1d', '1wk')

    Returns:
        Dict[str, Any]: 분석 결과 딕셔너리
    """
    # 로거 가져오기 (analysis_engine 상단에 정의된 logger 사용)
    logger = logging.getLogger(__name__) # 또는 get_logger(...) 사용
    
    # 분석 대상 정보 로깅
    analysis_info = f"티커={ticker or '알 수 없음'}, 기간={period or '알 수 없음'}, 타임프레임={interval or '알 수 없음'}"
    logger.info(f"데이터 분석 시작: {len(data)} 행, {analysis_info}")
    start_time = time.time()

    if data is None or data.empty or len(data) < 2:
        logger.warning(f"분석을 위한 데이터가 부족합니다. {analysis_info}")
        # 빈 결과를 반환하거나 적절한 예외 처리
        return {
            "error": "Insufficient data for analysis.",
            "base_data": {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
            "peaks_valleys": {"js_peaks": [], "js_valleys": [], "sec_peaks": [], "sec_valleys": []},
            "trend_info": {"periods": [], "zigzag_points": []},
            "patterns": {"completed_dt": [], "completed_db": [], "completed_hs": [], "completed_ihs": [], "failed_detectors_count": 0},
            "states": []
        }

    if not isinstance(data.index, pd.DatetimeIndex):
        logger.warning("Data index is not DatetimeIndex. Attempting conversion.")
        try:
            data.index = pd.to_datetime(data.index)
        except Exception as e:
            logger.error(f"데이터 인덱스를 DatetimeIndex로 변환 실패: {e}")
            # --- 수정된 오류 반환 값 ---
            return {
                "error": f"Invalid data index. Failed to convert to DatetimeIndex: {e}", # 오류 메시지 포함
                "base_data": {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
                "peaks_valleys": {"js_peaks": [], "js_valleys": [], "sec_peaks": [], "sec_valleys": []},
                "trend_info": {"periods": [], "zigzag_points": []},
                "patterns": {"completed_dt": [], "completed_db": [], "completed_hs": [], "completed_ihs": [], "failed_detectors_count": 0},
                "states": []
            }
    # 분석기 인스턴스 생성
    # 필요하다면 n_criteria 등 파라미터 조정
    detector = TrendDetector(n_criteria=2)
    manager = PatternManager(data)

    # --- V023 main 함수의 분석 루프 로직 ---
    # TrendDetector 초기화 (V023 main 참조)
    first = data.iloc[0]
    detector.update_reference_band(first['High'], first['Low'], 0)
    detector.data = data # TrendDetector 내부에서 data 참조 시 필요
    detector.states.append({ # 첫 캔들 상태 기록
        'index': 0, 'date': data.index[0], 'state': detector.state,
        'market_trend': detector.trend_info.market_trend, 'count': detector.trend_count,
        'reference_high': detector.reference_high, 'reference_low': detector.reference_low,
        'is_inside_bar': False, 'close': first['Close']
    })
    # detector.log_event(data.index[0], f"실시간 처리 초기화: State={detector.state}", "INFO") # 로그는 함수 내부에서

    logger.info("분석 메인 루프 실행...")
    for i in range(1, len(data)):
        current_date = data.index[i]
        try:
            current_candle_data = data.iloc[i]
            prev_candle_data = data.iloc[i - 1]
        except IndexError:
            logger.error(f"데이터 인덱싱 오류: index={i}")
            continue
        
        if current_date == pd.Timestamp('2023-06-29'):
            logger.debug(f"디버그 날짜: {current_date.strftime('%Y-%m-%d')}")


        # 1. TrendDetector 캔들 처리
        #    (process_candle 내 Secondary 등록 시 newly_registered_... 변수 할당 수정 적용 가정)
        detector.process_candle(current_candle_data, prev_candle_data, i, current_date, data)

        # 2. PatternManager 활성 감지기 업데이트
        current_candle_dict = current_candle_data.to_dict()
        current_candle_dict['date'] = current_date
        manager.update_all(current_candle_dict, detector.newly_registered_peak, detector.newly_registered_valley)

        # 3. 신규 패턴 감지기 생성 시도 (극점 타입 확인 로직 포함)
        new_extremum = detector.newly_registered_peak or detector.newly_registered_valley
        if new_extremum:
            # H&S/IHS는 모든 새로운 극점 발생 시 확인 시도
            # 참고: check_for_hs_ihs_start 내부에서 completion_mode 인자를 받거나 수정 필요
            manager.check_for_hs_ihs_start(
                detector.js_peaks + detector.secondary_peaks,
                detector.js_valleys + detector.secondary_valleys
                # completion_mode='neckline' # 필요시 명시적 전달
            )

            # DT/DB는 JS 타입 극점일 때만 확인 시도
            extremum_type = new_extremum.get('type', '') # 극점 생성 시 'type' 필드 추가 가정
            if detector.newly_registered_peak and extremum_type == 'js_peak':
                manager.add_detector("DT", detector.newly_registered_peak, data, detector.js_peaks, detector.js_valleys)
            if detector.newly_registered_valley and extremum_type == 'js_valley':
                manager.add_detector("DB", detector.newly_registered_valley, data, detector.js_peaks, detector.js_valleys)
    # --- 루프 종료 ---

    detector.finalize(data)
    end_time = time.time()
    logger.info(f"분석 메인 루프 완료 (소요 시간: {end_time - start_time:.2f}초)")

    # --- 결과 구조화 ---
    # API나 다른 모듈에서 사용하기 쉽도록 결과를 딕셔너리로 정리
    # 날짜/시간 객체는 나중에 API에서 JSON으로 변환 시 문자열로 바꿔야 함 (여기서는 객체 유지)

    # 기본 데이터 포맷팅 (날짜는 인덱스 객체 그대로 유지, 필요 시 API 레벨에서 변환)
    base_data_formatted = {
        "dates": data.index, # DatetimeIndex 객체
        "open": data['Open'].tolist(),
        "high": data['High'].tolist(),
        "low": data['Low'].tolist(),
        "close": data['Close'].tolist(),
        "volume": data['Volume'].tolist() if 'Volume' in data.columns else [0.0] * len(data) # float 처리
    }

    # ZigZag 포인트 생성 (V023 시각화 함수 로직 참조)
    all_points = detector.js_peaks + detector.js_valleys + detector.secondary_peaks + detector.secondary_valleys
    zigzag_points = sorted(all_points, key=lambda x: x.get('index', -1))


    analysis_results = {
        "base_data": base_data_formatted,
        "peaks_valleys": {
            # 각 리스트의 딕셔너리에 'type' 키가 포함되어 있다고 가정
            "js_peaks": detector.js_peaks,
            "js_valleys": detector.js_valleys,
            "sec_peaks": detector.secondary_peaks,
            "sec_valleys": detector.secondary_valleys
        },
        "trend_info": {
            "periods": detector.trend_info.periods, # [{'start': Timestamp, 'end': Timestamp, 'type': str}, ...]
            "zigzag_points": zigzag_points # 정렬된 전체 극점 리스트
        },
        "patterns": {
            # 각 패턴 딕셔너리 내의 Timestamp 객체는 나중에 변환 필요
            "completed_dt": manager.completed_dt,
            "completed_db": manager.completed_db,
            "completed_hs": manager.completed_hs,
            "completed_ihs": manager.completed_ihs,
            "failed_detectors_count": len(manager.failed_detectors)
        },
        "states": detector.states # 상태 정보 리스트 (필요 시 활용)
    }

    logger.info("분석 결과 구조화 완료")
    # logger.debug(f"분석 결과 샘플: {str(analysis_results)[:500]}") # 너무 길 수 있으므로 주의

    return analysis_results