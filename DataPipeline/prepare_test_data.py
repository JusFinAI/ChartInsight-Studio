#!/usr/bin/env python3
"""
주식 데이터 테스트 파일 생성 스크립트

이 스크립트는 키움증권 API를 사용하여 주식 데이터를 조회하고 
Parquet 형식으로 저장하는 범용 유틸리티입니다.

🔄 수정된 목적:
- 시뮬레이션용 충분한 과거 데이터 생성
- base_date 없이 현재 날짜 기준 과거 전체 수집
- 파일명을 {stock_code}_{timeframe}_full.parquet로 통일
- 타임존 처리 표준화 (UTC 기준 naive 형식)

Usage:
    # 단일 종목 데이터 생성 (base_date 제거됨)
    python prepare_test_data.py --timeframe minute --stock_code 005930 --period 2y --interval 5
    
    # 30개 타겟 종목 전체 데이터 생성
    python prepare_test_data.py --timeframe daily --period 2y --all-targets
"""

import argparse
import json
import os
import re
import sys
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# 필수 라이브러리 확인
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError as e:
    print(f"❌ 필수 라이브러리가 설치되지 않았습니다: {e}")
    print("💡 다음 명령어로 설치해주세요:")
    print("   pip install pandas pyarrow")
    sys.exit(1)

# Python 경로에 src 디렉토리 추가
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# 프로젝트 모듈 import
try:
    from kiwoom_api.services.chart import (
        get_daily_stock_chart, get_minute_chart, get_weekly_stock_chart, get_monthly_stock_chart,
        get_daily_inds_chart, get_weekly_inds_chart, get_monthly_inds_chart
    )
except ImportError as e:
    print(f"❌ 키움 API 모듈을 불러올 수 없습니다: {e}")
    print("💡 현재 작업 디렉토리에 src/kiwoom_api 디렉토리가 있는지 확인해주세요.")
    sys.exit(1)

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


