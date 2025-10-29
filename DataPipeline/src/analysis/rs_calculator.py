import pandas as pd
import logging
import datetime
from zoneinfo import ZoneInfo
import os
import sys
from pathlib import Path
from typing import Dict, List

# Make local imports like `from src.database import ...` work when running
# this module directly during local development. We prefer not to rely on
# external PYTHONPATH configuration for developers.
repo_root = Path(__file__).resolve().parents[2]
dp_src = repo_root / 'DataPipeline' / 'src'
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))
if str(dp_src) not in sys.path:
    sys.path.insert(0, str(dp_src))

# [추가] DB 및 시뮬레이션 데이터 로드를 위한 모듈 임포트
from src.database import SessionLocal, Stock
from src.data_collector import get_candles
from src.utils.logging_kst import configure_kst_logger
try:
    # Prefer Airflow Variable if available in the runtime
    from airflow.models import Variable as AirflowVariable  # type: ignore
except Exception:
    AirflowVariable = None

logger = configure_kst_logger(__name__)

# Configure module logger to emit timestamps in KST (Asia/Seoul) for module-level logs.
# Note: This only affects logs emitted via this module's `logger` (e.g., rs_calculator),
# not Airflow core logs which are managed by Airflow's global logging configuration.
try:
    kst_tz = ZoneInfo("Asia/Seoul")
    if not logger.handlers:
        handler = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", "%Y-%m-%d %H:%M:%S %Z")
        def _kst_converter(seconds):
            return datetime.datetime.fromtimestamp(seconds, tz=kst_tz).timetuple()
        fmt.converter = _kst_converter
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
except Exception:
    # If zoneinfo is not available or any error occurs, fall back to default logger behavior
    pass


