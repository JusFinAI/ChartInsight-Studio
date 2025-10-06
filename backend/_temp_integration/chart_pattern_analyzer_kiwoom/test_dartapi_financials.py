
import os
import requests
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional

# --- 1. 설정 (Configuration) ---
DART_API_KEY = "2cae1c66f8f4557528070d84877c183c0cb435cf" # 실제 키를 이곳에 붙여넣으세요

class AccountIDs:
    # EPS 계산에 가장 정확한 '지배기업 소유주지분 순이익' 사용
    NET_INCOME = "ifrs-full_ProfitLossAttributableToOwnersOfParent" 

# --- 2. API 클라이언트 ---
class DartApiClient:
    """Open DART API와의 모든 통신을 담당"""
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str):
        if not api_key or "YOUR_API_KEY_HERE" in api_key:
            raise ValueError("Open DART API 키가 설정되지 않았습니다.")
        self.api_key = api_key

    def _request_api(self, endpoint: str, params: Dict) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/{endpoint}"
        final_params = {"crtfc_key": self.api_key, **params}
        try:
            response = requests.get(url, params=final_params)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "000":
                if data.get("status") != "013":
                    print(f"API Warning ({endpoint}): {data.get('message')}")
                return None
            return data.get("list", [])
        except requests.exceptions.RequestException as e:
            print(f"HTTP Error ({endpoint}): {e}")
            return None
        except ValueError:
            print(f"JSON Parsing Error ({endpoint}): {response.text}")
            return None

    def get_financial_statements(self, corp_code: str, year: int, reprt_code: str) -> Optional[List[Dict]]:
        """연결재무제표(CFS)를 명시적으로 요청"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
        return self._request_api("fnlttSinglAcntAll.json", params)

    def get_annual_share_info(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        """[핵심 수정] 연간 사업보고서(11011)의 주식 총수만 조회"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        return self._request_api("stockTotqySttus.json", params)

# --- 3. 데이터 파서 ---
class FinancialDataParser:
    """DART API 원본 데이터를 분석 가능한 DataFrame으로 변환"""
    def _to_numeric(self, value: str) -> int:
        if not isinstance(value, str) or not value: return 0
        try: return int(value.replace(",", ""))
        except ValueError: return 0
            
    def _report_code_to_quarter(self, reprt_code: str) -> str:
        return {"11013": "Q1", "11012": "Q2", "11014": "Q3", "11011": "Q4"}.get(reprt_code, "Unknown")

    def parse(self, financials_raw: List[Dict], annual_shares_raw: List[Dict]) -> pd.DataFrame:
        processed_list = []
        for item in financials_raw:
            processed_list.append({
                "year": int(item["bsns_year"]),
                "quarter": self._report_code_to_quarter(item["reprt_code"]),
                "account_id": item.get("account_id"),
                "amount": self._to_numeric(item.get("thstrm_amount"))
            })
        for item in annual_shares_raw:
            # 보통주 정보만 필터링
            if item.get("se") == "보통주":
                processed_list.append({
                    "year": int(item["bsns_year"]),
                    "quarter": "Q4", # 사업보고서는 Q4 기준으로 저장
                    "account_id": "SharesOutstanding",
                    "amount": self._to_numeric(item.get("istc_totqy"))
                })
        df = pd.DataFrame(processed_list)
        return df.dropna(subset=['account_id']).drop_duplicates(
            subset=['year', 'quarter', 'account_id'], keep='last'
        ).reset_index(drop=True)

