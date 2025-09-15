"""
TradeSmartAI 데이터 수집 핵심 엔진

이 모듈은 TradeSmartAI 프로젝트의 데이터 수집 핵심 로직을 구현합니다.
Apache Airflow DAG 환경과 로컬 CLI 환경 모두에서 동작하며,
LIVE 모드(키움 API)와 SIMULATION 모드(Parquet 파일)를 지원합니다.

주요 기능:
- load_initial_history: 과거 데이터 대량 적재
- collect_and_store_candles: 최신 데이터 증분 수집 (멱등성 보장)
- CLI 인터페이스: initial, incremental 서브커맨드
"""

import os
import sys
import argparse
import logging
import pandas as pd
import time
from datetime import datetime, timedelta
from typing import Optional, List, Tuple
from zoneinfo import ZoneInfo
from pathlib import Path
import re


# 프로젝트 루트 디렉토리를 Python path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 로컬 모듈 임포트
from src.database import SessionLocal, Candle, Stock
from src.kiwoom_api.services.chart import get_minute_chart, get_daily_chart, get_weekly_chart
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 상수 정의
TIMEFRAME_TO_MINUTES = {
    '5m': 5,
    '30m': 30,
    '1h': 60
}

TIMEFRAME_TO_DB_FORMAT = {
    '5m': 'M5', 
    '30m': 'M30',
    '1h': 'H1',
    'd': 'D',
    'w': 'W'
}

TIMEFRAME_TO_LABEL = {
    '5m': '5분',
    '30m': '30분', 
    '1h': '1시간',
    'd': '일',
    'w': '주'
}

# 타임프레임별 최적화된 기본 기간 매핑
TIMEFRAME_DEFAULT_PERIODS = {
    '5m': '30d',    # 5분봉: 30일 (약 8,640개 캔들)
    '30m': '6m',    # 30분봉: 6개월 (약 8,760개 캔들)
    '1h': '1y',     # 1시간봉: 1년 (약 8,760개 캔들)
    'd': '5y',      # 일봉: 5년 (약 1,825개 캔들)
    'w': '10y'      # 주봉: 10년 (약 520개 캔들)
}

