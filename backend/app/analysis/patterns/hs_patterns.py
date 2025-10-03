import pandas as pd
import logging
from typing import Optional
from .base import PatternDetector

from app.utils.logger_config import get_logger

logger = get_logger("chartinsight-api.analysis", "analysis_engine")

class HeadAndShouldersDetector(PatternDetector):
    """Head and Shoulders 패턴 감지기 (수정 V4 - 규칙 변경 및 옵션 추가)"""
    def __init__(self, p1, data, creation_event_date: pd.Timestamp = None, peaks=None, valleys=None, completion_mode='aggressive', structural_points: dict = None, initial_stage: Optional[str] = None):
        self.pattern_type = "HS"
        super().__init__(p1, data, creation_event_date, peaks, valleys)
        # 안전한 포인트 초기화
        self.P1 = None; self.V1 = None; self.P2 = None; self.V2 = None; self.P3 = None; self.V3 = None
        self.P1 = p1
        self.completion_mode = completion_mode
        self.stage = initial_stage if initial_stage is not None else "AwaitingCompletion"

        # structural_points가 주어지면 안전히 할당
        if structural_points and isinstance(structural_points, dict):
            for k in ['P1','V1','P2','V2','P3','V3']:
                if k in structural_points:
                    setattr(self, k, structural_points.get(k))

    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None):
        """간소화된 H&S update:
        - 구조 검증/실시간 P3 탐지는 manager에서 수행한다고 가정
        - 감지기는 치명적 구조 붕괴 리셋과 AwaitingCompletion에서의 완성 판정만 수행
        """
        if not self.expectation_mode:
            return

        # 입력 유효성 검사
        if not isinstance(candle, dict) or not all(k in candle for k in ['date','Close','Open','High','Low']):
            self.log_event("오류: update에 전달된 candle 객체 불완전", "ERROR")
            return

        self.candle_history.append(candle)
        current_close = candle['Close']
        current_high = candle['High']
        current_low = candle['Low']

        # 최신 로직: 구조 검증은 탐색 단계에서 완료됨. 업데이트에서는 치명적 오류만 처리.
        if self.stage == "AwaitingCompletion":
            try:
                current_index_loc = self.data.index.get_loc(candle['date'])
            except Exception:
                self.log_event(f"오류: 현재 캔들 날짜를 self.data에서 찾을 수 없음 ({candle.get('date')})", "ERROR")
                self.reset("Internal data index error")
                return

            if current_index_loc <= 0:
                self.log_event("직전 캔들 없음으로 완성 조건 확인 불가", "WARNING")
                return

            prev_candle = self.data.iloc[current_index_loc - 1]

            # 사후 무효화: V3 이후 Close > max(P1, P3) 발생 시 리셋 (동적 규칙)
            try:
                if getattr(self, 'V3', None) and getattr(self, 'P1', None) and getattr(self, 'P3', None):
                    v3_idx = int(self.V3.get('index', -1))
                    p1_val = self.P1.get('value')
                    p3_val = self.P3.get('value')
                    if p1_val is not None and p3_val is not None and v3_idx >= 0 and current_index_loc > v3_idx:
                        invalidation_level = max(float(p1_val), float(p3_val))
                        if candle['Close'] > invalidation_level:
                            self.log_event(f"V3 이후 max(P1,P3) 상회(무효화): Level={invalidation_level:.0f}, Close={candle['Close']:.0f}", "WARNING")
                            self.reset("V3 이후 max(P1,P3) 상회(무효화)")
                            return
            except Exception as e:
                self.log_event(f"동적 무효화 검사 오류: {e}", "ERROR")
                pass

            if self.completion_mode == 'aggressive':
                if candle['Close'] < candle['Open'] and candle['Close'] < prev_candle['Low']:
                    self.stage = "Completed"
                    self.expectation_mode = False
                    self.log_event(f"*** Head & Shoulders 패턴 완성! (Aggressive) *** Price={candle['Close']:.0f}", "INFO")
                    return

            elif self.completion_mode == 'neckline':
                if getattr(self, 'V2', None) and getattr(self, 'V3', None):
                    try:
                        v2_idx = self.V2['index']; v3_idx = self.V3['index']
                        v2_val = self.V2.get('value'); v3_val = self.V3.get('value')
                        if v2_val is None or v3_val is None:
                            self.log_event("넥라인 계산을 위한 V2/V3 값 누락", "WARNING")
                            return
                        if v3_idx > v2_idx:
                            neck_run = v3_idx - v2_idx
                            neck_rise = v3_val - v2_val
                            neck_slope = neck_rise / neck_run if neck_run != 0 else 0
                            current_i = current_index_loc
                            neck_val = v2_val + (current_i - v2_idx) * neck_slope
                            if candle['Close'] <= neck_val:
                                self.stage = "Completed"
                                self.expectation_mode = False
                                self.neckline_level = neck_val
                                self.log_event(f"*** Head & Shoulders 패턴 완성! (Neckline Break) *** Price={candle['Close']:.0f}, Neckline={neck_val:.0f}", "INFO")
                                return
                        else:
                            self.log_event("넥라인 계산을 위한 V2/V3 인덱스 오류", "WARNING")
                    except Exception as e:
                        self.log_event(f"넥라인 완성 조건 확인 중 예외: {e}", "ERROR")
                        return

