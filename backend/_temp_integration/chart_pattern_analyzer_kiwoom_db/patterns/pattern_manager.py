from typing import List, Dict, Optional, Tuple
from .base import PatternDetector
from .double_patterns import DoubleTopDetector, DoubleBottomDetector
from .hs_patterns import HeadAndShouldersDetector, InverseHeadAndShouldersDetector
import pandas as pd

import logging
logger = logging.getLogger('backend')

class PatternManager:
    def __init__(self, data, tolerance: Optional[float] = None):
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

        # 이미 완성된 패턴의 앵커(패턴타입, 앵커인덱스)를 저장하여 재탐지를 방지
        self.completed_pattern_anchors: List[Tuple[str, int]] = []

        # 클래스 속성으로 head_rise_ratio 정의 (evaluate_candidate에서 사용)
        self.head_rise_ratio = 0.5  # 기본값, 나중에 파라미터화 가능

    def _score_structural_candidate(self, cand: Dict[str, Dict]) -> float:
        """후보(구조 포인트 dict)에 대해 점수를 계산하여 반환.
        점수 구성 요소:
          - head prominence (비중 0.45)
          - symmetry (비중 0.2)
          - balance (비중 0.15, 차이가 작을수록 가점)
          - js ratio (비중 0.1)
          - recency (비중 0.05)
          - compact span (비중 0.05)
          - neckline slope penalty (감점)
        """
        try:
            pt = cand.get('pattern_type')
            # 공통 값/시간 추출 유틸
            def _val(d, key='value'):
                return None if d is None else d.get(key)
            def _idx(d):
                try:
                    return int(d.get('index')) if d and 'index' in d else None
                except Exception:
                    return None
            def _ts(d):
                ad = None if d is None else d.get('actual_date')
                try:
                    return pd.to_datetime(ad) if ad is not None else None
                except Exception:
                    return None

            # 값들
            V1, P1, V2, P2, V3, P3 = cand.get('V1'), cand.get('P1'), cand.get('V2'), cand.get('P2'), cand.get('V3'), cand.get('P3')
            v1, p1, v2, p2, v3, p3 = _val(V1), _val(P1), _val(V2), _val(P2), _val(V3), _val(P3)

            # head prominence (evaluate_candidate와 동일한 정규화 기준 사용)
            head_prom = 0.0
            try:
                if pt == 'HS' and all(x is not None for x in [p1, p2, p3, v1, v2, v3]):
                    shoulder_high = max(p1, p3)
                    pattern_low = min(v1, v2, v3)
                    pattern_height = (p2 - pattern_low)
                    if pattern_height > 0:
                        head_prom = max(0.0, (p2 - shoulder_high) / float(pattern_height))
                elif pt == 'IHS' and all(x is not None for x in [v1, v2, v3, p1, p2, p3]):
                    shoulder_low = min(v1, v3)
                    pattern_high = max(p1, p2, p3)
                    pattern_height = (pattern_high - v2)
                    if pattern_height > 0:
                        head_prom = max(0.0, (shoulder_low - v2) / float(pattern_height))
            except Exception:
                head_prom = 0.0

            # symmetry (시간 대칭)
            p1_ts, p2_ts, p3_ts = _ts(P1), _ts(P2), _ts(P3)
            sym = 0.0
            try:
                if p1_ts and p2_ts and p3_ts:
                    L = max((p2_ts - p1_ts).total_seconds(), 1.0)
                    R = max((p3_ts - p2_ts).total_seconds(), 1.0)
                    ratio = max(L / R, R / L)
                    # 1에 가까울수록 1점, 멀어질수록 0점에 수렴
                    sym = 1.0 / ratio
            except Exception:
                sym = 0.0

            # balance (좌/우 평균 차이 작을수록 좋음)
            bal = 0.0
            try:
                if all(x is not None for x in [p1, v2, p3, v3]):
                    l_mid = 0.5 * (p1 + v2)
                    r_mid = 0.5 * (p3 + v3)
                    diff = abs(l_mid - r_mid)
                    denom = max(abs(l_mid), abs(r_mid), 1.0)
                    bal = 1.0 / (1.0 + diff / denom)
            except Exception:
                bal = 0.0

            # js ratio (6포인트 중 js_* 비율)
            def _is_js(d):
                t = None if d is None else str(d.get('type', ''))
                return t.startswith('js_')
            js_count = sum(1 for d in [V1, P1, V2, P2, V3, P3] if _is_js(d))
            js_ratio = js_count / 6.0

            # recency (앵커 인덱스가 클수록 가점)
            anchor_idx = None
            if pt == 'HS':
                anchor_idx = _idx(V3)
            else:
                anchor_idx = _idx(P3)
            recency = 0.0
            try:
                if anchor_idx is not None and len(self.data.index) > 0:
                    recency = max(0.0, min(1.0, float(anchor_idx) / float(len(self.data.index))))
            except Exception:
                recency = 0.0

            # compact span (짧을수록 가점)
            times = list(filter(None, [_ts(V1), _ts(P1), _ts(V2), _ts(P2), _ts(V3), _ts(P3)]))
            compact = 0.0
            try:
                if times:
                    span_days = max((max(times) - min(times)).days, 0)
                    compact = 1.0 / (1.0 + span_days)
            except Exception:
                compact = 0.0

            # neckline slope penalty (작을수록 가점)
            slope_penalty = 0.0
            try:
                if pt == 'HS' and all(_idx(x) is not None and _val(x) is not None for x in [V2, V3]):
                    run = float(_idx(V3) - _idx(V2))
                    if run != 0:
                        slope = abs((_val(V3) - _val(V2)) / run)
                        slope_penalty = min(0.5, slope / max(abs(_val(V2)), 1.0) * 20.0)
                elif pt == 'IHS' and all(_idx(x) is not None and _val(x) is not None for x in [P2, P3]):
                    run = float(_idx(P3) - _idx(P2))
                    if run != 0:
                        slope = abs((_val(P3) - _val(P2)) / run)
                        slope_penalty = min(0.5, slope / max(abs(_val(P2)), 1.0) * 20.0)
            except Exception:
                slope_penalty = 0.0

            # --- [추가] 약화되는 매수세(P3 < P1)에 대한 가점 ---
            declining_shoulder_bonus = 0.0
            try:
                if pt == 'HS' and p3 is not None and p1 is not None and float(p3) < float(p1):
                    declining_shoulder_bonus = 0.1
            except Exception:
                declining_shoulder_bonus = 0.0

            # 가중 합산
            score = (
                0.45 * head_prom +
                0.20 * sym +
                0.15 * bal +
                0.10 * js_ratio +
                0.05 * recency +
                0.05 * compact
            ) - slope_penalty + declining_shoulder_bonus
            return float(score)
        except Exception:
            return 0.0

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
    
    def _find_hs_ihs_structural_points(self, all_extremums: List[Dict], pattern_type_to_search: str, lookback_limit: int = 20,
                                       max_skip: int = 2, max_candidates: int = 15,
                                       symmetry_threshold: float = 2.5, head_rise_ratio: float = 0.5,
                                       current_index: Optional[int] = None) -> List[Dict[str, Dict]]:
        """HS/IHS 구조적 포인트 다중 후보 검색 (시간 기반 통합 처리 + V-P pair skip)
        
        주의: all_extremums는 이미 시간순으로 정렬되어 전달됨 (최신이 마지막)
        """
        if len(all_extremums) < 6: return []  # 최소 6포인트 필요

        # all_extremums는 이미 check_for_hs_ihs_start에서 정렬됨
        # 최신부터 처리하기 위해 역순으로 변경
        sorted_extremums = list(reversed(all_extremums))
        
        # 2. V-P-V-P 시퀀스 생성 (연속 동타입 처리)
        # 최신부터 과거로 가면서 처리
        # 같은 타입이 연속으로 나오면 더 극단적인 값 선택
        vp_sequence = []
        for ext in sorted_extremums:  # 최신부터 과거로
            if not vp_sequence:
                vp_sequence.append(ext)
            else:
                last_type = 'peak' if str(vp_sequence[-1].get('type', '')).endswith('peak') else 'valley'
                cur_type = 'peak' if str(ext.get('type', '')).endswith('peak') else 'valley'
                
                if cur_type != last_type:
                    # 타입이 다르면 그냥 추가
                    vp_sequence.append(ext)
                else:
                    # 같은 타입이면 더 극단적인 값으로 대체
                    if cur_type == 'peak':
                        if ext.get('value', 0) > vp_sequence[-1].get('value', 0):
                            vp_sequence[-1] = ext
                    else:  # valley
                        if ext.get('value', float('inf')) < vp_sequence[-1].get('value', float('inf')):
                            vp_sequence[-1] = ext
        
        # 3. 패턴 타입은 호출자가 명시 (듀얼 탐색 지원)
        if not vp_sequence:
            return []
        pattern_type = 'HS' if str(pattern_type_to_search).upper() == 'HS' else 'IHS'
        
        # 4. 재귀 함수로 후보 생성 (백트래킹 방식)
        candidates = []

        # ✨ 디버깅용: 모든 시도된 조합을 추적
        all_attempts = []  # [(mapping, eval_result, pos, skips_left), ...]

        def find_pattern_combinations(pos: int, points_so_far: List[Dict], skips_left: int):
            """
            백트래킹을 사용하여 가능한 모든 skip 조합을 탐색하는 재귀 함수.
            pos: vp_sequence에서 탐색을 시작할 현재 위치
            points_so_far: 현재까지 만들어진 패턴 후보
            skips_left: 남은 skip 가능 횟수 (V-P 쌍 기준)
            """
            # 후보 수 제한 또는 탐색 종료 조건
            if len(candidates) >= max_candidates or pos >= len(vp_sequence):
                return

            # 6포인트 완성 시 평가 및 저장
            if len(points_so_far) == 6:
                time_ordered = list(reversed(points_so_far))

                if pattern_type == 'HS':
                    mapping = {'V1': time_ordered[0], 'P1': time_ordered[1], 'V2': time_ordered[2],
                               'P2': time_ordered[3], 'V3': time_ordered[4], 'P3': time_ordered[5], 'pattern_type': 'HS'}
                else: # IHS
                    mapping = {'P1': time_ordered[0], 'V1': time_ordered[1], 'P2': time_ordered[2],
                               'V2': time_ordered[3], 'P3': time_ordered[4], 'V3': time_ordered[5], 'pattern_type': 'IHS'}

                # ✨ 디버깅용: 모든 시도된 조합 추적 (검증 결과 포함)
                try:
                    eval_result = self.evaluate_candidate(mapping, pattern_type, current_index=current_index)
                    all_attempts.append({
                        'mapping': mapping.copy(),
                        'eval_result': eval_result,
                        'pos': pos,
                        'skips_left': skips_left,
                        'points_so_far': points_so_far.copy(),
                        'time_ordered': time_ordered.copy()
                    })
                except Exception as e:
                    # 평가 중 오류 발생 시에도 기록
                    all_attempts.append({
                        'mapping': mapping.copy(),
                        'eval_result': False,
                        'error': str(e),
                        'pos': pos,
                        'skips_left': skips_left,
                        'points_so_far': points_so_far.copy(),
                        'time_ordered': time_ordered.copy()
                    })

                if self.evaluate_candidate(mapping, pattern_type, current_index=current_index):
                    # 중복된 후보 방지
                    if mapping not in candidates:
                        candidates.append(mapping)
                return

            # 다음에 찾아야 할 극점의 타입 결정
            if pattern_type == 'HS': # 역시간순: P3, V3, P2, ...
                expected_type = 'peak' if len(points_so_far) % 2 == 0 else 'valley'
            else: # IHS, 역시간순: V3, P3, V2, ...
                expected_type = 'valley' if len(points_so_far) % 2 == 0 else 'peak'

            # pos 위치부터 시작하여 다음 후보를 찾는다
            for i in range(pos, len(vp_sequence)):
                candidate_point = vp_sequence[i]
                cur_type = 'peak' if str(candidate_point.get('type', '')).endswith('peak') else 'valley'

                if cur_type == expected_type:
                    # 건너뛴 V-P 쌍의 개수 계산
                    pairs_skipped = (i - pos) // 2
                    
                    if pairs_skipped <= skips_left:
                        # 이 후보를 선택하고 다음 단계로 진행
                        new_points = points_so_far + [candidate_point]
                        find_pattern_combinations(i + 1, new_points, skips_left - pairs_skipped)

        # 가장 최신 극점부터 탐색 시작
        find_pattern_combinations(0, [], max_skip)

        # ✨ 디버깅용: 모든 시도된 조합 정보 반환
        return candidates, all_attempts

    # 평가 함수 (조건 검사)
    def evaluate_candidate(self, seq: List[Dict], pattern_type: str, current_index: Optional[int] = None) -> bool:
        # 입력 정규화: dict(mapping) 또는 list 모두 수용
        if isinstance(seq, dict):
            pattern_type = seq.get('pattern_type', pattern_type)
            seq_list = [v for k, v in seq.items() if k != 'pattern_type']
        else:
            seq_list = list(seq)

        if len(seq_list) < 6:
            return False
        if not all(hasattr(x, 'get') for x in seq_list):
            return False

        # 시간 정렬 (actual_date 우선, 없으면 안전 폴백: 인덱스→Timestamp)
        def _time_key(item):
            ad = item.get('actual_date')
            if ad is not None:
                try:
                    return pd.to_datetime(ad)
                except Exception:
                    pass
            try:
                if hasattr(self, 'data') and self.data is not None and 'index' in item:
                    idx = int(item.get('index', -1))
                    if 0 <= idx < len(self.data.index):
                        return self.data.index[idx]
            except Exception:
                pass
            return pd.Timestamp('1900-01-01')

        seq_time_order = sorted(seq_list, key=_time_key)
        if len(seq_time_order) < 6:
            return False

        # 타입 시퀀스 확인
        types = ['peak' if str(s.get('type','')).endswith('peak') else 'valley' for s in seq_time_order]
        hs_types = ['valley', 'peak', 'valley', 'peak', 'valley', 'peak']
        ihs_types = ['peak', 'valley', 'peak', 'valley', 'peak', 'valley']

        if types == hs_types:
            pattern_type = 'HS'
            V1, P1, V2, P2, V3, P3 = seq_time_order
        elif types == ihs_types:
            pattern_type = 'IHS'
            P1, V1, P2, V2, P3, V3 = seq_time_order
        else:
            return False

        # 값 추출
        v1_val, p1_val = V1.get('value'), P1.get('value')
        v2_val, p2_val = V2.get('value'), P2.get('value')
        v3_val, p3_val = V3.get('value'), P3.get('value')
        if None in [v1_val, p1_val, v2_val, p2_val, v3_val, p3_val]:
            return False

        # 1) 기하 규칙
        if pattern_type == 'HS':
            if not (p2_val > p1_val and p2_val > p3_val):
                return False
            if not (v2_val > v1_val):
                return False
        else:  # IHS
            if not (v2_val < v1_val and v2_val < v3_val):
                return False
            if not (p2_val < p1_val):
                return False

        # 2) 사후 무효화 (현재 시점까지만 검사)
        if hasattr(self, 'data') and isinstance(self.data, pd.DataFrame) and len(self.data.index) > 0:
            try:
                end_idx = int(current_index) if isinstance(current_index, int) else len(self.data.index) - 1
                if pattern_type == 'HS':
                    start_idx = int(V3.get('index', -1)) + 1
                    inv_level = max(float(p1_val), float(p3_val))
                    if 0 <= start_idx <= end_idx:
                        post_df = self.data.iloc[start_idx:end_idx+1]
                        if not post_df.empty and (post_df['Close'] > inv_level).any():
                            return False
                else:  # IHS
                    start_idx = int(P3.get('index', -1)) + 1
                    inv_level = min(float(v1_val), float(v3_val))
                    if 0 <= start_idx <= end_idx:
                        post_df = self.data.iloc[start_idx:end_idx+1]
                        if not post_df.empty and (post_df['Close'] < inv_level).any():
                            return False
            except Exception:
                pass

        # 3) 균형(Balance)
        if pattern_type == 'HS':
            l_mid = 0.5 * (p1_val + v2_val)
            r_mid = 0.5 * (p3_val + v3_val)
            if p1_val < r_mid or p3_val < l_mid:
                return False
        else:  # IHS
            l_mid = 0.5 * (v1_val + p2_val)
            r_mid = 0.5 * (v3_val + p3_val)
            if v1_val > r_mid or v3_val > l_mid:
                return False

        # 4) 시간 대칭(Symmetry)
        def _to_ts(item):
            ad = item.get('actual_date')
            try:
                return pd.to_datetime(ad)
            except Exception:
                try:
                    idx = int(item.get('index', -1))
                    if hasattr(self, 'data') and self.data is not None and 0 <= idx < len(self.data.index):
                        return self.data.index[idx]
                except Exception:
                    pass
            return None

        if pattern_type == 'HS':
            p1_ts, p2_ts, p3_ts = _to_ts(P1), _to_ts(P2), _to_ts(P3)
            if not p1_ts or not p2_ts or not p3_ts:
                return False
            l_time = (p2_ts - p1_ts).total_seconds()
            r_time = (p3_ts - p2_ts).total_seconds()
        else:
            v1_ts, v2_ts, v3_ts = _to_ts(V1), _to_ts(V2), _to_ts(V3)
            if not v1_ts or not v2_ts or not v3_ts:
                return False
            l_time = (v2_ts - v1_ts).total_seconds()
            r_time = (v3_ts - v2_ts).total_seconds()

        if l_time <= 0 or r_time <= 0 or r_time > 2.5 * l_time or l_time > 2.5 * r_time:
            return False

        # 5) 머리 돌출(Head Prominence Ratio) – 파라미터화
        MIN_PROMINENCE_RATIO = getattr(self, 'min_head_prom_ratio', 0.20)
        try:
            if pattern_type == 'HS':
                shoulder_high = max(p1_val, p3_val)
                pattern_low = min(v1_val, v2_val, v3_val)
                pattern_height = p2_val - pattern_low
                if pattern_height <= 0 or (p2_val - shoulder_high) / pattern_height < float(MIN_PROMINENCE_RATIO):
                    return False
            else:  # IHS
                shoulder_low = min(v1_val, v3_val)
                pattern_high = max(p1_val, p2_val, p3_val)
                pattern_height = pattern_high - v2_val
                if pattern_height <= 0 or (shoulder_low - v2_val) / pattern_height < float(MIN_PROMINENCE_RATIO):
                    return False
        except Exception:
            return False

        return True

    def check_for_hs_ihs_start(self, peaks: List[Dict], valleys: List[Dict], 
                               newly_registered_peak: Optional[Dict] = None, 
                               newly_registered_valley: Optional[Dict] = None,
                               completion_mode: str = 'neckline', current_index: Optional[int] = None):
        """
        새로운 극점 발생 시 H&S/IHS 패턴 시작 확인 (다중 후보 지원 버전).
        """
        # 입력 all_extremums actual_date 필터링 및 정렬
        valid_extremums = [x for x in peaks + valleys if x.get('actual_date') is not None and isinstance(x.get('actual_date'), pd.Timestamp)]
        none_count = len(peaks + valleys) - len(valid_extremums)
        if none_count > 0:
            logger.warning(f"[{pd.Timestamp.now().strftime('%Y-%m-%d')}] actual_date None {none_count}개 필터링 – HS/IHS 후보 영향 가능")
        
        # actual_date 안전 변환 후 시간순 정렬 (오래된 것부터 최신순)
        def _to_ts2(e):
            ad = e.get('actual_date')
            try:
                return pd.to_datetime(ad)
            except Exception:
                return pd.Timestamp('1900-01-01')
        
        def get_anchor_date_str(c):
            pt = c.get('pattern_type')
            anchor_extremum = c.get('V3') if pt == 'HS' else c.get('P3')
            if anchor_extremum and 'actual_date' in anchor_extremum:
                date_val = anchor_extremum['actual_date']
                # pd.Timestamp인지 확인 후 포맷팅, 아닐 경우 문자열로 변환
                return date_val.strftime('%Y-%m-%d') if hasattr(date_val, 'strftime') else str(date_val)
            return '날짜 N/A'
        
          # 포인트 정보 추출 헬퍼
        def get_point_str(point, key):
            if point:
                val = point.get('value', 'N/A')
                date = point.get('actual_date')
                date_str = date.strftime('%y%m%d') if isinstance(date, pd.Timestamp) else 'N/A'
                return f"{key}({val}):{date_str}"
            return f"{key}(N/A):N/A"

        all_extremums = sorted(valid_extremums, key=lambda x: _to_ts2(x))  # 오래된 것 -> 최신 순
        if len(all_extremums) < 6: return

        # 구조적 포인트 후보 찾기 (정렬된 데이터 전달)
        # ---- 듀얼 탐색 로직 시작 ----
        search_types = set()
        if newly_registered_peak:
            search_types.add('HS')
        if newly_registered_valley:
            search_types.add('IHS')

        if not search_types and all_extremums:
            last_ext = all_extremums[-1]
            search_types.add('IHS' if 'valley' in str(last_ext.get('type','')) else 'HS')

        if not search_types:
            return

        structural_points_list = []
        all_attempts = []

        for p_type in search_types:
            logger.debug(f"H&S/IHS: '{p_type}' 타입 패턴 탐색을 시작합니다.")
            s_points, attempts = self._find_hs_ihs_structural_points(
                all_extremums,
                pattern_type_to_search=p_type,
                current_index=current_index
            )
            structural_points_list.extend(s_points)
            all_attempts.extend(attempts)

        if len(structural_points_list) > 0:
            from collections import Counter
            anchor_summary = Counter(get_anchor_date_str(c) for c in structural_points_list)
            summary_str = ", ".join([f"'{date}'({count}개)" for date, count in anchor_summary.items()])
            logger.info(f"H&S/IHS: {len(structural_points_list)}개 유효 후보 발견. 앵커 그룹 요약: {summary_str}")
        # ---- 듀얼 탐색 로직 끝 ----

            

        # ✨ 디버깅용: 모든 시도된 조합을 저장 (전역 저장소에 누적)
        if not hasattr(self, '_debug_all_attempts'):
            self._debug_all_attempts = []
        self._debug_all_attempts.extend(all_attempts)

        # 복수 후보를 앵커별 그룹으로 묶고 그룹당 1개만 선택
        groups: Dict[Tuple[str, int], List[Dict]] = {}
        for sp in structural_points_list:
            pt = sp.get('pattern_type')
            try:
                if pt == 'HS':
                    anchor = int(sp.get('V3', {}).get('index')) if sp.get('V3') else None
                    key = ('HS', anchor)
                else:
                    anchor = int(sp.get('P3', {}).get('index')) if sp.get('P3') else None
                    key = ('IHS', anchor)
            except Exception:
                key = (pt or 'UNK', -1)
            groups.setdefault(key, []).append(sp)

        # 각 그룹에서 최고 점수 1개만 선택
        selected_candidates: List[Dict] = []
        for key, lst in groups.items():
            # 점수 계산 및 정렬
            scored = sorted(
                [(self._score_structural_candidate(x), x) for x in lst],
                key=lambda t: t[0], reverse=True
            )
                        
            if scored:
                winner_score, winner_candidate = scored[0]

                # ---- DEBUG/INFO 로그를 아래 코드로 대체합니다. ----
                anchor_date_str = get_anchor_date_str(lst[0]) if lst else '날짜 N/A'

                # 최종 선정된 후보의 6개 극점 가격과 날짜를 함께 추출
                pt = winner_candidate.get('pattern_type')
                point_keys = ['V1','P1','V2','P2','V3','P3'] if pt == 'HS' else ['P1','V1','P2','V2','P3','V3']
                point_details_parts = []
                for p_key in point_keys:
                    point = winner_candidate.get(p_key)
                    date_str, val_str = "N/A", "N/A"
                    if point:
                        if 'actual_date' in point:
                            p_date = point['actual_date']
                            date_str = p_date.strftime('%y%m%d') if hasattr(p_date, 'strftime') else str(p_date)
                        if 'value' in point:
                            p_val = point['value']
                            val_str = f"{p_val:.0f}" if isinstance(p_val, (int, float)) else str(p_val)
                    point_details_parts.append(f"{p_key}({val_str}):{date_str}")
                points_log_str = ", ".join(point_details_parts)

                logger.info( # 또는 logger.debug
                    f"H&S/IHS 그룹(앵커 날짜: {anchor_date_str}) 경쟁 결과: 총 {len(lst)}개 후보 중 "
                    f"최고점({winner_score:.2f}) 후보 선정. [구조: {points_log_str}]"
                )
                # ---- 여기까지 대체 ----
                
                selected_candidates.append(winner_candidate)

        for structural_points in selected_candidates:
            pattern_type = structural_points.get('pattern_type')

            # ---- 재탐지 방지: 이미 완성된 앵커면 감지기 생성 스킵 ----
            try:
                current_anchor_key = None
                if pattern_type == 'HS':
                    anchor_index = int(structural_points.get('V3', {}).get('index')) if structural_points.get('V3') else None
                    if anchor_index is not None:
                        current_anchor_key = ('HS', anchor_index)
                elif pattern_type == 'IHS':
                    anchor_index = int(structural_points.get('P3', {}).get('index')) if structural_points.get('P3') else None
                    if anchor_index is not None:
                        current_anchor_key = ('IHS', anchor_index)

                if current_anchor_key and current_anchor_key in getattr(self, 'completed_pattern_anchors', []):
                    logger.debug(f"H&S/IHS: 이미 완성된 앵커 {current_anchor_key} → 감지기 생성을 건너뜀")
                    continue
            except Exception:
                # 앵커 키 생성 실패 시 필터를 강제하지 않음 (로버스트)
                pass

            if pattern_type == 'HS':
                p1 = structural_points.get('P1')
                if p1 and not any(isinstance(d, HeadAndShouldersDetector) and d.P1 and d.P1.get('index') == p1.get('index') for d in self.active_detectors):
                    # 생성 트리거의 detected_date를 creation_event_date로 전달
                    creation_date = all_extremums[-1].get('detected_date', pd.Timestamp.now())
                    detector = HeadAndShouldersDetector(p1, self.data, creation_event_date=creation_date, peaks=peaks, valleys=valleys, completion_mode=completion_mode)
                    if not detector.is_failed():
                        detector.V1 = structural_points.get('V1')
                        detector.P1 = structural_points.get('P1')
                        detector.V2 = structural_points.get('V2')
                        detector.P2 = structural_points.get('P2')
                        detector.V3 = structural_points.get('V3')
                        detector.P3 = structural_points.get('P3')
                        detector.stage = "AwaitingCompletion"
                        self.active_detectors.append(detector)
                        
                        # 로그 생성
                        points = [get_point_str(detector.V1, 'V1'), get_point_str(detector.P1, 'P1'),
                                    get_point_str(detector.V2, 'V2'), get_point_str(detector.P2, 'P2'),
                                    get_point_str(detector.V3, 'V3'), get_point_str(detector.P3, 'P3')]
                        points_str = ", ".join(points)

                        logger.info(f"[{all_extremums[-1].get('detected_date', pd.Timestamp.now()).strftime('%Y-%m-%d')}] H&S 패턴(선정) 후보 감지. [구조: {points_str}]")
                        
                        
            elif pattern_type == 'IHS':
                v1 = structural_points.get('V1')
                if v1 and not any(isinstance(d, InverseHeadAndShouldersDetector) and d.V1 and d.V1.get('index') == v1.get('index') for d in self.active_detectors):
                    creation_date = all_extremums[-1].get('detected_date', pd.Timestamp.now())
                    detector = InverseHeadAndShouldersDetector(v1, self.data, creation_event_date=creation_date, peaks=peaks, valleys=valleys, completion_mode=completion_mode)
                    if not detector.is_failed():
                        detector.P1_ihs = structural_points.get('P1')
                        detector.V1_ihs = structural_points.get('V1')
                        detector.P2_ihs = structural_points.get('P2')
                        detector.V2_ihs = structural_points.get('V2')
                        detector.P3_ihs = structural_points.get('P3')
                        detector.V3_ihs = structural_points.get('V3')
                        detector.stage = "AwaitingCompletion"
                        self.active_detectors.append(detector)
                        
                        points = [get_point_str(detector.P1_ihs, 'P1'), get_point_str(detector.V1_ihs, 'V1'),
                                    get_point_str(detector.P2_ihs, 'P2'), get_point_str(detector.V2_ihs, 'V2'),
                                    get_point_str(detector.P3_ihs, 'P3'), get_point_str(detector.V3_ihs, 'V3')]
                        points_str = ", ".join(points)
                        logger.info(f"[{all_extremums[-1].get('detected_date', pd.Timestamp.now()).strftime('%Y-%m-%d')}] IHS 패턴(선정) 후보 감지. [구조: {points_str}]")
                        

    def get_debug_attempts(self) -> List[Dict]:
        """
        ✨ 디버깅용: 모든 시도된 패턴 조합들을 반환
        차트 시각화나 분석에 활용 가능
        """
        return getattr(self, '_debug_all_attempts', [])

    def print_debug_attempts(self, limit: int = 5):
        """
        ✨ 디버깅용: 성공한 패턴 조합들을 날짜와 함께 출력
        """
        attempts = self.get_debug_attempts()
        successful = [a for a in attempts if a['eval_result']]

        if not successful:
            print("성공한 패턴 조합이 없습니다.")
            return

        print(f"성공한 패턴 조합 ({len(successful)}개):")
        for i, attempt in enumerate(successful[:limit]):
            print(f"\n[{i+1}] {attempt['mapping']['pattern_type']} 패턴")

            # 포인트 정보를 날짜와 함께 표시 (연월일)
            points_info = []
            for p in attempt['time_ordered']:
                date = p.get('actual_date')
                date_str = date.strftime('%Y%m%d') if isinstance(date, pd.Timestamp) else 'N/A'
                points_info.append(f"{p.get('index')}({date_str})")

            print(f"  포인트: {points_info}")
            print(f"  위치: pos={attempt['pos']}, 스킵={attempt['skips_left']}")

    def clear_debug_attempts(self):
        """
        ✨ 디버깅용: 저장된 시도 기록을 초기화
        """
        if hasattr(self, '_debug_all_attempts'):
            self._debug_all_attempts.clear()

    def add_detector(self, pattern_type: str, extremum: Dict, data: pd.DataFrame, js_peaks: List[Dict], js_valleys: List[Dict]):
        """DT/DB 감지기 추가 로직 (수정된 생성자 호출 방식)"""
        detector = None
        
        # 개발 중: 엄격 검사(예외 발생)
        if not isinstance(js_peaks, list):
            raise TypeError(f"add_detector: js_peaks must be list, got {type(js_peaks).__name__}")
        if not isinstance(js_valleys, list):
            raise TypeError(f"add_detector: js_valleys must be list, got {type(js_valleys).__name__}")
        # 이후에는 안전하게 복사/사용
        peaks_arg = js_peaks.copy()
        valleys_arg = js_valleys.copy()
        
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
                                        'V1': detector.V1, 'P1': detector.P1, 'V2': detector.V2, 'P2': detector.P2, 'V3': detector.V3, 'P3': detector.P3,
                                        'mode': getattr(detector, 'completion_mode', 'neckline') }
                    self.completed_hs.append(completion_info)
                    p1_date_str = detector.P1.get('actual_date','N/A').strftime('%y%m%d') if detector.P1 and isinstance(detector.P1.get('actual_date'), pd.Timestamp) else 'N/A'
                    completion_details = f"H&S 시작 P1: {p1_date_str}"
                    logger.info(f"{log_prefix} Head and Shoulders 완성! {completion_details}")
                    # ---- 앵커 저장: HS는 V3 인덱스를 기준으로 저장 ----
                    try:
                        if detector.V3 and 'index' in detector.V3:
                            anchor_key = ('HS', int(detector.V3.get('index')))
                            if anchor_key not in self.completed_pattern_anchors:
                                self.completed_pattern_anchors.append(anchor_key)
                                logger.debug(f"H&S: 완성 앵커 저장 {anchor_key}")
                    except Exception as e:
                        logger.error(f"H&S 앵커 저장 오류: {e}")
                elif isinstance(detector, InverseHeadAndShouldersDetector):
                    completion_info = { 'date': candle['date'], 'price': candle['Close'], 'neckline': detector.neckline_level,
                                        'P1': detector.P1_ihs, 'V1': detector.V1_ihs, 'P2': detector.P2_ihs, 'V2': detector.V2_ihs, 'P3': detector.P3_ihs, 'V3': detector.V3_ihs,
                                        'mode': getattr(detector, 'completion_mode', 'neckline') }
                    self.completed_ihs.append(completion_info)
                    v1_date_str = detector.V1_ihs.get('actual_date','N/A').strftime('%y%m%d') if detector.V1_ihs and isinstance(detector.V1_ihs.get('actual_date'), pd.Timestamp) else 'N/A'
                    completion_details = f"IH&S 시작 V1: {v1_date_str}"
                    logger.info(f"{log_prefix} Inverse Head and Shoulders 완성! {completion_details}")
                    # ---- 앵커 저장: IHS는 P3 인덱스를 기준으로 저장 ----
                    try:
                        if detector.P3_ihs and 'index' in detector.P3_ihs:
                            anchor_key = ('IHS', int(detector.P3_ihs.get('index')))
                            if anchor_key not in self.completed_pattern_anchors:
                                self.completed_pattern_anchors.append(anchor_key)
                                logger.debug(f"IHS: 완성 앵커 저장 {anchor_key}")
                    except Exception as e:
                        logger.error(f"IHS 앵커 저장 오류: {e}")

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