def calculate_weighted_rs(target_df: pd.DataFrame, base_df: pd.DataFrame) -> float | None:
    """가중 상대강도(RS) 점수를 계산합니다."""
    if target_df.empty or base_df.empty:
        return None

    # 컬럼명 정규화: 다양한 소스의 컬럼명이 다를 수 있으므로 소문자화 및 공백->언더스코어 변환으로 표준화
    def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        new_cols = {c: c.strip().lower().replace(' ', '_') for c in df.columns}
        df = df.rename(columns=new_cols)
        # 흔히 'close' 컬럼이 'adj_close' 형태로 있으면 우선 'close'를 보존하거나 대체
        if 'close' not in df.columns and 'adj_close' in df.columns:
            df['close'] = df['adj_close']
        return df

    target_df = normalize_columns(target_df)
    base_df = normalize_columns(base_df)

    # 두 데이터프레임의 날짜를 기준으로 병합
    # ensure 'close' column exists
    if 'close' not in target_df.columns or 'close' not in base_df.columns:
        return None

    target = target_df.copy()
    base = base_df.copy()
    # reset_index may produce a column named 'index' or a named index column.
    target = target.reset_index()
    if 'index' in target.columns:
        target = target.rename(columns={'index': 'date'})
    else:
        # fallback: assume first column is the date index
        target = target.rename(columns={target.columns[0]: 'date'})

    base = base.reset_index()
    if 'index' in base.columns:
        base = base.rename(columns={'index': 'date'})
    else:
        base = base.rename(columns={base.columns[0]: 'date'})

    # Normalize both dataframes to YYYY-MM (period M) to avoid mismatches on day-of-month
    try:
        # 날짜를 KST 기준으로 정규화한 후 월(period)로 변환합니다.
        target['date'] = pd.to_datetime(target['date'])
        base['date'] = pd.to_datetime(base['date'])

        # KST 처리: DB에는 UTC로 저장된 타임스탬프가 있으므로,
        # tz-aware이면 KST로 변환하고, tz-naive이면 UTC로 로컬라이즈 후 KST로 변환합니다.
        try:
            if getattr(target['date'].dt, 'tz', None) is None:
                target['date'] = target['date'].dt.tz_localize('UTC').dt.tz_convert('Asia/Seoul')
            else:
                target['date'] = target['date'].dt.tz_convert('Asia/Seoul')
        except Exception:
            # 안전망: 강제 UTC->KST 변환
            target['date'] = target['date'].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT').dt.tz_convert('Asia/Seoul')

        try:
            if getattr(base['date'].dt, 'tz', None) is None:
                base['date'] = base['date'].dt.tz_localize('UTC').dt.tz_convert('Asia/Seoul')
            else:
                base['date'] = base['date'].dt.tz_convert('Asia/Seoul')
        except Exception:
            base['date'] = base['date'].dt.tz_localize('UTC', ambiguous='NaT', nonexistent='NaT').dt.tz_convert('Asia/Seoul')

        target['ym'] = target['date'].dt.to_period('M')
        base['ym'] = base['date'].dt.to_period('M')

        # For months with multiple rows, keep the last (most recent) entry to represent the month
        target_monthly = target.sort_values('date').groupby('ym', as_index=False).last()
        base_monthly = base.sort_values('date').groupby('ym', as_index=False).last()

        # Convert ym back to timestamp at period start for consistent merge keys
        target_monthly['date'] = target_monthly['ym'].dt.to_timestamp()
        base_monthly['date'] = base_monthly['ym'].dt.to_timestamp()

        merged_df = pd.merge(target_monthly[['date', 'close']], base_monthly[['date', 'close']], on='date', how='inner', suffixes=('_target', '_base'))
    except Exception as e:
        logger.error(f"[RS DEBUG] 월단위 정규화 및 병합 중 오류: {e}")
        return None

    if merged_df.empty:
        return None

    merged_df['date'] = pd.to_datetime(merged_df['date'])
    merged_df = merged_df.set_index('date').sort_index()

    # Debug: log merged_df size and range for diagnostics
    try:
        logger.info(f"[RS DEBUG] merged_df len={len(merged_df)} range={merged_df.index[0]} ~ {merged_df.index[-1]}")
    except Exception:
        logger.info(f"[RS DEBUG] merged_df len={len(merged_df)}")

    # 완화: 최소 11개월 데이터 이상이면 계산하도록 허용
    if len(merged_df) < 11:
        logger.info(f"[RS DEBUG] merged_df too short (len={len(merged_df)}), returning None")
        return None

    periods = {'3m': 3, '6m': 6, '9m': 9, '12m': 12}
    weights = {'3m': 0.4, '6m': 0.2, '9m': 0.2, '12m': 0.2}

    weighted_rs_score = 0

    # 최신 날짜를 기준으로 각 기간별 수익률 계산
    end_date = merged_df.index[-1]

    for key, p in periods.items():
        # 각 기간의 시작 날짜 계산 (근사치)
        start_date = end_date - pd.DateOffset(months=p)

        # 해당 기간의 데이터 슬라이싱
        period_df = merged_df.loc[start_date:end_date]
        if len(period_df) < 2:
            continue

        # 기간 첫날과 마지막 날의 종가로 수익률 계산
        target_ret = (period_df['close_target'].iloc[-1] / period_df['close_target'].iloc[0]) - 1
        base_ret = (period_df['close_base'].iloc[-1] / period_df['close_base'].iloc[0]) - 1

        diff_ret = (target_ret - base_ret) * 100
        weighted_rs_score += diff_ret * weights[key]

    return round(weighted_rs_score, 2)



