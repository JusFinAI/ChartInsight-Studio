from typing import Dict, Any, List, Optional
import pandas as pd
import hashlib
import json

# pandas-ta-classic import
import pandas_ta_classic as pta


def _params_hash(params: Dict[str, Any]) -> str:
    s = json.dumps(params, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(s.encode('utf-8')).hexdigest()


def compute_indicators(df: pd.DataFrame, spec: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Compute a basic set of indicators using pandas-ta-classic.

    Args:
        df: DataFrame with columns ['Open','High','Low','Close','Volume'] and datetime index
        spec: dict describing indicators to compute. Example:
            {
                "sma": [20,50],
                "ema": [20],
                "rsi": [14],
                "macd": [{"fast":12, "slow":26, "signal":9}]
            }

    Returns:
        dict: {
            "meta": {"params_hash":..., "spec": ...},
            "series": {"SMA_20": pd.Series, ...}
        }
    """
    if spec is None:
        spec = {}

    result = {"meta": {"params_hash": _params_hash(spec), "spec": spec}, "series": {}}

    if df is None or df.empty:
        return result

    close = df['Close']
    high = df['High']
    low = df['Low']
    volume = df['Volume'] if 'Volume' in df.columns else None

    # SMA (only compute if explicitly requested in spec)
    for p in spec.get('sma', []):
        try:
            # pandas-ta-classic exposes overlap indicators under pta.overlap
            s = pta.overlap.sma(close, length=p)
            key = f"SMA_{p}"
            result['series'][key] = s
        except Exception:
            continue

    # EMA (only compute if explicitly requested in spec)
    for p in spec.get('ema', []):
        try:
            s = pta.overlap.ema(close, length=p)
            key = f"EMA_{p}"
            result['series'][key] = s
        except Exception:
            continue

    # RSI (only compute if explicitly requested in spec)
    for p in spec.get('rsi', []):
        try:
            s = pta.momentum.rsi(close, length=p)
            key = f"RSI_{p}"
            result['series'][key] = s
        except Exception:
            continue

    # MACD (only compute if explicitly requested in spec)
    for cfg in spec.get('macd', []):
        try:
            fast = cfg.get('fast', 12)
            slow = cfg.get('slow', 26)
            signal = cfg.get('signal', 9)
            macd_df = pta.momentum.macd(close, fast=fast, slow=slow, signal=signal)
            # macd returns DataFrame with MACD_..., MACDh_..., MACDs_...
            for col in macd_df.columns:
                result['series'][col] = macd_df[col]
        except Exception:
            continue

    # Bollinger Bands (only compute if explicitly requested in spec)
    for cfg in spec.get('bbands', []):
        length = cfg.get('length', 20)
        std = cfg.get('std', 2)
        # call library API directly; let exceptions surface for debugging
        bb = pta.bbands(close, length=length, std=std)
        for col in bb.columns:
            result['series'][col] = bb[col]

    # ATR (only compute if explicitly requested in spec)
    for p in spec.get('atr', []):
        # call library API directly; let exceptions surface for debugging
        # prefer top-level atr if available (expects high, low, close)
        if hasattr(pta, 'atr'):
            s = pta.atr(high, low, close, length=p)
        else:
            s = pta.volatility.atr(high, low, close, length=p)
        key = f"ATR_{p}"
        result['series'][key] = s

    # OBV (only compute if explicitly requested in spec)
    if spec.get('obv', False):
        if volume is not None:
            # call library API directly; try top-level obv first
            if hasattr(pta, 'obv'):
                s = pta.obv(close, volume)
            elif hasattr(pta, 'volume') and hasattr(pta.volume, 'obv'):
                s = pta.volume.obv(close, volume)
            else:
                raise AttributeError('obv function not found in pandas_ta_classic')
            result['series']['OBV'] = s

    return result


