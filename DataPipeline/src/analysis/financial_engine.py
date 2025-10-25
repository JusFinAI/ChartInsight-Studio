"""
재무 분석 엔진 (Financial Analysis Engine)

이 모듈은 재무 데이터 수집, 파싱, EPS 계산, 재무 등급 판정 등의 핵심 로직을 제공합니다.
DAG와 분석 로직을 분리하여 재사용성과 테스트 용이성을 극대화합니다.

주요 클래스:
    - _FinancialDataParser: DART API 원본 데이터를 DataFrame으로 변환
    - _EpsCalculator: 재무 데이터로부터 EPS를 계산
    - _FinancialGradeAnalyzer: EPS 성장률 기반 재무 등급 판정
    
주요 함수:
    - fetch_live_financial_data: DART API로부터 재무 데이터 수집
"""

import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

import pandas as pd

# Defensive import for AirflowException
try:
    from airflow.exceptions import AirflowException
except ImportError:
    class AirflowException(Exception):
        pass

from src.utils.logging_kst import configure_kst_logger
from src.dart_api.client import DartApiClient

logger = configure_kst_logger(__name__)


class _FinancialDataParser:
    """DART API 원본 데이터를 분석 가능한 DataFrame으로 변환하는 파서"""
    
    class _AccountIDs:
        """DART 계정 과목 ID 상수"""
        NET_INCOME = "ifrs-full_ProfitLossAttributableToOwnersOfParent"
    
    def _to_numeric(self, value: str) -> int:
        """문자열을 안전하게 정수로 변환합니다.

        - None/빈값, '-', 'NaN' 등은 0으로 처리
        - 괄호 표기 '(123)'은 음수로 처리
        - 천단위 콤마, + 기호 제거
        - 소수는 float로 파싱 후 int로 변환
        - 문자열 내 숫자가 없으면 0 반환
        """
        if value is None:
            return 0

        # 이미 숫자인 경우
        if isinstance(value, (int, float)):
            try:
                return int(value)
            except Exception:
                return 0

        s = str(value).strip()
        if s in ['', '-', '—', '–', 'NaN', 'nan', 'None']:
            return 0

        # 괄호 표기 '(123)' -> -123
        if s.startswith('(') and s.endswith(')'):
            s = '-' + s[1:-1]

        # 제거 가능한 문자 정리
        s = s.replace(',', '').replace('+', '')

        # 숫자 패턴 추출 (정수/소수 허용)
        import re
        m = re.search(r'-?\d+(?:\.\d+)?', s)
        if not m:
            return 0

        try:
            return int(float(m.group(0)))
        except Exception:
            return 0
    
    def _report_code_to_quarter(self, reprt_code: str) -> str:
        """보고서 코드를 분기로 변환"""
        return {"11013": "Q1", "11012": "Q2", "11014": "Q3", "11011": "Q4"}.get(reprt_code, "Unknown")
    
    def parse(self, financials_raw: List[Dict], annual_shares_raw: List[Dict]) -> pd.DataFrame:
        """재무제표와 주식총수 원본 데이터를 통합 DataFrame으로 변환
        
        Args:
            financials_raw: DART 재무제표 API 응답
            annual_shares_raw: DART 주식총수 API 응답
            
        Returns:
            columns: ['year', 'quarter', 'account_id', 'amount']
        """
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


