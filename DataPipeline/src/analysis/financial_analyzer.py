"""
재무 분석 모듈 (SIMULATION 모드 전용)

이 모듈은 SIMULATION 모드에서 JSON 파일 기반의 재무 분석을 수행합니다.
LIVE 모드의 재무 분석은 dag_financials_update.py와 financial_engine.py가 담당합니다.

주요 함수:
    - analyze_financials_for_stocks: SIMULATION 모드 전용 재무 분석
    - _load_simulation_financial_data: JSON 파일로부터 모의 재무 데이터 로드

Note:
    - LIVE 모드 로직은 src.analysis.financial_engine으로 이관됨
    - dag_financials_update.py가 LIVE 모드 재무 분석을 전담
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, List

import pandas as pd

from src.utils.logging_kst import configure_kst_logger

logger = configure_kst_logger(__name__)

try:
    from airflow.models import Variable as AirflowVariable  # type: ignore
except Exception:
    AirflowVariable = None


def _load_simulation_financial_data() -> pd.DataFrame:
    """Load mock financial JSON from configured paths into a DataFrame.
    Supports multiple mock formats for convenience.
    """
    # path candidates: env -> Airflow Variable -> default
    sim_dir = os.getenv('SIMULATION_DATA_PATH')
    if not sim_dir and AirflowVariable is not None:
        try:
            sim_dir = AirflowVariable.get('SIMULATION_DATA_PATH', default_var=None)
        except Exception:
            sim_dir = None

    candidates = []
    if sim_dir:
        p = Path(sim_dir)
        if p.is_dir():
            candidates.append(p / 'mock_financial_data.json')
        else:
            candidates.append(Path(sim_dir))

    candidates.append(Path(os.getenv('SIMULATION_DATA_PATH', '/opt/airflow/data')) / 'mock_financial_data.json')

    data_path = None
    for p in candidates:
        if p.exists():
            data_path = p
            break

    if data_path is None:
        logger.error(f"시뮬레이션용 재무 데이터 파일을 찾을 수 없습니다. 검색 경로: {candidates}")
        return pd.DataFrame()

    try:
        with open(data_path, 'r', encoding='utf-8') as f:
            raw = json.load(f)

        # normalize into records of {'stock_code','year','quarter','eps'}
        records = []
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
            if 'code' in df.columns and 'stock_code' not in df.columns:
                df = df.rename(columns={'code': 'stock_code'})
            return df

        if isinstance(raw, dict):
            # flat yearly eps map
            sample = next(iter(raw.values()))
            if isinstance(sample, (int, float)):
                for code, val in raw.items():
                    try:
                        records.append({'stock_code': code, 'year': None, 'quarter': None, 'eps': float(val)})
                    except Exception:
                        continue
                return pd.DataFrame.from_records(records)

            # structured: yearly dicts
            for code, meta in raw.items():
                if isinstance(meta.get('eps'), dict):
                    for y, v in meta.get('eps', {}).items():
                        try:
                            records.append({'stock_code': code, 'year': int(y), 'quarter': None, 'eps': float(v)})
                        except Exception:
                            continue
                if isinstance(meta.get('quarters'), dict):
                    for qk, qv in meta.get('quarters', {}).items():
                        try:
                            y, q = qk.split('-Q')
                            records.append({'stock_code': code, 'year': int(y), 'quarter': int(q), 'eps': float(qv)})
                        except Exception:
                            continue

        if not records:
            df = pd.DataFrame.from_dict(raw, orient='index')
            df.reset_index(inplace=True)
            df.rename(columns={'index': 'stock_code'}, inplace=True)
            return df

        return pd.DataFrame.from_records(records)

    except Exception as e:
        logger.error(f"시뮬레이션 재무 데이터 로드 실패: {e}")
        return pd.DataFrame()


def analyze_financials_for_stocks(stock_codes: List[str], execution_mode: str = 'SIMULATION') -> Dict[str, Dict]:
    """종목들의 재무 분석 수행 (SIMULATION 모드 전용)
    
    Args:
        stock_codes: 분석할 종목 코드 리스트
        execution_mode: 실행 모드 ('SIMULATION'만 지원)
        
    Returns:
        종목코드별 재무 분석 결과 딕셔너리
        {
            'stock_code': {
                'eps_growth_yoy': float,
                'eps_annual_growth_avg': float,
                'financial_grade': str
            }
        }
        
    Note:
        LIVE 모드는 dag_financials_update.py가 담당하므로,
        이 함수에서 LIVE 모드를 사용하면 에러가 발생합니다.
    """
    if execution_mode == 'LIVE':
        raise ValueError(
            "analyze_financials_for_stocks는 SIMULATION 모드 전용입니다. "
            "LIVE 모드 재무 분석은 dag_financials_update.py를 사용하세요."
        )
    
    logger.info(f"재무 분석 시작 (모드: {execution_mode}): {len(stock_codes)}개 종목")
    
    results: Dict[str, Dict] = {}
    
    # SIMULATION 모드: JSON 파일 기반 분석
    df = _load_simulation_financial_data()
    if df.empty:
        return {code: {} for code in stock_codes}
    
    # reuse existing logic: normalize to records with 'stock_code','year','quarter','eps'
    for code in stock_codes:
        stock_df = df[df['stock_code'] == code].copy()
        if stock_df.empty:
            results[code] = {}
            continue
        
        # derive eps_growth_yoy and annual avg using same heuristics as previous implementation
        # We assume stock_df has columns year/quarter/eps or eps in 'eps' column
        # Normalize to 'eps' column
        if 'eps' in stock_df.columns:
            norm_df = stock_df[['stock_code', 'year', 'quarter', 'eps']].rename(columns={'eps': 'eps'})
        else:
            norm_df = stock_df
        
        # simple fallback: compute annual and quarterly indicators
        # Annual YoY
        annual = norm_df[norm_df['quarter'].isna()] if 'quarter' in norm_df.columns else norm_df
        annual = annual.sort_values(by='year', ascending=False)
        eps_annual_growth_avg = None
        if len(annual) >= 3 and annual.iloc[2].get('eps', 0):
            try:
                y1, y2, y3 = annual.iloc[0], annual.iloc[1], annual.iloc[2]
                cagr = ((y1['eps'] / y3['eps']) ** (1 / 2)) - 1
                eps_annual_growth_avg = round(cagr * 100, 2)
            except Exception:
                eps_annual_growth_avg = None
        
        # quarterly YoY fallback
        eps_growth_yoy = None
        if 'quarter' in norm_df.columns and norm_df['quarter'].notna().any():
            quarterly = norm_df.dropna(subset=['quarter']).sort_values(by=['year', 'quarter'], ascending=False)
            if len(quarterly) >= 1:
                latest = quarterly.iloc[0]
                prev = quarterly[(quarterly['year'] == latest['year'] - 1) & (quarterly['quarter'] == latest['quarter'])]
                if not prev.empty:
                    prev_eps = prev.iloc[0].get('eps')
                    if prev_eps and prev_eps > 0:
                        eps_growth_yoy = round(((latest.get('eps') / prev_eps) - 1) * 100, 2)
        else:
            if len(annual) >= 2:
                try:
                    latest, prev = annual.iloc[0], annual.iloc[1]
                    if prev.get('eps') and prev.get('eps') > 0:
                        eps_growth_yoy = round(((latest.get('eps') / prev.get('eps')) - 1) * 100, 2)
                except Exception:
                    eps_growth_yoy = None
        
        # simple grade logic for simulation
        financial_grade = 'C'
        if eps_growth_yoy is not None and eps_growth_yoy > 0 and eps_annual_growth_avg is not None and eps_annual_growth_avg > 10:
            financial_grade = 'B+'
        
        results[code] = {
            'eps_growth_yoy': eps_growth_yoy,
            'eps_annual_growth_avg': eps_annual_growth_avg,
            'financial_grade': financial_grade
        }
    
    logger.info(f"재무 분석 완료. {len(results)}개 종목 처리 완료.")
    return results
