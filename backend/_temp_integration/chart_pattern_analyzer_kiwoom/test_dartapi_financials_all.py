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

def setup_korean_font():
    """
    시스템에 설치된 한글 폰트를 자동으로 탐지하고 설정합니다.
    """
    try:
        # 환경 변수 설정 (matplotlib 백엔드 강제 설정)
        import os
        os.environ['MPLBACKEND'] = 'Agg'

        # 1. 직접 폰트 파일 등록 (가장 확실한 방법)
        font_paths_to_try = [
            '/usr/share/fonts/truetype/nanum/NanumGothic.ttf',
            '/usr/share/fonts/truetype/nanum/NanumSquareRoundB.ttf',
            '/usr/share/fonts/truetype/unfonts-core/UnDinaruBold.ttf',
            '/usr/share/fonts/opentype/noto/NotoSerifCJK-Bold.ttc',
            '/usr/share/fonts/truetype/baekmuk/batang.ttf',
        ]

        for font_path in font_paths_to_try:
            if os.path.exists(font_path):
                try:
                    fm.fontManager.addfont(font_path)
                    font_name = font_path.split('/')[-1].split('.')[0]
                    plt.rc('font', family=font_name)
                    print(f"✅ 한글 폰트 등록 및 설정 완료: {font_name}")
                    return True
                except Exception as e:
                    print(f"⚠️ 폰트 등록 실패 ({font_path}): {e}")
                    continue

        # 2. 시스템에 이미 설치된 폰트 검색
        try:
            import subprocess
            result = subprocess.run(['fc-list', ':lang=ko'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0 and result.stdout:
                font_lines = result.stdout.strip().split('\n')
                korean_fonts = [line.split(':')[0] for line in font_lines if line.strip()]
                if korean_fonts:
                    font_path = korean_fonts[0]
                    font_name = font_path.split('/')[-1].split('.')[0]
                    plt.rc('font', family=font_name)
                    print(f"✅ 시스템 한글 폰트 설정 완료: {font_name}")
                    return True
        except:
            pass

        # 3. matplotlib에서 폰트 직접 검색
        font_list = fm.findSystemFonts(fontpaths=None, fontext='ttf')
        korean_fonts = [f for f in font_list if any(keyword in f.lower() for keyword in [
            'nanum', 'noto', 'malgun', 'unfonts', 'baekmuk', 'gulim', 'batang', 'dotum',
            'han', 'un', 'baekmuk', 'sans', 'serif', 'square'
        ])]

        if korean_fonts:
            font_name = korean_fonts[0].split('/')[-1].split('.')[0]
            plt.rc('font', family=font_name)
            print(f"✅ 검색된 한글 폰트 설정 완료: {font_name}")
            return True

        # 4. 최후의 대안: 영문 폰트로 설정
        plt.rc('font', family='DejaVu Sans')
        print("ℹ️ 한글 폰트를 찾을 수 없어 영문 폰트로 대체합니다.")
        return False

    except Exception as e:
        print(f"⚠️ 폰트 설정 중 오류 발생: {e}")
        plt.rc('font', family='DejaVu Sans')
        return False

# --- 환경 설정 및 인증 로더 임포트 ---
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)
from kiwoom_data_loader import KiwoomDataLoader

# --- DART API 키 설정 ---
DART_API_KEY = "2cae1c66f8f4557528070d84877c183c0cb435cf"

# --- 계정 과목 ID (통일) ---
class AccountIDs:
    NET_INCOME = "ifrs-full_ProfitLossAttributableToOwnersOfParent"  # 지배기업 소유주지분 순이익

# --- 필터 제로 설정 (Configuration) ---
FILTER_ZERO_CONFIG = {
    "MIN_MARKET_CAP_KRW": 1000, 
    "EXCLUDE_KEYWORDS": [
        "관리종목", "투자주의", "투자경고", "투자위험", "거래정지", "증거금100",
        "ETN", "ETF", "TIGER", "KODEX", "ARIRANG", "KINDEX", "HANARO",
        "스팩", "선물", "인버스", "리츠"
    ]
}

# --- DART REST API 클라이언트 ---
class DartApiClient:
    """Open DART API와의 모든 통신을 담당 (REST API 직접 호출)"""
    BASE_URL = "https://opendart.fss.or.kr/api"

    def __init__(self, api_key: str):
        if not api_key or "YOUR_API_KEY_HERE" in api_key:
            raise ValueError("Open DART API 키가 설정되지 않았습니다.")
        self.api_key = api_key

    def _request_api(self, endpoint: str, params: Dict) -> Optional[List[Dict]]:
        """DART API REST 엔드포인트 직접 호출"""
        url = f"{self.BASE_URL}/{endpoint}"
        final_params = {"crtfc_key": self.api_key, **params}
        try:
            response = requests.get(url, params=final_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            if data.get("status") != "000":
                if data.get("status") != "013":  # 013: 데이터 없음 (정상)
                    pass  # 조용히 넘어감
                return None
            return data.get("list", [])
        except Exception:
            return None

    def get_financial_statements(self, corp_code: str, year: int, reprt_code: str) -> Optional[List[Dict]]:
        """연결재무제표(CFS)를 명시적으로 요청"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": reprt_code, "fs_div": "CFS"}
        return self._request_api("fnlttSinglAcntAll.json", params)

    def get_annual_share_info(self, corp_code: str, year: int) -> Optional[List[Dict]]:
        """연간 사업보고서(11011)의 주식 총수 조회"""
        params = {"corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"}
        return self._request_api("stockTotqySttus.json", params)

# --- 데이터 파서 ---
class FinancialDataParser:
    """DART API 원본 데이터를 분석 가능한 DataFrame으로 변환"""
    def _to_numeric(self, value: str) -> int:
        if not isinstance(value, str) or not value: return 0
        try: return int(value.replace(",", ""))
        except ValueError: return 0

    def _report_code_to_quarter(self, reprt_code: str) -> str:
        return {"11013": "Q1", "11012": "Q2", "11014": "Q3", "11011": "Q4"}.get(reprt_code, "Unknown")

    def parse(self, financials_raw: List[Dict], annual_shares_raw: List[Dict]) -> pd.DataFrame:
        """재무제표와 주식총수 데이터를 통합 DataFrame으로 변환"""
        processed_list = []
        
        # 재무제표 데이터 처리
        for item in financials_raw:
            processed_list.append({
                "year": int(item["bsns_year"]),
                "quarter": self._report_code_to_quarter(item["reprt_code"]),
                "account_id": item.get("account_id"),
                "amount": self._to_numeric(item.get("thstrm_amount"))
            })
        
        # 주식총수 데이터 처리 (보통주만)
        for item in annual_shares_raw:
            if item.get("se") == "보통주":
                processed_list.append({
                    "year": int(item["bsns_year"]),
                    "quarter": "Q4",  # 사업보고서는 Q4 기준
                    "account_id": "SharesOutstanding",
                    "amount": self._to_numeric(item.get("istc_totqy"))  # 유통주식수
                })
        
        df = pd.DataFrame(processed_list)
        return df.dropna(subset=['account_id']).drop_duplicates(
            subset=['year', 'quarter', 'account_id'], keep='last'
        ).reset_index(drop=True)

# --- CAN SLIM 분석 엔진 ---
class EpsAnalysisEngine:
    """
    DART와 Kiwoom API 데이터를 결합하여 전체 상장 기업의 CAN SLIM 분석을 수행하는 클래스
    """
    def __init__(self):
        self.kiwoom_loader = KiwoomDataLoader()
        self.dart_client = DartApiClient(DART_API_KEY)
        self.parser = FinancialDataParser()
        self.corp_map = self._get_corp_map()
        self.current_year = datetime.now().year

    def _format_stock_code(self, code_str: str) -> Optional[str]:
        """종목코드를 표준 6자리 숫자 형식으로 변환"""
        if code_str and code_str.isdigit():
            return code_str.zfill(6)
        return None

    def _get_corp_map(self) -> Dict[str, str]:
        """종목코드-기업코드 매핑 생성 (CSV 파일 우선 사용)"""
        map_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'dart_corp_list.csv')

        # 1. 먼저 로컬 CSV 파일 확인 (API 호출 없이 사용 가능)
        if os.path.exists(map_file):
            try:
                print(f"📁 로컬 CSV 파일 발견: {map_file}")
                df = pd.read_csv(map_file, dtype={'종목코드': str, '고유번호': str})
                corp_map = pd.Series(df.고유번호.values, index=df.종목코드).to_dict()
                print(f"✅ 로컬 CSV에서 {len(corp_map)}개 기업 매핑 정보 로드 완료.")
                return corp_map
            except Exception as e:
                print(f"⚠️ CSV 파일 읽기 실패: {e}")

        # 2. CSV 파일이 없거나 읽기 실패 시에만 DART API 시도
        print("📡 DART API로 기업 목록 조회 시도 중...")

        try:
            import dart_fss as dart
            dart.set_api_key(api_key=DART_API_KEY)

            print("DART API: 전체 기업 목록 실시간 조회 중...")
            corp_list = dart.get_corp_list()
            listed_corps = [corp for corp in corp_list if corp.stock_code]

            corp_map = {}
            for corp in listed_corps:
                formatted_code = self._format_stock_code(corp.stock_code)
                if formatted_code:
                    corp_map[formatted_code] = corp.corp_code

            print(f"✅ DART API를 통해 {len(corp_map)}개 유효 상장사 매핑 정보 획득.")

            # API 호출 성공 시 CSV 파일로 저장 (다음 사용을 위해)
            try:
                save_df = pd.DataFrame([
                    {'종목코드': code, '고유번호': corp_code}
                    for code, corp_code in corp_map.items()
                ])
                save_df.to_csv(map_file, index=False, encoding='utf-8-sig')
                print(f"✅ 매핑 정보를 '{map_file}'에 저장했습니다.")
            except Exception as e:
                print(f"⚠️ CSV 저장 실패: {e}")

            return corp_map

        except Exception as e:
            error_msg = str(e)
            if "사용한도를 초과" in error_msg or "OverQueryLimit" in error_msg:
                print("❌ DART API 사용 한도를 초과했습니다.")
                print("💡 해결 방법: 잠시 후 다시 시도하거나, 관리자에게 문의하세요.")
            else:
                print(f"❌ DART API 호출 실패: {error_msg}")

            if os.path.exists(map_file):
                print("📁 기존 CSV 파일을 사용합니다.")
                try:
                    df = pd.read_csv(map_file, dtype={'종목코드': str, '고유번호': str})
                    return pd.Series(df.고유번호.values, index=df.종목코드).to_dict()
                except Exception as e2:
                    print(f"❌ CSV 파일도 읽을 수 없습니다: {e2}")

            raise FileNotFoundError(
                f"DART API 호출 실패 및 CSV 파일도 사용할 수 없습니다. "
                f"먼저 'test_get_dart_corplist.py'를 실행하여 '{map_file}' 파일을 생성해주세요."
            )

    def _call_kiwoom_api(self, api_id: str, data: Dict, endpoint: str) -> Dict:
        """Kiwoom REST API 호출 래퍼"""
        token = self.kiwoom_loader._get_token()
        if not token: return None
        host = 'https://api.kiwoom.com'
        url = host + endpoint
        headers = {
            'Content-Type': 'application/json;charset=UTF-8',
            'authorization': f'Bearer {token}',
            'api-id': api_id
        }
        try:
            time.sleep(0.3)
            response = requests.post(url, headers=headers, json=data, timeout=20)
            if response.status_code == 200: return response.json()
            else: return None
        except Exception: return None

    def get_all_kiwoom_stocks(self) -> List[Dict]:
        """ka10099 API로 전체 종목 정보 수집 (원본 리스트 형태로 반환)"""
        print("Kiwoom API: 전체 종목 정보 수집 중...")
        all_stocks = []
        for market_tp in ['0', '10']:  # 0: 코스피, 10: 코스닥
            res = self._call_kiwoom_api('ka10099', {'mrkt_tp': market_tp}, '/api/dostk/stkinfo')
            if res and 'list' in res:
                all_stocks.extend(res['list'])
        print(f"✅ Kiwoom API를 통해 {len(all_stocks)}개 종목 정보 획득.")
        return all_stocks

    def _apply_filter_zero(self, all_stocks: List[Dict]) -> List[Dict]:
        """
        '필터 제로' 적용 - 분석 대상 종목을 대폭 압축
        
        검증된 market_sector_rs_calcurator_all_final.py의 로직 사용
        """
        print("\n--- [Filter Zero] 필터링 시작 ---")
        initial_count = len(all_stocks)
        filtered_stocks = []

        for stock in tqdm(all_stocks, desc="필터 제로 적용 중"):
            # 필터 1: 키워드 필터
            state_info = stock.get('state', '')
            audit_info = stock.get('auditInfo', '')
            # 필터 1: 키워드 필터 (수정된 버전)
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
                market_cap = (last_price * list_count) / 100_000_000  # 억원 단위
                if market_cap < FILTER_ZERO_CONFIG["MIN_MARKET_CAP_KRW"]:
                    continue
            except (ValueError, TypeError):
                continue

            # 모든 필터를 통과한 종목만 추가
            filtered_stocks.append(stock)

        final_count = len(filtered_stocks)
        print(f"✅ 필터링 완료: {initial_count}개 종목 -> {final_count}개 종목 ({initial_count - final_count}개 제외)")
        return filtered_stocks

    def fetch_financial_data(self, corp_code: str) -> Optional[pd.DataFrame]:
        """DART REST API를 직접 호출하여 재무제표 수집"""
        try:
            all_financials_raw = []
            all_annual_shares_raw = []
            
            for year in range(self.current_year - 4, self.current_year):
                # 모든 분기의 재무제표 수집
                for reprt_code in ["11013", "11012", "11014", "11011"]:
                    financials = self.dart_client.get_financial_statements(corp_code, year, reprt_code)
                    if financials:
                        all_financials_raw.extend(financials)
                
                # 연간 사업보고서의 주식 총수만 수집
                shares = self.dart_client.get_annual_share_info(corp_code, year)
                if shares:
                    for share_item in shares:
                        share_item['bsns_year'] = str(year)
                    all_annual_shares_raw.extend(shares)
            
            if not all_financials_raw:
                return None
            
            return self.parser.parse(all_financials_raw, all_annual_shares_raw)
        except Exception:
            return None

    def _calculate_eps(self, df: pd.DataFrame, current_list_count: int) -> Optional[pd.DataFrame]:
        """
        재무 데이터와 상장주식수를 결합하여 EPS 계산
        
        핵심 로직:
        1. 과거 연도(< current_year): DART 주식총수 사용
        2. 현재 연도(= current_year): Kiwoom 최신 상장주식수 사용
        3. 주식수 데이터 없는 경우: current_list_count 대체 사용
        """
        pivot_df = df.pivot_table(
            index=['year', 'quarter'],
            columns='account_id',
            values='amount',
            aggfunc='first'
        ).reset_index()
        
        if AccountIDs.NET_INCOME not in pivot_df.columns:
            return None

        # 주식수 컬럼 처리
        if "SharesOutstanding" in pivot_df.columns:
            # Forward Fill로 분기별 데이터 채움
            pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(method='ffill')
        else:
            # 주식수 정보가 없으면 현재 값으로 초기화
            pivot_df['SharesOutstanding'] = current_list_count

        # 현재 연도의 모든 분기는 최신 상장주식수 사용
        pivot_df.loc[pivot_df['year'] == self.current_year, 'SharesOutstanding'] = current_list_count

        # 여전히 주식수가 없는 행은 현재 값으로 대체
        pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(current_list_count)

        if pivot_df['SharesOutstanding'].isnull().all():
            return None

        # EPS 계산
        pivot_df["EPS"] = pivot_df.apply(
            lambda row: row[AccountIDs.NET_INCOME] / row['SharesOutstanding'] 
            if row['SharesOutstanding'] > 0 else 0,
            axis=1
        )
        
        eps_df = pivot_df[['year', 'quarter', 'EPS']].dropna().rename(columns={'EPS': 'amount'})
        eps_df['account_id'] = 'EPS'
        return pd.concat([df, eps_df], ignore_index=True)
    
    def calculate_per(self, current_price: float, eps_df: pd.DataFrame) -> Optional[float]:
        """가장 최근의 연간 EPS를 기준으로 PER를 계산합니다."""
        if eps_df.empty: return None
        
        # 연간(Q4) EPS 데이터만 필터링
        annual_eps_data = eps_df[(eps_df['account_id'] == 'EPS') & (eps_df['quarter'] == 'Q4')]
        if annual_eps_data.empty: return None
        
        # 가장 최근 연도의 EPS 값
        latest_annual_eps = annual_eps_data.sort_values('year').iloc[-1]['amount']
        
        # EPS가 0보다 클 때만 유효한 PER를 계산
        if latest_annual_eps <= 0: return None
        
        return round(current_price / latest_annual_eps, 2)

    def analyze_financial_grade(self, eps_df: pd.DataFrame) -> Tuple[str, float, float]:
        """
        EPS 데이터를 바탕으로 'Strict', 'Loose', 'Fail'의 재무 등급을 판정합니다.

        Args:
            eps_df (pd.DataFrame): 'EPS' account_id를 가진 데이터프레임.

        Returns:
            Tuple[str, float, float]: (재무 등급, 최근분기 YoY 성장률, 3년 연평균 성장률)
        """
        
        # --- 1. 데이터 준비 ---
        # 연간 EPS와 분기 EPS 데이터를 각각 분리하여 계산을 준비합.
        annual_eps = eps_df[eps_df['quarter'] == 'Q4'].set_index('year')['amount']
        quarterly_eps = eps_df[eps_df['quarter'] != 'Q4'].set_index(['year', 'quarter'])['amount']

        # --- 2. 최근 분기 YoY 성장률 계산 (CAN SLIM 'C' 기준) ---
        # 계절성을 제거하고 실질적인 분기성장을 확인하기 위해 전년 동기(YoY)와 비교
        yoy_growth = 0.0
        if not quarterly_eps.empty:
            latest_q_idx = quarterly_eps.index[-1]   # 가장 최근 분기 인덱스 (예: (2025, 'Q2'))
            prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1]) # 비교할 전년 동분기 인덱스 (예: (2024, 'Q2'))
            
            # 전년 동분기 데이터가 존재하고 0이 아닐 때만 성장률을 계산합니다.
            if prev_year_q_idx in quarterly_eps.index and quarterly_eps[prev_year_q_idx] != 0:
                yoy_growth = (quarterly_eps[latest_q_idx] / quarterly_eps[prev_year_q_idx] - 1) * 100

        # --- 3. 최근 3년간 연간 성장률 계산 (CAN SLIM 'A' 기준) ---
        # 꾸준한 연간 성장 실적을 확인하기 위해 최근 3개년의 성장률을 계산합니다.
        annual_growth_rates = []
        avg_annual_growth = 0.0
        if len(annual_eps) >= 4:  # 최소 4개년 데이터가 있어야 3년간의 성장률 계산이 가능
            for i in range(1, 4):  # i = 1, 2, 3 (1년전, 2년전, 3년전 성장률)
                prev_year_eps = annual_eps.iloc[-(i+1)]  # N년 전 EPS
                curr_year_eps = annual_eps.iloc[-i]   # (N-1)년 전 EPS
                if prev_year_eps > 0:  # 분모가 양수일 때만 의미 있는 성장률 계산
                    growth = (curr_year_eps / prev_year_eps - 1) * 100
                    annual_growth_rates.append(growth)
            
            # 3년간의 성장률이 모두 계산되었을 경우에만 평균을 구합
            if len(annual_growth_rates) == 3:
                avg_annual_growth = sum(annual_growth_rates) / len(annual_growth_rates)

        # --- 4. 'Strict' 등급 판정 ---
        # 안정성과 성장성을 겸비한 최상위 기업을 선별
        
        # [판정 1] 안정성: 최근 3년간 적자(EPS<=0) 이력이 없어야 합니다.
        has_negative_eps = False
        if len(annual_eps) >= 3:
            # 최근 3년의 연간 EPS가 하나라도 0 이하인 경우
            if any(eps <= 0 for eps in annual_eps.tail(3)):
                has_negative_eps = True

        # [판정 2] 연간 성장성 (A): 3년 평균 성장률이 25% 이상이어야 합니다.
        is_strict_a = (len(annual_growth_rates) == 3 and 
                       not has_negative_eps and 
                       avg_annual_growth >= 25)

        # [판정 3] 분기 성장성 (C): 최근 분기 YoY 성장률이 25% 이상이어야 합니다.
        is_strict_c = yoy_growth >= 25
        
        # 모든 엄격한 기준을 통과하면 'Strict' 등급을 부여합니다.
        if is_strict_a and is_strict_c:
            return 'Strict', yoy_growth, avg_annual_growth

       # --- 5. 'Loose' 등급 판정 ---
        # 성장 잠재력이 있는 기업(턴어라운드 포함)을 폭넓게 선별합니다.
        
        # [판정 1] 흑자 전환: 최근 분기 EPS는 흑자(+)인데, 전년 동기는 적자(-)였던 '턴어라운드' 기업
        is_turnaround = not quarterly_eps.empty and quarterly_eps.iloc[-1] > 0 and (
            prev_year_q_idx in quarterly_eps.index and quarterly_eps[prev_year_q_idx] < 0
        )
        
        # [판정 2] 최소 분기 성장: 최근 분기 실적이 최소한 역성장은 아닌 기업
        is_loose_c = yoy_growth >= 0
        
        # [판정 3] 최소 연간 성장: 최근 3년간 EPS가 꾸준히 증가하는 추세를 보이는 기업
        is_loose_a = len(annual_eps) >= 3 and (
            annual_eps.iloc[-1] > annual_eps.iloc[-2] > annual_eps.iloc[-3]
        )
        # 느슨한 기준 중 하나라도 만족하면 'Loose' 등급을 부여합니다.
        if is_turnaround or is_loose_c or is_loose_a:
            return 'Loose', yoy_growth, avg_annual_growth

        return 'Fail', yoy_growth, avg_annual_growth

    def visualize_results(self, results_df: pd.DataFrame):
        """
        분석 결과를 바탕으로 3종의 시각화 차트를 생성합니다.
        """
        # 스크립트 디렉토리 설정
        script_dir = os.path.dirname(os.path.abspath(__file__))
        print(f"📁 그래프 파일 저장 디렉토리: {script_dir}")

        # --- 한글 폰트 설정 ---
        font_success = setup_korean_font()
        plt.rcParams['axes.unicode_minus'] = False

        # --- 1. 시각화 1: 재무 등급 분포 ---
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

        # --- 2. 시각화 2: 성장률 분포 히스토그램 ---
        yoy_growth_clipped = results_df['eps_growth_yoy'].clip(-100, 300)
        annual_growth_clipped = results_df['eps_annual_growth_avg_3y'].clip(-100, 300)
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 6))
        ax1.hist(yoy_growth_clipped, bins=40, color='#4ECDC4', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax1.set_title('최근 분기 EPS 성장률(YoY) 분포', fontsize=15, fontweight='bold')
        ax1.set_xlabel('성장률 (%)', fontsize=12)
        ax1.set_ylabel('기업 수', fontsize=12)
        ax1.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax1.legend(fontsize=11)
        ax1.grid(True, linestyle='--', alpha=0.3)

        ax2.hist(annual_growth_clipped, bins=40, color='#FF6B6B', alpha=0.7, edgecolor='black', linewidth=0.5)
        ax2.set_title('3년 연평균 EPS 성장률 분포', fontsize=15, fontweight='bold')
        ax2.set_xlabel('성장률 (%)', fontsize=12)
        ax2.axvline(25, color='red', linestyle='--', linewidth=2, label='Strict 기준 (25%)')
        ax2.legend(fontsize=11)
        ax2.grid(True, linestyle='--', alpha=0.3)

        plt.tight_layout()
        plt.savefig(f'{script_dir}/growth_histograms.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/growth_histograms.png' 생성 완료.")

        # --- 3. 시각화 3: 성장성 사분면 분석 ---
        strict_df = results_df[results_df['financial_grade'] == 'Strict']
        loose_df = results_df[results_df['financial_grade'] == 'Loose']

        # 데이터가 없으면 건너뜀
        if len(strict_df) == 0 and len(loose_df) == 0:
            print("⚠️ 시각화할 데이터가 없습니다.")
            return

        plt.figure(figsize=(12, 9))

        # Loose 등급 점들
        if len(loose_df) > 0:
            plt.scatter(loose_df['eps_annual_growth_avg_3y'], loose_df['eps_growth_yoy'],
                        alpha=0.6, s=80, label=f'Loose 등급 ({len(loose_df)}개)',
                        color='#4ECDC4', edgecolor='black', linewidth=0.8)

        # Strict 등급 점들 (더 크게 강조)
        if len(strict_df) > 0:
            plt.scatter(strict_df['eps_annual_growth_avg_3y'], strict_df['eps_growth_yoy'],
                        s=200, alpha=0.9, label=f'Strict 등급 ({len(strict_df)}개)',
                        color='#FF6B6B', edgecolor='black', linewidth=2)

        # 기준선들
        plt.axhline(25, color='red', linestyle='-', linewidth=2, alpha=0.8, label='Strict 기준 (25%)')
        plt.axvline(25, color='red', linestyle='-', linewidth=2, alpha=0.8)

        # 사분면 라벨
        plt.text(175, 175, 'I. 지속적 고성장', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(-35, 175, 'II. 최근 실적 급증', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(-35, -50, 'III. 성장 둔화/역성장', ha='center', va='center', fontsize=14, fontweight='bold')
        plt.text(175, -50, 'IV. 과거 고성장/최근 부진', ha='center', va='center', fontsize=14, fontweight='bold')

        plt.title('EPS 성장성 사분면 분석', fontsize=18, fontweight='bold')
        plt.xlabel('3년 연평균 EPS 성장률 (%)', fontsize=14)
        plt.ylabel('최근 분기 EPS 성장률 (YoY, %)', fontsize=14)
        plt.xlim(-100, 300)
        plt.ylim(-100, 300)
        plt.legend(fontsize=12, loc='upper right')
        plt.grid(True, linestyle='--', alpha=0.4)
        plt.savefig(f'{script_dir}/growth_quadrant_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        print(f"✅ '{script_dir}/growth_quadrant_analysis.png' 생성 완료.")

    def run_full_analysis(self):
        """전체 상장 기업을 대상으로 EPS 계산 및 CAN SLIM 분석 실행"""
        print("="*80)
        print("🚀 전체 상장 기업 CAN SLIM 재무 분석 시작")
        print("="*80)
        
        # Step 1: Kiwoom API로 전체 종목 정보 수집
        all_stocks_raw = self.get_all_kiwoom_stocks()
        if not all_stocks_raw:
            print("❌ Kiwoom API를 통해 종목 정보를 가져오지 못했습니다.")
            return

        # Step 2: 필터 제로 적용 - 분석 대상 대폭 압축
        filtered_stocks = self._apply_filter_zero(all_stocks_raw)
        if not filtered_stocks:
            print("❌ 필터링 후 분석할 종목이 없습니다.")
            return

        # Step 3: 필터링된 종목만 순회하며 DART 분석
        print(f"\n--- 총 {len(filtered_stocks)}개 필터링된 종목 DART 분석 시작 ---")
        results = []
        
        for stock in tqdm(filtered_stocks, desc="필터링된 종목 EPS 분석 중"):
            stock_code = stock.get('code')
            stock_name = stock.get('name')
            list_count = int(stock.get('listCount', 0))
            last_price = int(stock.get('lastPrice', 0)) # lastPrice를 숫자로 변환하여 저장

            if not stock_code or list_count == 0:
                continue

            # 종목코드 -> 기업코드 매핑
            corp_code = self.corp_map.get(stock_code)
            if not corp_code:
                continue
            
            # DART API로 재무 데이터 수집
            financial_df = self.fetch_financial_data(corp_code)
            if financial_df is None:
                print(f"❌ DART API 재무 데이터 수집 실패: corp_code={corp_code}, stock_code={stock_code}, name={stock_name}")
                continue

            # EPS 계산
            eps_df = self._calculate_eps(financial_df, list_count)
            if eps_df is None:
                continue

            # 재무 등급 판정
            eps_only = eps_df[eps_df['account_id'] == 'EPS']
            if eps_only.empty:
                continue
                
            grade, yoy_g, annual_g = self.analyze_financial_grade(eps_only)
            
            # --- PER 계산 로직 추가 ---
            current_price = last_price
            per = self.calculate_per(current_price, eps_df)

            results.append({
                    'stock_code': stock_code,
                    'name': stock_name,
                    'financial_grade': grade,
                    'eps_growth_yoy': round(yoy_g, 2),
                    'eps_annual_growth_avg_3y': round(annual_g, 2),
                    'PER': per # PER 결과 추가
                })
            

        # Step 3: 결과 출력 및 저장
        if results:
            result_df = pd.DataFrame(results)
            print("\n" + "="*80)
            print("📈 최종 분석 결과")
            print("="*80)

            strict_df = result_df[result_df['financial_grade'] == 'Strict']
            loose_df = result_df[result_df['financial_grade'] == 'Loose']

            print(f"\n--- 'Strict' 등급 통과 기업 ({len(strict_df)}개) ---")
            if not strict_df.empty:
                print(strict_df.to_string(index=False))

            print(f"\n--- 'Loose' 등급 통과 기업 ({len(loose_df)}개) ---")
            if not loose_df.empty:
                print(loose_df.to_string(index=False))

            # CSV 파일로 저장 (스크립트와 동일한 폴더에 저장)
            script_dir = os.path.dirname(os.path.abspath(__file__))
            output_filename = os.path.join(script_dir, f"dart_financial_analysis_results_{datetime.now().strftime('%Y%m%d')}.csv")
            result_df.to_csv(output_filename, index=False, encoding='utf-8-sig')
            print(f"\n✅ 전체 분석 결과를 '{os.path.basename(output_filename)}' 파일로 저장했습니다.")
            print(f"   📁 저장 위치: {script_dir}")
            print(f"   - 총 통과 기업: {len(results)}개")
            print(f"   - Strict 등급: {len(strict_df)}개")
            print(f"   - Loose 등급: {len(loose_df)}개")

            # Step 4: 시각화 생성
            print(f"\n{'='*80}")
            print("📊 시각화 차트 생성 중...")
            print(f"{'='*80}")
            self.visualize_results(result_df)
            print(f"\n📁 생성된 시각화 파일들:")
            script_dir = os.path.dirname(os.path.abspath(__file__))
            print(f"  • {script_dir}/grade_distribution.png")
            print(f"  • {script_dir}/growth_histograms.png")
            print(f"  • {script_dir}/growth_quadrant_analysis.png")

        else:
            print("\n⚠️ 분석 기준을 통과한 기업이 없습니다.")

        print("\n" + "="*80)
        print("🎉 전체 분석 및 시각화 완료!")
        print("="*80)

if __name__ == '__main__':
    analyzer = EpsAnalysisEngine()
    analyzer.run_full_analysis()
