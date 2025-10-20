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


def _load_simulation_monthly_data(code: str) -> pd.DataFrame:
    """시뮬레이션용 월봉 Parquet 파일을 읽어 DataFrame으로 반환합니다."""
    # 시뮬레이션 데이터 경로 우선순위:
    # 1) OS 환경변수 SIMULATION_DATA_PATH
    # 2) Airflow Variable SIMULATION_DATA_PATH (if Airflow available)
    # 3) 기본값 /opt/airflow/data/simulation
    env_path = os.getenv("SIMULATION_DATA_PATH")
    if env_path:
        use_path = env_path
    else:
        use_path = None
        if AirflowVariable is not None:
            try:
                use_path = AirflowVariable.get('SIMULATION_DATA_PATH', default_var=None)
            except Exception:
                use_path = None

    if not use_path:
        # 마지막 안전망: 환경변수가 없으면 컨테이너 내부 기본 경로를 사용
        use_path = os.getenv('SIMULATION_DATA_PATH', '/opt/airflow/data/simulation')

    # Path 객체로 변환 및 존재 여부 확인
    simulation_data_dir = Path(use_path)
    logger.info(f"Using simulation data directory: {simulation_data_dir}")
    parquet_file = simulation_data_dir / f"{code}_mon_full.parquet"

    # Parquet 파일을 시도하고, 실패시 즉시 실패(개발 초기에는 fail-fast)
    if not parquet_file.exists():
        logger.error(f"시뮬레이션 Parquet 파일이 없습니다: {parquet_file}")
        raise FileNotFoundError(f"Missing parquet: {parquet_file}")

    try:
        df = pd.read_parquet(parquet_file)
    except Exception as e:
        # Fail-fast: Parquet 읽기 오류는 파일/작성 파이프라인 문제를 의미함
        logger.error(f"{parquet_file} 로드 실패(Parquet): {e}")
        raise

    # At this point df is either loaded from parquet or CSV (or empty if neither existed)
    if df.empty:
        return pd.DataFrame()

    # 날짜 인덱스가 있어야 후속 처리가 용이합니다.
    if not isinstance(df.index, pd.DatetimeIndex):
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.set_index('date')
        else:
            logger.error(f"{code} 파일에 'date' 컬럼 또는 DatetimeIndex가 없습니다.")
            return pd.DataFrame()

    # 월봉 데이터이므로 날짜를 월 단위로 정규화하여 시간(시분초) 차이로 인한 병합 실패를 방지합니다.
    try:
        # 먼저 DatetimeIndex로 보장
        df.index = pd.to_datetime(df.index)
        # tz-aware이면 UTC로 통일 후 tz 정보를 제거(Period 변환이 tz-aware를 지원하지 않음)
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_convert('UTC').tz_localize(None)
        # convert to period 'M' then back to timestamp at period start for consistent keys
        df.index = df.index.to_period('M').to_timestamp()
    except Exception:
        # fallback: sort index without period conversion
        df.index = pd.to_datetime(df.index)

    # 컬럼명 정규화: API/스クリプト별로 원시 컬럼명이 다를 수 있으므로 표준 컬럼명으로 매핑합니다.
    col_map = {
        'cur_prc': 'close',
        'open_pric': 'open',
        'high_pric': 'high',
        'low_pric': 'low',
        'trde_qty': 'volume',
        'trde_prica': 'value',
        'acc_trde_qty': 'acc_volume'
    }
    # rename if present
    intersect = {k: v for k, v in col_map.items() if k in df.columns}
    if intersect:
        df = df.rename(columns=intersect)

    # 숫자형으로 변환 (문자열에 +, 콤마 등이 포함될 수 있음)
    for num_col in ['open', 'high', 'low', 'close', 'volume', 'value', 'acc_volume']:
        if num_col in df.columns:
            df[num_col] = pd.to_numeric(df[num_col].astype(str).str.replace('[+,]', '', regex=True), errors='coerce')

    return df.sort_index()


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

    merged_df = pd.merge(target[['date', 'close']], base[['date', 'close']], on='date', how='inner', suffixes=('_target', '_base'))
    if merged_df.empty:
        return None

    merged_df['date'] = pd.to_datetime(merged_df['date'])
    merged_df = merged_df.set_index('date').sort_index()

    # 완화: 최소 11개월 데이터 이상이면 계산하도록 허용
    if len(merged_df) < 11:
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
    execution_mode에 따라 SIMULATION(Parquet 기반) 또는 LIVE(DB/API 기반)로 분기합니다.
    """
    logger.info(f"RS 계산 시작 (모드: {execution_mode}): {len(stock_codes)}개 종목")

    if execution_mode == 'SIMULATION':
        # 1. 공통 데이터 로드: 시장 지수 데이터
        kospi_data = _load_simulation_monthly_data("001")  # KOSPI 지수
        kosdaq_data = _load_simulation_monthly_data("101")  # KOSDAQ 지수

        if kospi_data.empty or kosdaq_data.empty:
            raise FileNotFoundError("시장 지수(KOSPI/KOSDAQ) 시뮬레이션 데이터 파일이 필요합니다.")

        # 2. DB에서 종목들의 시장 정보(KOSPI/KOSDAQ) 조회
        db = SessionLocal()
        try:
            stocks_info = db.query(Stock.stock_code, Stock.market_name).filter(Stock.stock_code.in_(stock_codes)).all()
            market_map = {info.stock_code: info.market_name for info in stocks_info}
        finally:
            db.close()

        # 3. 각 종목별 RS 점수 계산
        results = {}
        sector_data_cache = {}  # 업종 데이터 캐싱

        # --- 임시 업종 매핑 (테스트용) ---
        MOCK_SECTOR_MAP = {
            '005930': '013',
            '000660': '013',
            '035720': '029',
            '247540': '124'
        }

        for code in stock_codes:
            market_name = market_map.get(code)
            if not market_name:
                logger.warning(f"{code} 종목의 시장 정보를 DB에서 찾을 수 없습니다.")
                continue

            # 종목의 월봉 데이터 로드
            stock_data = _load_simulation_monthly_data(code)
            if stock_data.empty:
                continue

            # 3a. 시장 RS 계산 (기존 로직)
            market_data = kospi_data if 'KOSPI' in market_name else kosdaq_data
            market_rs = calculate_weighted_rs(stock_data, market_data)

            # 3b. 섹터 RS 계산
            sector_rs = None
            sector_code = MOCK_SECTOR_MAP.get(code)
            if sector_code:
                if sector_code not in sector_data_cache:
                    logger.info(f"업종 지수 데이터 로드 및 캐싱: {sector_code}")
                    sector_data_cache[sector_code] = _load_simulation_monthly_data(sector_code)

                sector_data = sector_data_cache.get(sector_code)
                if sector_data is not None and not sector_data.empty:
                    sector_rs = calculate_weighted_rs(stock_data, sector_data)

            results[code] = {
                'market_rs': market_rs,
                'sector_rs': sector_rs
            }

        logger.info(f"RS 계산 완료 (SIMULATION 모드). {len(results)}개 종목 처리 완료.")
        return results
    else:
        # LIVE 모드: DB 기반 간단한 구현 (임시)
        logger.info("LIVE 모드 RS 계산 시작 (간단한 DB 기반 구현)")
        
        try:
            # DB에서 월봉 데이터 조회
            from src.data_collector import get_candles
            
            results = {}
            
            # 시장 지수 데이터 로드 (KOSPI: 001, KOSDAQ: 101)
            kospi_data = get_candles('001', 'mon', execution_mode='LIVE')
            kosdaq_data = get_candles('101', 'mon', execution_mode='LIVE')
            
            if kospi_data.empty or kosdaq_data.empty:
                logger.warning("시장 지수 데이터를 불러올 수 없습니다. 모든 종목에 대해 None 반환.")
                return {code: {'market_rs': None, 'sector_rs': None} for code in stock_codes}
            
            # DB에서 종목들의 시장 정보 조회
            db = SessionLocal()
            try:
                stocks_info = db.query(Stock.stock_code, Stock.market_name).filter(Stock.stock_code.in_(stock_codes)).all()
                market_map = {info.stock_code: info.market_name for info in stocks_info}
            finally:
                db.close()
            
            # 각 종목별 RS 점수 계산
            for code in stock_codes:
                try:
                    market_name = market_map.get(code)
                    if not market_name:
                        logger.warning(f"{code} 종목의 시장 정보를 DB에서 찾을 수 없습니다.")
                        results[code] = {'market_rs': None, 'sector_rs': None}
                        continue
                    
                    # 종목의 월봉 데이터 로드
                    stock_data = get_candles(code, 'mon', execution_mode='LIVE')
                    if stock_data.empty:
                        logger.warning(f"{code} 종목의 월봉 데이터가 없습니다.")
                        results[code] = {'market_rs': None, 'sector_rs': None}
                        continue
                    
                    # 시장 RS 계산
                    market_data = kospi_data if 'KOSPI' in market_name else kosdaq_data
                    market_rs = calculate_weighted_rs(stock_data, market_data)
                    
                    # 섹터 RS는 임시로 None (Phase 2에서 구현 예정)
                    sector_rs = None
                    
                    results[code] = {
                        'market_rs': market_rs,
                        'sector_rs': sector_rs
                    }
                    
                except Exception as e:
                    logger.error(f"{code} RS 계산 중 오류 발생: {e}")
                    results[code] = {'market_rs': None, 'sector_rs': None}
            
            logger.info(f"RS 계산 완료 (LIVE 모드). {len(results)}개 종목 처리 완료.")
            return results
            
        except Exception as e:
            logger.error(f"LIVE 모드 RS 계산 중 치명적 오류 발생: {e}")
            logger.info("모든 종목에 대해 None 반환합니다.")
            return {code: {'market_rs': None, 'sector_rs': None} for code in stock_codes}
