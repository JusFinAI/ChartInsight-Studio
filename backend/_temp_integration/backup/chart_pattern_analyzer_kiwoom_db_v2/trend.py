import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
logger = logging.getLogger(__name__)

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
