from typing import List, Dict
import pandas as pd
import pandas_ta_classic as pta
import numpy as np
from src import data_collector
from src.utils.logging_kst import configure_kst_logger

"""
기술적 지표 및 패턴 분석 모듈

1단계: `sma_20_val` 및 `rsi_14_val` 계산 구현
향후 단계에서 MACD, STOCH, ATR, volume ratio 등을 추가합니다.
"""

# 모듈 전용 KST 로거 사용
logger = configure_kst_logger(__name__)


def analyze_technical_for_stocks(stock_codes: List[str], execution_mode: str = 'LIVE') -> Dict[str, Dict]:
    """
    주어진 종목 코드 리스트에 대해 핵심 기술 지표를 계산합니다.
    현재 1단계로 SMA(20)와 RSI(14)를 계산합니다.
    """
    results: Dict[str, Dict] = {}

    # 컬럼 매핑 (data_collector는 소문자 컬럼을 반환)
    COLUMN_MAP = {
        'open': 'Open',
        'high': 'High',
        'low': 'Low',
        'close': 'Close',
        'volume': 'Volume'
    }

    # 최소 길이
    MIN_LENGTH_SMA_20 = 20
    MIN_LENGTH_RSI_14 = 15
    REQUIRED_LENGTH = max(MIN_LENGTH_SMA_20, MIN_LENGTH_RSI_14)

    logger.info(f"기술적 지표 분석 시작 (모드: {execution_mode}): {len(stock_codes)}개 종목")

    for code in stock_codes:
        stock_result = {
            'sma_20_val': None,
            'rsi_14_val': None,
            # backward-compatible keys expected by DAG
            'sma_20': None,
            'rsi_14': None,
            # placeholders for future indicators
            'sma_60_val': None,
            'sma_120_val': None,
            'macd_hist': None,
            'stoch_d_val': None,
            'vol_sma_20_ratio': None,
            'atr_14_val': None,
            'trend_daily': None,
            'pattern_daily': None,
            'strategy_signal': None
        }

        try:
            # 데이터 로딩
            df_raw = data_collector.get_candles(code, 'd', execution_mode)

            if df_raw is None or df_raw.empty:
                logger.warning(f"[{code}] OHLCV 데이터가 없어 기술적 분석을 건너뜁니다.")
                results[code] = stock_result
                continue

            # 컬럼 매핑 및 안전 복사
            df = df_raw.rename(columns=COLUMN_MAP).copy()

            # 필요한 컬럼이 없는 경우 처리
            required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in df.columns for col in required_cols):
                logger.error(f"[{code}] 필요한 컬럼 누락: {required_cols} 중 {set(required_cols) - set(df.columns)}")
                results[code] = stock_result
                continue

            if len(df) < REQUIRED_LENGTH:
                logger.warning(f"[{code}] 데이터 길이 부족: {len(df)} < {REQUIRED_LENGTH}, 분석 일부 건너뜁니다.")
                results[code] = stock_result
                continue

            # SMA 20
            if len(df) >= MIN_LENGTH_SMA_20:
                try:
                    sma_20 = pta.overlap.sma(df['Close'], length=20)
                    val = sma_20.iloc[-1]
                    stock_result['sma_20_val'] = float(val) if pd.notna(val) else None
                    stock_result['sma_20'] = stock_result['sma_20_val']
                except Exception as e:
                    logger.error(f"[{code}] SMA 계산 오류: {e}")

            # RSI 14
            if len(df) >= MIN_LENGTH_RSI_14:
                try:
                    rsi_14 = pta.momentum.rsi(df['Close'], length=14)
                    val = rsi_14.iloc[-1]
                    stock_result['rsi_14_val'] = float(val) if pd.notna(val) else None
                    stock_result['rsi_14'] = stock_result['rsi_14_val']
                except Exception as e:
                    logger.error(f"[{code}] RSI 계산 오류: {e}")

        except Exception as e:
            logger.error(f"[{code}] 기술적 분석 중 예외 발생: {e}", exc_info=True)

        finally:
            # NaN -> None
            for k, v in list(stock_result.items()):
                try:
                    if isinstance(v, float) and np.isnan(v):
                        stock_result[k] = None
                except Exception:
                    pass

            results[code] = stock_result

    logger.info("기술적 지표 분석 완료")
    return results


