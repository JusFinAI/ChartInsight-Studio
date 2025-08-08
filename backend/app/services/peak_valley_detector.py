"""JS Peak-Valley와 Secondary Peak-Valley를 활용한 실시간 추세 분석 도구"""

import numpy as np
import pandas as pd
import logging
import sys
from app.utils.logger_config import get_logger  # 중앙 로깅 모듈 사용

# 로거 설정
logger = get_logger('TrendDetector', 'peak_valley_detection')

class TrendDetector:
    def __init__(self, n_criteria=2, window_size=5):
        self.state = 0
        self.trend_direction = None
        self.trend_count = -1
        self.reference_high = None
        self.reference_low = None
        self.reference_index = None
        self.reset_high = None
        self.reset_low = None
        self.is_reset_state = False
        self.highest_high = None
        self.highest_high_index = None
        self.lowest_low = None
        self.lowest_low_index = None
        self.js_peaks = []
        self.js_valleys = []
        self.secondary_peaks = []
        self.secondary_valleys = []
        self.states = []
        self.n_criteria = n_criteria
        self.window_size = window_size
        self.previous_trend = None
        self.debug_range = None
        # 새로운 변수 추가
        self.current_trend = "Sideways"
        self.trend_start_index = None
        self.trend_periods = []
        
        # 로거 상태 점검 및 강제 설정
        self.ensure_logger_handlers()
        logger.info("TrendDetector 초기화 완료")
        
    def ensure_logger_handlers(self):
        """로거 핸들러를 점검하고 필요 시 추가"""
        global logger
        if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
            logger.warning("파일 핸들러 없음, 강제로 추가")
            timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
            file_handler = logging.FileHandler(f"logs/peak_valley_detection_{timestamp}.log")
            file_handler.setLevel(logging.DEBUG)
            file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
            logger.warning("콘솔 핸들러 없음, 강제로 추가")
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter('%(levelname)s - %(message)s')
            console_handler.setFormatter(console_formatter)
            logger.addHandler(console_handler)
            
        logger.debug(f"로거 상태 점검: 핸들러 수={len(logger.handlers)}, 핸들러 타입={[type(h).__name__ for h in logger.handlers]}")

    def is_inside_bar(self, high, low, ref_high, ref_low):
        if ref_high is None or ref_low is None:
            return False
        return high <= ref_high and low >= ref_low

    def update_reference_band(self, high, low, index):
        self.reference_high = high
        self.reference_low = low
        self.reference_index = index

    def is_in_debug_range(self, date):
        return self.debug_range is None or (self.debug_range[0] <= date <= self.debug_range[1])

    def log_event(self, date, message, level="DEBUG"):
        if self.is_in_debug_range(date):
            self.ensure_logger_handlers()  # 매 로그 호출 시 핸들러 점검
            getattr(logger, level.lower())(f"[{date}] {message}")

    def register_js_peak(self, index, value, date, data=None):
        self.js_peaks.append({'index': index, 'value': value, 'date': date})
        # 수정: 로그 메시지 구체화
        self.log_event(date, f"JS Peak 등록: 인덱스 {index}, 가격 {value}, 날짜 {date}", "INFO")

        if data is not None and len(self.js_peaks) > 1:
            all_points = sorted(
                self.js_peaks[:-1] + self.js_valleys,
                key=lambda x: x['index']
            )
            if len(all_points) > 0:
                last_point = all_points[-1]
                if last_point in self.js_peaks[:-1]:
                    start_index = last_point['index']
                    end_index = index
                    if start_index < end_index:
                        window_data = data.iloc[start_index:end_index + 1]
                        valley_value = window_data['Low'].min()
                        valley_index = window_data['Low'].idxmin()
                        valley_index_relative = data.index.get_loc(valley_index)

                        if (valley_value < last_point['value'] and valley_value < value):
                            secondary_valley_indices = [v['index'] for v in self.secondary_valleys]
                            if valley_index_relative not in secondary_valley_indices:
                                self.secondary_valleys.append({
                                    'index': valley_index_relative,
                                    'value': valley_value,
                                    'date': valley_index
                                })
                                # 수정: 로그 메시지 구체화
                                self.log_event(valley_index, f"Secondary Valley 등록: 인덱스 {valley_index_relative}, 가격 {valley_value}, 날짜 {valley_index}", "INFO")

    def register_js_valley(self, index, value, date, data=None):
        self.js_valleys.append({'index': index, 'value': value, 'date': date})
        # 수정: 로그 메시지 구체화
        self.log_event(date, f"JS Valley 등록: 인덱스 {index}, 가격 {value}, 날짜 {date}", "INFO")

        if data is not None and len(self.js_valleys) > 1:
            all_points = sorted(
                self.js_peaks + self.js_valleys[:-1],
                key=lambda x: x['index']
            )
            if len(all_points) > 0:
                last_point = all_points[-1]
                if last_point in self.js_valleys[:-1]:
                    start_index = last_point['index']
                    end_index = index
                    if start_index < end_index:
                        window_data = data.iloc[start_index:end_index + 1]
                        peak_value = window_data['High'].max()
                        peak_index = window_data['High'].idxmax()
                        peak_index_relative = data.index.get_loc(peak_index)

                        if (peak_value > last_point['value'] and peak_value > value):
                            secondary_peak_indices = [p['index'] for p in self.secondary_peaks]
                            if peak_index_relative not in secondary_peak_indices:
                                self.secondary_peaks.append({
                                    'index': peak_index_relative,
                                    'value': peak_value,
                                    'date': peak_index
                                })
                                # 수정: 로그 메시지 구체화
                                self.log_event(peak_index, f"Secondary Peak 등록: 인덱스 {peak_index_relative}, 가격 {peak_value}, 날짜 {peak_index}", "INFO")

    def check_downtrend_start(self, current, i, date, data):
        if len(self.js_peaks) >= 2 and len(self.js_valleys) >= 1:
            all_peaks = sorted(
                [(p['index'], p['value'], p) for p in self.js_peaks + self.secondary_peaks],
                key=lambda x: x[0], reverse=True
            )
            if len(all_peaks) < 2:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"하락 추세 시작 조건 불충족: Peak 데이터 부족 (필요: 2, 현재: {len(all_peaks)})", "DEBUG")
                return False
            last_peak = all_peaks[0][2]
            prev_peak = all_peaks[1][2]

            all_valleys = sorted(
                [(v['index'], v['value'], v) for v in self.js_valleys + self.secondary_valleys],
                key=lambda x: x[0], reverse=True
            )
            if len(all_valleys) < 1:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"하락 추세 시작 조건 불충족: Valley 데이터 부족 (필요: 1, 현재: {len(all_valleys)})", "DEBUG")
                return False
            last_valley = all_valleys[0][2]

            if last_peak['value'] < prev_peak['value']:
                if last_valley['index'] < i and current['Close'] < last_valley['value']:
                    self.current_trend = "Downtrend"
                    self.trend_start_index = i
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"하락 추세 시작: Lower High 확인 (최근 Peak: {last_peak['value']}, 직전 Peak: {prev_peak['value']}), 직전 Valley({last_valley['value']}) 하향 돌파 (종가: {current['Close']})", "INFO")
                    return True
                else:
                    # 수정: 조건 불충족 이유 구체화
                    self.log_event(date, f"하락 추세 시작 조건 불충족: 직전 Valley({last_valley['value']}) 하향 돌파 실패 (종가: {current['Close']}, Valley 인덱스: {last_valley['index']}, 현재 인덱스: {i})", "DEBUG")
            else:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"하락 추세 시작 조건 불충족: Lower High 미형성 (최근 Peak: {last_peak['value']}, 직전 Peak: {prev_peak['value']})", "DEBUG")
        else:
            # 수정: 조건 불충족 이유 구체화
            self.log_event(date, f"하락 추세 시작 조건 불충족: JS Peak 또는 Valley 데이터 부족 (JS Peaks: {len(self.js_peaks)}, JS Valleys: {len(self.js_valleys)})", "DEBUG")
        return False

    def check_uptrend_start(self, current, i, date, data):
        if len(self.js_valleys) >= 2 and len(self.js_peaks) >= 1:
            all_valleys = sorted(
                [(v['index'], v['value'], v) for v in self.js_valleys + self.secondary_valleys],
                key=lambda x: x[0], reverse=True
            )
            if len(all_valleys) < 2:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"상승 추세 시작 조건 불충족: Valley 데이터 부족 (필요: 2, 현재: {len(all_valleys)})", "DEBUG")
                return False
            last_valley = all_valleys[0][2]
            prev_valley = all_valleys[1][2]

            all_peaks = sorted(
                [(p['index'], p['value'], p) for p in self.js_peaks + self.secondary_peaks],
                key=lambda x: x[0], reverse=True
            )
            if len(all_peaks) < 1:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"상승 추세 시작 조건 불충족: Peak 데이터 부족 (필요: 1, 현재: {len(all_peaks)})", "DEBUG")
                return False
            last_peak = all_peaks[0][2]

            if last_valley['value'] > prev_valley['value']:
                if last_peak['index'] < i and current['Close'] > last_peak['value']:
                    self.current_trend = "Uptrend"
                    self.trend_start_index = i
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"상승 추세 시작: Higher Low 확인 (최근 Valley: {last_valley['value']}, 직전 Valley: {prev_valley['value']}), 직전 Peak({last_peak['value']}) 상향 돌파 (종가: {current['Close']})", "INFO")
                    return True
                else:
                    # 수정: 조건 불충족 이유 구체화
                    self.log_event(date, f"상승 추세 시작 조건 불충족: 직전 Peak({last_peak['value']}) 상향 돌파 실패 (종가: {current['Close']}, Peak 인덱스: {last_peak['index']}, 현재 인덱스: {i})", "DEBUG")
            else:
                # 수정: 조건 불충족 이유 구체화
                self.log_event(date, f"상승 추세 시작 조건 불충족: Higher Low 미형성 (최근 Valley: {last_valley['value']}, 직전 Valley: {prev_valley['value']})", "DEBUG")
        else:
            # 수정: 조건 불충족 이유 구체화
            self.log_event(date, f"상승 추세 시작 조건 불충족: JS Valley 또는 Peak 데이터 부족 (JS Valleys: {len(self.js_valleys)}, JS Peaks: {len(self.js_peaks)})", "DEBUG")
        return False

    def check_uptrend_continuation(self, current, i, date, data):
        if self.current_trend == "Uptrend":
            last_js_valley = self.js_valleys[-1] if self.js_valleys else None
            last_sec_valley = self.secondary_valleys[-1] if self.secondary_valleys else None
            
            last_valley = None
            if last_js_valley and last_sec_valley:
                if last_js_valley['index'] > last_sec_valley['index']:
                    last_valley = last_js_valley
                    self.log_event(date, f"가장 최근 Valley: JS Valley {last_valley['date']} ({last_valley['value']})", "DEBUG")
                else:
                    last_valley = last_sec_valley
                    self.log_event(date, f"가장 최근 Valley: Secondary Valley {last_valley['date']} ({last_valley['value']})", "DEBUG")
            elif last_js_valley:
                last_valley = last_js_valley
                self.log_event(date, f"가장 최근 Valley: JS Valley {last_valley['date']} ({last_valley['value']})", "DEBUG")
            elif last_sec_valley:
                last_valley = last_sec_valley
                self.log_event(date, f"가장 최근 Valley: Secondary Valley {last_valley['date']} ({last_valley['value']})", "DEBUG")
            else:
                self.log_event(date, "Valley 없음: 상승 추세 유지", "DEBUG")
                return True

            if current['Close'] >= last_valley['value']:
                self.log_event(date, f"종가({current['Close']}) >= 최근 Valley 저점({last_valley['value']}), 상승 추세 유지", "DEBUG")
                if len(self.js_peaks) >= 2:
                    last_peak = self.js_peaks[-1]
                    prev_peak = self.js_peaks[-2]
                    if last_peak['value'] > prev_peak['value']:
                        # 수정: 로그 메시지 구체화
                        self.log_event(date, f"Higher High 확인: 최근 Peak({last_peak['value']}) > 직전 Peak({prev_peak['value']})", "DEBUG")
                        return True
                return True
            else:
                self.log_event(date, f"종가({current['Close']}) < 최근 Valley 저점({last_valley['value']}), 하향 돌파", "INFO")
                if self.trend_start_index is not None:
                    self.trend_periods.append({
                        'start': data.index[self.trend_start_index],
                        'end': date,
                        'type': "Uptrend"
                    })
                self.current_trend = "Sideways"
                self.trend_start_index = None
                self.log_event(date, "상승 추세 종료: 직전 Valley 저점 하향 돌파, Sideways로 전환", "INFO")
                self.log_event(date, f"trend_periods 업데이트: {self.trend_periods}", "DEBUG")
                return False
        return True

    def check_downtrend_continuation(self, current, i, date, data):
        if self.current_trend == "Downtrend":
            last_js_peak = self.js_peaks[-1] if self.js_peaks else None
            last_sec_peak = self.secondary_peaks[-1] if self.secondary_peaks else None
            
            last_peak = None
            if last_js_peak and last_sec_peak:
                if last_js_peak['index'] > last_sec_peak['index']:
                    last_peak = last_js_peak
                    self.log_event(date, f"가장 최근 Peak: JS Peak {last_peak['date']} ({last_peak['value']})", "DEBUG")
                else:
                    last_peak = last_sec_peak
                    self.log_event(date, f"가장 최근 Peak: Secondary Peak {last_peak['date']} ({last_peak['value']})", "DEBUG")
            elif last_js_peak:
                last_peak = last_js_peak
                self.log_event(date, f"가장 최근 Peak: JS Peak {last_peak['date']} ({last_peak['value']})", "DEBUG")
            elif last_sec_peak:
                last_peak = last_sec_peak
                self.log_event(date, f"가장 최근 Peak: Secondary Peak {last_peak['date']} ({last_peak['value']})", "DEBUG")
            else:
                self.log_event(date, "Peak 없음: 하락 추세 유지", "DEBUG")
                return True

            if current['Close'] <= last_peak['value']:
                self.log_event(date, f"종가({current['Close']}) <= 최근 Peak 고점({last_peak['value']}), 하락 추세 유지", "DEBUG")
                if len(self.js_valleys) >= 2:
                    last_valley = self.js_valleys[-1]
                    prev_valley = self.js_valleys[-2]
                    if last_valley['value'] < prev_valley['value']:
                        # 수정: 로그 메시지 구체화
                        self.log_event(date, f"Lower Low 확인: 최근 Valley({last_valley['value']}) < 직전 Valley({prev_valley['value']})", "DEBUG")
                        return True
                return True
            else:
                self.log_event(date, f"종가({current['Close']}) > 최근 Peak 고점({last_peak['value']}), 상향 돌파", "INFO")
                if self.trend_start_index is not None:
                    self.trend_periods.append({
                        'start': data.index[self.trend_start_index],
                        'end': date,
                        'type': "Downtrend"
                    })
                self.current_trend = "Sideways"
                self.trend_start_index = None
                self.log_event(date, "하락 추세 종료: 직전 Peak 고점 상향 돌파, Sideways로 전환", "INFO")
                self.log_event(date, f"trend_periods 업데이트: {self.trend_periods}", "DEBUG")
                return False
        return True

    def process_candle(self, current, prev, i, date, data):
        is_inside = self.is_inside_bar(current['High'], current['Low'], self.reference_high, self.reference_low)
        self.log_event(date, f"내부봉 여부: {is_inside}", "DEBUG")

        if self.state == 0:
            self.handle_state_0(current, prev, i, date)
        elif self.state == 1:
            if is_inside:
                self.log_event(date, f"State 1({self.trend_direction}) 유지 (내부봉)", "DEBUG")
            else:
                self.handle_state_1(current, prev, i, date)
        elif self.state == 2:
            if is_inside:
                self.log_event(date, "State 2 유지 (내부봉)", "DEBUG")
            else:
                self.handle_state_2(current, prev, i, date)
        elif self.state == 3:
            if is_inside:
                self.log_event(date, f"State 3 유지 ({'상승' if self.trend_direction == 'up' else '하락'})", "DEBUG")
            else:
                self.handle_state_3(current, prev, i, date, data)

        if not is_inside:
            self.update_reference_band(current['High'], current['Low'], i)
            self.log_event(date, f"기준 band 업데이트: High={current['High']}, Low={current['Low']}", "DEBUG")

        # 추가: 최근 JS 포인트 등록 확인 및 추가 검증
        self.check_recent_js_registration(i, date, data)

        # 추세 판단 로직
        if self.current_trend == "Sideways":
            if self.check_downtrend_start(current, i, date, data):
                pass
            elif self.check_uptrend_start(current, i, date, data):
                pass
        elif self.current_trend == "Downtrend":
            if not self.check_downtrend_continuation(current, i, date, data):
                pass
        elif self.current_trend == "Uptrend":
            if not self.check_uptrend_continuation(current, i, date, data):
                pass

        # 수정: 디버깅 로그 추가 - 주요 변수 상태 출력
        self.log_event(date, f"현재 상태 - 추세: {self.current_trend}, trend_periods: {self.trend_periods}, JS Peaks: {len(self.js_peaks)}, JS Valleys: {len(self.js_valleys)}", "DEBUG")

        self.states.append({
            'index': i, 'date': date, 'state': self.state, 'trend': self.current_trend,
            'count': self.trend_count, 'reference_high': self.reference_high,
            'reference_low': self.reference_low, 'is_inside_bar': is_inside,
            'close': current['Close']  # ZigZag 선을 그리기 위해 종가 저장
        })
    
    def handle_state_0(self, current, prev, i, date):
        self.is_reset_state = False
        self.previous_trend = self.trend_direction
        if i == 1:
            if current['Close'] < current['Open']:
                self.state = 1
                self.trend_direction = 'down'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"첫 캔들: 하락 추세 가설(State 0 -> State 1, 음봉 확인, 종가: {current['Close']}, 시가: {current['Open']})", "INFO")
            elif current['Close'] > current['Open']:
                self.state = 1
                self.trend_direction = 'up'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"첫 캔들: 상승 추세 가설(State 0 -> State 1, 양봉 확인, 종가: {current['Close']}, 시가: {current['Open']})", "INFO")
        else:
            if not self.is_inside_bar(current['High'], current['Low'], self.reference_high, self.reference_low):
                if current['Low'] < prev['Low']:
                    self.state = 1
                    self.trend_direction = 'down'
                    self.trend_count = 0
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"State 0 -> State 1 (하락 추세 가설: 저점 돌파, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
                elif current['High'] > prev['High']:
                    self.state = 1
                    self.trend_direction = 'up'
                    self.trend_count = 0
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"State 0 -> State 1 (상승 추세 가설: 고점 돌파, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")

    def handle_state_1(self, current, prev, i, date):
        previous_candle_range = prev['High'] - prev['Low']
        close_to_close_move = abs(current['Close'] - prev['Close'])
        is_bullish_candle = current['Close'] > current['Open']
        is_bearish_candle = current['Close'] < current['Open']
        is_bullish_move = current['Close'] > prev['Close']
        is_bearish_move = current['Close'] < prev['Close']
        
        is_strong_move = close_to_close_move > previous_candle_range
        direction_match = ((self.trend_direction == 'up' and is_bullish_candle and is_bullish_move) or
                          (self.trend_direction == 'down' and is_bearish_candle and is_bearish_move))
        
        if is_strong_move and direction_match:
            self.state = 3
            self.trend_count = self.n_criteria
            if self.trend_direction == 'up':
                self.highest_high = current['High']
                self.highest_high_index = i
            else:
                self.lowest_low = current['Low']
                self.lowest_low_index = i
            # 수정: 로그 메시지 구체화
            self.log_event(date, f"State 1({self.trend_direction}) -> State 3 (즉시 추세 확정, 종가 이동: {close_to_close_move}, 이전 캔들 범위: {previous_candle_range})", "INFO")
            return

        if self.trend_direction == 'up':
            if current['High'] > prev['High'] and current['Low'] >= prev['Low']:
                self.state = 2
                self.trend_count = 1
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(up) -> State 2(up) (상승 추세 형성, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")
            elif current['Low'] < prev['Low'] and current['Close'] < prev['Open']:
                self.state = 1
                self.trend_direction = 'down'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(up) -> State 1(down) (방향 전환, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
            elif current['High'] <= prev['High'] and current['Low'] < prev['Low']:
                self.state = 0
                self.trend_direction = None
                self.trend_count = -1
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(up) -> State 0 (추세 가설 취소, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
        elif self.trend_direction == 'down':
            if current['Low'] < prev['Low'] and current['High'] <= prev['High']:
                self.state = 2
                self.trend_count = 1
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(down) -> State 2(down) (하락 추세 형성, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
            elif current['High'] > prev['High'] and current['Close'] > prev['Open']:
                self.state = 1
                self.trend_direction = 'up'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(down) -> State 1(up) (방향 전환, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")
            elif current['Low'] >= prev['Low'] and current['High'] > prev['High']:
                self.state = 0
                self.trend_direction = None
                self.trend_count = -1
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 1(down) -> State 0 (추세 가설 취소, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")

    def handle_state_2(self, current, prev, i, date):
        if self.trend_direction == 'up':
            if current['High'] > prev['High'] and current['Low'] >= prev['Low']:
                self.trend_count += 1
                if self.trend_count >= self.n_criteria:
                    self.state = 3
                    self.highest_high = current['High']
                    self.highest_high_index = i
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"State 2 -> State 3 (상승 추세 확정, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")
                else:
                    # 수정: 로그 메시지 추가
                    self.log_event(date, f"State 2(up) 유지 (trend_count: {self.trend_count}, 현재 High: {current['High']}, 직전 High: {prev['High']})", "DEBUG")
            elif current['Low'] < prev['Low'] and current['Close'] < prev['Open']:
                self.state = 1
                self.trend_direction = 'down'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 2(up) -> State 1(down) (방향 전환, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
            elif current['Low'] < prev['Low'] and current['High'] <= prev['High']:
                self.state = 0
                self.trend_count = -1
                self.reset_low = current['Low']
                self.is_reset_state = True
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 2(up) -> State 0 (리셋, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
        elif self.trend_direction == 'down':
            if current['Low'] < prev['Low'] and current['High'] <= prev['High']:
                self.trend_count += 1
                if self.trend_count >= self.n_criteria:
                    self.state = 3
                    self.lowest_low = current['Low']
                    self.lowest_low_index = i
                    # 수정: 로그 메시지 구체화
                    self.log_event(date, f"State 2 -> State 3 (하락 추세 확정, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "INFO")
                else:
                    # 수정: 로그 메시지 추가
                    self.log_event(date, f"State 2(down) 유지 (trend_count: {self.trend_count}, 현재 Low: {current['Low']}, 직전 Low: {prev['Low']})", "DEBUG")
            elif current['High'] > prev['High'] and current['Close'] > prev['Open']:
                self.state = 1
                self.trend_direction = 'up'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 2(down) -> State 1(up) (방향 전환, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")
            elif current['High'] > prev['High'] and current['Low'] >= prev['Low']:
                self.state = 0
                self.trend_count = -1
                self.reset_high = current['High']
                self.is_reset_state = True
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 2(down) -> State 0 (리셋, 현재 High: {current['High']}, 직전 High: {prev['High']})", "INFO")

    def handle_state_3(self, current, prev, i, date, data):
        if self.trend_direction == 'up':
            if current['High'] > self.highest_high:
                self.highest_high = current['High']
                self.highest_high_index = i
                self.log_event(date, f"최고점 갱신: {self.highest_high}", "INFO")
            elif current['Close'] < self.reference_low:
                window_data = data.iloc[self.highest_high_index:i + 1]
                peak_value = window_data['High'].max()
                peak_index = window_data['High'].idxmax()
                peak_index_relative = data.index.get_loc(peak_index)
                self.register_js_peak(peak_index_relative, peak_value, peak_index, data)
                self.state = 1
                self.trend_direction = 'down'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 3(up) -> State 1(down) (JS Peak 등록, 종가: {current['Close']}, 기준 Low: {self.reference_low})", "INFO")
        elif self.trend_direction == 'down':
            if current['Low'] < self.lowest_low:
                self.lowest_low = current['Low']
                self.lowest_low_index = i
                self.log_event(date, f"최저점 갱신: {self.lowest_low}", "INFO")
            elif current['Close'] > self.reference_high:
                window_data = data.iloc[self.lowest_low_index:i + 1]
                valley_value = window_data['Low'].min()
                valley_index = window_data['Low'].idxmin()
                valley_index_relative = data.index.get_loc(valley_index)
                self.register_js_valley(valley_index_relative, valley_value, valley_index, data)
                self.state = 1
                self.trend_direction = 'up'
                self.trend_count = 0
                # 수정: 로그 메시지 구체화
                self.log_event(date, f"State 3(down) -> State 1(up) (JS Valley 등록, 종가: {current['Close']}, 기준 High: {self.reference_high})", "INFO")

    def detect_peaks_valleys(self, data, debug_range=None):
        self.debug_range = debug_range
        self.ensure_logger_handlers()  # 분석 시작 전 핸들러 점검

        if len(data) > 0:
            first = data.iloc[0]
            self.update_reference_band(first['High'], first['Low'], 0)
            self.states.append({
                'index': 0, 'date': data.index[0], 'state': self.state,
                'trend': self.current_trend, 'count': self.trend_count,
                'reference_high': self.reference_high, 'reference_low': self.reference_low,
                'is_inside_bar': False, 'close': first['Close']
            })
            self.log_event(data.index[0], f"초기화: State {self.state}", "INFO")

        for i in range(1, len(data)):
            current_date = data.index[i]
            self.process_candle(data.iloc[i], data.iloc[i-1], i, current_date, data)

        # 마지막 추세 구간 마무리
        if self.current_trend in ["Uptrend", "Downtrend"] and self.trend_start_index is not None:
            self.trend_periods.append({
                'start': data.index[self.trend_start_index],
                'end': data.index[-1],
                'type': self.current_trend
            })
            # 수정: 로그 메시지 추가
            self.log_event(data.index[-1], f"마지막 추세 구간 기록: {self.current_trend} ({data.index[self.trend_start_index]} ~ {data.index[-1]})", "INFO")

        return self.js_peaks, self.js_valleys, self.secondary_peaks, self.secondary_valleys, self.states, self.trend_periods

    def check_recent_js_registration(self, current_index, date, data):
        """최근에 JS Peak/Valley가 등록되었는지 확인하고, Secondary 패턴을 추가로 검증합니다."""
        # 직전 캔들에서 JS 포인트가 등록되었는지 확인
        recent_registration = False
        
        # 최근 JS Peak 등록 확인 (마지막 JS Peak의 인덱스가 현재 인덱스보다 1~2 작은지 확인)
        if self.js_peaks and (current_index - self.js_peaks[-1]['index'] <= 2):
            recent_registration = True
            self.log_event(date, f"최근 JS Peak 등록 확인 (인덱스: {self.js_peaks[-1]['index']}), Secondary Valley 검증", "DEBUG")
            # Secondary Valley 재검증
            self.verify_secondary_valleys_between_peaks(date, data)
        
        # 최근 JS Valley 등록 확인 (마지막 JS Valley의 인덱스가 현재 인덱스보다 1~2 작은지 확인)
        if self.js_valleys and (current_index - self.js_valleys[-1]['index'] <= 2):
            recent_registration = True
            self.log_event(date, f"최근 JS Valley 등록 확인 (인덱스: {self.js_valleys[-1]['index']}), Secondary Peak 검증", "DEBUG")
            # Secondary Peak 재검증
            self.verify_secondary_peaks_between_valleys(date, data)
        
        return recent_registration

    def verify_secondary_valleys_between_peaks(self, date, data):
        """최근 JS Peak들 사이의 Secondary Valley를 검증합니다."""
        if len(self.js_peaks) < 2:
            self.log_event(date, "JS Peak가 2개 미만이어서 Secondary Valley 검증 건너뜀", "DEBUG")
            return
        
        # 마지막 두 JS Peak 가져오기
        last_peak = self.js_peaks[-1]
        prev_peak = self.js_peaks[-2]
        
        # 두 JS Peak 사이의 데이터에서 저점 찾기
        start_index = prev_peak['index']
        end_index = last_peak['index']
        
        if start_index >= end_index:
            self.log_event(date, f"Peak 인덱스 역전 (이전: {start_index}, 최근: {end_index}), 검증 건너뜀", "DEBUG")
            return
        
        window_data = data.iloc[start_index:end_index + 1]
        valley_value = window_data['Low'].min()
        valley_index = window_data['Low'].idxmin()
        valley_index_relative = data.index.get_loc(valley_index)
        
        # Secondary Valley 검증 조건
        if valley_value < prev_peak['value'] and valley_value < last_peak['value']:
            # 이미 등록된 Secondary Valley인지 확인
            secondary_valley_indices = [v['index'] for v in self.secondary_valleys]
            if valley_index_relative not in secondary_valley_indices:
                # JS Valley와 중복이 아닌지 확인
                js_valley_indices = [v['index'] for v in self.js_valleys]
                if valley_index_relative not in js_valley_indices:
                    self.secondary_valleys.append({
                        'index': valley_index_relative,
                        'value': valley_value,
                        'date': valley_index
                    })
                    self.log_event(date, f"추가 검증으로 Secondary Valley 등록: 인덱스 {valley_index_relative}, 가격 {valley_value}, 날짜 {valley_index}", "INFO")

    def verify_secondary_peaks_between_valleys(self, date, data):
        """최근 JS Valley들 사이의 Secondary Peak를 검증합니다."""
        if len(self.js_valleys) < 2:
            self.log_event(date, "JS Valley가 2개 미만이어서 Secondary Peak 검증 건너뜀", "DEBUG")
            return
        
        # 마지막 두 JS Valley 가져오기
        last_valley = self.js_valleys[-1]
        prev_valley = self.js_valleys[-2]
        
        # 두 JS Valley 사이의 데이터에서 고점 찾기
        start_index = prev_valley['index']
        end_index = last_valley['index']
        
        if start_index >= end_index:
            self.log_event(date, f"Valley 인덱스 역전 (이전: {start_index}, 최근: {end_index}), 검증 건너뜀", "DEBUG")
            return
        
        window_data = data.iloc[start_index:end_index + 1]
        peak_value = window_data['High'].max()
        peak_index = window_data['High'].idxmax()
        peak_index_relative = data.index.get_loc(peak_index)
        
        # Secondary Peak 검증 조건
        if peak_value > prev_valley['value'] and peak_value > last_valley['value']:
            # 이미 등록된 Secondary Peak인지 확인
            secondary_peak_indices = [p['index'] for p in self.secondary_peaks]
            if peak_index_relative not in secondary_peak_indices:
                # JS Peak과 중복이 아닌지 확인
                js_peak_indices = [p['index'] for p in self.js_peaks]
                if peak_index_relative not in js_peak_indices:
                    self.secondary_peaks.append({
                        'index': peak_index_relative,
                        'value': peak_value,
                        'date': peak_index
                    })
                    self.log_event(date, f"추가 검증으로 Secondary Peak 등록: 인덱스 {peak_index_relative}, 가격 {peak_value}, 날짜 {peak_index}", "INFO")