class StockDataPreparer:
    """주식 데이터 준비 클래스"""
    
    def __init__(self):
        self.output_dir = Path("./data/simulation")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 출력 디렉토리 준비: {self.output_dir}")
        
    def parse_period(self, period_str: str, timeframe: str = 'daily') -> int:
        """
        기간 문자열을 파싱하여 캔들 개수로 변환
        
        Args:
            period_str: 기간 문자열 ('1d', '4h', '30m', '2y', '3m' 등)
            timeframe: 'minute', 'daily', 'weekly'
        
        Returns:
            int: 캔들 개수
        """
        if not period_str:
            # 기본값 설정
            if timeframe == 'minute':
                return 390  # 1일 거래시간 (6시간 30분 = 390분)
            elif timeframe == 'daily':
                return 252  # 1년 거래일
            elif timeframe == 'weekly':
                return 52   # 1년 주수
            elif timeframe == 'monthly':
                return 12   # 1년 12개월
            else:
                return 100  # 기본값
        
        total_units = 0
        
        # 년(y) 매칭
        year_match = re.search(r'(\d+)y', period_str)
        if year_match:
            years = int(year_match.group(1))
            if timeframe == 'minute':
                total_units += years * 252 * 390  # 252 거래일 * 390분
            elif timeframe == 'daily':
                total_units += years * 252  # 252 거래일
            elif timeframe == 'weekly':
                total_units += years * 52   # 52주
        
        # 월(m) 매칭
        month_match = re.search(r'(\d+)m', period_str)
        if month_match:
            months = int(month_match.group(1))
            if timeframe == 'minute':
                total_units += months * 21 * 390  # 21 거래일 * 390분
            elif timeframe == 'daily':
                total_units += months * 21  # 21 거래일
            elif timeframe == 'weekly':
                total_units += months * 4   # 4주
            elif timeframe == 'monthly':
                total_units += months      # months for monthly
        
        # 주(w) 매칭
        week_match = re.search(r'(\d+)w', period_str)
        if week_match:
            weeks = int(week_match.group(1))
            if timeframe == 'minute':
                total_units += weeks * 5 * 390  # 5 거래일 * 390분
            elif timeframe == 'daily':
                total_units += weeks * 5    # 5 거래일
            elif timeframe == 'weekly':
                total_units += weeks        # 주수
        
        # 일(d) 매칭 - 분봉에서만 의미 있음
        day_match = re.search(r'(\d+)d', period_str)
        if day_match:
            days = int(day_match.group(1))
            if timeframe == 'minute':
                total_units += days * 390   # 390분/일
            elif timeframe == 'daily':
                total_units += days         # 일수
            elif timeframe == 'weekly':
                total_units += days // 7    # 주수로 변환
        
        # 시간(h) 매칭 - 분봉에서만 의미 있음
        hour_match = re.search(r'(\d+)h', period_str)
        if hour_match:
            hours = int(hour_match.group(1))
            if timeframe == 'minute':
                total_units += hours * 60   # 60분/시간
            elif timeframe == 'daily':
                total_units += max(1, hours // 6)  # 대략 변환
            elif timeframe == 'weekly':
                total_units += max(1, hours // (6*5))  # 대략 변환
        
        # 숫자만 있는 경우 해당 단위로 취급
        if total_units == 0 and period_str.isdigit():
            total_units = int(period_str)
        
        # 최소값 보장
        return max(1, total_units)
        
    def get_target_stocks(self, limit: int = 30) -> List[str]:
        """
        타겟 종목 리스트를 가져옵니다.
        
        Args:
            limit: 가져올 종목 수 (기본값: 30)
            
        Returns:
            종목 코드 리스트
        """
        stock_codes = []
        
        # KOSPI 종목 읽기
        kospi_path = Path("data/kospi_code.json")
        kosdaq_path = Path("data/kosdaq_code.json")
        
        if not kospi_path.exists():
            logger.error(f"❌ KOSPI 파일을 찾을 수 없습니다: {kospi_path}")
            return []
            
        if not kosdaq_path.exists():
            logger.error(f"❌ KOSDAQ 파일을 찾을 수 없습니다: {kosdaq_path}")
            return []
        
        try:
            # KOSPI 데이터 로드
            with open(kospi_path, 'r', encoding='utf-8') as f:
                kospi_data = json.load(f)
                
            # KOSDAQ 데이터 로드
            with open(kosdaq_path, 'r', encoding='utf-8') as f:
                kosdaq_data = json.load(f)
                
            # 대형주 우선 선택을 위한 필터링
            target_stocks = []
            
            # KOSPI에서 대형주 우선 선택
            for code, info in kospi_data.items():
                if info.get('upSizeName') == '대형주':
                    target_stocks.append(code)
                    if len(target_stocks) >= limit // 2:  # 절반은 KOSPI 대형주
                        break
            
            # KOSPI 중형주 추가
            for code, info in kospi_data.items():
                if info.get('upSizeName') == '중형주' and code not in target_stocks:
                    target_stocks.append(code)
                    if len(target_stocks) >= limit * 3 // 4:  # 3/4은 KOSPI
                        break
            
            # KOSDAQ 대형주로 나머지 채우기
            for code, info in kosdaq_data.items():
                if info.get('upSizeName') == '대형주' and code not in target_stocks:
                    target_stocks.append(code)
                    if len(target_stocks) >= limit:
                        break
            
            logger.info(f"📊 선택된 타겟 종목 수: {len(target_stocks)}")
            return target_stocks[:limit]
            
        except Exception as e:
            logger.error(f"❌ 타겟 종목 로드 실패: {e}")
            return []
    
    def get_timeframe_label(self, timeframe: str, interval: int = 1) -> str:
        """
        타임프레임과 간격을 기반으로 파일명용 라벨 생성
        
        Args:
            timeframe: 'minute', 'daily', 'weekly'
            interval: 분봉 간격
            
        Returns:
            파일명용 라벨 (예: '5m', '1h', 'd', 'w')
        """
        if timeframe == 'minute':
            if interval == 60:
                return '1h'  # 60분봉을 1h로 매핑
            else:
                return f'{interval}m'
        elif timeframe == 'daily':
            return 'd'
        elif timeframe == 'weekly':
            return 'w'
        elif timeframe == 'monthly':
            return 'mon'
        else:
            return timeframe

    def fetch_chart_data(self, timeframe: str, stock_code: str, 
                        period: str, interval: int = 1):
        """
        차트 데이터를 조회합니다.
        
        Args:
            timeframe: 'minute', 'daily', 'weekly'
            stock_code: 종목 코드
            period: 기간 문자열 ('1d', '1y', '3m' 등)
            interval: 분봉 간격
            
        Returns:
            ChartData 객체 또는 None
        """
        try:
            # period를 캔들 개수로 변환
            num_candles = self.parse_period(period, timeframe)
            
            logger.info(f"📊 {stock_code} {timeframe} 데이터 조회 시작 (기간: {period}, 캔들수: {num_candles})")
            
            if timeframe == 'minute':
                return get_minute_chart(
                    stock_code=stock_code,
                    interval=str(interval),
                    base_date=None,  # base_date 제거: 현재 날짜 기준
                    num_candles=num_candles
                )
            elif timeframe == 'daily':
                return get_daily_stock_chart(
                    stock_code=stock_code,
                    base_date=None,  # base_date 제거: 현재 날짜 기준
                    num_candles=num_candles
                )
            elif timeframe == 'weekly':
                return get_weekly_stock_chart(
                    stock_code=stock_code,
                    base_date=None,  # base_date 제거: 현재 날짜 기준
                    num_candles=num_candles
                )

            elif timeframe == 'monthly':
                return get_monthly_stock_chart(
                    stock_code=stock_code,
                    base_date=None,
                    num_candles=num_candles
                )
            else:
                logger.error(f"❌ 지원하지 않는 타임프레임: {timeframe}")
                return None
                
        except Exception as e:
            logger.error(f"❌ {stock_code} 데이터 조회 실패: {e}")
            return None
    
    def save_to_parquet(self, chart_data, stock_code: str, timeframe: str, 
                       interval: int = 1) -> bool:
        """
        차트 데이터를 Parquet 파일로 저장합니다.
        
        Args:
            chart_data: ChartData 객체
            stock_code: 종목 코드
            timeframe: 타임프레임
            interval: 분봉 간격
            
        Returns:
            저장 성공 여부
        """
        try:
            # DataFrame 변환
            df = chart_data.to_dataframe()
            if df is None or df.empty:
                logger.warning(f"⚠️ {stock_code} 데이터가 비어있습니다.")
                return False
            
            # 파일명 생성 (base_date 제거, _full 추가)
            timeframe_label = self.get_timeframe_label(timeframe, interval)
            filename = f"{stock_code}_{timeframe_label}_full.parquet"
            filepath = self.output_dir / filename

            # 타임존 처리 로직
            logger.info(f"타임존 처리 시작: {stock_code}")
            
            # 1. DatetimeIndex 변환 (ChartData에서 이미 처리된 경우 스킵)
            if not isinstance(df.index, pd.DatetimeIndex):
                # 일봉/주봉 데이터 처리: 'dt' 컬럼을 DatetimeIndex로 변환
                if 'dt' in df.columns:
                    logger.info(f"일봉/주봉 데이터 처리: 'dt' 컬럼을 DatetimeIndex로 변환합니다.")
                    df.index = pd.to_datetime(df['dt'], format='%Y%m%d')
                else:
                    logger.error(f"❌ {stock_code} 데이터의 인덱스를 DatetimeIndex로 변환할 수 없습니다.")
                    return False
            else:
                logger.info(f"이미 DatetimeIndex로 처리됨 (ChartData에서 처리)")

            # 2. 항상 Asia/Seoul로 localize (tz 정보가 없으면)
            if isinstance(df.index, pd.DatetimeIndex):
                if df.index.tz is None:
                    df.index = df.index.tz_localize('Asia/Seoul')
                    logger.info(f"타임존 정보 부여: Naive -> Asia/Seoul")
                else:
                    df.index = df.index.tz_convert('Asia/Seoul')
            else:
                logger.error(f"❌ {stock_code} 데이터의 인덱스를 DatetimeIndex로 변환할 수 없습니다.")
                return False

            # 3. UTC로 변환 (PostgreSQL과 동일한 원칙: UTC timezone-aware로 저장)
            df.index = df.index.tz_convert('UTC')
            logger.info(f"타임존 표준화 완료: Asia/Seoul -> UTC (timezone-aware)")

            # Parquet 저장
            df.to_parquet(filepath, index=True)
            
            # 데이터 범위 로깅
            first_date = df.index.min().strftime('%Y-%m-%d')
            last_date = df.index.max().strftime('%Y-%m-%d')
            
            logger.info(f"✅ {stock_code} 저장 완료: {filepath}")
            logger.info(f"   📊 데이터 범위: {first_date} ~ {last_date} ({len(df)}개 캔들)")
            return True
            
        except Exception as e:
            logger.error(f"❌ {stock_code} 저장 실패: {e}")
            return False
    
    def process_single_stock(self, timeframe: str, stock_code: str, 
                           period: str, interval: int = 1) -> bool:
        """
        단일 종목 데이터를 처리합니다.
        
        Args:
            timeframe: 타임프레임
            stock_code: 종목 코드
            period: 기간 문자열
            interval: 분봉 간격
            
        Returns:
            처리 성공 여부
        """
        logger.info(f"🚀 {stock_code} 데이터 처리 시작")
        
        # 1. 데이터 조회
        chart_data = self.fetch_chart_data(timeframe, stock_code, period, interval)
        if chart_data is None:
            return False
        
        # 2. Parquet 저장 (base_date 매개변수 제거)
        success = self.save_to_parquet(chart_data, stock_code, timeframe, interval)
        
        # 3. API 호출 제한 준수
        time.sleep(0.5)
        
        return success
    
    def process_all_targets(self, timeframe: str, 
                          period: str, interval: int = 1) -> Dict[str, bool]:
        """
        모든 타겟 종목 데이터를 처리합니다.
        
        Args:
            timeframe: 타임프레임
            period: 기간 문자열
            interval: 분봉 간격
            
        Returns:
            종목별 처리 결과 딕셔너리
        """
        logger.info(f"🎯 타겟 종목 전체 처리 시작 (timeframe: {timeframe}, period: {period})")
        
        # 타겟 종목 가져오기
        target_stocks = self.get_target_stocks()
        if not target_stocks:
            logger.error("❌ 타겟 종목을 가져올 수 없습니다.")
            return {}
        
        results = {}
        
        for i, stock_code in enumerate(target_stocks, 1):
            logger.info(f"📈 진행상황: {i}/{len(target_stocks)} - {stock_code}")
            
            try:
                result = self.process_single_stock(timeframe, stock_code, period, interval)
                results[stock_code] = result
                
                if result:
                    logger.info(f"✅ {stock_code} 성공")
                else:
                    logger.warning(f"⚠️ {stock_code} 실패")
                    
            except Exception as e:
                logger.error(f"❌ {stock_code} 처리 중 오류: {e}")
                results[stock_code] = False
            
            # 마지막 종목이 아닌 경우, API 과부하 방지를 위해 잠시 대기
            if i < len(target_stocks):
                time.sleep(0.5)
        
        # 결과 요약
        success_count = sum(1 for success in results.values() if success)
        logger.info(f"🏁 전체 처리 완료: {success_count}/{len(target_stocks)} 성공")
        
        return results


def create_parser() -> argparse.ArgumentParser:
    """명령행 인자 파서를 생성합니다."""
    parser = argparse.ArgumentParser(
        description='주식 데이터 테스트 파일 생성 도구 (시뮬레이션용)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
🔄 수정된 사용 예시 (base_date 제거됨):
  # 삼성전자 5분봉 2년치 데이터 (현재 날짜 기준 과거 2년)
  python prepare_test_data.py --timeframe minute --stock_code 005930 --period 2y --interval 5
  
  # 삼성전자 일봉 2년치 데이터
  python prepare_test_data.py --timeframe daily --stock_code 005930 --period 2y
  
  # 30개 타겟 종목 일봉 2년치 데이터
  python prepare_test_data.py --timeframe daily --period 2y --all-targets
  
  # 분봉 1주일치 데이터
  python prepare_test_data.py --timeframe minute --stock_code 005930 --period 5d --interval 5

📁 생성되는 파일명:
  - {stock_code}_{timeframe}_full.parquet
  - 예: 005930_5m_full.parquet, 005930_1h_full.parquet, 005930_d_full.parquet

🎯 목적:
  - 시뮬레이션용 충분한 과거 데이터 준비
  - 타임존 처리 표준화 (UTC 기준 naive 형식)
  - base_date는 시뮬레이션 실행 시 Airflow Variables로 설정

기간 형식:
  분봉: 1d(1일), 5d(5일), 1w(1주), 1m(1개월), 2y(2년)
  일봉: 1y(1년), 2y(2년), 6m(6개월), 30d(30일)
  주봉: 2y(2년), 3y(3년), 52w(52주), 12m(12개월)
        """
    )
    
    # 필수 인자
    parser.add_argument(
        '--timeframe',
        required=True,
        choices=['minute', 'daily', 'weekly', 'monthly'],
        help='데이터 타임프레임'
    )
    
    parser.add_argument(
        '--period',
        required=True,
        help='조회 기간 (예: 1d, 5d, 1w, 1m, 1y, 2y) - 현재 날짜 기준 과거'
    )
    
    # 선택적 인자
    parser.add_argument(
        '--stock_code',
        help='종목 코드 (예: 005930)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        choices=[1, 3, 5, 10, 15, 30, 60],
        help='분봉 간격 (기본값: 5분)'
    )
    
    parser.add_argument(
        '--all-targets',
        action='store_true',
        help='30개 타겟 종목 전체 처리'
    )
    
    return parser


def validate_args(args) -> bool:
    """명령행 인자를 검증합니다."""
    
    # 1. 종목 코드 또는 전체 타겟 중 하나는 필수
    if not args.stock_code and not getattr(args, 'all_targets', False):
        logger.error("❌ --stock_code 또는 --all-targets 중 하나는 필수입니다.")
        return False
    
    # 2. 기간 형식 검증 (base_date 검증 제거됨)
    period_pattern = r'^(\d+[ymdwh])+$|^\d+$'
    if not re.match(period_pattern, args.period):
        logger.error(f"❌ 잘못된 기간 형식: {args.period} (예: 1d, 5d, 1w, 1m, 1y, 2y)")
        return False
    
    # 3. 분봉에서만 interval 의미있음
    if args.timeframe != 'minute' and args.interval != 5:
        logger.warning(f"⚠️ {args.timeframe}에서는 interval 파라미터가 무시됩니다.")
    
    return True


def main():
    """메인 함수"""
    try:
        # 1. 인자 파싱
        parser = create_parser()
        args = parser.parse_args()
        
        # 2. 인자 검증
        if not validate_args(args):
            parser.print_help()
            sys.exit(1)
        
        # 3. 처리 준비
        preparer = StockDataPreparer()
        
        logger.info("=" * 60)
        logger.info("🚀 시뮬레이션용 주식 데이터 생성 시작")
        logger.info(f"📋 타임프레임: {args.timeframe}")
        logger.info(f"⏰ 조회 기간: {args.period} (현재 날짜 기준 과거)")
        if args.timeframe == 'minute':
            logger.info(f"🕐 분봉 간격: {args.interval}분")
        logger.info(f"📁 파일명 형식: {{stock_code}}_{{timeframe}}_full.parquet")
        logger.info("🕐 타임존 처리: UTC 기준 naive 형식으로 표준화")
        logger.info("=" * 60)
        
        # 4. 데이터 처리
        if getattr(args, 'all_targets', False):
            # 전체 타겟 처리 (base_date 매개변수 제거)
            results = preparer.process_all_targets(
                timeframe=args.timeframe,
                period=args.period,
                interval=args.interval
            )
            
            # 결과 출력
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"🏁 전체 처리 결과: {success_count}/{len(results)} 성공")
            
            if success_count == 0:
                sys.exit(1)
                
        else:
            # 단일 종목 처리 (base_date 매개변수 제거)
            success = preparer.process_single_stock(
                timeframe=args.timeframe,
                stock_code=args.stock_code,
                period=args.period,
                interval=args.interval
            )
            
            if not success:
                logger.error(f"❌ {args.stock_code} 처리 실패")
                sys.exit(1)
            else:
                logger.info(f"✅ {args.stock_code} 처리 완료")
        
        logger.info("🎉 모든 작업이 완료되었습니다!")
        
    except KeyboardInterrupt:
        logger.info("\n⏹️ 사용자에 의해 중단되었습니다.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ 예상치 못한 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main() 