def calculate_rs_for_stocks(stock_codes: List[str], execution_mode: str = 'LIVE') -> Dict[str, Dict]:
    """
    주어진 종목 코드 리스트에 대해 시장 상대강도(RS) 점수를 계산합니다.
    execution_mode에 따라 SIMULATION 또는 LIVE 모드로 동작합니다.
    """
    logger.info(f"RS 계산 시작 (모드: {execution_mode}): {len(stock_codes)}개 종목")
    
    # execution_mode에 관계없이 get_candles를 통해 데이터를 가져옵니다.
    kospi_data = get_candles("001", "mon", execution_mode)
    kosdaq_data = get_candles("101", "mon", execution_mode)
    
    if kospi_data.empty or kosdaq_data.empty:
        logger.warning("시장 지수 데이터를 불러올 수 없습니다. 모든 종목에 대해 None 반환.")
        return {code: {'market_rs': None, 'sector_rs': None} for code in stock_codes}
    
    # DB에서 종목들의 시장/업종 정보 조회 (공통 로직)
    db = SessionLocal()
    try:
        stocks_info = db.query(Stock.stock_code, Stock.market_name, Stock.sector_code).filter(Stock.stock_code.in_(stock_codes)).all()
        stock_info_map = {info.stock_code: info for info in stocks_info}
    finally:
        db.close()
    
    # 각 종목별 RS 점수 계산 (공통 로직)
    results = {}
    sector_candle_cache = {}
    
    for code in stock_codes:
        try:
            stock_info = stock_info_map.get(code)
            if not stock_info:
                logger.warning(f"[{code}] 종목의 시장/업종 정보를 DB에서 찾을 수 없습니다.")
                results[code] = {'market_rs': None, 'sector_rs': None}
                continue
            
            # 종목의 월봉 데이터 로드
            stock_data = get_candles(code, 'mon', execution_mode)
            if stock_data.empty:
                logger.warning(f"[{code}] 종목의 월봉 데이터가 없습니다.")
                results[code] = {'market_rs': None, 'sector_rs': None}
                continue
            
            # 시장 RS 계산 (market_name 정규화하여 KOSPI/KOSDAQ 판정)
            mn_raw = (stock_info.market_name or '')
            mn_norm = mn_raw.strip().upper()
            use_kospi = False
            if 'KOSPI' in mn_norm or '거래소' in mn_raw or '코스피' in mn_raw:
                use_kospi = True

            market_data = kospi_data if use_kospi else kosdaq_data
            market_rs = calculate_weighted_rs(stock_data, market_data)
            if market_rs is None:
                logger.debug(f"[{code}] market_rs 계산 불가 (데이터 부족). market_name={mn_raw}")

            # --- Sector RS 계산 활성화 (안정성 및 로깅 강화) ---
            sector_rs = None
            scode = getattr(stock_info, 'sector_code', None)
            if scode:
                try:
                    if scode not in sector_candle_cache:
                        logger.info(f"업종 지수 데이터 로드 및 캐싱: {scode}")
                        sector_candle_cache[scode] = get_candles(scode, 'mon', execution_mode)
                    sector_data = sector_candle_cache.get(scode)
                    if sector_data is None or sector_data.empty:
                        logger.debug(f"[RS DEBUG] [{code}] sector({scode}) mon empty or None")
                    else:
                        try:
                            logger.debug(f"[RS DEBUG] [{code}] sector({scode}) mon len={len(sector_data)} range={sector_data.index[0]} ~ {sector_data.index[-1]}")
                        except Exception:
                            logger.debug(f"[RS DEBUG] [{code}] sector({scode}) mon len={len(sector_data)}")
                    if sector_data is None or sector_data.empty:
                        logger.debug(f"[{code}] 업종({scode}) 데이터 없음 또는 빈 데이터")
                    else:
                        sector_rs = calculate_weighted_rs(stock_data, sector_data)
                        if sector_rs is None:
                            logger.debug(f"[{code}] sector_rs 계산 불가 (데이터 부족) for sector {scode}")
                except Exception as e:
                    logger.error(f"[{code}] 업종 지수 로드/계산 중 예외: sector_code={scode}, error={e}")
                    sector_rs = None
            # --- [완료] ---
            
            results[code] = {
                'market_rs': market_rs,
                'sector_rs': sector_rs
            }
            
        except Exception as e:
            logger.error(f"{code} RS 계산 중 오류 발생: {e}")
            results[code] = {'market_rs': None, 'sector_rs': None}
    
    logger.info(f"RS 계산 완료 ({execution_mode} 모드). {len(results)}개 종목 처리 완료.")
    return results
