import numpy as np
import pandas as pd
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

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

        # Stage 1 리셋: V2 감지 전 P1 고점 상회 (`현재 High > P1['value']`).
        if self.P1 and current_high > self.P1['value'] and self.stage == "LeftShoulderPeakDetected": 
            self.log_event(f"리셋 (Stage 1): 현재 High({current_high:.0f}) > P1({self.P1['value']:.0f})", "INFO"); 
            self.reset("P1 고점 상회"); 
            return
        #Stage 2 리셋: P2 감지 전 V2 저점 하회 (`현재 Close < V2['value']`).
        if self.V2 and current_close < self.V2['value'] and self.stage == "LeftNecklineValleyDetected": 
            self.log_event(f"리셋 (Stage 2): 현재 Close({current_close:.0f}) < V2({self.V2['value']:.0f})", "INFO"); 
            self.reset("V2 저점 하회"); 
            return
        # P2(머리) 고점 돌파 리셋: P2 형성 후 ~ 완성 전까지 모든 단계에서 확인
        if self.P2 and current_high > self.P2['value'] and self.stage in ["HeadPeakDetected", "RightNecklineValleyDetected", "AwaitingCompletion"]:
            self.log_event(f"리셋 (Stage {self.stage}): 현재 High({current_high:.0f}) > P2({self.P2['value']:.0f})", "INFO"); 
            self.reset("머리 고점 상회"); 
            return
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
        
        """H&S 또는 IHS 패턴을 구성하는 5개의 핵심 구조적 극점을 탐색합니다.

        가장 최근에 발생한 극점부터 시작하여 과거 기록을 역추적하며, H&S 패턴의
        뼈대(V1, P1, V2, P2, V3) 또는 IHS 패턴의 뼈대(P1, V1, P2, V2, P3)를 식별합니다.

        이 함수의 핵심적인 기능은 '연속 버퍼'를 이용한 지능적인 필터링입니다.
        연속으로 나타나는 동일 타입의 극점들(예: 여러 개의 작은 봉우리)을 하나의
        그룹으로 묶고, 그 그룹 내에서 가장 의미 있는 극점(가장 높거나 낮은 값)
        하나만을 대표로 선택합니다. 이 과정을 통해 시장의 미세한 노이즈를
        효과적으로 제거하고 명확한 패턴 구조만을 추출할 수 있습니다.

        Args:
            all_extremums (List[Dict]): JS와 Secondary를 포함하여 시간순(`index` 기준)으로
                정렬된 전체 극점 리스트.
            lookback_limit (int): 패턴 구조를 찾기 위해 과거로 탐색할 최대 극점의 수.
                계산 효율성과 패턴의 시의성을 보장하는 역할을 합니다.

        Returns:
            Optional[Dict[str, Dict]]:
                성공 시, 찾은 5개의 구조적 극점과 패턴 타입을 포함하는 딕셔너리를
                반환합니다. 예: `{'V1': {...}, 'P1': {...}, 'V2': {...}, 'P2': {...}, 'V3': {...}, 'pattern_type': 'HS'}`
                
                실패 시 (유효한 구조를 찾지 못했거나 최종 시간 순서 검증에 실패한 경우),
                `None`을 반환합니다.
        """
        if len(all_extremums) < 5:
            return None

        structural_points = {}
        last_extremum = all_extremums[-1]
        current_index = len(all_extremums) - 1
        points_found = 0
        consecutive_buffer = [] # 연속된 동일 타입 극점 임시 저장

        # 패턴 타입 결정 및 목표 극점 설정
        # 마지막 극점이 'valley'인 경우에는 H&S 패턴을 찾습니다. 이 때 마지막 극점은 'V3'로 간주하며, 찾아야 하는 타겟은 'P2'로 설정
        # 마지막 극점이 'peak'인 경우에는 IHS 패턴을 찾습니다. 이 때 마지막 극점은 'P3'로 간주하며, 찾아야 하는 타겟은 'V2'로 설정
        # 확장: 문서/실전 요구에 따라 5개의 구조적 극점(V1,P1,V2,P2,V3 또는 P1,V1,P2,V2,P3)을 찾도록 조정
        if last_extremum.get('type', '').endswith('valley'):
            pattern_type = 'HS'
            # 역순으로 찾아가며 V3(이미 있음) -> P2 -> V2 -> P1 -> V1 을 수집
            target_sequence = ['V3', 'P2', 'V2', 'P1', 'V1']
            structural_points['V3'] = last_extremum
            current_target_role = 'P2'
            current_target_type = 'peak'
            points_found = 1
        elif last_extremum.get('type', '').endswith('peak'):
            pattern_type = 'IHS'
            # 역순으로 찾아가며 P3(이미 있음) -> V2 -> P2 -> V1 -> P1 수집
            target_sequence = ['P3', 'V2', 'P2', 'V1', 'P1']
            structural_points['P3'] = last_extremum
            current_target_role = 'V2'
            current_target_type = 'valley'
            points_found = 1
        else:
            return None # 마지막 극점 타입 불분명

        # 루프 시작점: 마지막 극점 바로 이전부터
        search_index = current_index - 1
        lookback_count = 0
        
      

        # --- 구조적 극점 역방향 탐색 루프 ---
        # 가장 마지막 극점부터 시작하여 과거로 이동하며 H&S/IHS 패턴의 뼈대를 구성하는
        # 5개의 구조적 극점을 순서대로 찾습니다.
        #
        # 핵심 전략:
        # 1. '연속 버퍼(consecutive_buffer)'를 사용하여 연속으로 나타나는 동일 타입의 극점들을 그룹화합니다.
        # 2. 다른 타입의 극점이 나타나면, 버퍼에 저장된 후보들 중 가장 의미 있는 극점
        #    (Peak 중 최고가, Valley 중 최저가) 하나만을 대표로 선택하여 구조에 포함시킵니다.
        #
        # 종료 조건:
        # - 5개의 구조적 극점을 모두 찾았을 경우
        # - 탐색 범위 제한(lookback_limit)에 도달했을 경우
        # - 더 이상 탐색할 과거 극점이 없을 경우
        

        while search_index >= 0 and points_found < 5 and lookback_count < lookback_limit:
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
                        if points_found == 5: break # 필요한 4개 다 찾음

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
        if points_found < len(target_sequence) and consecutive_buffer:
            representative_point = None
            if current_target_type == 'peak':
                representative_point = max(consecutive_buffer, key=lambda x: x.get('value', -np.inf))
            else: # valley
                representative_point = min(consecutive_buffer, key=lambda x: x.get('value', np.inf))

            if representative_point:
                structural_points[current_target_role] = representative_point
                points_found += 1

        # 최종 확인
        # 성공적으로 모든 목표 포인트를 찾았는지 확인
        if points_found == len(target_sequence):
            structural_points['pattern_type'] = pattern_type
            # 시간 순서 재확인: target_sequence는 역순(최신->과거)으로 만들어졌으므로
            # 역순으로 뒤집어 실제 시계열 순서(P1/V1 -> ... -> V3/P3)를 얻는다.
            indices = []
            roles = target_sequence[::-1]
            valid_sequence = True
            for role in roles:
                if role not in structural_points:
                    valid_sequence = False; break
                indices.append(structural_points[role]['index'])

            if valid_sequence and all(indices[i] < indices[i+1] for i in range(len(indices)-1)):
                return structural_points
            else:
                logger.debug(f"Found structural points for {pattern_type}: indices={indices}")
                return None # 시간 순서가 맞지 않으면 유효하지 않음
        else:
            logger.debug(f"Could not find 5 structural points ({points_found} found).") # 로그 추가
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
        if len(all_extremums) < 5: return

        # 1. 구조적 극점 후보 찾기 (V1,P1,V2,P2,V3 또는 P1,V1,P2,V2,P3)
        structural_points = self._find_hs_ihs_structural_points(all_extremums)
        # logger.debug(f"Checking for H&S/IHS start: Structural points found: {'Yes' if structural_points else 'No'}") # 디버깅 필요 시 활성화

        if structural_points:
            pattern_type = structural_points.get('pattern_type')
            log_date = all_extremums[-1].get('detected_date', pd.Timestamp.now()).strftime('%Y-%m-%d')

            try: # 딕셔너리 키 접근 및 검증 로직 오류 방지
                if pattern_type == 'HS':
                    
                    v1 = structural_points.get('V1')  
                    p1 = structural_points.get('P1')
                    v2 = structural_points.get('V2')
                    p2 = structural_points.get('P2')
                    v3 = structural_points.get('V3')
                    

                    # logger.debug(f"[{log_date}] Checking H&S candidate: P1={p1.get('index')} V2={v2.get('index')} P2={p2.get('index')} V3={v3.get('index')} V1={getattr(v1,'index',None)}")

                    if not all([v1,p1, v2, p2, v3]):
                        return

                    is_valid = True
                    # 기본 규칙: 머리(P2)는 반드시 왼쪽 어깨(P1)보다 높아야 함
                    if not (p2.get('value', -np.inf) > p1.get('value', -np.inf)):
                        is_valid = False
                        logger.info(f"[{log_date}] H&S Initial Rule Fail: P2({p2.get('value'):.0f}) <= P1({p1.get('value'):.0f})")
                    
                    # ✨ 검증 2: 제안에 따른 '패턴 조화' 검증 ✨
                    if is_valid:
                        shoulder_rise = p1['value'] - v1['value']
                        head_rise_from_shoulder = p2['value'] - p1['value']
                        
                        if shoulder_rise <= 0:
                            is_valid = False
                            logger.info(f"[{log_date}] H&S Harmony Rule Fail: 어깨 높이(P1-V1)가 0 이하임")
                        else:
                            HEAD_RISE_TOLERANCE = 0.5
                            ratio = head_rise_from_shoulder / shoulder_rise
                            if ratio > HEAD_RISE_TOLERANCE:
                                is_valid = False
                                logger.info(f"[{log_date}] H&S Harmony Rule Fail: 머리/어깨 비율({ratio:.2f}) > {HEAD_RISE_TOLERANCE}")

                    

                    # 3. 유효성 검증 통과 시 감지기 생성 시도
                    if is_valid:
                        # 동일한 P1으로 시작하는 활성 H&S 감지기가 없는지 확인
                        if not any(isinstance(d, HeadAndShouldersDetector) and d.P1 and d.P1.get('index') == p1.get('index') for d in self.active_detectors):
                            p1_date_str = p1.get('actual_date', pd.Timestamp('NaT')).strftime('%y%m%d') if isinstance(p1.get('actual_date'), pd.Timestamp) else 'N/A'
                            logger.info(f"[{log_date}] H&S 패턴 후보 감지. P1={p1_date_str}, Completion Mode='{completion_mode}'")

                            # Detector 생성 시 completion_mode 전달
                            # 추가: 수집된 V1(있을 경우) 정보를 메타로 전달하기 위해 생성자에 P1만 전달한 뒤 속성으로 할당
                            detector = HeadAndShouldersDetector(p1, self.data, peaks, valleys, completion_mode=completion_mode)
                            # V1 정보가 수집되어 있으면 detector에 할당(추후 활용 가능)
                            if v1 and not detector.is_failed():
                                detector.V1 = v1
                            if not detector.is_failed():
                                detector.V2 = v2; detector.P2 = p2; detector.V3 = v3
                                detector.stage = "RightNecklineValleyDetected" # V3까지 찾음, P3 탐색 및 검증 단계
                                self.active_detectors.append(detector)
                            else:
                                if detector not in self.failed_detectors: self.failed_detectors.append(detector)

                elif pattern_type == 'IHS':
                    p1 = structural_points.get('P1')
                    v1 = structural_points.get('V1')
                    p2 = structural_points.get('P2')
                    v2 = structural_points.get('V2')
                    p3 = structural_points.get('P3')

                    # logger.debug(f"[{log_date}] Checking IHS candidate: V1={v1.get('index')} P2={p2.get('index')} V2={v2.get('index')} P3={p3.get('index')}") # 디버깅 필요 시 활성화

                    if not all([p1,v1, p2, v2, p3]):
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
                                        'V1': detector.V1, 'P1': detector.P1, 'V2': detector.V2, 'P2': detector.P2, 'V3': detector.V3, 'P3': detector.P3 }
                    self.completed_hs.append(completion_info)
                    p1_date_str = detector.P1.get('actual_date','N/A').strftime('%y%m%d') if detector.P1 and isinstance(detector.P1.get('actual_date'), pd.Timestamp) else 'N/A'
                    completion_details = f"H&S 시작 P1: {p1_date_str}"
                    logger.info(f"{log_prefix} Head and Shoulders 완성! {completion_details}")
                elif isinstance(detector, InverseHeadAndShouldersDetector):
                    completion_info = { 'date': candle['date'], 'price': candle['Close'], 'neckline': detector.neckline_level,
                                        'P1': detector.P1, 'V1': detector.V1, 'P2': detector.P2_ihs, 'V2': detector.V2_ihs, 'P3': detector.P3_ihs, 'V3': detector.V3_ihs }
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
