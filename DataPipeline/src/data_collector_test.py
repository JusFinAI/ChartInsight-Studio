import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import logging
import pandas as pd
import sys
import os

# 프로젝트 루트 디렉토리를 Python path에 추가
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

# Kiwoom API 서비스
# chart_service 객체를 직접 사용하는 대신, 래퍼 함수를 사용합니다.
from src.kiwoom_api.services.chart import get_minute_chart

# 데이터베이스 관련
from src.database import SessionLocal, Candle, Stock # DB 세션 및 Candle, Stock 모델

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def _db_upsert_candles(db: Session, stock_code: str, timeframe_minutes: int, df_candles: pd.DataFrame) -> int:
    """
    DataFrame 형태의 캔들 데이터를 Candle 테이블에 UPSERT 합니다.
    stock_code, timestamp, timeframe 기준으로 중복 체크 및 삽입을 수행합니다. (업데이트는 생략)
    """
    if df_candles is None or df_candles.empty:
        logger.info(f"[{stock_code}] DB에 저장할 캔들 데이터가 없습니다.")
        return 0

    logger.info(f"[{stock_code}] {len(df_candles)}개 캔들 데이터 DB 저장 시작...")
    
    upserted_count = 0
    try:
        # 기존 데이터 조회 (배치로 한번에)
        timeframe_str = f"M{timeframe_minutes}"
        
        # DataFrame에서 timestamp 추출
        timestamps = []
        for idx, row in df_candles.iterrows():
            if 'timestamp' in df_candles.columns:
                timestamp = row['timestamp']
            else:
                timestamp = idx
            
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
            candle_timestamp = timestamps[i]
            
            if candle_timestamp not in existing_timestamps:
                new_candle = Candle(
                    stock_code=stock_code,
                    timestamp=candle_timestamp,
                    timeframe=timeframe_str,
                    open=float(row['Open']) if 'Open' in row else float(row['open']),
                    high=float(row['High']) if 'High' in row else float(row['high']),
                    low=float(row['Low']) if 'Low' in row else float(row['low']),
                    close=float(row['Close']) if 'Close' in row else float(row['close']),
                    volume=int(row['Volume']) if 'Volume' in row else int(row['volume'])
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
        logger.error(f"[{stock_code}] DataFrame 인덱스 타입: {type(df_candles.index)}")
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"[{stock_code}] DB 저장 중 예기치 않은 오류 발생: {e}")
        raise
        
    return upserted_count

