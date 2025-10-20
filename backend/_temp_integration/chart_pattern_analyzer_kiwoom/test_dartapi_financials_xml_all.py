
import pandas as pd
import os
import sys
import time
import requests
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from tqdm import tqdm
import zipfile
import io
import xml.etree.ElementTree as ET

def setup_korean_font():
    """
    시스템에 설치된 한글 폰트를 자동으로 탐지하고 설정합니다.
    """
    try:
        import os
        os.environ['MPLBACKEND'] = 'Agg'
        font_paths_to_try = [
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
        ]
        for font_path in font_paths_to_try:
            if os.path.exists(font_path):
                try:
                    fm.fontManager.addfont(font_path)
                    font_name = font_path.split('/')[-1].split('.')[0]
                    plt.rc('font', family=font_name)
                    print(f"✅ 한글 폰트 등록 및 설정 완료: {font_name}")
                    return True
                except Exception:
                    continue
        plt.rc('font', family='DejaVu Sans')
        print("ℹ️ 한글 폰트를 찾을 수 없어 영문 폰트로 대체합니다.")
        return False
    except Exception:
        plt.rc('font', family='DejaVu Sans')
        return False

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from kiwoom_data_loader import KiwoomDataLoader

DART_API_KEY = "2cae1c66f8f4557528070d84877c183c0cb435cf"

class AccountIDs:
    NET_INCOME = "ifrs-full_ProfitLossAttributableToOwnersOfParent"

FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000, 
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}

