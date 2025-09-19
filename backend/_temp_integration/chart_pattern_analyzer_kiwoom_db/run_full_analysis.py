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

# 모듈 폴더 아래 logs 디렉토리를 기본으로 사용하도록 지정
from pathlib import Path
MODULE_LOGS_DIR = Path(__file__).resolve().parent / "logs"
logger = configure_logger(__name__, log_file_prefix="chart_pattern_analyzer_v3", logs_dir=MODULE_LOGS_DIR, level=logging.INFO)
    

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
        
        if current_date.date() == pd.Timestamp('2025-03-21').date():
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

    # 기본 데이터 포맷팅 (DatetimeIndex 직접 사용 - V030 방식)
    base_data_formatted = {
        "dates": data.index, # DatetimeIndex 객체 직접 사용
        "open": data['Open'].tolist(),
        "high": data['High'].tolist(),
        "low": data['Low'].tolist(),
        "close": data['Close'].tolist(),
        "volume": data['Volume'].tolist() if 'Volume' in data.columns else [0.0] * len(data) # float 처리
    }

    # ZigZag 포인트 생성 (V030 방식)
    all_points = detector.js_peaks + detector.js_valleys + detector.secondary_peaks + detector.secondary_valleys
    zigzag_points = sorted(all_points, key=lambda x: x.get('index', -1))


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