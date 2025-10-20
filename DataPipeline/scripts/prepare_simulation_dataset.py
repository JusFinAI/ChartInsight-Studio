#!/usr/bin/env python3
"""Prepare simulation dataset (Parquet) - restored class-based implementation

This file is a refactored, class-based restoration of the original
`prepare_test_data.py` helper, adapted to be used as
`DataPipeline/scripts/prepare_simulation_dataset.py` for both local and
containerized execution.

Usage examples:
  python DataPipeline/scripts/prepare_simulation_dataset.py --stock_code 005930 --timeframe monthly --period 5y
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

try:
    import pandas as pd
    import pyarrow as pa  # noqa: F401
    import pyarrow.parquet as pq  # noqa: F401
except ImportError as e:
    print(f"❌ 필수 라이브러리가 설치되지 않았습니다: {e}")
    print("💡 다음 명령어로 설치해주세요:")
    print("   pip install pandas pyarrow")
    sys.exit(1)

# Ensure repository root and DataPipeline/src are on sys.path
repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
src_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src')
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)
if src_path not in sys.path:
    sys.path.insert(0, src_path)
# Also ensure DataPipeline directory is on sys.path so imports like `src.xxx` resolve
data_pipeline_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)))
if data_pipeline_dir not in sys.path:
    sys.path.insert(0, data_pipeline_dir)

from kiwoom_api.services.chart import (
    get_daily_stock_chart, get_minute_chart, get_weekly_stock_chart, get_monthly_stock_chart,
    get_daily_inds_chart, get_weekly_inds_chart, get_monthly_inds_chart,
)

from src.utils.logging_kst import configure_kst_logger

# Use module-level KST logger
logger = configure_kst_logger(__name__)


class StockDataPreparer:
    """주식 데이터 준비 클래스"""

    def __init__(self):
        sim_path = os.getenv("SIMULATION_DATA_PATH", "DataPipeline/data/simulation")
        self.output_dir = Path(sim_path)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 출력 디렉토리 준비: {self.output_dir}")

    def parse_period(self, period_str: str, timeframe: str = 'daily') -> int:
        if not period_str:
            if timeframe == 'minute':
                return 390
            elif timeframe == 'daily':
                return 252
            elif timeframe == 'weekly':
                return 52
            elif timeframe == 'monthly':
                return 12
            else:
                return 100

        total_units = 0

        year_match = re.search(r'(\d+)y', period_str)
        if year_match:
            years = int(year_match.group(1))
            if timeframe == 'minute':
                total_units += years * 252 * 390
            elif timeframe == 'daily':
                total_units += years * 252
            elif timeframe == 'weekly':
                total_units += years * 52
            elif timeframe == 'monthly':
                total_units += years * 12

        month_match = re.search(r'(\d+)m', period_str)
        if month_match:
            months = int(month_match.group(1))
            if timeframe == 'minute':
                total_units += months * 21 * 390
            elif timeframe == 'daily':
                total_units += months * 21
            elif timeframe == 'weekly':
                total_units += months * 4
            elif timeframe == 'monthly':
                total_units += months

        week_match = re.search(r'(\d+)w', period_str)
        if week_match:
            weeks = int(week_match.group(1))
            if timeframe == 'minute':
                total_units += weeks * 5 * 390
            elif timeframe == 'daily':
                total_units += weeks * 5
            elif timeframe == 'weekly':
                total_units += weeks

        day_match = re.search(r'(\d+)d', period_str)
        if day_match:
            days = int(day_match.group(1))
            if timeframe == 'minute':
                total_units += days * 390
            elif timeframe == 'daily':
                total_units += days
            elif timeframe == 'weekly':
                total_units += days // 7

        hour_match = re.search(r'(\d+)h', period_str)
        if hour_match:
            hours = int(hour_match.group(1))
            if timeframe == 'minute':
                total_units += hours * 60
            elif timeframe == 'daily':
                total_units += max(1, hours // 6)
            elif timeframe == 'weekly':
                total_units += max(1, hours // (6 * 5))

        if total_units == 0 and period_str.isdigit():
            total_units = int(period_str)

        return max(1, total_units)

    def get_target_stocks(self, limit: int = 30) -> List[str]:
        stock_codes = []
        kospi_path = Path("data/kospi_code.json")
        kosdaq_path = Path("data/kosdaq_code.json")

        if not kospi_path.exists():
            logger.error(f"❌ KOSPI 파일을 찾을 수 없습니다: {kospi_path}")
            return []
        if not kosdaq_path.exists():
            logger.error(f"❌ KOSDAQ 파일을 찾을 수 없습니다: {kosdaq_path}")
            return []

        try:
            with open(kospi_path, 'r', encoding='utf-8') as f:
                kospi_data = json.load(f)
            with open(kosdaq_path, 'r', encoding='utf-8') as f:
                kosdaq_data = json.load(f)

            target_stocks = []
            for code, info in kospi_data.items():
                if info.get('upSizeName') == '대형주':
                    target_stocks.append(code)
                    if len(target_stocks) >= limit // 2:
                        break

            for code, info in kospi_data.items():
                if info.get('upSizeName') == '중형주' and code not in target_stocks:
                    target_stocks.append(code)
                    if len(target_stocks) >= limit * 3 // 4:
                        break

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
        if timeframe == 'minute':
            if interval == 60:
                return '1h'
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
        try:
            num_candles = self.parse_period(period, timeframe)
            logger.info(f"📊 {stock_code} {timeframe} 데이터 조회 시작 (기간: {period}, 캔들수: {num_candles})")
            chart_data = None

            # 업종/지수 코드(지수 전용 엔드포인트)를 사용할 경우 인덱스 전용 함수를 호출
            inds_codes = {"001", "101", "013", "029", "124"}
            is_inds_code = str(stock_code) in inds_codes

            if timeframe == 'minute':
                chart_data = get_minute_chart(stock_code=stock_code, interval=str(interval), num_candles=num_candles, auto_pagination=True)
            elif timeframe == 'daily':
                if is_inds_code:
                    chart_data = get_daily_inds_chart(inds_code=stock_code, num_candles=num_candles, auto_pagination=True)
                else:
                    chart_data = get_daily_stock_chart(stock_code=stock_code, num_candles=num_candles, auto_pagination=True)
            elif timeframe == 'weekly':
                if is_inds_code:
                    chart_data = get_weekly_inds_chart(inds_code=stock_code, num_candles=num_candles, auto_pagination=True)
                else:
                    chart_data = get_weekly_stock_chart(stock_code=stock_code, num_candles=num_candles, auto_pagination=True)
            elif timeframe == 'monthly':
                if is_inds_code:
                    chart_data = get_monthly_inds_chart(inds_code=stock_code, num_candles=num_candles, auto_pagination=True)
                else:
                    chart_data = get_monthly_stock_chart(stock_code=stock_code, num_candles=num_candles, auto_pagination=True)
            else:
                logger.error(f"❌ 지원하지 않는 타임프레임: {timeframe}")
                return None

            if chart_data:
                chart_data.preprocessing_required = True
            return chart_data
        except Exception as e:
            logger.error(f"❌ {stock_code} 데이터 조회 실패: {e}")
            return None

    def save_to_parquet(self, chart_data, stock_code: str, timeframe: str,
                       interval: int = 1) -> bool:
        try:
            df = chart_data.to_dataframe()
            if df is None or df.empty:
                logger.warning(f"⚠️ {stock_code} 데이터가 비어있습니다.")
                return False

            timeframe_label = self.get_timeframe_label(timeframe, interval)
            filename = f"{stock_code}_{timeframe_label}_full.parquet"
            filepath = self.output_dir / filename

            logger.info(f"타임존 처리 시작: {stock_code}")

            if not isinstance(df.index, pd.DatetimeIndex):
                if 'dt' in df.columns:
                    logger.info(f"일봉/주봉 데이터 처리: 'dt' 컬럼을 DatetimeIndex로 변환합니다.")
                    df.index = pd.to_datetime(df['dt'], format='%Y%m%d')
                else:
                    logger.error(f"❌ {stock_code} 데이터의 인덱스를 DatetimeIndex로 변환할 수 없습니다.")
                    return False
            else:
                logger.info(f"이미 DatetimeIndex로 처리됨 (ChartData에서 처리)")

            if isinstance(df.index, pd.DatetimeIndex):
                if df.index.tz is None:
                    df.index = df.index.tz_localize('Asia/Seoul')
                    logger.info(f"타임존 정보 부여: Naive -> Asia/Seoul")
                else:
                    df.index = df.index.tz_convert('Asia/Seoul')
            else:
                logger.error(f"❌ {stock_code} 데이터의 인덱스를 DatetimeIndex로 변환할 수 없습니다.")
                return False

            df.index = df.index.tz_convert('UTC')
            logger.info(f"타임존 표준화 완료: Asia/Seoul -> UTC (timezone-aware)")

            df.to_parquet(filepath, index=True)

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
        logger.info(f"🚀 {stock_code} 데이터 처리 시작")

        chart_data = self.fetch_chart_data(timeframe, stock_code, period, interval)
        if chart_data is None:
            return False

        success = self.save_to_parquet(chart_data, stock_code, timeframe, interval)
        time.sleep(0.5)
        return success

    def process_all_targets(self, timeframe: str,
                          period: str, interval: int = 1) -> Dict[str, bool]:
        logger.info(f"🎯 타겟 종목 전체 처리 시작 (timeframe: {timeframe}, period: {period})")

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

            if i < len(target_stocks):
                time.sleep(0.5)

        success_count = sum(1 for success in results.values() if success)
        logger.info(f"🏁 전체 처리 완료: {success_count}/{len(target_stocks)} 성공")
        return results


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='주식 데이터 테스트 파일 생성 도구 (시뮬레이션용)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

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

    parser.add_argument('--stock_code', help='종목 코드 (예: 005930)')

    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        choices=[1, 3, 5, 10, 15, 30, 60],
        help='분봉 간격 (기본값: 5분)'
    )

    parser.add_argument('--all-targets', action='store_true', help='30개 타겟 종목 전체 처리')
    return parser


def validate_args(args) -> bool:
    if not args.stock_code and not getattr(args, 'all_targets', False):
        logger.error("❌ --stock_code 또는 --all-targets 중 하나는 필수입니다.")
        return False

    period_pattern = r'^(\d+[ymdwh])+$|^\d+$'
    if not re.match(period_pattern, args.period):
        logger.error(f"❌ 잘못된 기간 형식: {args.period} (예: 1d, 5d, 1w, 1m, 1y, 2y)")
        return False

    if args.timeframe != 'minute' and args.interval != 5:
        logger.warning(f"⚠️ {args.timeframe}에서는 interval 파라미터가 무시됩니다.")

    return True


def main():
    try:
        parser = create_parser()
        args = parser.parse_args()

        if not validate_args(args):
            parser.print_help()
            sys.exit(1)

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

        if getattr(args, 'all_targets', False):
            results = preparer.process_all_targets(
                timeframe=args.timeframe,
                period=args.period,
                interval=args.interval,
            )
            success_count = sum(1 for success in results.values() if success)
            logger.info(f"🏁 전체 처리 결과: {success_count}/{len(results)} 성공")
            if success_count == 0:
                sys.exit(1)
        else:
            success = preparer.process_single_stock(
                timeframe=args.timeframe,
                stock_code=args.stock_code,
                period=args.period,
                interval=args.interval,
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


