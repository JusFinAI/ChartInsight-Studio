import numpy as np
import pandas as pd

import time
import logging
import sys
from dataclasses import dataclass, field
from typing import List, Dict, Any,Optional, Tuple # 타입 힌팅 추가
import os
from datetime import datetime

# Avoid import-time side effects for logging. Application entrypoint should
# call configure_logger(...) if file handlers are required.
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import configure_logger

# Band tolerance for dynamic band sizing (e.g. 0.05 = 5%)
BAND_TOLERANCE = 0.2

# ===== 로깅 설정 (개선된 방식) =====
from pathlib import Path

# 모듈별 로그 디렉토리 설정
MODULE_LOGS_DIR = Path(__file__).resolve().parent / "logs"

# 공통 백엔드 로거 사용 (main_dashboard.py에서 backend_events.log로 설정됨)
# configure_logger를 사용하지 않고 getLogger만 사용 (이미 main_dashboard.py에서 설정됨)
logger = logging.getLogger('backend')
    

# Import refactored components (TrendDetector and PatternManager)
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.trend import TrendDetector
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.patterns import PatternManager


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
    # 공통 백엔드 로거 사용 (이미 상단에서 설정됨)
    # logger = logging.getLogger(__name__) # 또는 get_logger(...) 사용
    
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
        
        if current_date.date() == pd.Timestamp('2024-12-20').date():
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
            # H&S/IHS 직접 호출 블록 전체 삭제 – check_for_hs_ihs_start로 중앙화
            all_peaks = detector.js_peaks + detector.secondary_peaks
            all_valleys = detector.js_valleys + detector.secondary_valleys
            manager.check_for_hs_ihs_start(
                peaks=all_peaks,
                valleys=all_valleys,
                newly_registered_peak=detector.newly_registered_peak,
                newly_registered_valley=detector.newly_registered_valley,
                completion_mode='neckline',
                current_index=i
            )

            # DT/DB는 'confirmed' 또는 'provisional' 신뢰도 등급을 시작점으로 허용
            confidence = new_extremum.get('confidence', '') if isinstance(new_extremum, dict) else ''
            if confidence in ['confirmed', 'provisional']:
                if detector.newly_registered_peak:
                    manager.add_detector("DT", detector.newly_registered_peak, data, all_peaks, all_valleys)
                if detector.newly_registered_valley:
                    manager.add_detector("DB", detector.newly_registered_valley, data, all_peaks, all_valleys)
    # --- 루프 종료 ---

    detector.finalize(data)
    end_time = time.time()
    logger.info(f"분석 메인 루프 완료 (소요 시간: {end_time - start_time:.2f}초)")

    # --- 결과 구조화 ---
    # API나 다른 모듈에서 사용하기 쉽도록 결과를 딕셔너리로 정리
    # 날짜/시간 객체는 나중에 API에서 JSON으로 변환 시 문자열로 바꿔야 함 (여기서는 객체 유지)

    # 기본 데이터 포맷팅 (DatetimeIndex 직접 사용 - V030 방식)
    base_data_formatted = {
        "dates": data.index, # DatetimeIndex 객체 직접 사용
        "open": data['Open'].tolist(),
        "high": data['High'].tolist(),
        "low": data['Low'].tolist(),
        "close": data['Close'].tolist(),
        "volume": data['Volume'].tolist() if 'Volume' in data.columns else [0.0] * len(data) # float 처리
    }

    # --- ✨ 신뢰도 기반 Zigzag 정제 헬퍼 함수 추가 ✨ ---
    def create_alternating_zigzag(points: List[Dict], min_delta_pct: float = 0.005) -> List[Dict]:
        """
        'JS 뼈대 우선 방식'으로 최종 지그재그 리스트를 생성합니다.
        연속된 JS 극점 사이를 가장 적합한 Secondary 극점으로 연결하여 재구성합니다.
        """
        # 이미 상단에서 설정된 공통 백엔드 로거 사용
        if not points:
            return []

        def find_best_intermediate_point(candidates: List[Dict], point_type: str) -> Optional[Dict]:
            if not candidates:
                return None
            conf_map = {'confirmed': 3, 'provisional': 2, 'base': 1}
            def score(p):
                c = conf_map.get(p.get('confidence', 'base'), 1)
                v = float(p.get('value', 0) or 0)
                price_score = v if point_type == 'peak' else -v
                return (c, price_score)
            return max(candidates, key=score)

        # 0단계: 정렬
        sorted_points = sorted(points, key=lambda p: p.get('index', -1))
        skeleton_points = [p for p in sorted_points if str(p.get('type', '')).startswith('js')]
        secondary_points = [p for p in sorted_points if not str(p.get('type', '')).startswith('js')]

        # 폴백: JS 뼈대가 없으면 기존 방식으로 처리
        if not skeleton_points:
            logger.warning("JS 뼈대가 없어 기존 방식으로 Zigzag를 정제합니다.")
            conf_map = {'confirmed': 3, 'provisional': 2, 'base': 1}
            clean = [sorted_points[0].copy()]
            for cur in sorted_points[1:]:
                cur_type = 'peak' if cur.get('type','').endswith('peak') else 'valley'
                last = clean[-1]
                last_type = 'peak' if last.get('type','').endswith('peak') else 'valley'
                if cur_type != last_type:
                    clean.append(cur.copy()); continue
                cur_conf = conf_map.get(cur.get('confidence','base'),1)
                last_conf = conf_map.get(last.get('confidence','base'),1)
                try:
                    cur_val = float(cur.get('value'))
                    last_val = float(last.get('value'))
                except Exception:
                    continue
                if cur_conf > last_conf:
                    clean[-1] = cur.copy()
                elif cur_conf == last_conf:
                    replace = False
                    if cur_type == 'peak':
                        if (cur_val - last_val) / max(1.0, abs(last_val)) > min_delta_pct: replace = True
                    else:
                        if (last_val - cur_val) / max(1.0, abs(last_val)) > min_delta_pct: replace = True
                    if replace: clean[-1] = cur.copy()
            logger.info(f"Zigzag 정제(Fallback): {len(sorted_points)}개 -> {len(clean)}개")
            return clean

        # 2단계: 뼈대 재구성 — 삭제하지 않고 연결하기
        final_zigzag: List[Dict] = [skeleton_points[0]]
        for i in range(1, len(skeleton_points)):
            prev_bone = final_zigzag[-1]
            curr_bone = skeleton_points[i]

            prev_type = 'peak' if 'peak' in prev_bone.get('type', '') else 'valley'
            curr_type = 'peak' if 'peak' in curr_bone.get('type', '') else 'valley'

            if prev_type != curr_type:
                final_zigzag.append(curr_bone)
                continue

            # 같은 타입(P-P 또는 V-V)
            start_idx = int(prev_bone.get('index', -1))
            end_idx = int(curr_bone.get('index', -1))
            flesh_type_to_find = 'peak' if prev_type == 'valley' else 'valley'

            candidates = [
                p for p in secondary_points
                if start_idx < int(p.get('index', -1)) < end_idx and flesh_type_to_find in p.get('type','')
            ]

            best_flesh_point = find_best_intermediate_point(candidates, flesh_type_to_find)
            if best_flesh_point:
                final_zigzag.append(best_flesh_point)
                logger.debug(f"뼈대 {prev_type}({start_idx})-{curr_type}({end_idx}) 사이를 {flesh_type_to_find}({best_flesh_point.get('index')})로 연결")
            else:
                # 적절한 살이 없으면 이는 논리적 오류로 간주하고 즉시 실패를 알린다.
                candidate_indices = [int(p.get('index', -1)) for p in candidates]
                error_msg = (
                    f"논리적 오류: JS {prev_type} (Idx: {start_idx})와 JS {curr_type} (Idx: {end_idx}) 사이에서 "
                    f"필수적인 {flesh_type_to_find}를 찾지 못했습니다. 후보 인덱스: {candidate_indices}"
                )
                logger.info(error_msg)
                raise ValueError(error_msg)

            # 현재 뼈대 추가(교체가 일어나지 않았다면 append)
            if final_zigzag[-1].get('index') != curr_bone.get('index'):
                final_zigzag.append(curr_bone)

        logger.info(f"Zigzag 정제(Skeleton-First-Reconstruct): {len(sorted_points)}개 -> {len(final_zigzag)}개")
        return final_zigzag
    # --- 헬퍼 끝 ---

    # ZigZag 포인트 생성 (V030 방식) - 신뢰도 기반 정제 적용
    all_points = detector.js_peaks + detector.js_valleys + detector.secondary_peaks + detector.secondary_valleys

    # --- ✨ 안전검증: all_points 정규화 및 필드 검증 (Cursor.AI 제안 기반) ✨ ---
    clean_points: List[Dict] = []
    missing_key_examples: List[str] = []
    for p in all_points:
        if not isinstance(p, dict):
            continue
        # 필수 키(index, type, value) 확인
        if not all(key in p for key in ['index', 'type', 'value']):
            missing_key_examples.append(f"Idx:{p.get('index', 'N/A')}, Type:{p.get('type', 'N/A')}")
            continue
        # confidence 키가 없으면 'base'로 기본값 설정
        if 'confidence' not in p:
            p['confidence'] = 'base'
        clean_points.append(p)

    if missing_key_examples:
        logger.warning(f"Zigzag 생성 전 필수 키가 누락된 {len(missing_key_examples)}개의 극점을 필터링했습니다. 예시: {missing_key_examples[:3]}")

    all_points = clean_points
    # --- ✨ 안전검증 끝 ✨ ---

    zigzag_points = create_alternating_zigzag(all_points)


    analysis_results = {
        "base_data": base_data_formatted,
        "peaks_valleys": {
            # 원래 데이터 구조 유지 (V030 방식)
            "js_peaks": detector.js_peaks,
            "js_valleys": detector.js_valleys,
            "sec_peaks": detector.secondary_peaks,
            "sec_valleys": detector.secondary_valleys
        },
        "trend_info": {
            "periods": detector.trend_info.periods, # 원래 데이터 구조 유지 (V030 방식)
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