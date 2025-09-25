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
    def __init__(self, n_criteria=2, n_window=1):
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
        # 보관용: JS 확정으로 제거된 secondary 극점들을 저장(디버깅/감사용)
        self.archived_secondaries: List[Dict] = []

        # --- ✨ 1단계 추가: 신뢰도 모델 상태 관리 변수 ✨ ---
        self.n_window: int = n_window # N-Window 크기 (기본값 3)

        # Secondary 극점 탐색 상태를 관리합니다.
        # 'IDLE': 기본 상태
        # 'TRACKING_PEAK': JS Valley 이후 Secondary Peak 후보를 찾는 중
        # 'TRACKING_VALLEY': JS Peak 이후 Secondary Valley 후보를 찾는 중
        self.secondary_search_state: str = 'IDLE'

        # 현재 추적 중인 1등급(Base) 극점 후보를 저장합니다.
        # 이 후보는 더 나은 후보가 나타나면 갱신됩니다.
        self.candidate_extremum: Optional[Dict] = None
        # --- 1단계 추가 끝 ---

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
            # Temporarily use a simple formatter for this logger call so that
            # the logger name and level do not appear in the output for this module.
            # We restore original formatters after emitting the log.
            record_msg = f"[{log_date_str}] {message}"
            # Collect handlers from this logger and its ancestors (where propagate applies)
            handlers = []
            old_formatters = []
            try:
                l = logger
                while l is not None:
                    if getattr(l, 'handlers', None):
                        for h in l.handlers:
                            handlers.append(h)
                    if not getattr(l, 'propagate', True):
                        break
                    l = getattr(l, 'parent', None)

                # deduplicate handlers while preserving order
                seen = set()
                unique_handlers = []
                for h in handlers:
                    if id(h) not in seen:
                        unique_handlers.append(h)
                        seen.add(id(h))

                for h in unique_handlers:
                    old_formatters.append(h.formatter)
                    try:
                        h.setFormatter(logging.Formatter("%(message)s"))
                    except Exception:
                        old_formatters[-1] = None

                getattr(logger, level.lower())(record_msg)
            finally:
                # restore formatters
                for h, fmt in zip(unique_handlers, old_formatters):
                    if fmt is not None:
                        try:
                            h.setFormatter(fmt)
                        except Exception:
                            pass

    # trend.py -> _find_base_extremum_n_window 함수

    def _find_base_extremum_n_window(self, i: int, data: pd.DataFrame, detected_date: pd.Timestamp) -> List[Dict]:
        """
        [Look-ahead 버전]
        N-Window 중앙 캔들 방식으로 1등급 '기본 극점'을 찾습니다.
        """
        # n_window 값은 좌우에 몇개의 데이터를 사용할지 결정
        n = self.n_window

        
        if i < n * 2:
            return None

        window = data.iloc[i - n*2 : i + 1]
        
        # <<--- 핵심 수정 1: 검사 대상을 '중앙 캔들'로 변경 --- >>
        # n=2일 경우, i-1이 중앙 캔들이 됩니다.
        target_candle_index = i - n
        target_candle = data.iloc[target_candle_index]

        is_peak = target_candle['High'] == window['High'].max() and len(window[window['High'] == target_candle['High']]) == 1
        is_valley = target_candle['Low'] == window['Low'].min() and len(window[window['Low'] == target_candle['Low']]) == 1

        found = []
        if is_peak:
            found.append({
                'type': 'sec_peak',
                'confidence': 'base',
                'index': target_candle_index, # <-- 인덱스도 target_candle_index 사용
                'value': target_candle['High'],
                'actual_date': data.index[target_candle_index], # <-- 날짜도 target_candle_index 사용
                'detected_date': detected_date # 감지 시점은 현재 캔들(i)의 날짜
            })
        if is_valley:
            # (Valley 로직도 대칭적으로 수정)
            found.append({
                'type': 'sec_valley',
                'confidence': 'base',
                'index': target_candle_index,
                'value': target_candle['Low'],
                'actual_date': data.index[target_candle_index],
                'detected_date': detected_date
            })

        return found

    def _handle_base_extremum(self, base_extremum: Dict, detected_date: pd.Timestamp):
        """
        [최종 완성 버전 V2]
        1등급 극점을 처리합니다. 'strict 모드 무시' 로그와 개선된 에러 처리를 포함합니다.
        """

        # --- ✨ 'strict' 모드 무시 로그 추가 ✨ ---
        if self.secondary_search_state == 'TRACKING_PEAK' and base_extremum['type'] == 'sec_peak':
            last_prov_peak = next((p for p in reversed(self.secondary_peaks) if p.get('confidence') == 'provisional'), None)
            if last_prov_peak and base_extremum['value'] > last_prov_peak['value']:
                # last_prov_peak의 actual_date가 있으면 날짜 문자열로 포함
                lp_date = last_prov_peak.get('actual_date')
                try:
                    if lp_date is not None and hasattr(lp_date, 'strftime'):
                        lp_date_str = lp_date.strftime('%Y-%m-%d')
                    else:
                        lp_date_str = str(lp_date) if lp_date is not None else 'N/A'
                except Exception:
                    lp_date_str = str(lp_date)
                self.log_event(detected_date, f"더 높은 Peak 후보({base_extremum['value']:.2f}) 발견. strict 모드이므로 기존 2등급 Peak({last_prov_peak['value']:.2f} @ {lp_date_str}) 유지.", "INFO")

        elif self.secondary_search_state == 'TRACKING_VALLEY' and base_extremum['type'] == 'sec_valley':
            last_prov_valley = next((p for p in reversed(self.secondary_valleys) if p.get('confidence') == 'provisional'), None)
            if last_prov_valley and base_extremum['value'] < last_prov_valley['value']:
                lv_date = last_prov_valley.get('actual_date')
                try:
                    if lv_date is not None and hasattr(lv_date, 'strftime'):
                        lv_date_str = lv_date.strftime('%Y-%m-%d')
                    else:
                        lv_date_str = str(lv_date) if lv_date is not None else 'N/A'
                except Exception:
                    lv_date_str = str(lv_date)
                self.log_event(detected_date, f"더 낮은 Valley 후보({base_extremum['value']:.2f}) 발견. strict 모드이므로 기존 2등급 Valley({last_prov_valley['value']:.2f} @ {lv_date_str}) 유지.", "INFO")
        # --- ✨ 로그 추가 끝 ✨ ---

        # --- Secondary Peak 탐색 및 승격 로직 ---
        if self.secondary_search_state == 'TRACKING_PEAK' and base_extremum['type'] == 'sec_peak':
            if self.candidate_extremum is None or base_extremum['value'] > self.candidate_extremum['value']:
                self.candidate_extremum = base_extremum
                self.log_event(detected_date, f"DEBUG: Peak 후보 갱신: {base_extremum['value']:.2f} at {base_extremum['actual_date'].strftime('%y%m%d')}", "DEBUG")
                return
            else:
                provisional_peak = self.candidate_extremum.copy()
                provisional_peak['confidence'] = 'provisional'
                provisional_peak['detected_date'] = detected_date
                # 표시용 메타: 즉시 승격(live)
                provisional_peak['promotion'] = 'live'

                # OHLC 보강: 개발 단계에서는 strict하게 실패를 드러내도록 함
                try:
                    actual_candle = self.data.loc[provisional_peak['actual_date']]
                    provisional_peak.update({
                        'open': actual_candle['Open'], 'high': actual_candle['High'],
                        'low': actual_candle['Low'], 'close': actual_candle['Close']
                    })
                except KeyError:
                    self.log_event(detected_date, f"심각한 오류: 2등급 Peak 승격 시 OHLC 날짜({provisional_peak.get('actual_date')})를 찾을 수 없음. 데이터 정합성 확인 필요.", "ERROR")
                    raise

                if not any(p.get('index') == provisional_peak.get('index') and p.get('type') == provisional_peak.get('type') for p in self.secondary_peaks):
                    self.secondary_peaks.append(provisional_peak)
                    self.newly_registered_peak = provisional_peak
                    be_idx = provisional_peak.get('index', 'N/A')
                    self.log_event(detected_date, f"(idx={be_idx}) ✨ 2등급 '잠정적 Peak' 승격: {provisional_peak['value']:.2f} at {provisional_peak['actual_date'].strftime('%y%m%d')} (트리거: {base_extremum['value']:.2f})", "INFO")

                self.candidate_extremum = base_extremum

        # --- Secondary Valley 탐색 및 승격 로직 (대칭) ---
        elif self.secondary_search_state == 'TRACKING_VALLEY' and base_extremum['type'] == 'sec_valley':
            if self.candidate_extremum is None or base_extremum['value'] < self.candidate_extremum['value']:
                self.candidate_extremum = base_extremum
                self.log_event(detected_date, f"DEBUG: Valley 후보 갱신: {base_extremum['value']:.2f} at {base_extremum['actual_date'].strftime('%y%m%d')}", "DEBUG")
                return
            else:
                provisional_valley = self.candidate_extremum.copy()
                provisional_valley['confidence'] = 'provisional'
                provisional_valley['detected_date'] = detected_date
                # 즉시 승격 표시(live) - Peak와 대칭되도록 설정
                provisional_valley['promotion'] = 'live'

                try:
                    actual_candle = self.data.loc[provisional_valley['actual_date']]
                    provisional_valley.update({
                        'open': actual_candle['Open'], 'high': actual_candle['High'],
                        'low': actual_candle['Low'], 'close': actual_candle['Close']
                    })
                except KeyError:
                    self.log_event(detected_date, f"심각한 오류: 2등급 Valley 승격 시 OHLC 날짜({provisional_valley.get('actual_date')})를 찾을 수 없음. 데이터 정합성 확인 필요.", "ERROR")
                    raise

                if not any(v.get('index') == provisional_valley.get('index') and v.get('type') == provisional_valley.get('type') for v in self.secondary_valleys):
                    self.secondary_valleys.append(provisional_valley)
                    self.newly_registered_valley = provisional_valley
                    be_idx = provisional_valley.get('index', 'N/A')
                    self.log_event(detected_date, f"(idx={be_idx}) ✨ 2등급 '잠정적 Valley' 승격: {provisional_valley['value']:.2f} at {provisional_valley['actual_date'].strftime('%y%m%d')} (트리거: {base_extremum['value']:.2f})", "INFO")

                self.candidate_extremum = base_extremum

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
        """JS Peak 등록 (소급 승격 로직 포함)"""
        # 소급 승격 로직: 시간적 범위를 명확히 제한하여 미래 사건이 과거 승격에 영향을 주지 않도록 함
        if self.secondary_search_state == 'TRACKING_VALLEY' and self.candidate_extremum:
            # 이전 JS Peak을 js_peaks에서만 조회하여 시간적 시작점을 JS 극점으로 제한
            last_js_peak_list = [p for p in self.js_peaks if p.get('index', -1) < index]
            last_js_peak = max(last_js_peak_list, key=lambda x: x['index']) if last_js_peak_list else None
            last_js_peak_idx = last_js_peak['index'] if last_js_peak else -1

            # 조사 범위를 이전 JS Peak 이후 ~ 현재 JS Peak(actual index) 이전으로 제한
            new_js_peak_actual_idx = index
            promoted_valleys_in_session = [
                v for v in self.secondary_valleys
                if v.get('confidence') == 'provisional' and last_js_peak_idx < v.get('index', -1) < new_js_peak_actual_idx
            ]

            if not promoted_valleys_in_session:
                try:
                    cand_actual = self.candidate_extremum.get('actual_date')
                except Exception:
                    cand_actual = None

                if cand_actual is None:
                    self.log_event(detected_date, f"소급승격 거부: candidate actual_date 없음 ({self.candidate_extremum})", "DEBUG")
                else:
                    if pd.Timestamp(cand_actual) <= pd.Timestamp(actual_date):
                        provisional_valley = self.candidate_extremum.copy()
                        provisional_valley['confidence'] = 'provisional'
                        provisional_valley['detected_date'] = detected_date
                        try:
                            actual_candle = self.data.loc[provisional_valley['actual_date']]
                            provisional_valley.update({
                                'open': actual_candle['Open'], 'high': actual_candle['High'],
                                'low': actual_candle['Low'], 'close': actual_candle['Close']
                            })
                            if not any(v.get('index') == provisional_valley.get('index') for v in self.secondary_valleys):
                                self.secondary_valleys.append(provisional_valley)
                                self.newly_registered_valley = provisional_valley
                                self.log_event(detected_date, f"✨ 2등급 '잠정적 Valley' 소급 승격: {provisional_valley['value']:.2f} at {provisional_valley['actual_date'].strftime('%y%m%d')}", "INFO")
                        except KeyError:
                            self.log_event(detected_date, f"오류: 2등급 Valley 소급 승격 시 OHLC 정보 조회 실패({provisional_valley['actual_date']})", "ERROR")
        # --- ✨ 소급 승격 로직 끝 ✨ ---

        try:
            actual_candle = data.loc[actual_date]
        except KeyError:
            self.log_event(detected_date, f"오류: JS Peak 등록 시 실제 캔들({actual_date})을 찾을 수 없음", "ERROR")
            return

        new_peak = {
            'type': 'js_peak', 'confidence': 'confirmed',
            'index': index, 'value': value,
            'actual_date': actual_date, 'detected_date': detected_date,
            'open': actual_candle['Open'], 'high': actual_candle['High'],
            'low': actual_candle['Low'], 'close': actual_candle['Close']
        }
        if not any(p['index'] == index for p in self.js_peaks):
            self.js_peaks.append(new_peak)
            self.newly_registered_peak = new_peak
            self.log_event(detected_date, f"Idx={index} JS Peak 등록: Val={value:.2f}, Actual={actual_date.strftime('%y%m%d')}", "INFO")


            self.secondary_search_state = 'TRACKING_VALLEY'
            # 후보가 현재 'valley' 타입이면 유지, 그렇지 않으면 초기화
            if not (self.candidate_extremum and 'valley' in self.candidate_extremum.get('type', '')):
                self.candidate_extremum = None
            self.log_event(detected_date, f"상태 전환: Secondary Valley 탐색 시작 ('TRACKING_VALLEY')", "INFO")

            # --- JS Peak 확정에 따라 동일 위치의 secondary peak 정리(아카이브) ---
            try:
                removed = [p for p in self.secondary_peaks if p.get('index') == index]
                if removed:
                    self.archived_secondaries.extend(removed)
                    self.secondary_peaks = [p for p in self.secondary_peaks if p.get('index') != index]
                    for r in removed:
                        self.log_event(detected_date, f"Secondary Peak archived due to JS Peak confirmation: idx={index}, val={r.get('value')}", "INFO")
            except Exception as e:
                self.log_event(detected_date, f"오류: JS Peak 확정 후 secondary 정리 실패: {e}", "ERROR")


    def register_js_valley(self, index: int, value: float, actual_date: pd.Timestamp, detected_date: pd.Timestamp, data: pd.DataFrame):
        """JS Valley 등록 (소급 승격 로직 포함)"""
        # 소급 승격 로직: 시간적 범위를 명확히 제한하여 미래 사건이 과거 승격에 영향을 주지 않도록 함
        if self.secondary_search_state == 'TRACKING_PEAK' and self.candidate_extremum:
            last_js_valley_list = [v for v in self.js_valleys if v.get('index', -1) < index]
            last_js_valley = max(last_js_valley_list, key=lambda x: x['index']) if last_js_valley_list else None
            last_js_valley_idx = last_js_valley['index'] if last_js_valley else -1

            new_js_valley_actual_idx = index
            promoted_peaks_in_session = [
                p for p in self.secondary_peaks
                if p.get('confidence') == 'provisional' and 
                   last_js_valley_idx < p.get('index', -1) < new_js_valley_actual_idx
            ]

            if not promoted_peaks_in_session:
                try:
                    cand_actual = self.candidate_extremum.get('actual_date')
                except Exception:
                    cand_actual = None

                if cand_actual is None:
                    self.log_event(detected_date, f"소급승격 거부: candidate actual_date 없음 ({self.candidate_extremum})", "DEBUG")
                else:
                    if pd.Timestamp(cand_actual) <= pd.Timestamp(actual_date):
                        provisional_peak = self.candidate_extremum.copy()
                        provisional_peak['confidence'] = 'provisional'
                        provisional_peak['detected_date'] = detected_date
                        # 소급 승격 표시(retro)
                        provisional_peak['promotion'] = 'retro'
                        try:
                            actual_candle = self.data.loc[provisional_peak['actual_date']]
                            provisional_peak.update({
                                'open': actual_candle['Open'], 'high': actual_candle['High'],
                                'low': actual_candle['Low'], 'close': actual_candle['Close']
                            })
                            if not any(p.get('index') == provisional_peak.get('index') for p in self.secondary_peaks):
                                self.secondary_peaks.append(provisional_peak)
                                self.newly_registered_peak = provisional_peak
                                be_idx = provisional_peak.get('index', 'N/A')
                                # log with idx and promotion tag
                                self.log_event(detected_date, f"(idx={be_idx}) ✨ 2등급 '잠정적 Peak' 소급 승격: {provisional_peak['value']:.2f} at {provisional_peak['actual_date'].strftime('%y%m%d')}", "INFO")
                        except KeyError:
                            self.log_event(detected_date, f"오류: 2등급 Peak 소급 승격 시 OHLC 정보 조회 실패({provisional_peak['actual_date']})", "ERROR")
        # --- ✨ 소급 승격 로직 끝 ✨ ---

        try:
            actual_candle = data.loc[actual_date]
        except KeyError:
            self.log_event(detected_date, f"오류: JS Valley 등록 시 실제 캔들({actual_date})을 찾을 수 없음", "ERROR")
            return

        new_valley = {
            'type': 'js_valley', 'confidence': 'confirmed',
            'index': index, 'value': value,
            'actual_date': actual_date, 'detected_date': detected_date,
            'open': actual_candle['Open'], 'high': actual_candle['High'],
            'low': actual_candle['Low'], 'close': actual_candle['Close']
        }
        if not any(v['index'] == index for v in self.js_valleys):
            self.js_valleys.append(new_valley)
            self.newly_registered_valley = new_valley
            self.log_event(detected_date, f"Idx={index} JS Valley 등록: Val={value:.2f}, Actual={actual_date.strftime('%y%m%d')}", "INFO")

            
            self.secondary_search_state = 'TRACKING_PEAK'
            # 후보가 현재 'peak' 타입이면 유지, 그렇지 않으면 초기화
            if not (self.candidate_extremum and 'peak' in self.candidate_extremum.get('type', '')):
                self.candidate_extremum = None
            self.log_event(detected_date, f"상태 전환: Secondary Peak 탐색 시작 ('TRACKING_PEAK')", "INFO")

            # --- JS Valley 확정에 따라 동일 위치의 secondary valley 정리(아카이브) ---
            try:
                removed = [v for v in self.secondary_valleys if v.get('index') == index]
                if removed:
                    self.archived_secondaries.extend(removed)
                    self.secondary_valleys = [v for v in self.secondary_valleys if v.get('index') != index]
                    for r in removed:
                        self.log_event(detected_date, f"Secondary Valley archived due to JS Valley confirmation: idx={index}, val={r.get('value')}", "INFO")
            except Exception as e:
                self.log_event(detected_date, f"오류: JS Valley 확정 후 secondary 정리 실패: {e}", "ERROR")



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
        """개별 캔들 처리 메인 로직 (신뢰도 모델 3단계 적용)"""
        self.log_event(date, f"Candle OHLC: O={current['Open']:.2f} H={current['High']:.2f} L={current['Low']:.2f} C={current['Close']:.2f}", "DEBUG")
        
        self.newly_registered_peak = None
        self.newly_registered_valley = None
        
        # --- 1/2/3단계 로직 실행 ---
        # 1단계: N-Window로 1등급 '기본 극점' 탐지 (리스트 반환)
        base_extremums = self._find_base_extremum_n_window(i, data, date)

        if base_extremums:
            # 디버그/테스트 시 로그 레벨을 쉽게 바꿀 수 있도록 로컬 변수로 분리
            log_level = "INFO"  # 필요 시 "INFO"로 변경하여 1등급 발견 로그를 보이게 할 수 있음
            for base_extremum in base_extremums:
                # 로그에 인덱스 정보를 추가하여 디버깅 시 위치를 바로 파악할 수 있도록 함
                be_idx = base_extremum.get('index', 'N/A')
                self.log_event(date, f"(idx={be_idx}) 1등급 '기본 극점' 후보 발견: {base_extremum['type']} @ {base_extremum['value']:.2f}", log_level)
                # 3단계: 각 1등급 극점을 처리하여 2등급으로 승격 시도
                self._handle_base_extremum(base_extremum, date)
        # --- 로직 실행 끝 ---

        is_inside = self.is_inside_bar(current['High'], current['Low'], self.reference_high, self.reference_low)

        

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
