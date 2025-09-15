"""DB 기반 분석 진입점 스텁

이 파일은 새로운 분석 엔트리포인트 `run_analysis_from_db`를 제공합니다.
초기 버전은 DB에서 pandas.DataFrame을 받아 기존 알고리즘과 동일한
입력 포맷으로 변환한 뒤, 이후 통합 알고리즘을 호출하도록 설계됩니다.
"""

from typing import Optional, Dict, Any
import pandas as pd
import logging

# 백엔드의 CRUD 함수를 재사용하여 DB에서 candles를 직접 로드하는 helper를
# 같은 모듈에 두고 run_analysis_from_db_by_symbol을 제공합니다.
# Use the local, bundled engine implementation by default
from backend.app.crud import get_candles, get_latest_candles
# Use the local, bundled engine implementation by default
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis_impl import run_full_analysis as engine_run_full_analysis

# 로컬 logger_config 사용 (절대 import로 통일)
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import configure_logger

logger = configure_logger(__name__, log_file_prefix="chart_pattern_analyzer_v3", level=logging.INFO)


def run_analysis_from_db(
    df: pd.DataFrame,
    ticker: Optional[str] = None,
    period: Optional[str] = None,
    interval: Optional[str] = None,
) -> Dict[str, Any]:
    """DB에서 로드한 DataFrame을 받아 분석을 수행하고 결과를 반환합니다.

    Args:
        df: pandas.DataFrame, 인덱스는 datetime 타입(UTC 권장), 컬럼은 Open/High/Low/Close/Volume
        ticker: 선택적 티커 식별자
        period: 요청된 기간 문자열(예: '2y')
        interval: 시간 간격 문자열(예: '1d')

    Returns:
        dict: analysis results (base_data, peaks_valleys, trend_info, patterns 등)
    """
    # 아직 내부 알고리즘 통합 전 단계: 기본적인 포맷 확인 및 간단 결과 반환
    if df is None or df.empty:
        logger.warning("입력 데이터프레임이 비어있습니다.")
        return {
            "error": "No input data",
            "base_data": {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []},
            "peaks_valleys": {"js_peaks": [], "js_valleys": [], "sec_peaks": [], "sec_valleys": []},
            "trend_info": {"periods": [], "zigzag_points": []},
            "patterns": {"completed_dt": [], "completed_db": [], "completed_hs": [], "completed_ihs": [], "failed_detectors_count": 0},
            "states": []
        }

    # 기본 base_data 포맷 생성
    dates = list(df.index)
    base_data = {
        "dates": dates,
        "open": df['Open'].tolist() if 'Open' in df.columns else [],
        "high": df['High'].tolist() if 'High' in df.columns else [],
        "low": df['Low'].tolist() if 'Low' in df.columns else [],
        "close": df['Close'].tolist() if 'Close' in df.columns else [],
        "volume": df['Volume'].tolist() if 'Volume' in df.columns else []
    }

    # If the verified engine is available, call it to perform full analysis.
    logger.info(f"run_analysis_from_db: df_rows={len(df)}, ticker={ticker}, period={period}, interval={interval}")

    # Call the local engine implementation
    try:
        analysis_results = engine_run_full_analysis(df, ticker=ticker, period=period, interval=interval)
        if analysis_results is None:
            return {"error": "Engine returned None"}
        return analysis_results
    except Exception as e:
        logger.error(f"engine_run_full_analysis error: {e}")
        return {"error": str(e)}


def run_analysis_from_df(df: pd.DataFrame, ticker: str, interval: str, period: Optional[str] = None) -> Dict[str, Any]:
    """이미 로드된 DataFrame을 받아 분석만 수행합니다. (중복 DB 조회 방지)
    
    Args:
        df: 이미 로드된 pandas DataFrame (캔들 데이터)
        ticker: 종목 코드
        interval: 타임프레임 (예: '1d', '30m')
        period: 기간 문자열 (예: 'MAX')
    
    Returns:
        dict: 분석 결과
    """
    if df is None or df.empty:
        logger.warning(f"빈 DataFrame 전달됨: {ticker}, {interval}")
        return {"error": "Empty DataFrame", "base_data": {"dates": [], "open": [], "high": [], "low": [], "close": [], "volume": []}}
    
    # --- DataFrame 검증 및 전처리 (validate_and_prepare_df 인라인) ---
    try:
        # 인덱스를 datetime으로 변환 시도
        try:
            df.index = pd.to_datetime(df.index)
        except Exception:
            return {"error": "Index cannot be parsed as datetime"}

        # 정렬: 오래된 -> 최신
        if not df.index.is_monotonic_increasing:
            df = df.sort_index()

        # 중복 타임스탬프 제거(첫값 보존)
        dup_count = df.index.duplicated().sum()
        if dup_count > 0:
            logger.warning(f"validate: {dup_count} duplicated timestamps found; removing duplicates")
            df = df[~df.index.duplicated(keep='first')]

        # 필수 컬럼 존재 확인
        required = ['Open', 'High', 'Low', 'Close']
        for col in required:
            if col not in df.columns:
                return {"error": f"Missing required column: {col}"}

        # 숫자형 변환 및 결측 검사
        for col in required + ['Volume']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        if df[required].isnull().any().any():
            nulls = df[required].isnull().sum().to_dict()
            return {"error": f"Null values present in required columns: {nulls}"}

        # 최소 길이 검사
        min_required = 30 if interval.endswith('m') or interval.endswith('h') else 10
        if len(df) < min_required:
            return {"error": f"Insufficient data: {len(df)} rows (minimum {min_required} required)"}

        # 간단한 논리 검사(High/Low 관계)
        inconsistent = ((df['High'] < df[['Open', 'Close', 'Low']].max(axis=1)) | (df['Low'] > df[['Open', 'Close', 'High']].min(axis=1))).any()
        if inconsistent:
            logger.warning("Some OHLC relationships are inconsistent (High/Low vs O/C)")

        validated_df = df
    except Exception as e:
        logger.error(f"validate_and_prepare_df error: {e}")
        return {"error": str(e)}

    # 핵심 분석 엔진 호출
    try:
        analysis_results = engine_run_full_analysis(validated_df, ticker=ticker, period=period or "MAX", interval=interval)
        if analysis_results is None:
            return {"error": "Engine returned None"}
        return analysis_results
    except Exception as e:
        logger.error(f"engine_run_full_analysis error: {e}")
        return {"error": str(e)}


# NOTE: `run_analysis_from_db_by_symbol` removed from v3: callers should use
# `run_analysis_from_df` after loading/constructing a DataFrame (see data_loader.py).


# Note: validate_and_prepare_df was inlined into `run_analysis_from_df`.