# --- 4. 분석기 ---
class CanslimAnalyzer:
    
    """
    재무 데이터 DataFrame을 입력받아 EPS를 계산하고, CAN SLIM의 'C'와 'A' 기준을
    분석하는 핵심 분석기 클래스.
    """

    """
    분석기 클래스를 초기화합니다.

    초기화 과정에서 `_calculate_eps` 메서드를 호출하여 원본 DataFrame에
    계산된 EPS 데이터를 자동으로 추가합니다.
    """
    def __init__(self, df: pd.DataFrame):
        self.df = self._calculate_eps(df)
        
        

    def _calculate_eps(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        순이익과 발행주식수 데이터를 사용하여 분기별 및 연간 EPS(주당순이익)를 계산합니다.

        [핵심 로직]
        1. 연간 사업보고서(Q4)에만 있는 발행주식수 정보를 이전 분기들(Q1, Q2, Q3)에 채워넣어(ffill)
        모든 분기에서 EPS를 계산할 수 있도록 합니다.
        2. '지배주주순이익 / 보통주 발행주식수' 공식으로 EPS를 계산합니다.
        3. 계산된 EPS 데이터를 원본 DataFrame에 새로운 행으로 추가하여 반환합니다.
        """
    
        pivot_df = df.pivot_table(index=['year', 'quarter'], columns='account_id', values='amount', aggfunc='first').reset_index()
        if AccountIDs.NET_INCOME not in pivot_df.columns:
            return df

        # [핵심 수정] 연간 주식 수를 모든 분기에 적용 (Forward Fill)
        if "SharesOutstanding" in pivot_df.columns:
            pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
        else:
            return df # 주식 수 정보가 없으면 EPS 계산 불가

        pivot_df["EPS"] = pivot_df.apply(
            lambda row: row[AccountIDs.NET_INCOME] / row['SharesOutstanding'] if row['SharesOutstanding'] > 0 else 0,
            axis=1
        )
        eps_df = pivot_df[['year', 'quarter', 'EPS']].dropna().rename(columns={'EPS': 'amount'})
        eps_df['account_id'] = 'EPS'
        return pd.concat([df, eps_df], ignore_index=True)
    

    def get_eps_data(self, period: str = 'all') -> pd.DataFrame:
        eps_df = self.df[self.df["account_id"] == "EPS"].sort_values(by=["year", "quarter"])
        if period == 'annual':
            return eps_df[eps_df["quarter"] == "Q4"].reset_index(drop=True)
        return eps_df.reset_index(drop=True)
    

    def calculate_yoy_growth(self, eps_data: pd.DataFrame) -> Optional[float]:
        """
        가장 최근 분기의 EPS를 전년 동기 EPS와 비교하여 YoY(전년 동기 대비) 성장률을 계산합니다.
        CAN SLIM의 'C' 기준을 검증하는 데 사용됩니다.
        """
    
        if len(eps_data) < 2: return None
        latest_q = eps_data.iloc[-1]
        prev_year_q = eps_data[(eps_data["year"] == latest_q["year"] - 1) & (eps_data["quarter"] == latest_q["quarter"])]
        if prev_year_q.empty: return None
        latest_eps, previous_eps = latest_q["amount"], prev_year_q.iloc[0]["amount"]
        if previous_eps <= 0: return None
        return ((latest_eps / previous_eps) - 1) * 100

    def calculate_annual_growth_rates(self, annual_eps_data: pd.DataFrame, num_years: int) -> Optional[pd.Series]:
        if len(annual_eps_data) < num_years: return None
        recent_years_eps = annual_eps_data.tail(num_years)
        return recent_years_eps["amount"].pct_change().dropna() * 100

    
    def check_calculate_yoy_growth(self, min_growth_rate: float = 25.0) -> Dict:
        """
        CAN SLIM 'C' 기준(최근 분기 EPS 성장률)의 통과 여부를 검증합니다.
        내부적으로 `calculate_yoy_growth`를 호출하여 얻은 성장률이 `min_growth_rate` 이상인지 확인합니다.
        """
        eps_data = self.get_eps_data()
        growth_rate = self.calculate_yoy_growth(eps_data)
        if growth_rate is None: return {"pass": False, "reason": "성장률 계산 불가"}
        return {"pass": growth_rate >= min_growth_rate, "growth_rate": f"{growth_rate:.2f}%"}
    
        eps_data = self.get_eps_data()
        growth_rate = self.calculate_yoy_growth(eps_data)
        if growth_rate is None: return {"pass": False, "reason": "성장률 계산 불가"}
        return {"pass": growth_rate >= min_growth_rate, "growth_rate": f"{growth_rate:.2f}%"}

       
    def check_annual_growth_rates(self, num_years: int = 3, min_growth_rate: float = 25.0) -> Dict:
        """
        3년 연간 EPS 성장률을 계산하고, CAN SLIM의 'A' 기준을 검증합니다.
        """
        annual_eps_data = self.get_eps_data('annual')
        if len(annual_eps_data) < num_years: return {"pass": False, "reason": f"{num_years}년치 연간 데이터 부족"}
        
        recent_years_eps = annual_eps_data.tail(num_years)
        if not all(recent_years_eps["amount"].diff().dropna() > 0):
            return {"pass": False, "reason": "EPS 비지속적 증가", "data": recent_years_eps.to_dict('records')}
            
        growth_rates = self.calculate_annual_growth_rates(recent_years_eps, num_years)
        if growth_rates is None or not all(growth_rates >= min_growth_rate):
            return {"pass": False, "reason": "최소 성장률 미달", "data": growth_rates.tolist() if growth_rates is not None else []}

        return {"pass": True, "reason": "기준 충족", "data": growth_rates.tolist()}

    def calculate_per(self, current_price: float) -> Optional[float]:
        annual_eps_data = self.get_eps_data('annual')
        if annual_eps_data.empty: return None
        latest_annual_eps = annual_eps_data.iloc[-1]['amount']
        if latest_annual_eps <= 0: return None
        return current_price / latest_annual_eps
# --- 5. 메인 실행 로직 ---
if __name__ == "__main__":
    client = DartApiClient(DART_API_KEY)
    parser = FinancialDataParser()
    
    target_corp = "00126380" # 삼성전자
    current_year = datetime.now().year
    years_to_fetch = range(current_year - 4, current_year)
    
    print(f"--- {target_corp} 재무 데이터 수집 시작 ({min(years_to_fetch)}~{max(years_to_fetch)}) ---")
    all_financials_raw, all_annual_shares_raw = [], []
    for year in years_to_fetch:
        # 1. 모든 분기의 재무제표 수집
        for reprt_code in ["11013", "11012", "11014", "11011"]:
            financials = client.get_financial_statements(target_corp, year, reprt_code)
            if financials:
                all_financials_raw.extend(financials)
        
        # 2. 연간 사업보고서의 주식 총수만 수집
        shares = client.get_annual_share_info(target_corp, year)
        if shares:
            # 데이터 보강
            for share_item in shares:
                share_item['bsns_year'] = str(year)
            all_annual_shares_raw.extend(shares)
            
    if all_financials_raw:
        master_df = parser.parse(all_financials_raw, all_annual_shares_raw)
        analyzer = CanslimAnalyzer(master_df)

        print("\n--- 최종 분석용 DataFrame (핵심 ID만 필터링) ---")
        core_ids = ['EPS', AccountIDs.NET_INCOME, 'SharesOutstanding']
        # quarter를 기준으로 정렬하여 보기 쉽게 출력
        print(analyzer.df[analyzer.df['account_id'].isin(core_ids)].sort_values(by=['year','quarter']))
        
        # ... (이하 CAN SLIM 분석 및 출력 로직은 이전과 동일)
        result_c = analyzer.check_calculate_yoy_growth()
        print(f"\n[C] 최근 분기 EPS 성장률: {'\033[92mPASS\033[0m' if result_c['pass'] else '\033[91mFAIL\033[0m'}")
        print(f"   ㄴ Details: {result_c}")
        
        result_a = analyzer.check_annual_growth_rates()
        print(f"\n[A] 3년 연간 EPS 성장률: {'\033[92mPASS\033[0m' if result_a['pass'] else '\033[91mFAIL\033[0m'}")
        print(f"   ㄴ Details: {result_a}")
    else:
        print("데이터 수집에 실패했습니다.")