# --- 신규: Inverse Head and Shoulders 감지기 클래스 ---
class InverseHeadAndShouldersDetector(PatternDetector):
    """Inverse Head and Shoulders 패턴 감지기 (수정 V4 - 규칙 변경 및 옵션 추가)"""
    def __init__(self, v1, data, creation_event_date: pd.Timestamp = None, peaks=None, valleys=None, completion_mode='neckline', structural_points: dict = None, initial_stage: Optional[str] = None):
        self.pattern_type = "IHS"
        super().__init__(v1, data, creation_event_date, peaks, valleys)
        # 안전한 포인트 초기화 (IHS용 변수와 일반 변수 모두 준비)
        self.P1_ihs = None; self.V1_ihs = None; self.P2_ihs = None; self.V2_ihs = None; self.P3_ihs = None; self.V3_ihs = None
        self.P1 = None; self.V1 = None; self.P2 = None; self.V2 = None; self.P3 = None; self.V3 = None

        # anchor (일반적으로 V1)를 기본으로 설정
        self.V1 = v1
        self.V1_ihs = v1
        self.completion_mode = completion_mode
        self.stage = initial_stage if initial_stage is not None else "AwaitingCompletion"

        # structural_points가 주어지면 안전히 할당(대칭성 유지)
        if structural_points and isinstance(structural_points, dict):
            # IHS 키는 P1,V1,P2,V2,P3,V3 (IHS 시 매핑됨)
            for k in ['P1','V1','P2','V2','P3','V3']:
                if k in structural_points:
                    # IHS 전용과 일반 명칭 모두에 할당
                    setattr(self, f"{k}_ihs", structural_points.get(k))
                    setattr(self, k, structural_points.get(k))
        # 생성 로그 (간단히)
        try:
            self.log_event(f"Stage 0 -> 1: 감지기 생성 (V1={self.V1.get('actual_date').strftime('%y%m%d')}@ {self.V1.get('value', 0):.0f})", "INFO")
        except Exception:
            self.log_event("Stage 0 -> 1: IHS 감지기 생성", "INFO")

    def update(self, candle, newly_registered_peak=None, newly_registered_valley=None):
        """IHS update (간소화):
        - 구조 검증 및 V3 탐지 로직 제거
        - 치명적 붕괴 리셋과 AwaitingCompletion에서의 완성 조건만 처리
        """
        if not self.expectation_mode:
            return

        # 입력 검증
        if not isinstance(candle, dict) or not all(k in candle for k in ['date', 'Close', 'Open', 'High', 'Low']):
            self.log_event("오류: update에 전달된 candle 객체 불완전", "ERROR")
            return

        self.candle_history.append(candle)
        current_close = candle['Close']
        current_high = candle['High']
        current_low = candle['Low']

        # 최신 로직: 구조 검증은 탐색 단계에서 완료됨. 업데이트에서는 치명적 오류만 처리.
        if self.stage == "AwaitingCompletion":
            try:
                current_index_loc = self.data.index.get_loc(candle['date'])
            except Exception:
                self.log_event(f"오류: 현재 캔들 날짜를 데이터 인덱스에서 찾을 수 없음 ({candle['date']})", "ERROR")
                self.reset("Internal data index error")
                return

            if current_index_loc <= 0:
                self.log_event("직전 캔들 없음으로 완성 조건 확인 불가", "WARNING")
                return

            prev_candle = self.data.iloc[current_index_loc - 1]

            # 사후 무효화: P3 이후 Close < min(V1, V3) 발생 시 리셋 (동적 규칙, min 사용)
            try:
                if getattr(self, 'P3_ihs', None) and getattr(self, 'V1_ihs', None) and getattr(self, 'V3_ihs', None):
                    p3_idx = int(self.P3_ihs.get('index', -1))
                    v1_val = self.V1_ihs.get('value')
                    v3_val = self.V3_ihs.get('value')
                    if v1_val is not None and v3_val is not None and p3_idx >= 0 and current_index_loc > p3_idx:
                        # [수정!] 동적 무효화 기준선은 두 어깨 저점 중 '더 낮은' 값
                        invalidation_level = min(float(v1_val), float(v3_val))
                        if candle['Close'] < invalidation_level:
                            self.log_event(f"P3 이후 min(V1,V3) 하회(무효화): Level={invalidation_level:.0f}, Close={candle['Close']:.0f}", "WARNING")
                            self.reset("P3 이후 min(V1,V3) 하회(무효화)")
                            return
            except Exception as e:
                self.log_event(f"동적 무효화 검사 오류: {e}", "ERROR")
                pass

            if self.completion_mode == 'aggressive':
                if candle['Close'] > candle['Open'] and candle['Close'] > prev_candle['High']:
                    self.stage = "Completed"
                    self.expectation_mode = False
                    self.log_event(f"*** Inverse Head & Shoulders 패턴 완성! (Aggressive) *** Price={candle['Close']:.0f}, Prev High={prev_candle['High']:.0f}", "INFO")
                    return

            elif self.completion_mode == 'neckline':
                if getattr(self, 'P2_ihs', None) and getattr(self, 'P3_ihs', None):
                    try:
                        p2_idx = self.P2_ihs['index']; p3_idx = self.P3_ihs['index']
                        p2_val = self.P2_ihs.get('value'); p3_val = self.P3_ihs.get('value')
                        if p2_val is None or p3_val is None:
                            self.log_event("넥라인 계산을 위한 P2/P3 값 누락", "WARNING")
                            return
                        if p3_idx > p2_idx:
                            neck_run = p3_idx - p2_idx
                            neck_rise = p3_val - p2_val
                            neck_slope = neck_rise / neck_run if neck_run != 0 else 0
                            current_i = current_index_loc
                            neck_val = p2_val + (current_i - p2_idx) * neck_slope
                            if candle['Close'] >= neck_val:
                                self.stage = "Completed"
                                self.expectation_mode = False
                                self.neckline_level = neck_val
                                self.log_event(f"*** Inverse Head & Shoulders 패턴 완성! (Neckline Break) *** Price={candle['Close']:.0f}, Neckline={neck_val:.0f}", "INFO")
                                return
                        else:
                            self.log_event("넥라인 계산을 위한 P2/P3 인덱스 오류", "WARNING")
                    except Exception as e:
                        self.log_event(f"넥라인 완성 조건 확인 중 예외: {e}", "ERROR")
                        return

