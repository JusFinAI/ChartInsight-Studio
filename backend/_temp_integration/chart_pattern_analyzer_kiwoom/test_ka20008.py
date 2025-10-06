import requests
import json
import sys
import os
import time
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple

# --- 환경 설정 및 인증 로더 임포트 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from kiwoom_data_loader import KiwoomDataLoader

# --- 메인 클래스 정의 ---
class MarketSectorRSCalculator:
    def __init__(self):
        self.loader = KiwoomDataLoader()
        self.base_dt = datetime.now().strftime('%Y%m%d')
        self.cache = {}

    def _call_api(self, api_id: str, data: Dict, endpoint: str) -> Dict:
        token = self.loader._get_token()
        if not token: return None
        host = 'https://api.kiwoom.com'
        url = host + endpoint
        headers = {'Content-Type': 'application/json;charset=UTF-8', 'authorization': f'Bearer {token}', 'api-id': api_id}
        try:
            time.sleep(0.25)
            response = requests.post(url, headers=headers, json=data, timeout=15)
            if response.status_code == 200: return response.json()
            else: return None
        except Exception: return None

    def get_sector_list(self, market_code: str) -> Dict[str, str]:
        cache_key = f"sector_list_{market_code}"
        if cache_key in self.cache: return self.cache[cache_key]
        print(f"업종 목록({market_code}) API 호출...")
        res = self._call_api('ka10101', {'mrkt_tp': market_code}, '/api/dostk/stkinfo')
        if res and 'list' in res:
            sector_dict = {item['code']: item['name'] for item in res['list']}
            self.cache[cache_key] = sector_dict
            return sector_dict
        return {}

    def get_stock_info(self, stock_code: str) -> Tuple[str, str, str]:
        cache_key = f"stock_info_{stock_code}"
        if cache_key in self.cache: return self.cache[cache_key]
        res = self._call_api('ka10010', {'stk_cd': stock_code}, '/api/dostk/info')
        if res and res.get('stk_info'):
            info = res['stk_info'][0]
            market_code = "001" if info['stk_mkt_dv_cd'] == '1' else "101"
            sector_code = info['stk_ix_cd']
            sector_name = info['stk_ix_nm']
            self.cache[cache_key] = (market_code, sector_code, sector_name)
            return market_code, sector_code, sector_name
        return None, None, None

    # !--- 여기가 수정된 핵심 부분입니다 ---!
    def _get_chart_data(self, api_id: str, params: dict, response_key: str) -> pd.DataFrame:
        """차트 조회 API(ka10083, ka20008)의 공통 로직을 처리합니다."""
        res = self._call_api(api_id, params, '/api/dostk/chart')
        if res and response_key in res:
            df = pd.DataFrame(res[response_key])
            if df.empty: return pd.DataFrame()

            # ka10083과 ka20008의 실제 응답 컬럼명을 모두 포함하여 rename_map을 확장
            rename_map = {
                'cur_prc': 'close',      # ka10083, ka20008 공통 종가
                'stk_prc': 'close',      # 예비용
                'inds_prc': 'close',     # 예비용
                'dt': 'date'
            }
            df.rename(columns=rename_map, inplace=True)

            if 'close' in df.columns:
                df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                # 빈 문자열이나 공백이 있는 경우를 대비하여 에러 핸들링 추가
                df['close'] = pd.to_numeric(df['close'], errors='coerce').fillna(0)
                return df.sort_values('date').reset_index(drop=True)
            else:
                return pd.DataFrame()
        return pd.DataFrame()

    def get_monthly_data_stock(self, stock_code: str) -> pd.DataFrame:
        params = {'stk_cd': stock_code, 'base_dt': self.base_dt, 'upd_stkpc_tp': '1'}
        return self._get_chart_data('ka10083', params, 'stk_mth_pole_chart_qry')

    def get_monthly_data_sector(self, sector_code: str) -> pd.DataFrame:
        cache_key = f"sector_data_{sector_code}"
        if cache_key in self.cache: return self.cache[cache_key]
        print(f"업종 월봉({sector_code}) API 호출...")
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
            if len(merged_df) >= p:
                recent_prices = merged_df.tail(p)
                target_ret = (recent_prices['close_target'].iloc[-1] / recent_prices['close_target'].iloc[0]) - 1
                base_ret = (recent_prices['close_base'].iloc[-1] / recent_prices['close_base'].iloc[0]) - 1
                diff_ret = (target_ret - base_ret) * 100
                weighted_rs_score += diff_ret * weights[key]
        return weighted_rs_score

    def run_analysis(self, sample_stocks: List[str]):
        print("="*60)
        print("🚀 시장/업종 상대강도(RS) 통합 분석을 시작합니다.")
        print(f"분석 대상: {', '.join(sample_stocks)}")
        print("="*60)
        print("\n--- [Step 1] 기준 지수 데이터 수집 중... ---")
        kospi_data = self.get_monthly_data_sector("001")
        kosdaq_data = self.get_monthly_data_sector("101")
        print("✅ 기준 지수 데이터 수집 완료.")

        results = []
        for stock_code in sample_stocks:
            print(f"\n--- [종목 분석] {stock_code} ---")
            market_code, sector_code, sector_name = self.get_stock_info(stock_code)
            stock_data = self.get_monthly_data_stock(stock_code)
            if not market_code or stock_data.empty:
                print(f"❌ {stock_code}의 기본 정보 또는 월봉 데이터 수집 실패.")
                continue
            print(f"  - 소속: {'KOSPI' if market_code == '001' else 'KOSDAQ'}, 업종: {sector_name}({sector_code})")
            market_data = kospi_data if market_code == "001" else kosdaq_data
            sector_data = self.get_monthly_data_sector(sector_code)
            market_rs = self.calculate_weighted_rs(stock_data, market_data)
            sector_rs = self.calculate_weighted_rs(stock_data, sector_data)
            results.append({'종목코드': stock_code, '시장RS': round(market_rs, 2), '업종RS': round(sector_rs, 2), '업종명': sector_name})
            print(f"  - 시장 상대강도: {market_rs:.2f}")
            print(f"  - 업종 상대강도: {sector_rs:.2f}")

        print("\n" + "="*60)
        print("📈 최종 분석 결과")
        print("="*60)
        if results:
            result_df = pd.DataFrame(results)
            print(result_df.to_string(index=False))
        else:
            print("분석 결과가 없습니다.")
        print("\n" + "="*60)
        print("🎉 모든 분석 완료!")

if __name__ == '__main__':
    SAMPLE_STOCK_LIST = ['005930', '035720', '068270', '091990', '086520']
    calculator = MarketSectorRSCalculator()
    calculator.run_analysis(SAMPLE_STOCK_LIST)