class _EpsCalculator:
    """EPS 계산을 전담하는 클래스"""
    
    def calculate(self, df: pd.DataFrame, current_list_count: int) -> Optional[pd.DataFrame]:
        """재무 데이터와 상장주식수를 결합하여 EPS 계산
        
        Args:
            df: _FinancialDataParser.parse()가 반환한 DataFrame
            current_list_count: 현재 발행 주식 총수
            
        Returns:
            columns: ['year', 'quarter', 'EPS']를 포함한 DataFrame
        """
        current_year = datetime.now().year
        net_income_account = _FinancialDataParser._AccountIDs.NET_INCOME
        
        # 1. 피벗 테이블 생성
        pivot_df = df.pivot_table(
            index=['year', 'quarter'],
            columns='account_id',
            values='amount',
            aggfunc='first'
        ).reset_index()
        
        # 2. 필수 컬럼 확인
        if net_income_account not in pivot_df.columns:
            logger.warning("EPS 계산에 필요한 당기순이익 컬럼이 없습니다.")
            return None
        
        # 3. 주식수 컬럼 처리
        if "SharesOutstanding" in pivot_df.columns:
            # Forward Fill로 분기별 데이터 채움
            pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].ffill()
        else:
            # 주식수 정보가 없으면 현재 값으로 초기화
            pivot_df['SharesOutstanding'] = current_list_count
        
        # 4. 현재 연도의 모든 분기는 최신 상장주식수 사용
        pivot_df.loc[pivot_df['year'] == current_year, 'SharesOutstanding'] = current_list_count
        
        # 5. 여전히 주식수가 없는 행은 현재 값으로 대체
        pivot_df['SharesOutstanding'] = pivot_df['SharesOutstanding'].fillna(current_list_count)
        
        if pivot_df['SharesOutstanding'].isnull().all():
            logger.warning("주식수 데이터가 전혀 없습니다.")
            return None
        
        # 6. EPS 계산
        pivot_df["EPS"] = pivot_df.apply(
            lambda row: row[net_income_account] / row['SharesOutstanding'] 
            if row['SharesOutstanding'] > 0 else 0,
            axis=1
        )
        
        # 7. 결과 DataFrame 생성
        result = pivot_df[['year', 'quarter', 'EPS']].dropna()
        return result


class _FinancialGradeAnalyzer:
    """재무 등급 판정을 전담하는 클래스"""
    
    def analyze(self, eps_df: pd.DataFrame) -> Dict:
        """EPS 데이터를 바탕으로 재무 등급을 판정
        
        Args:
            eps_df: _EpsCalculator.calculate()가 반환한 DataFrame
            
        Returns:
            {'eps_growth_yoy': float, 'eps_annual_growth_avg': float, 'financial_grade': str}
        """
        # 1. 데이터 준비
        annual_eps = eps_df[eps_df['quarter'] == 'Q4'].set_index('year')['EPS']
        quarterly_eps = eps_df[eps_df['quarter'] != 'Q4'].set_index(['year', 'quarter'])['EPS']
        
        # 2. 최근 분기 YoY 성장률 계산 (CAN SLIM 'C' 기준)
        yoy_growth = 0.0
        if not quarterly_eps.empty:
            try:
                # Use the last index as the most recent quarter (assumes parse() preserved chronological order)
                latest_q_idx = quarterly_eps.index[-1]
                prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1])

                # Ensure values are Python floats for arithmetic
                try:
                    latest_val = float(quarterly_eps.loc[latest_q_idx])
                except Exception:
                    latest_val = None

                if prev_year_q_idx in quarterly_eps.index:
                    try:
                        prev_val = float(quarterly_eps.loc[prev_year_q_idx])
                    except Exception:
                        prev_val = None
                else:
                    prev_val = None

                if prev_val is not None and prev_val != 0 and latest_val is not None:
                    yoy_growth = (latest_val / prev_val - 1) * 100
            except Exception as e:
                logger.warning(f"YoY 성장률 계산 중 오류: {e}")
        
        # 3. 최근 3년간 연간 성장률 계산 (단순 평균)
        avg_annual_growth = 0.0
        # Require at least 4 years of annual EPS to compute three year-over-year growth rates
        if len(annual_eps) >= 4:
            try:
                # Ensure chronological order
                sorted_annual = annual_eps.sort_index()
                annual_growth_rates = []

                # compute growth rates for the last 3 year-over-year pairs
                for i in range(1, 4):
                    # current year value and previous year value
                    curr = sorted_annual.iloc[-i]
                    prev = sorted_annual.iloc[-(i+1)]
                    try:
                        curr_v = float(curr)
                        prev_v = float(prev)
                    except Exception:
                        continue

                    if prev_v > 0:
                        growth = (curr_v / prev_v - 1) * 100
                        annual_growth_rates.append(growth)

                if len(annual_growth_rates) == 3:
                    avg_annual_growth = sum(annual_growth_rates) / len(annual_growth_rates)
            except Exception as e:
                logger.warning(f"연평균 성장률 계산 중 오류: {e}")
        
        # 4. 재무 등급 판정
        # Strict: 최근 3년 모두 흑자 + YoY 25% 이상 + 연평균 25% 이상
        if len(annual_eps) >= 3:
            recent_3_years = annual_eps.sort_index(ascending=False).iloc[:3]
            all_positive = (recent_3_years > 0).all()
            
            if all_positive and yoy_growth >= 25 and avg_annual_growth >= 25:
                return {
                    'eps_growth_yoy': float(round(yoy_growth, 2)),
                    'eps_annual_growth_avg': float(round(avg_annual_growth, 2)),
                    'financial_grade': 'Strict'
                }
        
        # Loose: 관대한 기준 (검증된 코드 기준)
        if len(annual_eps) >= 2:
            # 1) Turnaround: 최근 분기 기준, 최근 분기가 양수이고 전년 동기 분기가 음수인 경우
            is_turnaround = False
            try:
                if not quarterly_eps.empty:
                    latest_q_idx = quarterly_eps.index[-1]
                    prev_year_q_idx = (latest_q_idx[0] - 1, latest_q_idx[1])
                    latest_q_val = float(quarterly_eps.loc[latest_q_idx]) if latest_q_idx in quarterly_eps.index else None
                    prev_q_val = float(quarterly_eps.loc[prev_year_q_idx]) if prev_year_q_idx in quarterly_eps.index else None
                    if latest_q_val is not None and prev_q_val is not None and prev_q_val < 0 and latest_q_val > 0:
                        is_turnaround = True
            except Exception:
                is_turnaround = False

            # 2) Loose C: 최근 분기 YoY가 역성장이 아닌 경우 (>= 0)
            is_loose_c = (yoy_growth >= 0)

            # 3) Loose A: 최근 3년 연속 증가 추세 (annual_eps 최신 3년 증가)
            is_loose_a = False
            try:
                if len(annual_eps) >= 3:
                    sorted_annual = annual_eps.sort_index()
                    if float(sorted_annual.iloc[-1]) > float(sorted_annual.iloc[-2]) > float(sorted_annual.iloc[-3]):
                        is_loose_a = True
            except Exception:
                is_loose_a = False

            if is_turnaround or is_loose_c or is_loose_a:
                return {
                    'eps_growth_yoy': float(round(yoy_growth, 2)),
                    'eps_annual_growth_avg': float(round(avg_annual_growth, 2)),
                    'financial_grade': 'Loose'
                }
        
        return {
            'eps_growth_yoy': float(round(yoy_growth, 2)),
            'eps_annual_growth_avg': float(round(avg_annual_growth, 2)),
            'financial_grade': 'Fail'
        }


