#!/usr/bin/env python3
"""
fetch_sector_master.py

간단한 스크립트로 test_ka10101.py의 fn_ka10101 함수를 호출하여
KOSPI/KOSDAQ 업종 코드 리스트를 받아 로컬 JSON 파일로 저장합니다.

Usage (run inside container where KiwoomDataLoader works):
    python DataPipeline/scripts/fetch_sector_master.py

"""
import json
import os
from pathlib import Path

from src.kiwoom_api.core.client import client
from src.utils.logging_kst import configure_kst_logger

logger = configure_kst_logger(__name__)

# Filter Zero config (adapted from market_sector_rs_calcurator)
FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000,  # 억 단위 기준
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}

SECTOR_NAME_MAP = { '부동산': '일반서비스', '금융업': '금융', '리츠': '부동산' }

def _extract_items_from_response(resp):
    # client.request returns {'data': ..., 'headers': ...}
    data = None
    if isinstance(resp, dict) and 'data' in resp:
        data = resp['data']
    else:
        data = resp
    # possible keys (including 'list' as returned by API)
    for key in ['list', 'stk_ix_info', 'data', 'result', 'items']:
        if isinstance(data, dict) and key in data:
            return data[key]

    if isinstance(data, list):
        return data

    return []


def main():
    
    sim_path = os.getenv("SIMULATION_DATA_PATH", "/opt/airflow/data/simulation")
    out_dir = Path(sim_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'sector_master.json'

    results = {}

    # Step 1: get sector lists for KOSPI and KOSDAQ
    sector_lists = {}
    for mrkt_tp, name, list_key in [('0', 'KOSPI', '001'), ('1', 'KOSDAQ', '101')]:
        params = {'mrkt_tp': mrkt_tp}
        try:
            resp = client.request(endpoint='/api/dostk/stkinfo', api_id='ka10101', data=params)
        except Exception as e:
            print(f"API call failed for market {name}: {e}")
            continue

        items = _extract_items_from_response(resp)
        if not items:
            print(f"No sector list returned for {name}")
            sector_lists[list_key] = {}
            continue

        sector_dict = {str(entry.get('code')): entry.get('name') for entry in items if isinstance(entry, dict) and entry.get('code')}
        sector_lists[list_key] = sector_dict

    # Step 2: get all stock info via ka10099 for relevant markets
    all_stocks = []
    for market_tp in ['0', '10']:
        try:
            resp = client.request(endpoint='/api/dostk/stkinfo', api_id='ka10099', data={'mrkt_tp': market_tp})
        except Exception as e:
            print(f"API call failed for ka10099 market {market_tp}: {e}")
            continue
        items = _extract_items_from_response(resp)
        if items:
            all_stocks.extend(items)
    # Step 3: apply Filter Zero (filtering + enrichment) and build mapping
    def _apply_filter_and_enrich(stocks, all_sector_lists):
        passed = []
        mismatched = []

        def _normalize(text: str) -> str:
            return ''.join(ch for ch in (text or '').lower() if ch.isalnum())

        for s in stocks:
            try:
                name = s.get('name', '')
                state_info = s.get('state', '')
                order_warning = s.get('orderWarning', '0')

                # keyword filter
                if any(k in name for k in FILTER_ZERO_CONFIG['EXCLUDE_KEYWORDS']):
                    continue
                if any(k in state_info for k in ["관리종목", "거래정지", "증거금100"]):
                    continue
                if order_warning != '0':
                    continue

                # market cap filter
                try:
                    last_price = int(s.get('lastPrice', '0'))
                    list_count = int(s.get('listCount', '0'))
                    market_cap = (last_price * list_count) / 100_000_000
                    if market_cap < FILTER_ZERO_CONFIG['MIN_MARKET_CAP_KRW']:
                        continue
                except (ValueError, TypeError):
                    continue

                market_name = s.get('marketName', '')
                sector_name_from_api = s.get('upName', '')
                market_code_for_list = '001' if market_name == '거래소' else '101'

                corrected_sector_name = SECTOR_NAME_MAP.get(sector_name_from_api, sector_name_from_api)
                target_sector_list = all_sector_lists.get(market_code_for_list, {})
                found_code = None

                # Heuristic: if upName is empty, try to infer from name/companyClassName/kind
                up_empty = not (sector_name_from_api and sector_name_from_api.strip())
                if up_empty:
                    name_lower = (s.get('name') or '').lower()
                    comp_class = (s.get('companyClassName') or '').lower()
                    kind = (s.get('kind') or '').lower()

                    # tokens indicating banking/financial
                    if any(tok in name_lower for tok in ['은행', '뱅크', 'bank']) or any(tok in comp_class for tok in ['금융', '은행']) or any(tok in kind for tok in ['bank', '금융']):
                        for mk, sl in all_sector_lists.items():
                            for scode, sname in sl.items():
                                if '금융' in (sname or ''):
                                    found_code = scode
                                    break
                            if found_code:
                                break
                        if found_code:
                            # mapped via heuristic
                            pass
                        else:
                            # no suitable 금융 sector found -> treat as zero-filter (exclude)
                            continue

                    # ETF or symbol indicates ETF -> zero-filter (exclude)
                    if (s.get('marketName') == 'ETF') or ('ETF' in (s.get('name') or '')):
                        continue

                    # default: treat as zero-filter per policy
                    continue

                # If upName provided (non-empty) or heuristic didn't apply, try normalized matching
                n_up = ''.join(ch for ch in (corrected_sector_name or '').lower() if ch.isalnum())
                if n_up:
                    for code, s_name in target_sector_list.items():
                        s_norm = ''.join(ch for ch in (s_name or '').lower() if ch.isalnum())
                        if s_norm == n_up or n_up in s_norm or s_norm in n_up:
                            found_code = code
                            break

                # If still not found, record mismatch (only when api provided a non-empty sector name)
                if not found_code:
                    if sector_name_from_api:
                        mismatched.append({'stock_code': s.get('code'), 'api_sector_name': sector_name_from_api})
                    continue

                s['marketCode'] = market_code_for_list
                s['sectorCode'] = found_code
                s['sectorName'] = sector_name_from_api
                passed.append(s)
            except Exception:
                continue

        return passed, mismatched

    passed_stocks, mismatched_stocks = _apply_filter_and_enrich(all_stocks, sector_lists)
    print(f"Filtered & enriched stocks: {len(passed_stocks)}, mismatches: {len(mismatched_stocks)}")
    # write mismatched details for debugging
    try:
        mismatched_path = out_path.parent / 'sector_master_mismatched.json'
        with open(mismatched_path, 'w', encoding='utf-8') as mf:
            json.dump({'mismatches': mismatched_stocks}, mf, ensure_ascii=False, indent=2)
        print(f'Wrote mismatched sample to {mismatched_path}')
    except Exception as e:
        print('Failed to write mismatched file:', e)

    # build results structure from passed_stocks
    results = {k: {'market': None, 'members': []} for k in sector_lists}
    for s in passed_stocks:
        sec = s.get('sectorCode')
        if sec not in results:
            results.setdefault(sec, {'market': None, 'members': []})
        results[sec]['members'].append(str(s.get('code')))

    # ensure every sector code from sector_lists has market metadata
    for s_code, s_name in sector_lists.get('001', {}).items():
        results.setdefault(s_code, {'market': 'KOSPI', 'members': []})
    for s_code, s_name in sector_lists.get('101', {}).items():
        results.setdefault(s_code, {'market': 'KOSDAQ', 'members': []})

    # create reverse mapping stock -> sector from results
    stock_to_sector = {}
    for sector_code, info in results.items():
        for mem in info.get('members', []):
            stock_to_sector[mem] = sector_code

    payload = {
        'generated_at': __import__('datetime').datetime.utcnow().isoformat() + 'Z',
        'source': 'ka10101_one_time_fetch',
        'mapping': stock_to_sector,
    }

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f'Wrote sector master mapping to {out_path} (entries: {len(stock_to_sector)})')


if __name__ == '__main__':
    main()


