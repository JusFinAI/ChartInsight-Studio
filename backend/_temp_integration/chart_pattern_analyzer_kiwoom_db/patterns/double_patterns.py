from .base import PatternDetector
import pandas as pd
import logging

logger = logging.getLogger('backend')

class DoubleBottomDetector(PatternDetector):
    
    """
    Double Bottom (DB) 패턴의 형성 과정을 실시간으로 탐지하고 관리합니다.

    `first_extremum`(첫 번째 저점)이 확인된 후 활성화됩니다.
    이후 `pullback_high`(반등 고점)가 형성되고, 가격이 다시 하락하여
    `first_extremum`과 유사한 수준으로 재진입(`Reentry`)하는 과정을 추적합니다.

    재진입의 유효성은 'Pullback 깊이'와 `tolerance`를 이용해 계산된 동적
    지지 밴드(`band`)를 기준으로 판단하며, 밴드 터치 후 재반등이 확인되는
    `reentry_confirmation` 단계를 거쳐 패턴의 다음 단계로 진행합니다.

    Attributes:
        first_extremum (dict): 패턴 탐지를 시작하게 한 첫 번째 저점(Valley)의 정보.
        pullback_high (float): `first_extremum` 이후 형성된 반등 고점(Peak)의 가격.
        second_valley (float): 지지 밴드(`band`)에 닿았을 때 기록되는 두 번째 저점 후보의 가격.
        band (dict): 두 번째 저점 후보를 찾기 위한 동적 지지 밴드. {'low', 'high'} 형태이며,
                      Pullback 깊이에 따라 너비가 동적으로 결정됩니다.
        straight_peak (float): 두 저점 사이의 고점(넥라인) 가격. 이 가격을 돌파하면
                               패턴이 무효화될 수 있습니다.
    """
        
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
            # pullback_high: actual -> confirmation 구간의 High max
            try:
                actual_idx = data.index.get_loc(self.first_extremum['actual_date'])
                detected_idx = data.index.get_loc(self.first_extremum['detected_date'])
                if actual_idx <= detected_idx:
                    pullback_window = data.iloc[actual_idx: detected_idx + 1]
                else:
                    pullback_window = data.iloc[detected_idx: actual_idx + 1]
                self.pullback_high = float(pullback_window['High'].max())
            except Exception:
                # fallback: confirmation high
                self.pullback_high = float(self.confirmation_candle.get('High', self.first_extremum.get('high')))
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

        # Dynamic band 초기값 계산: band.high = actual_valley_price + pullback_depth * tolerance
        actual_valley_price = float(self.actual_candle.get('Low', self.actual_candle.get('Close')))
        pullback_high = getattr(self, 'pullback_high', None)
        if pullback_high is None:
            pullback_high = float(self.confirmation_candle.get('High', self.actual_candle.get('High')))
        pullback_depth = max(0.0, float(pullback_high) - actual_valley_price)
        tolerance = globals().get('BAND_TOLERANCE', 0.05)
        calculated_band_high = actual_valley_price + pullback_depth * float(tolerance)

        # 안전캡: band_high은 실제 캔들의 High 또는 확인캔들 High보다 크지 않도록 제한(선택적)
        cap_high = max(float(self.actual_candle.get('High', calculated_band_high)), float(self.confirmation_candle.get('High', calculated_band_high)))
        calculated_band_high = min(calculated_band_high, cap_high)

        self.band = {
            'low': actual_valley_price,
            'high': calculated_band_high
        }
        # 저장된 pullback 정보
        self.pullback_high = float(pullback_high)
        self.pullback_depth = float(pullback_depth)
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
        # 2. Detector가 알고 있는 모든 Peak 목록(self.peaks)에서 첫 번째 Valley 이전에 발생한 Peak들을 선택합니다.
        #    변경 사항: 이제 JS 전용 필터를 제거하여, 신뢰도 등급과 상관없이 가장 마지막에 나온 Peak를 기준으로 사용합니다.
        prior_peaks = [p for p in self.peaks if p['index'] < valley_index]
        if prior_peaks:
            return max(prior_peaks, key=lambda x: x['index'])['value']
        else:
            return None

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
                band_low_val = self.band.get('low') if self.band else None
                band_low_str = f"{band_low_val:.2f}" if isinstance(band_low_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) < Band Low({band_low_str})" if (self.band and band_low_val is not None and candle['Close'] < band_low_val) else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
            # first_positive_candle 존재 여부 확인 추가
            if candle['Close'] > candle['Open'] and self.first_positive_candle and candle['Close'] > self.first_positive_candle['Close']:
                self.stage = "Reentry"; self.log_event("Stage Pullback -> Reentry", "DEBUG", candle['date'])

        elif self.stage == "Reentry":
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                band_low_val = self.band.get('low') if self.band else None
                band_low_str = f"{band_low_val:.2f}" if isinstance(band_low_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) < Band Low({band_low_str})" if (self.band and band_low_val is not None and candle['Close'] < band_low_val) else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
            # Dynamic expansion: observed pullback_high up to current candle may be larger than init pullback_high
            try:
                actual_idx = self.data.index.get_loc(self.first_extremum['actual_date'])
                cur_idx = self.data.index.get_loc(candle['date'])
                if cur_idx >= actual_idx:
                    observed_high = float(self.data['High'].iloc[actual_idx:cur_idx+1].max())
                else:
                    observed_high = getattr(self, 'pullback_high', float(self.confirmation_candle.get('High', self.actual_candle.get('High'))))
            except Exception:
                observed_high = getattr(self, 'pullback_high', float(self.confirmation_candle.get('High', self.actual_candle.get('High'))))

            effective_pullback_high = max(getattr(self, 'pullback_high', observed_high), observed_high)
            pullback_depth_effective = max(0.0, float(effective_pullback_high) - float(self.band['low']))
            tolerance = globals().get('BAND_TOLERANCE', 0.05)
            new_band_high = float(self.band['low']) + pullback_depth_effective * float(tolerance)
            
            cap_high = max(float(self.actual_candle.get('High', new_band_high)), float(self.confirmation_candle.get('High', new_band_high)))
            new_band_high = min(new_band_high, cap_high)
            # expand band high if larger
            if new_band_high > (self.band.get('high') if self.band else 0):
                self.band['high'] = new_band_high
                self.observed_pullback_high = observed_high
            
            body_low = min(candle['Open'], candle['Close'])
            body_touch = body_low <= self.band['high']
            wick_touch = (candle['Low'] <= self.band['high']) and not body_touch
                       
            
            prev_candle = self.candle_history[-2] if len(self.candle_history) >= 2 else None
            prev_close = prev_candle.get('Close') if prev_candle else None
            is_down_close = (prev_close is not None and candle['Close'] < prev_close)
            
            is_doji = (candle['Close'] == candle['Open'])
            is_bearish_or_doji = (candle['Close'] < candle['Open']) or is_doji
            
            
            if body_touch:
                self.second_valley = candle['Low']
                self.stage = "reentry_confirmation"
                self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Valley Cand: {self.second_valley:.0f})", "DEBUG", candle['date'])
                if self.second_valley < self.band['low']:
                    self.log_event(f"Band Low 업데이트: {self.band['low']:.0f} -> {self.second_valley:.0f}", "DEBUG", candle['date']); self.band['low'] = self.second_valley
            
            elif wick_touch:
                
                self.second_valley = candle['Low']
                self.stage = "reentry_confirmation"
                self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Valley Cand: {self.second_valley:.0f})", "DEBUG", candle['date'])
                if self.second_valley < self.band['low']:
                    self.log_event(f"Band Low 업데이트: {self.band['low']:.0f} -> {self.second_valley:.0f}", "DEBUG", candle['date']); self.band['low'] = self.second_valley
            else:
                self.log_event(f"Reentry 후보 무시: band_touch but not valid retrace (is_down_close={is_down_close}, is_bearish_or_doji={is_bearish_or_doji})", "DEBUG", candle['date'])
                
                    

        elif self.stage == "reentry_confirmation":
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                band_low_val = self.band.get('low') if self.band else None
                band_low_str = f"{band_low_val:.2f}" if isinstance(band_low_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) < Band Low({band_low_str})" if (band_low_val is not None and candle['Close'] < band_low_val) else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
            if (self.band and candle['Close'] < self.band['low']) or candle['Close'] > self.straight_peak:
                band_low_val = self.band.get('low') if self.band else None
                band_low_str = f"{band_low_val:.2f}" if isinstance(band_low_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) < Band Low({band_low_str})" if (band_low_val is not None and candle['Close'] < band_low_val) else f"Close({candle['Close']:.2f}) > Straight Peak({self.straight_peak:.2f})"
                self.reset(reason); return
                
            # 문서 기준 완료 판정: 직전 캔들 타입에 따라 분기 검증
            prev_candle = self.candle_history[-2] if len(self.candle_history) >= 2 else None
            if prev_candle is None:
                doc_ok = (candle['Close'] > candle['Open'])
            else:
                if prev_candle['Close'] > prev_candle['Open']:
                    doc_ok = (candle['Close'] > prev_candle['Close'])
                else:
                    doc_ok = (candle['Close'] > prev_candle['Open'])

            if doc_ok:
                self.stage = "Completed"
                self.expectation_mode = False
                self.log_event(f"*** Double Bottom 패턴 완성! *** Price={candle['Close']:.0f}", "INFO", candle['date'])
        