def fetch_and_store_initial_minute_data(stock_code: str, timeframe_minutes: int, base_date_str: str, num_candles: int) -> str | None:
    """
    초기 데이터 적재용. 특정 종목의 지정된 과거 날짜부터 num_candles 개수만큼의 분봉 데이터를 가져와 DB에 저장합니다.
    """
    logger.info(f"초기 분봉 데이터 수집 시작: 종목코드={stock_code}, 간격={timeframe_minutes}분, 기준일={base_date_str}, 개수={num_candles}")

    db: Session = SessionLocal()
    last_collected_timestamp_str = None
    try:
        # 종목코드 유효성 검사 (선택사항)
        stock_info = db.query(Stock).filter_by(stock_code=stock_code).first()
        if not stock_info:
            logger.error(f"[{stock_code}] DB에 존재하지 않는 종목코드입니다.")
            return None

        logger.info(f"[{stock_code}] API 요청: 기준일={base_date_str}, 캔들개수={num_candles}")

        # 키움 API 호출 - 단순하게 num_candles만큼 요청
        chart_data_obj = get_minute_chart(
            stock_code=stock_code,
            interval=str(timeframe_minutes),
            base_date=base_date_str,
            num_candles=num_candles,
            auto_pagination=True  # num_candles만큼 받을 때까지 페이징
        )
        time.sleep(0.2) # API 호출 제한

        if chart_data_obj and chart_data_obj.data:
            logger.info(f"[{stock_code}] API 응답 데이터 개수: {len(chart_data_obj.data)}")
            
            df = chart_data_obj.to_dataframe()
            if df is None or df.empty:
                logger.warning(f"[{stock_code}] API로부터 데이터를 받았으나 DataFrame 변환 결과가 비어있습니다.")
                return None

            logger.info(f"[{stock_code}] DataFrame 크기: {df.shape}")
            logger.info(f"[{stock_code}] DataFrame 컬럼: {df.columns.tolist()}")
            
            if df.empty:
                logger.warning(f"[{stock_code}] 최종 데이터가 없습니다.")
                return None

            logger.info(f"[{stock_code}] 최종 선택된 데이터 {len(df)}개")
            
            _db_upsert_candles(db, stock_code, timeframe_minutes, df)
            
            # 마지막 저장된 캔들의 타임스탬프 반환 (인덱스에서 가져오기)
            last_timestamp = df.index.max()
            last_collected_timestamp_str = last_timestamp.strftime("%Y%m%d%H%M%S")
        else:
            logger.warning(f"[{stock_code}] API로부터 초기 분봉 데이터를 가져오지 못했습니다.")

    except SQLAlchemyError as e:
        logger.error(f"[{stock_code}] 초기 데이터 처리 중 DB 오류: {e}")
    except Exception as e:
        logger.error(f"[{stock_code}] 초기 데이터 처리 중 예외 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if db:
            db.close()
    return last_collected_timestamp_str

def fetch_and_store_next_minute_candle(stock_code: str, timeframe_minutes: int, last_timestamp_str: str = None) -> str | None:
    """
    스마트 증분 업데이트용. API로 최신 데이터를 가져와서 DB의 최신 캔들 이후의 모든 신규 데이터를 배치로 저장합니다.
    
    Args:
        stock_code (str): 종목 코드
        timeframe_minutes (int): 시간 간격(분)
        last_timestamp_str (str, optional): 이전 타임스탬프 (사용하지 않음, 호환성 유지용)
        
    Returns:
        str | None: 새로 저장된 가장 최신 캔들의 타임스탬프 (YYYYMMDDHHMMSS)
    """
    logger.info(f"스마트 증분 업데이트 시작: 종목코드={stock_code}, 간격={timeframe_minutes}분")

    db: Session = SessionLocal()
    new_collected_timestamp_str = None
    try:
        # 1. 종목코드 유효성 검사
        stock_info = db.query(Stock).filter_by(stock_code=stock_code).first()
        if not stock_info:
            logger.error(f"[{stock_code}] DB에 존재하지 않는 종목코드입니다.")
            return None

        # 2. DB에서 해당 종목의 가장 최신 캔들 조회
        timeframe_str = f"M{timeframe_minutes}"
        latest_candle = db.query(Candle).filter(
            Candle.stock_code == stock_code,
            Candle.timeframe == timeframe_str
        ).order_by(Candle.timestamp.desc()).first()
        
        if latest_candle:
            # UTC로 읽어온 타임스탬프를 KST로 변환
            latest_db_timestamp = latest_candle.timestamp.astimezone(ZoneInfo('Asia/Seoul'))
            logger.info(f"[{stock_code}] DB 최신 캔들: {latest_db_timestamp.strftime('%Y%m%d%H%M%S')}")
        else:
            latest_db_timestamp = None
            logger.info(f"[{stock_code}] DB에 기존 캔들 데이터가 없습니다.")

        # 3. 키움 API 호출 - 최신 데이터 가져오기
        logger.info(f"[{stock_code}] API 요청: 최신 분봉 데이터 조회")
        chart_data_obj = get_minute_chart(
            stock_code=stock_code,
            interval=str(timeframe_minutes),
            base_date=None,  # 최신 데이터 요청
            num_candles=900,  # 충분한 개수로 요청
            auto_pagination=False  # 한 페이지만
        )
        time.sleep(0.2)  # API 호출 제한

        if not chart_data_obj or not chart_data_obj.data:
            logger.warning(f"[{stock_code}] API로부터 데이터를 가져오지 못했습니다.")
            return None

        logger.info(f"[{stock_code}] API 응답 데이터 개수: {len(chart_data_obj.data)}")
        
        # 4. DataFrame 변환
        df = chart_data_obj.to_dataframe()
        if df is None or df.empty:
            logger.warning(f"[{stock_code}] DataFrame 변환 결과가 비어있습니다.")
            return None

        # 5. 신규 데이터 필터링 - DB 이후의 모든 신규 데이터!
        if latest_db_timestamp is not None:
            # DB에 데이터가 있는 경우: DB 최신 캔들 이후의 모든 신규 데이터 선택
            logger.info(f"[{stock_code}] DB 최신 캔들(KST): {latest_db_timestamp}")
            logger.info(f"[{stock_code}] API 최신 캔들(KST): {df.index.max()}")
            
            # DB 최신 캔들보다 이후의 모든 데이터 필터링
            mask = df.index > latest_db_timestamp
            newer_data_df = df[mask].copy()
            
            if newer_data_df.empty:
                logger.info(f"[{stock_code}] DB 이후의 신규 캔들이 API에 없습니다.")
                return latest_db_timestamp.strftime("%Y%m%d%H%M%S")
            else:
                # 신규 캔들 중 가장 오래된(첫 번째) 1개만 선택
                first_new_timestamp = newer_data_df.index.min()
                new_data_df = newer_data_df.loc[[first_new_timestamp]].copy()
                
                logger.info(f"[{stock_code}] DB 이후 신규 캔들 {len(newer_data_df)}개 중 첫 번째 1개 선택")
                logger.info(f"[{stock_code}] 선택된 캔들: {first_new_timestamp}")
        else:
            # DB에 데이터가 없는 경우: 모든 API 데이터를 신규로 간주
            new_data_df = df.copy()
            logger.info(f"[{stock_code}] DB가 비어있음. 전체 {len(new_data_df)}개 데이터를 신규로 처리")

        # 6. 신규 데이터 범위 출력
        if not new_data_df.empty:
            first_new = new_data_df.index.min().strftime('%Y%m%d%H%M%S')
            last_new = new_data_df.index.max().strftime('%Y%m%d%H%M%S')
            logger.info(f"[{stock_code}] 신규 데이터 범위: {first_new} ~ {last_new}")

            # 7. DB에 배치 저장
            _db_upsert_candles(db, stock_code, timeframe_minutes, new_data_df)
            
            # 8. 가장 최신 타임스탬프 반환
            new_collected_timestamp_str = new_data_df.index.max().strftime("%Y%m%d%H%M%S")
            logger.info(f"[{stock_code}] 스마트 증분 업데이트 완료. 최신 타임스탬프: {new_collected_timestamp_str}")
        
    except SQLAlchemyError as e:
        logger.error(f"[{stock_code}] DB 오류: {e}")
    except Exception as e:
        logger.error(f"[{stock_code}] 예외 발생: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        if db:
            db.close()
    
    return new_collected_timestamp_str

if __name__ == '__main__':
    # 테스트 실행 예시 (로컬에서 직접 실행 시)
    logger.info("data_collector_test.py 로컬 테스트 시작")
    
    # .env 파일 및 DB 연결이 설정되어 있어야 함
    # Kiwoom API 설정 (app_key, secret_key 등)도 src/kiwoom_api/config/settings.yaml에 있어야 함
    
    TEST_STOCK_CODE = '005930'  # 삼성전자
    TEST_TIMEFRAME_MINUTES = 5
    
    # 초기 데이터 적재 테스트
    # 키움 API 특성: base_time은 마지막 캔들 시간, period만큼 과거로 조회
    TEST_BASE_DATE_STR = '20250529' 
    TEST_NUM_INITIAL_CANDLES = 77
    
    logger.info(f"초기 데이터 적재 테스트: {TEST_STOCK_CODE}")
    last_ts = fetch_and_store_initial_minute_data(
        stock_code=TEST_STOCK_CODE,
        timeframe_minutes=TEST_TIMEFRAME_MINUTES,
        base_date_str=TEST_BASE_DATE_STR,
        num_candles=TEST_NUM_INITIAL_CANDLES
    )
    
    if last_ts:
        logger.info(f"초기 적재 완료. 마지막 타임스탬프: {last_ts}")
        
        # 다음 캔들 업데이트 테스트 (연속 3번)
        for i in range(3):
            logger.info(f"다음 캔들 업데이트 테스트 ({i+1}/3): {TEST_STOCK_CODE}, 이전 타임스탬프: {last_ts}")
            if not last_ts:
                logger.error("이전 타임스탬프가 없어 다음 캔들 테스트를 중단합니다.")
                break
            
            time.sleep(1) # 실제 API 호출 간격 유지 (get_minute_chart 내 sleep과 별개로 함수 호출 간 간격)
            next_ts = fetch_and_store_next_minute_candle(
                stock_code=TEST_STOCK_CODE,
                timeframe_minutes=TEST_TIMEFRAME_MINUTES,
                last_timestamp_str=last_ts
            )
            
            if next_ts:
                logger.info(f"다음 캔들 저장 완료. 새로운 타임스탬프: {next_ts}")
                last_ts = next_ts # 다음 테스트를 위해 업데이트
            else:
                logger.error("다음 캔들 저장 실패. 테스트 중단.")
                break
            
            # 실제 API 연속 호출 시에는 1초 이상 간격 권장
            # 여기서는 get_minute_chart 내부에 time.sleep(0.2)가 이미 있음
            # time.sleep(1) 
    else:
        logger.error("초기 데이터 적재 실패.")
        
    logger.info("data_collector_test.py 로컬 테스트 종료") 