def fetch_live_financial_data(corp_code: str, last_analysis_date: Optional[date] = None) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
    """DART API로부터 재무제표와 주식총수 데이터를 수집합니다.
    
    Args:
        corp_code: DART 고유번호
        
    Returns:
        Tuple[재무제표 원본 리스트, 주식총수 원본 리스트]
        - 첫 번째: 재무제표 API 응답 원본 (List[Dict])
        - 두 번째: 주식총수 API 응답 원본 (List[Dict])
    """
    dart = DartApiClient()
    # DART API expects an 8-character corp_code with leading zeros.
    corp_code = str(corp_code).zfill(8)
    current_date = date.today()
    current_year = current_date.year

    # Helper: intelligent selection of report codes
    def _select_report_codes_by_date(year: int, current_date: date) -> List[str]:
        """연도와 현재 시점에 따라 조회할 DART 보고서 코드를 지능적으로 선택합니다.

        - 현재 연도: 월별로 발행 완료된 보고서만 조회
        - 최근 2년: YoY 계산을 위해 모든 분기 조회
        - 그 이전 연도: 사업보고서(11011)만 조회 (API 절감)
        - 미래 연도: 빈 리스트 반환(방어)
        """
        current_year = current_date.year

        # 1) 미래 연도는 방어적으로 빈 리스트 반환
        if year > current_year:
            return []

        # 2) 현재 연도는 월별로 발행 완료된 보고서만 조회 (최신 보고서만)
        if year == current_year:
            month = current_date.month
            if month < 5:
                # 1~4월: 당해 연도 보고서 아직 없음
                return []
            elif month < 8:
                # 5~7월: 1분기 보고서(11013) 발행 완료
                return ['11013']
            elif month < 11:
                # 8~10월: 반기 보고서(11012)만 조회 (API 절감)
                return ['11012']
            else:
                # 11월~12월: 3분기 보고서(11014)만 조회 (API 절감)
                return ['11014']

        # 3) 직전 1년은 YoY 계산을 위해 모든 분기 조회
        if year == current_year - 1:
            # Order: business (Q4), Q3, Q2, Q1
            return ['11011', '11014', '11012', '11013']

        # 4) 그 이전 연도는 사업보고서(11011)만 조회 (API 절감)
        if year < current_year - 1:
            return ['11011']
        
        return []

    # years_to_fetch 결정: (신규 종목 vs 기존 종목)
    if last_analysis_date is None:
        # 신규 종목: 과거 4년 + 현재 연도 포함 (현재 연도는 발행 완료된 보고서만 조회)
        years_to_fetch = range(current_year - 4, current_year + 1)
    else:
        # 기존 종목이지만, 분석 시점이 현재 연도와 같거나 미래면 → 히스토리 부족 → 신규 처리
        if last_analysis_date.year >= current_year:
            logger.warning(f"[{corp_code}] last_analysis_date({last_analysis_date})가 현재/미래 연도, 과거 4년 데이터 수집")
            years_to_fetch = range(current_year - 4, current_year + 1)
        else:
            # 정상적인 기존 종목: 마지막 분석 연도부터 현재 연도까지 재검증
            # 단, 너무 오래된 경우(3년 이상 차이) 신규 종목처럼 처리
            years_gap = current_year - last_analysis_date.year
            if years_gap > 3:
                logger.warning(f"[{corp_code}] last_analysis_date({last_analysis_date})가 {years_gap}년 전, 과거 4년 데이터 수집")
                years_to_fetch = range(current_year - 4, current_year + 1)
            else:
                years_to_fetch = range(last_analysis_date.year, current_year + 1)

    all_financials_raw: List[Dict] = []
    all_annual_shares_raw: List[Dict] = []

    logger.info(f"[{corp_code}] years_to_fetch: {list(years_to_fetch)}")
    
    for year in years_to_fetch:
        report_codes_to_fetch = _select_report_codes_by_date(year, current_date)
        logger.info(f"[{corp_code}] {year}년 조회 보고서: {report_codes_to_fetch}")
        for reprt_code in report_codes_to_fetch:
            try:
                items = dart.get_financial_statements(corp_code, year, reprt_code)
                if items:
                    all_financials_raw.extend(items)
                time.sleep(0.1)
            except Exception as e:
                if "한도" in str(e):
                    # If DART returns an explicit quota message, raise to let DAG decide
                    raise AirflowException(f"DART API 한도를 초과하여 DAG를 중단합니다: {e}")
                logger.warning(f"[{corp_code}] 재무제표 수집 중 오류: {e}")

        if '11011' in report_codes_to_fetch:
            try:
                shares = dart.get_annual_share_info(corp_code, year)
                if shares:
                    for share_item in shares:
                        share_item['bsns_year'] = str(year)
                    all_annual_shares_raw.extend(shares)
                time.sleep(0.1)
            except Exception as e:
                logger.warning(f"[{corp_code}] 연간 주식 정보 수집 중 오류: {e}")

    # If no share info was found in the fetched years, attempt a conservative fallback
    # to the latest complete year (current_year - 1) to cover cases where
    # company reports have not yet included '11011' in the selected years.
    if not all_annual_shares_raw:
        latest_complete_year = current_year - 1
        try:
            logger.info(f"[{corp_code}] 주식총수 정보가 없어 직전 연도({latest_complete_year}) 조회 시도")
            shares = dart.get_annual_share_info(corp_code, latest_complete_year)
            if shares:
                for share_item in shares:
                    share_item['bsns_year'] = str(latest_complete_year)
                all_annual_shares_raw.extend(shares)
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"[{corp_code}] 직전 연도 주식 정보 수집 중 오류: {e}")

    # debug: summary of collected data
    logger.info(f"[{corp_code}] 총 수집 재무레코드 수: {len(all_financials_raw)}, 주식정보 레코드 수: {len(all_annual_shares_raw)}")
    if len(all_financials_raw) > 0:
        for sample in all_financials_raw[:5]:
            logger.debug(f"[{corp_code}] final sample financial: bsns_year={sample.get('bsns_year')} reprt_code={sample.get('reprt_code')} account_id={sample.get('account_id')} amount={sample.get('thstrm_amount')}")

    if not all_financials_raw:
        return None, None

    return all_financials_raw, all_annual_shares_raw