def _db_upsert_candles(db: Session, stock_code: str, timeframe: str, df_candles: pd.DataFrame, execution_mode: str = 'LIVE') -> int:
    """
    DataFrame 형태의 캔들 데이터를 Candle 테이블에 UPSERT 합니다.
    stock_code, timestamp, timeframe 기준으로 중복 체크 및 삽입을 수행합니다.
    
    Args:
        db (Session): DB 세션
        stock_code (str): 종목 코드
        timeframe (str): 타임프레임 (5m, 30m, 1h, d, w)
        df_candles (pd.DataFrame): 캔들 데이터 DataFrame
        
    Returns:
        int: 새로 삽입된 캔들 데이터 개수
    """
    if df_candles is None or df_candles.empty:
        logger.info(f"[{stock_code}] DB에 저장할 캔들 데이터가 없습니다.")
        return 0

    # 모드에 따라 사용할 스키마를 결정하고 테이블 객체에 적용합니다.
    target_schema = 'simulation' if execution_mode == 'SIMULATION' else 'live'
    Stock.__table__.schema = target_schema
    Candle.__table__.schema = target_schema
    logger.info(f"Target schema set to: {target_schema}")

    logger.info(f"[{stock_code}] {len(df_candles)}개 캔들 데이터 DB 저장 시작...")
    
    upserted_count = 0
    try:
        # 기존 데이터 조회 (배치로 한번에)
        timeframe_str = TIMEFRAME_TO_DB_FORMAT.get(timeframe, timeframe)
        
        # DataFrame에서 timestamp 추출 (data_collector_test.py 방식 적용)
        timestamps = []
        for idx, row in df_candles.iterrows():
            if 'timestamp' in df_candles.columns:
                timestamp = row['timestamp']
            else:
                timestamp = idx  # DataFrame 인덱스 사용 (키움 API 방식)
            
            if not isinstance(timestamp, datetime):
                timestamp = pd.Timestamp(timestamp).to_pydatetime()
            
            timestamps.append(timestamp)
        
        # 기존 데이터 배치 조회
        existing_timestamps = set()
        if timestamps:
            existing_candles = db.query(Candle.timestamp).filter(
                Candle.stock_code == stock_code,
                Candle.timeframe == timeframe_str,
                Candle.timestamp.in_(timestamps)
            ).all()
            existing_timestamps = {candle.timestamp for candle in existing_candles}
            logger.info(f"[{stock_code}] 기존 데이터 {len(existing_timestamps)}개 발견")
        
        # 새로운 데이터만 삽입
        new_candles = []
        for i, (idx, row) in enumerate(df_candles.iterrows()):
            # 타임스탬프 추출 (data_collector_test.py 방식 적용)
            if 'timestamp' in df_candles.columns:
                timestamp = row['timestamp']
            else:
                timestamp = idx  # DataFrame 인덱스 사용 (키움 API 방식)
            
            if not isinstance(timestamp, datetime):
                timestamp = pd.Timestamp(timestamp).to_pydatetime()
            
            candle_timestamp = timestamp
            
            # timezone-naive 타임스탬프를 KST로 localize
            if candle_timestamp.tzinfo is None:
                candle_timestamp = candle_timestamp.replace(tzinfo=ZoneInfo('Asia/Seoul'))
            
            # KST tz-aware를 UTC로 변환하여 기존 데이터와 비교
            candle_timestamp_utc = candle_timestamp.astimezone(ZoneInfo('UTC'))
            
            if candle_timestamp_utc not in existing_timestamps:
                # 컬럼명 매핑 (키움 API 응답 형식 지원)
                open_val = (float(row['Open']) if 'Open' in row else 
                           float(row['open']) if 'open' in row else 
                           float(row['open_pric']) if 'open_pric' in row else None)
                
                high_val = (float(row['High']) if 'High' in row else 
                           float(row['high']) if 'high' in row else 
                           float(row['high_pric']) if 'high_pric' in row else None)
                
                low_val = (float(row['Low']) if 'Low' in row else 
                          float(row['low']) if 'low' in row else 
                          float(row['low_pric']) if 'low_pric' in row else None)
                
                close_val = (float(row['Close']) if 'Close' in row else 
                            float(row['close']) if 'close' in row else 
                            float(row['cur_prc']) if 'cur_prc' in row else None)
                
                volume_val = (int(row['Volume']) if 'Volume' in row else 
                             int(row['volume']) if 'volume' in row else 
                             int(row['trde_qty']) if 'trde_qty' in row else None)
                
                if None in [open_val, high_val, low_val, close_val, volume_val]:
                    logger.error(f"[{stock_code}] 필수 컬럼 값을 찾을 수 없습니다. 사용 가능한 컬럼: {list(row.index)}")
                    continue
                
                new_candle = Candle(
                    stock_code=stock_code,
                    timestamp=candle_timestamp,  # KST tz-aware 저장 (PostgreSQL이 자동으로 UTC로 정규화)
                    timeframe=timeframe_str,
                    open=open_val,
                    high=high_val,
                    low=low_val,
                    close=close_val,
                    volume=volume_val
                )
                new_candles.append(new_candle)
        
        # 배치 삽입
        if new_candles:
            db.add_all(new_candles)
            upserted_count = len(new_candles)
            logger.info(f"[{stock_code}] {upserted_count}개 신규 캔들 데이터 삽입 중...")
            db.commit()
            logger.info(f"[{stock_code}] {upserted_count}개의 신규 캔들 데이터가 DB에 커밋되었습니다.")
        else:
            logger.info(f"[{stock_code}] 모든 데이터가 이미 존재합니다. 새로 추가된 데이터 없음.")
            
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"[{stock_code}] DB 저장/커밋 중 SQLAlchemy 오류 발생: {e}")
        raise  
    except KeyError as e:
        db.rollback()
        logger.error(f"[{stock_code}] DataFrame에 필요한 컬럼({e})이 없습니다. 사용 가능한 컬럼: {list(df_candles.columns)}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{stock_code}] DB 저장 중 예기치 않은 오류 발생: {e}")
        raise
        
    return upserted_count