class DartApiClient:
    BASE_URL = "https://opendart.fss.or.kr/api"
    def __init__(self, api_key: str):
        if not api_key or "YOUR_API_KEY_HERE" in api_key:
            raise ValueError("Open DART API 키가 설정되지 않았습니다.")
        self.api_key = api_key
    def _request_api(self, endpoint: str, params: Dict) -> Optional[List[Dict]]:
        url = f"{self.BASE_URL}/{endpoint}"
        final_params = {"crtfc_key": self.api_key, **params}
        try:
            response = requests.get(url, params=final_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "000":
                if data.get("status") != "013":
                    pass
                return None
            return data.get("list", [])
        except Exception:
            return None
    def get_financial_statements(self, corp_code: str, year: int, reprt_code: str) -> Optional[List[Dict]]:
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
        return self._request_api("fnlttSinglAcntAll.json", params)
    def get_annual_share_info(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        return self._request_api("stockTotqySttus.json", params)

class FinancialDataParser:
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
            if item.get("se") == "보통주":
                processed_list.append({
                    "year": int(item["bsns_year"]),
                    "quarter": "Q4",
                    "account_id": "SharesOutstanding",
                    "amount": self._to_numeric(item.get("istc_totqy"))
                })
        df = pd.DataFrame(processed_list)
        return df.dropna(subset=['account_id']).drop_duplicates(
            subset=['year', 'quarter', 'account_id'], keep='last'
        ).reset_index(drop=True)

class EpsAnalysisEngine:
    def __init__(self):
        self.kiwoom_loader = KiwoomDataLoader()
        self.dart_client = DartApiClient(DART_API_KEY)
        self.parser = FinancialDataParser()
        self.corp_map = self._get_corp_map()
        self.current_year = datetime.now().year

    def _format_stock_code(self, code_str: str) -> Optional[str]:
        if code_str and code_str.isdigit():
            return code_str.zfill(6)
        return None

    def _get_corp_map(self) -> Dict[str, str]:
        """
        종목코드-기업코드 매핑 생성 (CSV 파일 우선 사용, API 직접 호출 방식)
        """
        map_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dart_corp_list_from_xml.csv')

        if os.path.exists(map_file):
            try:
                print(f"📁 로컬 CSV 파일 발견: {map_file}")
                df = pd.read_csv(map_file, dtype={'stock_code': str, 'corp_code': str})
                corp_map = pd.Series(df.corp_code.values, index=df.stock_code).to_dict()
                print(f"✅ 로컬 CSV에서 {len(corp_map)}개 기업 매핑 정보 로드 완료.")
                return corp_map
            except Exception as e:
                print(f"⚠️ CSV 파일 읽기 실패: {e}")

        print("📡 DART API(corpCode.xml)로 기업 목록 직접 조회 시도 중...")
        corp_code_url = f"https://opendart.fss.or.kr/api/corpCode.xml?crtfc_key={self.dart_client.api_key}"

        try:
            response = requests.get(corp_code_url)
            response.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                with z.open('CORPCODE.xml') as f:
                    tree = ET.parse(f)
                    root = tree.getroot()

            corp_list_from_xml = []
            for item in root.findall('./list'):
                corp_code = item.find('corp_code').text
                corp_name = item.find('corp_name').text
                stock_code = item.find('stock_code').text
                modify_date = item.find('modify_date').text
                
                if stock_code and stock_code.strip():
                    corp_list_from_xml.append({
                        'corp_code': corp_code,
                        'corp_name': corp_name,
                        'stock_code': stock_code.strip(),
                        'modify_date': modify_date
                    })
            
            df = pd.DataFrame(corp_list_from_xml)
            df.to_csv(map_file, index=False, encoding='utf-8-sig')
            print(f"✅ 매핑 정보를 '{map_file}'에 저장했습니다.")

            corp_map = pd.Series(df.corp_code.values, index=df.stock_code).to_dict()
            print(f"✅ DART API(XML)를 통해 {len(corp_map)}개 유효 상장사 매핑 정보 획득.")
            return corp_map

        except Exception as e:
            print(f"❌ DART API(XML) 호출 실패: {e}")
            raise FileNotFoundError(f"DART API(XML) 호출 실패 및 CSV 파일도 사용할 수 없습니다: {map_file}")

    def _call_kiwoom_api(self, api_id: str, data: Dict, endpoint: str) -> Dict:
        token = self.kiwoom_loader._get_token()
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

    def get_all_kiwoom_stocks(self) -> List[Dict]:
        print("Kiwoom API: 전체 종목 정보 수집 중...")
        all_stocks = []
        for market_tp in ['0', '10']:
            res = self._call_kiwoom_api('ka10099', {'mrkt_tp': market_tp}, '/api/dostk/stkinfo')
            if res and 'list' in res:
                all_stocks.extend(res['list'])
        print(f"✅ Kiwoom API를 통해 {len(all_stocks)}개 종목 정보 획득.")
        return all_stocks

    def _apply_filter_zero(self, all_stocks: List[Dict]) -> List[Dict]:
        print("\n--- [Filter Zero] 필터링 시작 ---")
        initial_count = len(all_stocks)
        filtered_stocks = []
        for stock in tqdm(all_stocks, desc="필터 제로 적용 중"):
            name = stock.get('name', '')
            state_info = stock.get('state', '')
            order_warning = stock.get('orderWarning', '0')
            if any(keyword in name for keyword in FILTER_ZERO_CONFIG["EXCLUDE_KEYWORDS"]): continue
            if any(keyword in state_info for keyword in ["관리종목", "거래정지", "증거금100"]): continue
            if order_warning != '0': continue
            try:
                last_price = int(stock.get('lastPrice', '0'))
                list_count = int(stock.get('listCount', '0'))
                market_cap = (last_price * list_count) / 100_000_000
                if market_cap < FILTER_ZERO_CONFIG["MIN_MARKET_CAP_KRW"]:
                    continue
            except (ValueError, TypeError): continue
            filtered_stocks.append(stock)
        final_count = len(filtered_stocks)
        print(f"✅ 필터링 완료: {initial_count}개 종목 -> {final_count}개 종목 ({initial_count - final_count}개 제외)")
        return filtered_stocks

    def fetch_financial_data(self, corp_code: str) -> Optional[pd.DataFrame]:
        try:
            all_financials_raw, all_annual_shares_raw = [], []
            for year in range(self.current_year - 4, self.current_year):
                for reprt_code in ["11013", "11012", "11014", "11011"]:
                    financials = self.dart_client.get_financial_statements(corp_code, year, reprt_code)
                    if financials: all_financials_raw.extend(financials)
                shares = self.dart_client.get_annual_share_info(corp_code, year)
                if shares:
                    for share_item in shares: share_item['bsns_year'] = str(year)
                    all_annual_shares_raw.extend(shares)
            if not all_financials_raw: return None
            return self.parser.parse(all_financials_raw, all_annual_shares_raw)
        except Exception: return None

    def _calculate_eps(self, df: pd.DataFrame, current_list_count: int) -> Optional[pd.DataFrame]:
        pivot_df = df.pivot_table(index=['year', 'quarter'], columns='account_id', values='amount', aggfunc='first').reset_index()
        if AccountIDs.NET_INCOME not in pivot_df.columns: return None
        if "SharesOutstanding" in pivot_df.columns:
            pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
        else:
            pivot_df['SharesOutstanding'] = current_list_count
        pivot_df.loc[pivot_df['year'] == self.current_year, 'SharesOutstanding'] = current_list_count
        pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(current_list_count)
        if pivot_df['SharesOutstanding'].isnull().all(): return None
        pivot_df["EPS"] = pivot_df.apply(lambda row: row[AccountIDs.NET_INCOME] / row['SharesOutstanding'] if row['SharesOutstanding'] > 0 else 0, axis=1)
        eps_df = pivot_df[['year', 'quarter', 'EPS']].dropna().rename(columns={'EPS': 'amount'})
        eps_df['account_id'] = 'EPS'
        return pd.concat([df, eps_df], ignore_index=True)
    
    def calculate_per(self, current_price: float, eps_df: pd.DataFrame) -> Optional[float]:
        if eps_df.empty: return None
        annual_eps_data = eps_df[(eps_df['account_id'] == 'EPS') & (eps_df['quarter'] == 'Q4')]
        if annual_eps_data.empty: return None
        latest_annual_eps = annual_eps_data.sort_values('year').iloc[-1]['amount']
        if latest_annual_eps <= 0: return None
        return round(current_price / latest_annual_eps, 2)

    def analyze_financial_grade(self, eps_df: pd.DataFrame) -> Tuple[str, float, float]:
        annual_eps = eps_df[eps_df['quarter'] == 'Q4'].set_index('year')['amount']
        quarterly_eps = eps_df[eps_df['quarter'] != 'Q4'].set_index(['year', 'quarter'])['amount']
        yoy_growth = 0.0
        if not quarterly_eps.empty:
            latest_q_idx = quarterly_eps.index[-1]
            prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1])
            if prev_year_q_idx in quarterly_eps.index and quarterly_eps[prev_year_q_idx] != 0:
                yoy_growth = (quarterly_eps[latest_q_idx] / quarterly_eps[prev_year_q_idx] - 1) * 100
        annual_growth_rates, avg_annual_growth = [], 0.0
        if len(annual_eps) >= 4:
            for i in range(1, 4):
                prev_year_eps, curr_year_eps = annual_eps.iloc[-(i+1)], annual_eps.iloc[-i]
                if prev_year_eps > 0:
                    annual_growth_rates.append((curr_year_eps / prev_year_eps - 1) * 100)
            if len(annual_growth_rates) == 3:
                avg_annual_growth = sum(annual_growth_rates) / len(annual_growth_rates)
        has_negative_eps = False
        if len(annual_eps) >= 3 and any(eps <= 0 for eps in annual_eps.tail(3)):
            has_negative_eps = True
        is_strict_a = len(annual_growth_rates) == 3 and not has_negative_eps and avg_annual_growth >= 25
        is_strict_c = yoy_growth >= 25
        if is_strict_a and is_strict_c:
            return 'Strict', yoy_growth, avg_annual_growth
        is_turnaround = not quarterly_eps.empty and quarterly_eps.iloc[-1] > 0 and (prev_year_q_idx in quarterly_eps.index and quarterly_eps[prev_year_q_idx] < 0)
        is_loose_c = yoy_growth >= 0
        is_loose_a = len(annual_eps) >= 3 and (annual_eps.iloc[-1] > annual_eps.iloc[-2] > annual_eps.iloc[-3])
        if is_turnaround or is_loose_c or is_loose_a:
            return 'Loose', yoy_growth, avg_annual_growth
        return 'Fail', yoy_growth, avg_annual_growth

    def visualize_results(self, results_df: pd.DataFrame):
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 그래프 파일 저장 디렉토리: {script_dir}")
        setup_korean_font()
        plt.rcParams['axes.unicode_minus'] = False
        grade_counts = results_df['financial_grade'].value_counts().sort_index()
        plt.figure(figsize=(8, 6))
        bars = plt.bar(grade_counts.index, grade_counts.values, color=['#FF6B6B', '#4ECDC4'])
        plt.title(f'재무 등급 분포 (총 {len(results_df)}개 기업)', fontsize=16, fontweight='bold')
        plt.ylabel('기업 수', fontsize=12)
        plt.xticks(fontsize=12)
        for bar in bars:
            yval = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2.0, yval, int(yval), va='bottom', ha='center', fontsize=12, fontweight='bold')
        plt.savefig(f'{script_dir}/grade_distribution.png', dpi=800, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/grade_distribution.png' 생성 완료.")
        yoy_growth_clipped = results_df['eps_growth_yoy'].clip(-100, 300)
        annual_growth_clipped = results_df['eps_annual_growth_avg_3y'].clip(-100, 300)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        ax1.hist(yoy_growth_clipped, bins=40, color='#4ECDC4', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax1.set_title('최근 분기 EPS 성장률(YoY) 분포', fontsize=15, fontweight='bold')
        ax1.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax1.legend(fontsize=11)
        ax2.hist(annual_growth_clipped, bins=40, color='#FF6B6B', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.set_title('3년 연평균 EPS 성장률 분포', fontsize=15, fontweight='bold')
        ax2.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax2.legend(fontsize=11)
        plt.tight_layout()
        plt.savefig(f'{script_dir}/growth_histograms.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/growth_histograms.png' 생성 완료.")

    def run_full_analysis(self):
        print("="*80 + "\n🚀 전체 상장 기업 CAN SLIM 재무 분석 시작" + "\n" + "="*80)
        all_stocks_raw = self.get_all_kiwoom_stocks()
        if not all_stocks_raw:
            print("❌ Kiwoom API를 통해 종목 정보를 가져오지 못했습니다.")
            return
        filtered_stocks = self._apply_filter_zero(all_stocks_raw)
        if not filtered_stocks:
            print("❌ 필터링 후 분석할 종목이 없습니다.")
            return
        print(f"\n--- 총 {len(filtered_stocks)}개 필터링된 종목 DART 분석 시작 ---")
        results = []
        for stock in tqdm(filtered_stocks, desc="필터링된 종목 EPS 분석 중"):
            stock_code, stock_name = stock.get('code'), stock.get('name')
            list_count, last_price = int(stock.get('listCount', 0)), int(stock.get('lastPrice', 0))
            if not stock_code or list_count == 0: continue
            corp_code = self.corp_map.get(stock_code)
            if not corp_code: continue
            financial_df = self.fetch_financial_data(corp_code)
            if financial_df is None:
                print(f"❌ DART API 재무 데이터 수집 실패: corp_code={corp_code}, stock_code={stock_code}, name={stock_name}")
                continue
            eps_df = self._calculate_eps(financial_df, list_count)
            if eps_df is None: continue
            eps_only = eps_df[eps_df['account_id'] == 'EPS']
            if eps_only.empty: continue
            grade, yoy_g, annual_g = self.analyze_financial_grade(eps_only)
            per = self.calculate_per(last_price, eps_df)
            results.append({'stock_code': stock_code, 'name': stock_name, 'financial_grade': grade, 'eps_growth_yoy': round(yoy_g, 2), 'eps_annual_growth_avg_3y': round(annual_g, 2), 'PER': per})
        if results:
            result_df = pd.DataFrame(results)
            print("\n" + "="*80 + "\n📈 최종 분석 결과" + "\n" + "="*80)
            strict_df = result_df[result_df['financial_grade'] == 'Strict']
            loose_df = result_df[result_df['financial_grade'] == 'Loose']
            if not strict_df.empty: print(f"\n--- 'Strict' 등급 통과 기업 ({len(strict_df)}개) ---\n{strict_df.to_string(index=False)}")
            if not loose_df.empty: print(f"\n--- 'Loose' 등급 통과 기업 ({len(loose_df)}개) ---\n{loose_df.to_string(index=False)}")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_filename = os.path.join(script_dir, f"dart_financial_analysis_results_{datetime.now().strftime('%Y%m%d')}.csv")
            result_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 전체 분석 결과를 '{os.path.basename(output_filename)}' 파일로 저장했습니다.")
            self.visualize_results(result_df)
        else:
            print("\n⚠️ 분석 기준을 통과한 기업이 없습니다.")
        print("\n" + "="*80 + "\n🎉 전체 분석 및 시각화 완료!" + "\n" + "="*80)

if __name__ == '__main__':
    analyzer = EpsAnalysisEngine()
    analyzer.run_full_analysis()
