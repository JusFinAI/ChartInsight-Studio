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
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import pandas as pd

from src.utils.logging_kst import configure_kst_logger
from src.dart_api.client import DartApiClient

logger = configure_kst_logger(__name__)


class _FinancialDataParser:
    """DART API 원본 데이터를 분석 가능한 DataFrame으로 변환하는 파서"""
    
    class _AccountIDs:
        """DART 계정 과목 ID 상수"""
        NET_INCOME = "ifrs-full_ProfitLossAttributableToOwnersOfParent"
    
    def _to_numeric(self, value: str) -> int:
        """문자열을 안전하게 숫자로 변환"""
        if not isinstance(value, str) or not value:
            return 0
        try:
            return int(value.replace(",", ""))
        except ValueError:
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
                sorted_quarters = quarterly_eps.sort_index(ascending=False)
                if len(sorted_quarters) >= 2:
                    latest = sorted_quarters.iloc[0]
                    year_ago_idx = (sorted_quarters.index[0][0] - 1, sorted_quarters.index[0][1])
                    if year_ago_idx in sorted_quarters.index:
                        year_ago = sorted_quarters.loc[year_ago_idx]
                        if year_ago > 0:
                            yoy_growth = ((latest - year_ago) / year_ago) * 100
            except Exception as e:
                logger.warning(f"YoY 성장률 계산 중 오류: {e}")
        
        # 3. 연평균 EPS 성장률 계산 (3년 기준, CAGR)
        avg_annual_growth = 0.0
        if len(annual_eps) >= 3:
            try:
                sorted_annual = annual_eps.sort_index(ascending=False)
                recent_3_years = sorted_annual.iloc[:3]
                oldest = recent_3_years.iloc[-1]
                latest = recent_3_years.iloc[0]
                num_years = recent_3_years.index[0] - recent_3_years.index[-1]  # 실제 연도 차이
                
                if oldest > 0 and num_years > 0:
                    # CAGR = (최종값/초기값)^(1/기간) - 1
                    cagr = ((latest / oldest) ** (1 / num_years)) - 1
                    avg_annual_growth = cagr * 100
            except Exception as e:
                logger.warning(f"연평균 성장률 계산 중 오류: {e}")
        
        # 4. 재무 등급 판정
        # Strict: 최근 3년 모두 흑자 + YoY 25% 이상 + 연평균 25% 이상
        if len(annual_eps) >= 3:
            recent_3_years = annual_eps.sort_index(ascending=False).iloc[:3]
            all_positive = (recent_3_years > 0).all()
            
            if all_positive and yoy_growth >= 25 and avg_annual_growth >= 25:
                return {
                    'eps_growth_yoy': round(yoy_growth, 2),
                    'eps_annual_growth_avg': round(avg_annual_growth, 2),
                    'financial_grade': 'Strict'
                }
        
        # Loose: 턴어라운드 또는 YoY 25% 이상 또는 연평균 15% 이상
        if len(annual_eps) >= 2:
            sorted_annual = annual_eps.sort_index(ascending=False)
            latest = sorted_annual.iloc[0]
            previous = sorted_annual.iloc[1]
            
            # 턴어라운드: 직전 적자 → 최근 흑자
            turnaround = (previous <= 0 and latest > 0)
            
            if turnaround or yoy_growth >= 25 or avg_annual_growth >= 15:
                return {
                    'eps_growth_yoy': round(yoy_growth, 2),
                    'eps_annual_growth_avg': round(avg_annual_growth, 2),
                    'financial_grade': 'Loose'
                }
        
        return {
            'eps_growth_yoy': round(yoy_growth, 2),
            'eps_annual_growth_avg': round(avg_annual_growth, 2),
            'financial_grade': 'Fail'
        }


def fetch_live_financial_data(corp_code: str) -> Tuple[Optional[List[Dict]], Optional[List[Dict]]]:
    """DART API로부터 재무제표와 주식총수 데이터를 수집합니다.
    
    Args:
        corp_code: DART 고유번호
        
    Returns:
        Tuple[재무제표 원본 리스트, 주식총수 원본 리스트]
        - 첫 번째: 재무제표 API 응답 원본 (List[Dict])
        - 두 번째: 주식총수 API 응답 원본 (List[Dict])
    """
    dart = DartApiClient()
    # DART API expects an 8-character corp_code with leading zeros. Ensure padding here so
    # callers can provide either padded or unpadded codes.
    corp_code = str(corp_code).zfill(8)
    current_year = datetime.now().year
    
    all_financials_raw = []
    all_annual_shares_raw = []
    
    # 5년치 데이터 수집 (current_year - 5 부터 current_year까지)
    for year in range(current_year - 5, current_year + 1):
        # [기존] 재무제표 수집 로직
        for reprt_code in ['11013', '11012', '11014', '11011']:
            try:
                items = dart.get_financial_statements(corp_code, year, reprt_code)
            except Exception:
                items = None
            if items:
                all_financials_raw.extend(items)
        
        # [추가] 연간 발행 주식 수 수집 로직
        try:
            shares = dart.get_annual_share_info(corp_code, year)
        except Exception:
            shares = None
        if shares:
            # 데이터 보강: API 응답에 누락된 사업연도(bsns_year)를 수동으로 추가
            for share_item in shares:
                share_item['bsns_year'] = str(year)
            all_annual_shares_raw.extend(shares)
    
    # 재무제표 데이터가 없으면 None 반환
    if not all_financials_raw:
        return None, None
    
    return all_financials_raw, all_annual_shares_raw


