"""DB 기반 분석 진입점 스텁

이 파일은 새로운 분석 엔트리포인트 `run_analysis_from_df`를 제공합니다.
초기 버전은 DB에서 pandas.DataFrame을 받아 기존 알고리즘과 동일한
입력 포맷으로 변환한 뒤, 이후 통합 알고리즘을 호출하도록 설계됩니다.
"""

from typing import Optional, Dict, Any
import pandas as pd
import logging


# Use the local, bundled engine implementation by default
from backend.app.crud import get_candles, get_latest_candles
# Use the local, bundled engine implementation by default
# Use the refactored orchestrator module (run_full_analysis.py)
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis import run_full_analysis

# 로컬 logger_config 사용 (절대 import로 통일)
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.logger_config import configure_logger

logger = configure_logger(__name__, log_file_prefix="chart_pattern_analyzer_v3", level=logging.INFO)


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
        analysis_results = run_full_analysis(validated_df, ticker=ticker, period=period or "MAX", interval=interval)
        if analysis_results is None:
            return {"error": "Engine returned None"}
        return analysis_results
    except Exception as e:
        logger.error(f"run_full_analysis error: {e}")
        return {"error": str(e)}