# --- DoubleTopDetector 전체 코드 (수정된 __init__ 포함) ---
class DoubleTopDetector(PatternDetector):
    """
    Double Top (DT) 패턴의 형성 과정을 실시간으로 탐지하고 관리합니다.

    `first_extremum`(첫 번째 고점)이 확인된 후 활성화됩니다.
    이후 `pullback_low`(되돌림 저점)가 형성되고, 가격이 다시 상승하여
    `first_extremum`과 유사한 수준으로 재진입(`Reentry`)하는 과정을 추적합니다.

    재진입의 유효성은 'Pullback 깊이'와 `tolerance`를 이용해 계산된 동적
    저항 밴드(`band`)를 기준으로 판단하며, 밴드 터치 후 재하락이 확인되는
    `reentry_confirmation` 단계를 거쳐 패턴의 다음 단계로 진행합니다.

    Attributes:
        first_extremum (dict): 패턴 탐지를 시작하게 한 첫 번째 고점(Peak)의 정보.
        pullback_low (float): `first_extremum` 이후 형성된 되돌림 저점(Valley)의 가격.
        second_peak (float): 저항 밴드(`band`)에 닿았을 때 기록되는 두 번째 고점 후보의 가격.
        band (dict): 두 번째 고점 후보를 찾기 위한 동적 저항 밴드. {'low', 'high'} 형태이며,
                      Pullback 깊이에 따라 너비가 동적으로 결정됩니다.
        straight_valley (float): 두 고점 사이의 저점(넥라인) 가격. 이 가격이 붕괴되면
                                 패턴이 무효화될 수 있습니다.
    """
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
        
        # Dynamic band 계산: band.low = actual_peak_price - pullback_depth * tolerance
        actual_peak_price = float(self.actual_candle.get('High', self.actual_candle.get('Close')))
        try:
            actual_idx = data.index.get_loc(self.first_extremum['actual_date'])
            detected_idx = data.index.get_loc(self.first_extremum['detected_date'])
            if actual_idx <= detected_idx:
                pullback_window = data.iloc[actual_idx: detected_idx + 1]
            else:
                pullback_window = data.iloc[detected_idx: actual_idx + 1]
            self.pullback_low = float(pullback_window['Low'].min())
        except Exception:
            self.pullback_low = float(self.confirmation_candle.get('Low', self.actual_candle.get('Low')))

        pullback_depth = max(0.0, actual_peak_price - float(self.pullback_low))
        tolerance = globals().get('BAND_TOLERANCE', 0.05)
        calculated_band_low = actual_peak_price - pullback_depth * float(tolerance)
        # 안전캡: band_low는 actual/confirmation의 Low보다 낮아지지 않도록 제한
        cap_low = min(float(self.actual_candle.get('Low', calculated_band_low)), float(self.confirmation_candle.get('Low', calculated_band_low)))
        calculated_band_low = max(calculated_band_low, cap_low)

        self.band = {
            'high': actual_peak_price,
            'low': calculated_band_low
        }
        # 저장 정보
        self.pullback_high = actual_peak_price
        self.pullback_depth = float(pullback_depth)
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
        # 변경 사항: JS 전용 필터 제거. 가장 마지막에 발생한 Valley(등급 무관)를 사용
        prior_valleys = [v for v in self.valleys if v['index'] < peak_index]
        if prior_valleys:
            return max(prior_valleys, key=lambda x: x['index'])['value']
        else:
            return None

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
                band_high_val = self.band.get('high') if self.band else None
                band_high_str = f"{band_high_val:.2f}" if isinstance(band_high_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) > Band High({band_high_str})" if (self.band and band_high_val is not None and candle['Close'] > band_high_val) else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
            if candle['Close'] < candle['Open']:
                # first_negative_candle 존재 여부 확인 추가
                if self.first_negative_candle and candle['Close'] < self.first_negative_candle['Close']:
                    self.stage = "Reentry"; self.log_event("Stage Pullback -> Reentry", "DEBUG", candle['date'])

        elif self.stage == "Reentry":
            if (self.band and candle['Close'] > self.band['high']) or candle['Close'] < self.straight_valley:
                band_high_val = self.band.get('high') if self.band else None
                band_high_str = f"{band_high_val:.2f}" if isinstance(band_high_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) > Band High({band_high_str})" if (self.band and band_high_val is not None and candle['Close'] > band_high_val) else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
            
            try:
                actual_idx = self.data.index.get_loc(self.first_extremum['actual_date'])
                cur_idx = self.data.index.get_loc(candle['date'])
                if cur_idx >= actual_idx:
                    observed_low = float(self.data['Low'].iloc[actual_idx:cur_idx+1].min())
                else:
                    observed_low = getattr(self, 'pullback_low', float(self.confirmation_candle.get('Low', self.actual_candle.get('Low'))))
            except Exception:
                observed_low = getattr(self, 'pullback_low', float(self.confirmation_candle.get('Low', self.actual_candle.get('Low'))))

            # effective pullback low is the deeper (smaller) of initial and observed
            effective_pullback_low = min(getattr(self, 'pullback_low', observed_low), observed_low)
            # pullback depth relative to the peak
            pullback_depth_effective = max(0.0, float(self.pullback_high) - float(effective_pullback_low))
            tolerance = globals().get('BAND_TOLERANCE', 0.05)
            new_band_low = float(self.pullback_high) - pullback_depth_effective * float(tolerance)

            # safety cap: do not move band_low above the actual/confirmation low (avoid excessive lowering)
            cap_low = min(float(self.actual_candle.get('Low', new_band_low)), float(self.confirmation_candle.get('Low', new_band_low)))
            new_band_low = max(new_band_low, cap_low)     
            
            band_low_val_current = self.band.get('low') if self.band else None
            if band_low_val_current is None:
                compare_low = float('inf')
            else:
                compare_low = band_low_val_current
            if new_band_low < compare_low:
                self.band['low'] = new_band_low
                self.observed_pullback_low = observed_low
            
            # Reentry touch logic: body-touch preferred; wick-touch requires additional confirmation
            # body_high = max(Open, Close)
            body_high = max(candle['Open'], candle['Close'])
            body_touch = body_high >= self.band['low']
            wick_touch = (candle['High'] >= self.band['low']) and not body_touch

            # previous candle for retrace/rally confirmation
            prev_candle = self.candle_history[-2] if len(self.candle_history) >= 2 else None
            prev_close = prev_candle.get('Close') if prev_candle else None
            is_up_close = (prev_close is not None and candle['Close'] > prev_close)
            is_doji = (candle['Close'] == candle['Open'])
            is_bullish_or_doji = (candle['Close'] > candle['Open']) or is_doji
            
            if body_touch:
                # immediate acceptance if the body itself touches or exceeds the band_low
                self.second_peak = candle['High']
                self.stage = "reentry_confirmation"
                self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Peak Cand: {self.second_peak:.0f})", "DEBUG", candle['date'])
                if self.second_peak > self.band['high']:
                    self.log_event(f"Band High 업데이트: {self.band['high']:.0f} -> {self.second_peak:.0f}", "DEBUG", candle['date']); self.band['high'] = self.second_peak
            elif wick_touch:
                # require rally confirmation for wick-only touches: previous-close must be lower and current is bullish/doji
                if is_up_close and is_bullish_or_doji:
                    self.second_peak = candle['High']
                    self.stage = "reentry_confirmation"
                    self.log_event(f"Stage Reentry -> reentry_confirmation (Sec Peak Cand: {self.second_peak:.0f})", "DEBUG", candle['date'])
                    if self.second_peak > self.band['high']:
                        self.log_event(f"Band High 업데이트: {self.band['high']:.0f} -> {self.second_peak:.0f}", "DEBUG", candle['date']); self.band['high'] = self.second_peak
                else:
                    self.log_event(f"Reentry 후보 무시: band_touch but not valid rally (is_up_close={is_up_close}, is_bullish_or_doji={is_bullish_or_doji})", "DEBUG", candle['date'])
            else:
                # no touch
                pass
                    

        elif self.stage == "reentry_confirmation":
            if (self.band and candle['Close'] > self.band['high']) or candle['Close'] < self.straight_valley:
                band_high_val = self.band.get('high') if self.band else None
                band_high_str = f"{band_high_val:.2f}" if isinstance(band_high_val, (int, float)) else "N/A"
                reason = f"Close({candle['Close']:.2f}) > Band High({band_high_str})" if (band_high_val is not None and candle['Close'] > band_high_val) else f"Close({candle['Close']:.2f}) < Straight Valley({self.straight_valley:.2f})"
                self.reset(reason); return
                
            # 문서 기준 완료 판정(대칭 규칙): 직전 캔들 타입에 따라 분기 검증
            prev_candle = self.candle_history[-2] if len(self.candle_history) >= 2 else None
            if prev_candle is None:
                doc_ok = (candle['Close'] < candle['Open'])
            else:
                if prev_candle['Close'] < prev_candle['Open']:
                    doc_ok = (candle['Close'] < prev_candle['Close'])
                else:
                    doc_ok = (candle['Close'] < prev_candle['Open'])

            if doc_ok:
                self.stage = "Completed"
                self.expectation_mode = False
                self.log_event(f"*** Double Top 패턴 완성! *** Price={candle['Close']:.0f}", "INFO", candle['date'])