def _parse_period(period: str, timeframe: str) -> int:
    """
    기간 문자열과 타임프레임을 기반으로 요청할 캔들 개수를 계산합니다.

    Args:
        period (str): 기간 문자열 (예: '30d', '6m', '2y', '10w') 또는 None
        timeframe (str): 타임프레임 (예: '5m', '30m', '1h', 'd', 'w')
    
    Returns:
        int: 요청할 캔들 개수 (최소 1개 보장)
    
    Raises:
        ValueError: 지원하지 않는 타임프레임이거나 잘못된 기간 형식
        TypeError: period가 문자열이 아닌 경우
    
    Examples:
        >>> _parse_period('30d', '5m')
        2340  # 30일 × 78개/일 = 2,340개
        >>> _parse_period('6m', '30m') 
        1638  # 6개월 × 21일/월 × 13개/일 = 1,638개
        >>> _parse_period('5y', 'd')
        1260  # 5년 × 252일/년 × 1개/일 = 1,260개
        >>> _parse_period(None, '5m')
        2340  # 기본값 30d 사용
    """
    # 입력 검증
    if not isinstance(timeframe, str):
        raise TypeError(f"timeframe은 문자열이어야 합니다: {type(timeframe)}")
    
    timeframe = timeframe.lower()
    
    # period가 None이거나 빈 문자열인 경우 기본값 사용
    if not period:
        period = TIMEFRAME_DEFAULT_PERIODS.get(timeframe, '1y')
        print(f"⚠️ period가 지정되지 않아 기본값 사용: {timeframe} → {period}")
    
    if not isinstance(period, str):
        raise TypeError(f"period는 문자열이어야 합니다: {type(period)}")
    
    period = period.lower().strip()
    total_days = 0

    # 1. 기간 문자열을 총 '거래일 수'로 변환
    try:
        if 'y' in period:
            match = re.search(r'(\d+)y', period)
            if not match:
                raise ValueError(f"잘못된 연도 형식: {period}")
            years = int(match.group(1))
            total_days = years * 252  # 1년 = 약 252 거래일
            
        elif 'm' in period:
            match = re.search(r'(\d+)m', period)
            if not match:
                raise ValueError(f"잘못된 월 형식: {period}")
            months = int(match.group(1))
            total_days = months * 21   # 1개월 = 약 21 거래일
            
        elif 'w' in period:
            match = re.search(r'(\d+)w', period)
            if not match:
                raise ValueError(f"잘못된 주 형식: {period}")
            weeks = int(match.group(1))
            total_days = weeks * 5     # 1주 = 5 거래일
            
        elif 'd' in period:
            match = re.search(r'(\d+)d', period)
            if not match:
                raise ValueError(f"잘못된 일 형식: {period}")
            days = int(match.group(1))
            total_days = days
            
        else:
            # 숫자만 있는 경우 일수로 취급
            total_days = int(period)
            
    except ValueError as e:
        raise ValueError(f"잘못된 기간 형식 '{period}': {str(e)}")
    except Exception as e:
        raise ValueError(f"기간 파싱 중 오류 발생 '{period}': {str(e)}")

    # 2. 주봉(w)은 특별 처리: 거래일 수를 주 수로 변환
    if timeframe == 'w':
        # 1주는 5거래일이므로, 총 거래일을 5로 나눈 값이 주봉 캔들 수
        return max(1, total_days // 5)

    # 3. 타임프레임별 하루당 캔들 수 정의 (한국 주식시장 기준)
    candles_per_day = {
        '5m': 78,   # (6시간 30분 * 60분) / 5분 = 78개
        '30m': 13,  # (6.5시간 * 60) / 30분 = 13개
        '1h': 7,    # (6.5시간 * 60) / 60분 = 6.5개 → 올림 처리
        'd': 1,     # 일봉은 하루에 1개
    }
    
    if timeframe not in candles_per_day:
        raise ValueError(f"지원하지 않는 타임프레임: {timeframe}")

    # 4. 최종 캔들 수 계산: (총 거래일 수) * (하루당 캔들 수)
    total_candles = total_days * candles_per_day[timeframe]
    
    # 5. 최소값 보장 및 결과 반환
    result = max(1, int(total_candles))
    
    # 디버깅을 위한 로그 (선택사항)
    print(f" 기간 계산: {period} ({timeframe}) → {total_days}일 → {result}개 캔들")
    
    return result

def _calculate_start_date(end_date: str, period: str) -> str:
    """
    종료일과 기간을 기반으로 시작일을 계산합니다.
    
    Args:
        end_date (str): 종료일 (YYYYMMDD)
        period (str): 기간 문자열 (예: '2y', '6m', '30d')
        
    Returns:
        str: 시작일 (YYYYMMDD)
    """
    days = _parse_period(period, 'd') # 일봉 기준으로 파싱
    end_date_obj = datetime.strptime(end_date, '%Y%m%d')
    
    # 거래일을 달력일로 변환 (주말 고려)
    calendar_days = int(days * 1.4)
    start_date_obj = end_date_obj - timedelta(days=calendar_days)
    
    return start_date_obj.strftime('%Y%m%d')

def _load_simulation_data(stock_code: str, timeframe: str, execution_time: str = None) -> pd.DataFrame:
    """
    시뮬레이션 모드에서 Parquet 파일로부터 데이터를 로드합니다.
    prepare_test_data.py에서 생성한 파일 형식에 맞춰 파일을 찾습니다.
    
    Args:
        stock_code (str): 종목 코드
        timeframe (str): 타임프레임 (5m, 30m, 1h, d, w)
        execution_time (str, optional): 실행 시간 (YYYYMMDDHHMMSS)
        
    Returns:
        pd.DataFrame: 시뮬레이션 데이터 (서울 시간으로 변환됨)
    """
    # 올바른 시뮬레이션 데이터 디렉토리 경로
    simulation_data_dir = Path("data/simulation")
    
    # prepare_test_data.py에서 생성한 파일명 패턴: {stock_code}_{timeframe}_full.parquet
    # timeframe 변수를 그대로 사용 (매핑 로직 제거)
    parquet_file = simulation_data_dir / f"{stock_code}_{timeframe}_full.parquet"
    
    # 파일 존재 여부 확인
    if not parquet_file.exists():
        logger.warning(f"시뮬레이션 데이터 파일을 찾을 수 없습니다: {parquet_file}")
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(parquet_file)
        logger.info(f"시뮬레이션 파일 로드: {parquet_file.name}, 원본 데이터: {len(df)}개")
        
        # 🔥 타임존 변환: "저장은 UTC, 사용은 로컬 타임존" 황금률 적용
        if hasattr(df.index, 'tz'):
            # 타임존 처리 (PostgreSQL과 동일한 원칙)
            if df.index.tz is None:
                # 기존 파일 호환성: naive를 UTC로 가정
                df.index = df.index.tz_localize('UTC')
                logger.info("타임존 변환: Timezone-naive → UTC (기존 파일 호환성)")
            
            # UTC → Asia/Seoul로 변환 (PostgreSQL과 동일)
            df.index = df.index.tz_convert(ZoneInfo('Asia/Seoul'))
            logger.info("타임존 변환: UTC → Asia/Seoul")
        else:
            logger.warning("DataFrame 인덱스가 datetime이 아닙니다. 타임존 변환을 건너뜁니다.")
        
        # execution_time이 지정된 경우 해당 시간까지의 데이터만 필터링
        # 이것이 핵심: 시뮬레이션에서 "현재 시간"까지의 데이터만 보여줌
        if execution_time:
            execution_dt = pd.to_datetime(execution_time, format='%Y%m%d%H%M%S')
            # execution_dt를 서울 시간으로 설정
            execution_dt = execution_dt.tz_localize(ZoneInfo('Asia/Seoul'))
            
            # 필터링 전 데이터 개수
            original_count = len(df)
            df = df[df.index <= execution_dt]
            
            logger.info(f"시간 필터링: {execution_time} 이전 데이터만 선택")
            logger.info(f"필터링 결과: {original_count}개 → {len(df)}개")
        
        logger.info(f"시뮬레이션 데이터 로드 완료: {len(df)}개 레코드 (서울 시간)")
        return df
        
    except Exception as e:
        logger.error(f"시뮬레이션 데이터 로드 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return pd.DataFrame()

def load_initial_history(stock_code: str, timeframe: str, base_date: str = None, period: str = None, execution_mode: str = 'LIVE') -> bool:
    """과거의 특정 기간 데이터를 대량으로 조회하여 DB에 저장합니다.

    `base_date`와 `period`를 조합하여 조회 기간을 결정합니다.
    
    Args:
        stock_code (str): 종목 코드
        timeframe (str): 시간 간격 (예: '5m', 'd')
        base_date (str, optional): 데이터 조회의 기준일(YYYYMMDD). None이면 현재 날짜.
        period (str, optional): 기준일로부터의 과거 기간 (예: '2y', '6m'). None이면 API 허용 최장 기간.
        execution_mode (str, optional): 실행 모드 ('LIVE' or 'SIMULATION'). Defaults to 'LIVE'.

    Returns:
        bool: 1개 이상의 데이터 저장 시 True, 그 외 False.
    """
    # 타임프레임별 최적화된 기간 적용
    if period is None:
        period = TIMEFRAME_DEFAULT_PERIODS.get(timeframe, '2y')
        logger.info(f"타임프레임별 최적화 기간 적용: {timeframe} -> {period}")
    
    logger.info(f"초기 이력 데이터 적재 시작: {stock_code} ({TIMEFRAME_TO_LABEL.get(timeframe, timeframe)})")
    logger.info(f"실행 모드: {execution_mode}, 기준일: {base_date}, 기간: {period}")
    
    # Candle 모델에만 동적으로 스키마를 설정합니다. Stock은 항상 'live'를 사용합니다.
    if execution_mode == 'SIMULATION':
        Candle.__table__.schema = 'simulation'
    else:
        # 명시적으로 live로 설정하여 다른 DAG 실행에 영향이 없도록 합니다.
        Candle.__table__.schema = 'live'

    logger.info(f"Target schema for Candles set to: {Candle.__table__.schema}")
    
    db: Session = SessionLocal()
    try:
        # 종목코드 유효성 검사
        stock_info = db.query(Stock).filter_by(stock_code=stock_code).first()
        if not stock_info:
            logger.error(f"[{stock_code}] DB에 존재하지 않는 종목코드입니다.")
            logger.error("종목 정보를 먼저 적재해주세요. (예: python src/stock_info_collector.py)")
            return False
        
        # 기준일 설정
        if base_date is None:
            base_date = datetime.now().strftime('%Y%m%d')
        
        # 기간 계산
        num_candles = _parse_period(period, timeframe)
        
        df_candles = pd.DataFrame()
        
        if execution_mode == 'LIVE':
            # 키움 API 호출
            logger.info(f"[{stock_code}] 키움 API 호출: {num_candles}개 캔들 요청")
            
            if timeframe in ['5m', '30m', '1h']:
                # 분봉 데이터
                interval_minutes = TIMEFRAME_TO_MINUTES[timeframe]
                chart_data_obj = get_minute_chart(
                    stock_code=stock_code,
                    interval=str(interval_minutes),
                    base_date=base_date,
                    num_candles=num_candles,
                    auto_pagination=True
                )
            elif timeframe == 'd':
                # 일봉 데이터
                chart_data_obj = get_daily_chart(
                    stock_code=stock_code,
                    base_date=base_date,
                    num_candles=num_candles,
                    auto_pagination=True
                )
            elif timeframe == 'w':
                # 주봉 데이터
                chart_data_obj = get_weekly_chart(
                    stock_code=stock_code,
                    base_date=base_date,
                    num_candles=num_candles,
                    auto_pagination=True
                )
            else:
                logger.error(f"지원하지 않는 타임프레임: {timeframe}")
                return False
            
            # API 호출 제한
            time.sleep(0.2)
            
            if chart_data_obj and chart_data_obj.data:
                # 일봉 데이터도 전처리 활성화 (날짜 인덱스 설정)
                chart_data_obj.preprocessing_required = True
                df_candles = chart_data_obj.to_dataframe()
                logger.info(f"[{stock_code}] API 응답 데이터 개수: {len(df_candles)}")
            else:
                logger.warning(f"[{stock_code}] API로부터 데이터를 가져오지 못했습니다.")
                return False
                
        elif execution_mode == 'SIMULATION':
            # 시뮬레이션 데이터 로드
            logger.info(f"[{stock_code}] 시뮬레이션 데이터 로드")
                        
            # 👇 [수정] _load_simulation_data 호출 시 base_date를 execution_time으로 전달합니다.
            # 이렇게 하면 데이터를 로드하는 단계에서부터 필터링이 이루어집니다.
            base_datetime_str = base_date + "235959" # 해당 날짜의 자정 직전까지 포함
            df_candles = _load_simulation_data(stock_code, timeframe, execution_time=base_datetime_str)
                       
            if df_candles.empty:
                logger.warning(f"[{stock_code}] 시뮬레이션 데이터가 없습니다.")
                return False
                
            # 기간 필터링
            if period:
                start_date = _calculate_start_date(base_date, period)
                start_dt = pd.to_datetime(start_date, format='%Y%m%d')
                # 타임존을 Asia/Seoul로 설정하여 비교 (df_candles.index는 이미 Asia/Seoul)
                start_dt = start_dt.tz_localize(ZoneInfo('Asia/Seoul'))
                df_candles = df_candles[df_candles.index >= start_dt]
                
            logger.info(f"[{stock_code}] 시뮬레이션 데이터 로드 완료: {len(df_candles)}개")
        
        else:
            logger.error(f"지원하지 않는 실행 모드: {execution_mode}")
            return False
        
        # 데이터 검증
        if df_candles.empty:
            logger.warning(f"[{stock_code}] 적재할 데이터가 없습니다.")
            return False
        
        # DB 저장
        upserted_count = _db_upsert_candles(db, stock_code, timeframe, df_candles, execution_mode=execution_mode)
        
        if upserted_count > 0:
            logger.info(f"[{stock_code}] 초기 이력 데이터 적재 완료: {upserted_count}개")
            return True
        else:
            logger.info(f"[{stock_code}] 새로 추가된 데이터가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"[{stock_code}] 초기 이력 데이터 적재 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if db:
            db.close()

def collect_and_store_candles(stock_code: str, timeframe: str, execution_mode: str, execution_time: str | None = None) -> bool:
    """DB의 마지막 데이터 이후 최신 데이터를 수집하여 저장합니다. (멱등성 보장)

    - DB에 해당 종목/타임프레임의 데이터가 없으면 작업을 수행하지 않습니다.
    
    Args:
        stock_code (str): 종목 코드
        timeframe (str): 시간 간격 (예: '5m', 'd')
        execution_mode (str): 실행 모드 ('LIVE' or 'SIMULATION')
        execution_time (str | None, optional): SIMULATION 모드의 기준 시간 (YYYYMMDDHHMMSS). Defaults to None.

    Returns:
        bool: 1개 이상의 신규 데이터 저장 시 True, 그 외 False.
    """
    logger.info(f"증분 업데이트 시작: {stock_code} ({TIMEFRAME_TO_LABEL.get(timeframe, timeframe)})")
    logger.info(f"실행 모드: {execution_mode}, 실행 시간: {execution_time}")
    
    # Candle 모델에만 동적으로 스키마를 설정합니다. Stock은 항상 'live'를 사용합니다.
    if execution_mode == 'SIMULATION':
        Candle.__table__.schema = 'simulation'
    else:
        Candle.__table__.schema = 'live'

    logger.info(f"Target schema for Candles set to: {Candle.__table__.schema}")
    
    db: Session = SessionLocal()
    try:
        # 종목코드 유효성 검사
        stock_info = db.query(Stock).filter_by(stock_code=stock_code).first()
        if not stock_info:
            logger.error(f"[{stock_code}] DB에 존재하지 않는 종목코드입니다.")
            logger.error("종목 정보를 먼저 적재해주세요. (예: python src/stock_info_collector.py)")
            return False
        
        # DB에서 해당 종목/타임프레임의 가장 최신 캔들 조회
        timeframe_str = TIMEFRAME_TO_DB_FORMAT.get(timeframe, timeframe)
        latest_candle = db.query(Candle).filter(
            Candle.stock_code == stock_code,
            Candle.timeframe == timeframe_str
        ).order_by(Candle.timestamp.desc()).first()
        
        if not latest_candle:
            logger.warning(f"[{stock_code}] DB에 기존 데이터가 없습니다. 초기 적재를 먼저 수행해주세요.")
            return False
        
        # 최신 캔들 타임스탬프 (KST)
        latest_db_timestamp = latest_candle.timestamp.astimezone(ZoneInfo('Asia/Seoul'))
        logger.info(f"[{stock_code}] DB 최신 캔들: {latest_db_timestamp.strftime('%Y%m%d%H%M%S')}")
        
        df_new_candles = pd.DataFrame()
        
        if execution_mode == 'LIVE':
            # 키움 API 호출
            logger.info(f"[{stock_code}] 키움 API 호출: 최신 데이터 조회")
            
            if timeframe in ['5m', '30m', '1h']:
                # 분봉 데이터
                interval_minutes = TIMEFRAME_TO_MINUTES[timeframe]
                chart_data_obj = get_minute_chart(
                    stock_code=stock_code,
                    interval=str(interval_minutes),
                    base_date=None,  # 최신 데이터 요청
                    num_candles=500,  # 충분한 개수로 요청
                    auto_pagination=False
                )
            elif timeframe == 'd':
                # 일봉 데이터
                chart_data_obj = get_daily_chart(
                    stock_code=stock_code,
                    base_date=None,
                    num_candles=30,  # 최근 30일
                    auto_pagination=False
                )
            elif timeframe == 'w':
                # 주봉 데이터
                chart_data_obj = get_weekly_chart(
                    stock_code=stock_code,
                    base_date=None,
                    num_candles=10,  # 최근 10주
                    auto_pagination=False
                )
            else:
                logger.error(f"지원하지 않는 타임프레임: {timeframe}")
                return False
            
            # API 호출 제한
            time.sleep(0.2)
            
            if chart_data_obj and chart_data_obj.data:
                # 일봉 데이터도 전처리 활성화 (날짜 인덱스 설정)
                chart_data_obj.preprocessing_required = True
                df_all_candles = chart_data_obj.to_dataframe()
                logger.info(f"[{stock_code}] API 응답 데이터 개수: {len(df_all_candles)}")
                
                # DB 이후의 신규 데이터 필터링
                if not df_all_candles.empty:
                    mask = df_all_candles.index > latest_db_timestamp
                    df_new_candles = df_all_candles[mask].copy()
                    
                    if not df_new_candles.empty:
                        logger.info(f"[{stock_code}] 신규 데이터 {len(df_new_candles)}개 발견")
                    else:
                        logger.info(f"[{stock_code}] 신규 데이터가 없습니다.")
                        
            else:
                logger.warning(f"[{stock_code}] API로부터 데이터를 가져오지 못했습니다.")
                return False
                
        elif execution_mode == 'SIMULATION':
            # 시뮬레이션 데이터 로드
            logger.info(f"[{stock_code}] 시뮬레이션 데이터 로드")
            df_all_candles = _load_simulation_data(stock_code, timeframe, execution_time)
            
            if df_all_candles.empty:
                logger.warning(f"[{stock_code}] 시뮬레이션 데이터가 없습니다.")
                return False
            
            # DB 이후의 신규 데이터 필터링
            mask = df_all_candles.index > latest_db_timestamp
            df_new_candles = df_all_candles[mask].copy()
            
            if not df_new_candles.empty:
                logger.info(f"[{stock_code}] 시뮬레이션 신규 데이터 {len(df_new_candles)}개 발견")
            else:
                logger.info(f"[{stock_code}] 시뮬레이션 신규 데이터가 없습니다.")
                
        else:
            logger.error(f"지원하지 않는 실행 모드: {execution_mode}")
            return False
        
        # 신규 데이터 저장
        if df_new_candles.empty:
            logger.info(f"[{stock_code}] 저장할 신규 데이터가 없습니다.")
            return False
        
        # DB 저장
        upserted_count = _db_upsert_candles(db, stock_code, timeframe, df_new_candles, execution_mode=execution_mode)
        
        if upserted_count > 0:
            logger.info(f"[{stock_code}] 증분 업데이트 완료: {upserted_count}개")
            return True
        else:
            logger.info(f"[{stock_code}] 새로 추가된 데이터가 없습니다.")
            return False
            
    except Exception as e:
        logger.error(f"[{stock_code}] 증분 업데이트 중 오류 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False
    finally:
        if db:
            db.close()

def main():
    """CLI 메인 함수"""
    parser = argparse.ArgumentParser(description='TradeSmartAI 데이터 수집 엔진')
    subparsers = parser.add_subparsers(dest='command', help='사용 가능한 명령')
    
    # initial 서브커맨드
    initial_parser = subparsers.add_parser('initial', help='초기 데이터 적재')
    initial_parser.add_argument('stock_code', help='종목 코드')
    initial_parser.add_argument('timeframe', choices=['5m', '30m', '1h', 'd', 'w'], help='타임프레임')
    initial_parser.add_argument('--base-date', help='기준일 (YYYYMMDD)')
    initial_parser.add_argument('--period', help='기간 (예: 2y, 6m, 30d)')
    initial_parser.add_argument('--mode', choices=['LIVE', 'SIMULATION'], default='LIVE', help='실행 모드')
    
    # incremental 서브커맨드
    incremental_parser = subparsers.add_parser('incremental', help='증분 업데이트')
    incremental_parser.add_argument('stock_code', help='종목 코드')
    incremental_parser.add_argument('timeframe', choices=['5m', '30m', '1h', 'd', 'w'], help='타임프레임')
    incremental_parser.add_argument('--mode', choices=['LIVE', 'SIMULATION'], default='LIVE', help='실행 모드')
    incremental_parser.add_argument('--execution-time', help='실행 시간 (SIMULATION 모드, YYYYMMDDHHMMSS)')
    
    args = parser.parse_args()
    
    if args.command == 'initial':
        success = load_initial_history(
            stock_code=args.stock_code,
            timeframe=args.timeframe,
            base_date=args.base_date,
            period=args.period,
            execution_mode=args.mode
        )
        
        if success:
            logger.info("초기 데이터 적재가 성공적으로 완료되었습니다.")
            sys.exit(0)
        else:
            logger.error("초기 데이터 적재가 실패했습니다.")
            sys.exit(1)
            
    elif args.command == 'incremental':
        success = collect_and_store_candles(
            stock_code=args.stock_code,
            timeframe=args.timeframe,
            execution_mode=args.mode,
            execution_time=args.execution_time
        )
        
        if success:
            logger.info("증분 업데이트가 성공적으로 완료되었습니다.")
            sys.exit(0)
        else:
            logger.error("증분 업데이트가 실패했습니다.")
            sys.exit(1)
            
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == '__main__':
    main()