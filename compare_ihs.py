# compare_ihs.py (프로젝트 루트에 저장)
import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

# load .env if available
try:
    import importlib
    dotenv = importlib.import_module('dotenv')
    load_dotenv = getattr(dotenv, 'load_dotenv', None)
    if load_dotenv:
        load_dotenv((ROOT / '.env').as_posix())
except Exception:
    pass

import pandas as pd
from backend.app.database import SessionLocal
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.analysis import run_analysis_from_db_by_symbol as run_db_by_symbol
# original engine (kiwoom) run_full_analysis expects a DataFrame
from backend._temp_integration.chart_pattern_analyzer_kiwoom.analysis_engine import run_full_analysis as run_orig_engine
from backend._temp_integration.chart_pattern_analyzer_kiwoom_db.run_full_analysis_impl import run_full_analysis as run_db_engine

db = SessionLocal()
# 005930, 1d: same ticker/interval as in dashboard
analysis = run_db_by_symbol(db, '005930', '1d', period=None, limit=None)
db.close()

# build DataFrame from base_data so both engines get the same input
base = analysis.get('base_data', {})
dates = base.get('dates', [])
if len(dates) == 0:
    print("No base data")
    sys.exit(1)
try:
    if isinstance(dates[0], (int, float)):
        idx = pd.to_datetime(dates, unit='s')
    else:
        idx = pd.to_datetime(dates)
except Exception:
    idx = pd.to_datetime(dates)

df = pd.DataFrame({
    'Open': base.get('open', []),
    'High': base.get('high', []),
    'Low': base.get('low', []),
    'Close': base.get('close', []),
    'Volume': base.get('volume', [0]*len(dates))
}, index=idx)
df.index.name = 'Date'

# Run original engine and DB engine on exact same df
print("Running original engine...")
r_orig = run_orig_engine(df.copy(), ticker='005930', period=None, interval='1d')
print("Running DB engine...")
r_db = run_db_engine(df.copy(), ticker='005930', period=None, interval='1d')

print("original completed_ihs:", r_orig.get('patterns', {}).get('completed_ihs', [])[:3])
print("db completed_ihs:", r_db.get('patterns', {}).get('completed_ihs', [])[:3])
# also print candidate lists / failed detectors if available
print("original completed_hs:", r_orig.get('patterns', {}).get('completed_hs', [])[:3])
print("db completed_hs:", r_db.get('patterns', {}).get('completed_hs', [])[:3])