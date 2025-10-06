import requests
import json
import sys
import os
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple
from tqdm import tqdm

# --- 환경 설정 및 인증 로더 임포트 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from kiwoom_data_loader import KiwoomDataLoader

# --- 설정 (Configuration) ---
FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000, 
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}
SECTOR_NAME_MAP = { '부동산': '일반서비스', '금융업': '금융' }

class MarketSectorRSCalculator:
    """
    KOSPI/KOSDAQ 전체 종목의 시장 및 업종 상대강도(RS)를 계산하는 클래스.
    가장 효율적인 API 호출 구조를 적용한 최종 버전입니다.
    """
    def __init__(self):
        self.loader = KiwoomDataLoader()
        self.base_dt = datetime.now().strftime('%Y%m%d')
        self.cache = {}
        self.mismatched_sectors = []

    def _call_api(self, api_id: str, data: Dict, endpoint: str) -> Dict:
        token = self.loader._get_token()
        if not token: return None
        host = 'https://api.kiwoom.com'
        url = host + endpoint
        headers = {'Content-Type': 'application/json;charset=UTF-8', 'authorization': f'Bearer {token}', 'api-id': api_id}
        try:
            time.sleep(0.3)
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 200: return response.json()
            else: return None
        except Exception: return None

    def get_all_stock_codes(self) -> List[Dict]:
        """
        ka10099 (종목정보 리스트) API를 이용하여 KOSPI/KOSDAQ의 모든 종목 '전체 정보'를 가져옵니다.
        (code, name 외에 필터링에 필요한 lastPrice, listCount 등 모든 정보를 포함)
        """
        print("전체 종목 정보 수집 중...")
        all_stocks = []
        for market_tp in ['0', '10']:
            res = self._call_api('ka10099', {'mrkt_tp': market_tp}, '/api/dostk/stkinfo')
            if res and 'list' in res: all_stocks.extend(res['list'])
        return all_stocks

    def get_sector_list(self, market_code: str) -> Dict[str, str]:
        """ka10101 (업종코드 리스트) API를 이용하여 특정 시장의 전체 업종 목록을 가져옵니다."""
        cache_key = f"sector_list_{market_code}"
        if cache_key in self.cache: return self.cache[cache_key]
        res = self._call_api('ka10101', {'mrkt_tp': market_code}, '/api/dostk/stkinfo')
        if res and 'list' in res:
            sector_dict = {item['code']: item['name'] for item in res['list']}
            self.cache[cache_key] = sector_dict
            return sector_dict
        return {}
    
    def _apply_filter_and_enrich(self, all_stocks: List[Dict], all_sector_lists: Dict) -> List[Dict]:
        """
        '필터 제로' 적용 및 업종 코드 정보를 추가(enrich)하는 핵심 함수.
        ka10099로 받은 풍부한 정보를 활용하여 RS 분석 전 대상 종목을 압축합니다.
        """
        print("\n--- [Filter Zero] 필터링 및 정보 보강 시작 ---")
        initial_count = len(all_stocks)
        passed_stocks = []

        for stock in tqdm(all_stocks, desc="필터링 및 정보 보강 중"):
            # 필터 1: 키워드 필터
            state_info = stock.get('state', '')
                        
            name = stock.get('name', '')
            state_info = stock.get('state', '')
            order_warning = stock.get('orderWarning', '0') # 0: 해당없음

            # 1-1. 종목명에 포함된 키워드 (ETF, 스팩 등) 필터링
            if any(keyword in name for keyword in FILTER_ZERO_CONFIG["EXCLUDE_KEYWORDS"]):
                continue

            # 1-2. 종목 상태(state)에 포함된 키워드 (관리종목, 증거금100 등) 필터링
            if any(keyword in state_info for keyword in ["관리종목", "거래정지", "증거금100"]):
                continue

            # 1-3. 투자 유의(orderWarning) 상태 필터링 (0: 해당없음 외에는 모두 제외)
            if order_warning != '0':
                continue

            # 필터 2: 시가총액 필터
            try:
                last_price = int(stock.get('lastPrice', '0'))
                list_count = int(stock.get('listCount', '0'))
                market_cap = (last_price * list_count) / 100_000_000
                if market_cap < FILTER_ZERO_CONFIG["MIN_MARKET_CAP_KRW"]: continue
            except (ValueError, TypeError): continue

            # 정보 보강(Enrichment): 업종 코드 찾기
            market_name = stock.get('marketName', '')
            sector_name_from_api = stock.get('upName', '')
            market_code_for_list = "001" if market_name == "거래소" else "101"
            
            corrected_sector_name = SECTOR_NAME_MAP.get(sector_name_from_api, sector_name_from_api)
            target_sector_list = all_sector_lists.get(market_code_for_list, {})
            found_sector_code = None
            for code, s_name in target_sector_list.items():
                if s_name in corrected_sector_name or corrected_sector_name in s_name:
                    found_sector_code = code
                    break
            
            if not found_sector_code and sector_name_from_api:
                mismatch_log = {'stock_code': stock['code'], 'api_sector_name': sector_name_from_api}
                if mismatch_log not in self.mismatched_sectors: self.mismatched_sectors.append(mismatch_log)
                continue # 업종 코드를 못찾으면 분석 대상에서 제외

            # 모든 필터를 통과하고 정보 보강이 완료된 종목만 추가
            stock['marketCode'] = market_code_for_list
            stock['sectorCode'] = found_sector_code
            stock['sectorName'] = sector_name_from_api
            passed_stocks.append(stock)

        final_count = len(passed_stocks)
        print(f"✅ 필터링/보강 완료: {initial_count}개 종목 -> {final_count}개 종목 ({initial_count - final_count}개 제외)")
        return passed_stocks


    def _get_chart_data(self, api_id: str, params: dict, response_key: str) -> pd.DataFrame:
        res = self._call_api(api_id, params, '/api/dostk/chart')
        if res and response_key in res:
            df = pd.DataFrame(res[response_key])
            if df.empty: return pd.DataFrame()
            rename_map = {'cur_prc': 'close', 'stk_prc': 'close', 'inds_prc': 'close', 'dt': 'date'}
            df.rename(columns=rename_map, inplace=True)
            if 'close' in df.columns:
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                df['close'] = pd.to_numeric(df['close'], errors='coerce').fillna(0)
                return df.sort_values('date').reset_index(drop=True)
        return pd.DataFrame()

    def get_monthly_data_stock(self, stock_code: str) -> pd.DataFrame:
        params = {'stk_cd': stock_code, 'base_dt': self.base_dt, 'upd_stkpc_tp': '1'}
        return self._get_chart_data('ka10083', params, 'stk_mth_pole_chart_qry')

    def get_monthly_data_sector(self, sector_code: str) -> pd.DataFrame:
        cache_key = f"sector_data_{sector_code}"
        if cache_key in self.cache: return self.cache[cache_key]
        params = {'inds_cd': sector_code, 'base_dt': self.base_dt}
        df = self._get_chart_data('ka20008', params, 'inds_mth_pole_qry')
        self.cache[cache_key] = df
        return df

    def calculate_weighted_rs(self, target_df: pd.DataFrame, base_df: pd.DataFrame) -> float:
        if target_df.empty or base_df.empty: return 0.0
        merged_df = pd.merge(target_df[['date', 'close']], base_df[['date', 'close']], on='date', suffixes=('_target', '_base')).set_index('date')
        periods = {'3m': 3, '6m': 6, '9m': 9, '12m': 12}
        weights = {'3m': 0.4, '6m': 0.2, '9m': 0.2, '12m': 0.2}
        weighted_rs_score = 0
        for key, p in periods.items():
            if len(merged_df) >= p + 1:
                recent_prices = merged_df.tail(p + 1)
                target_ret = (recent_prices['close_target'].iloc[-1] / recent_prices['close_target'].iloc[0]) - 1
                base_ret = (recent_prices['close_base'].iloc[-1] / recent_prices['close_base'].iloc[0]) - 1
                diff_ret = (target_ret - base_ret) * 100
                weighted_rs_score += diff_ret * weights[key]
        return weighted_rs_score

    def run_analysis(self):
        print("="*60 + "\n🚀 시장/업종 상대강도(RS) 전체 종목 분석을 시작합니다.\n" + "="*60)
        
        # Step 1: 업종 목록, 기준 지수 데이터 등 공통 데이터 수집
        print("\n--- [Step 1] 공통 데이터 수집 ---")
        kospi_sector_list = self.get_sector_list('0')
        kosdaq_sector_list = self.get_sector_list('1')
        all_sector_lists = {'001': kospi_sector_list, '101': kosdaq_sector_list}
        kospi_data = self.get_monthly_data_sector("001")
        kosdaq_data = self.get_monthly_data_sector("101")
        print("✅ 공통 데이터 수집 완료.")
        
        # Step 2: 전체 종목 정보 수집 후, 필터링 및 정보 보강
        all_stocks_raw = self.get_all_stock_codes()
        if not all_stocks_raw: return
        
        filtered_stocks = self._apply_filter_and_enrich(all_stocks_raw, all_sector_lists)
        if not filtered_stocks: return
        
        print(f"\n--- [Step 2] {len(filtered_stocks)}개 종목 대상 RS 분석 시작 ---")
        results = []
        for stock in tqdm(filtered_stocks, desc="RS 스코어 계산 중"):
            stock_code = stock['code']
            stock_name = stock['name']
            market_code = stock['marketCode']
            sector_code = stock['sectorCode']
            sector_name = stock['sectorName']
            
            stock_data = self.get_monthly_data_stock(stock_code)
            if stock_data.empty: continue
            
            market_data = kospi_data if market_code == "001" else kosdaq_data
            sector_data = self.get_monthly_data_sector(sector_code)
            
            market_rs = self.calculate_weighted_rs(stock_data, market_data)
            sector_rs = self.calculate_weighted_rs(stock_data, sector_data)
            
            results.append({'종목코드': stock_code, '종목명': stock_name, '시장RS': round(market_rs, 2), '업종RS': round(sector_rs, 2), '업종명': sector_name})

        # --- 최종 결과 출력 및 저장 ---
        if results:
            result_df = pd.DataFrame(results)
            strong_stocks = result_df[(result_df['시장RS'] > 0) & (result_df['업종RS'] > 0)].sort_values(by=['시장RS', '업종RS'], ascending=False)
            
            print("\n" + "="*60 + "\n📈 최종 분석 결과\n" + "="*60)
            print("--- 시장과 업종을 모두 이기는 주도주 ---")
            print(strong_stocks.to_string(index=False))
            
            output_filename = f"market_sector_rs_results_{self.base_dt}.csv"
            strong_stocks.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 강력한 주도주 목록({len(strong_stocks)}개)을 '{output_filename}' 파일로 저장했습니다.")
        
        if self.mismatched_sectors:
            print("\n" + "="*60 + "\n⚠️ 업종명 매칭에 실패한 경우들\n" + "="*60)
            mismatch_df = pd.DataFrame(self.mismatched_sectors)
            print(mismatch_df.to_string(index=False))
            
        print("\n" + "="*60 + f"\n🎉 모든 분석 완료! 총 {len(results)}개의 유효 종목 분석 완료.")

if __name__ == '__main__':
    calculator = MarketSectorRSCalculator()
    calculator.run_analysis()