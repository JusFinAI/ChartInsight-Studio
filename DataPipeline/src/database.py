# DataPipeline/src/database.py

from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    Integer,
    Numeric,
    DateTime,
    BigInteger,
    UniqueConstraint,
    ForeignKey,
    Index,
    inspect,
    func,
    text,
    Boolean,
    Date,
)
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import expression
import os
import logging

logger = logging.getLogger(__name__)

# --- Simplified DATABASE_URL-only resolution ---
# The runtime environment (local shell or Docker) must set DATABASE_URL.
DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    error_msg = "DATABASE_URL 환경 변수가 설정되지 않았습니다. 프로그램을 실행할 수 없습니다."
    logger.error(error_msg)
    raise ValueError(error_msg)

# 로그에는 비밀번호를 마스킹하여 출력
try:
    from sqlalchemy.engine import make_url
    masked = make_url(DATABASE_URL).render_as_string(hide_password=True)
    logger.info(f"DB 연결 시도: {masked}")
except Exception:
    logger.info("DB 연결 시도 중... (URL 파싱 불가)")

# Create engine with pool pre-ping to avoid stale connections
engine = create_engine(DATABASE_URL, future=True, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Expose resolved DB components for scripts that may import them
try:
    from sqlalchemy.engine import make_url as _make_url
    parsed = _make_url(DATABASE_URL)
    DB_USER = parsed.username or ''
    DB_HOST = parsed.host or ''
    DB_PORT = str(parsed.port) if parsed.port is not None else ''
    DB_NAME = parsed.database or ''
except Exception:
    DB_USER = ''
    DB_HOST = ''
    DB_PORT = ''
    DB_NAME = ''

class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = {'schema': 'live'}  # 명시적 스키마 지정

    stock_code = Column(String(20), primary_key=True, index=True)  # 종목코드 (기본키)
    stock_name = Column(String(100), index=True)  # 종목명
    list_count = Column(BigInteger, nullable=True)  # 상장주식수 (정수형)
    audit_info = Column(String(50), nullable=True)  # 감사의견
    reg_day = Column(String(8), nullable=True)  # 등록일
    last_price = Column(Numeric(12, 2), nullable=True)  # 현재가 (숫자형, 소수점 2자리)
    state = Column(Text, nullable=True)  # 종목 상태
    market_code = Column(String(20), nullable=True)  # 시장구분코드
    market_name = Column(String(50), nullable=True)  # 시장구분명
    industry_name = Column(String(100), nullable=True)  # 업종명 (upName)
    company_size_name = Column(String(50), nullable=True)  # 기업규모명 (upSizeName)
    company_class_name = Column(String(50), nullable=True)  # 기업구분명 (코스닥만 존재)
    order_warning = Column(String(20), nullable=True)  # 주문경고 여부
    nxt_enable = Column(String(1), nullable=True)  # NXT 가능 여부

    # 운영 플래그: 분석 대상 포함 여부 및 초기 백필 필요 플래그
    is_active = Column(Boolean, nullable=False, server_default=expression.true(), default=True)
    backfill_needed = Column(Boolean, nullable=False, server_default=expression.true(), default=True)
    
    # [신규] 분석 대상 여부 플래그
    # True: '필터 제로' 기준을 통과하여 실제 분석에 사용될 종목.
    # False: ETF, 스팩, 관리종목 등 원장에는 기록되지만 분석에서는 제외할 종목.
    is_analysis_target = Column(Boolean, nullable=False, server_default=expression.false(), default=False, comment='분석 대상 여부 (필터 제로 통과)')

    # Stock과 Candle 간의 관계 정의 (ORM 활용)
    # stock.candles로 해당 종목의 모든 캔들 데이터에 접근 가능
    candles = relationship("Candle", back_populates="stock", cascade="all, delete-orphan")


class Candle(Base):
    __tablename__ = "candles"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)  # 자동 증가 Primary Key
    stock_code = Column(String(20), ForeignKey("live.stocks.stock_code"), index=True, nullable=False)  # ForeignKey에 스키마 포함
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)  # timezone-aware (DB에서 UTC로 정규화)
    timeframe = Column(String(10), index=True, nullable=False)  # 'D', 'W', 'M5', 'M30', 'H1'
    open = Column(Numeric(15, 4), nullable=False)   # 시가 (정밀도 향상)
    high = Column(Numeric(15, 4), nullable=False)   # 고가
    low = Column(Numeric(15, 4), nullable=False)    # 저가
    close = Column(Numeric(15, 4), nullable=False)  # 종가
    volume = Column(BigInteger, nullable=False)     # 거래량

    # Candle과 Stock 간의 관계 정의
    # candle.stock으로 해당 캔들의 종목 정보에 접근 가능
    stock = relationship("Stock", back_populates="candles")

    # 테이블 제약조건 및 인덱스 정의
    __table_args__ = (
        # 유니크 제약조건: 특정 종목의 특정 시간, 특정 타임프레임 데이터는 하나만 존재
        UniqueConstraint('stock_code', 'timestamp', 'timeframe', name='_stock_timestamp_timeframe_uc'),
        
        # 성능 최적화를 위한 복합 인덱스
        Index('idx_stock_timeframe_timestamp', 'stock_code', 'timeframe', 'timestamp'),  # 종목별 타임프레임별 시간 순 조회
        Index('idx_timestamp_timeframe', 'timestamp', 'timeframe'),  # 전체 시장 특정 시간 조회
        
        {'schema': 'live'}  # 명시적 스키마 지정
    )


class DailyAnalysisResult(Base):
    __tablename__ = "daily_analysis_results"
    __table_args__ = (
        # 비즈니스 규칙: 특정 날짜의 특정 종목 분석 결과는 유일해야 함
        UniqueConstraint('analysis_date', 'stock_code', name='_date_stock_uc'),
        # 조회 성능을 위한 인덱스
        Index('idx_analysis_date_stock_code', 'analysis_date', 'stock_code'),
        
        {'schema': 'live'}  # 명시적 스키마 지정
    )

    # 시스템이 사용하는 유일한 식별자 (단일 기본 키)
    id = Column(BigInteger, primary_key=True, autoincrement=True)

    # 분석 날짜 및 종목코드 (UniqueConstraint로 중복 방지)
    # Phase 2.1: 중복 적재 방지를 위해 시간 정보가 제거된 날짜(Date) 타입으로 변경
    analysis_date = Column(Date, nullable=False)
    stock_code = Column(String(20), ForeignKey("live.stocks.stock_code"), nullable=False)  # ForeignKey에 스키마 포함

    # 분석 결과 컬럼들
    market_rs_score = Column(Numeric(10, 2), nullable=True)
    sector_rs_score = Column(Numeric(10, 2), nullable=True)

    eps_growth_yoy = Column(Numeric(10, 2), nullable=True)
    eps_annual_growth_avg = Column(Numeric(10, 2), nullable=True)

    financial_grade = Column(String(10), nullable=True)
    rs_grade = Column(String(10), nullable=True)

    sma_20_val = Column(Numeric(15, 4), nullable=True)
    rsi_14_val = Column(Numeric(10, 2), nullable=True)

    trend_daily = Column(String(20), nullable=True)
    pattern_daily = Column(String(50), nullable=True)
    strategy_signal = Column(String(50), nullable=True)

    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    stock = relationship("Stock")


class FinancialAnalysisResult(Base):
    """
    재무 분석 결과를 저장하는 테이블
    
    목적:
    - dag_financials_update가 주 1회 DART API를 통해 수집한 재무 데이터를 분석하여
      EPS 성장률 및 재무 등급을 계산한 결과를 영구 저장합니다.
    - dag_daily_batch는 매일 이 테이블을 조회하여 최신 재무 등급을 사용합니다.
    
    특징:
    - stock_code + analysis_date 복합 유니크 제약: 같은 날짜에 동일 종목의 분석 결과가 중복 저장되지 않도록 보장
    - analysis_date, financial_grade 컬럼에 인덱스 추가: 조회 성능 최적화
    """
    __tablename__ = 'financial_analysis_results'
    __table_args__ = (
        # 복합 유니크 제약: 같은 종목에 대해 같은 날짜의 분석 결과는 하나만 존재
        UniqueConstraint('stock_code', 'analysis_date', name='_stock_analysis_date_uc'),
        
        # 성능 최적화를 위한 인덱스
        Index('idx_far_analysis_date', 'analysis_date'),  # 최신 날짜 조회 최적화
        Index('idx_far_financial_grade', 'financial_grade'),  # 등급별 필터링 최적화
        
        {'schema': 'live'}  # 명시적 스키마 지정
    )
    
    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Foreign Key: 어떤 종목의 분석 결과인지
    stock_code = Column(String(6), ForeignKey('live.stocks.stock_code'), nullable=False, index=True)
    
    # 분석 기준 날짜
    analysis_date = Column(Date, nullable=False)
    
    # EPS 성장률 지표
    eps_growth_yoy = Column(Numeric(10, 2), nullable=True, comment='최근 분기 YoY EPS 성장률 (%)')
    eps_annual_growth_avg = Column(Numeric(10, 2), nullable=True, comment='3년 연평균 EPS 성장률 (%)')
    
    # 재무 등급
    financial_grade = Column(String(10), nullable=True, comment="재무 등급: 'Strict', 'Loose', 'Fail'")
    
    # 레코드 생성 시각 (감사 추적용)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Stock과의 관계 정의
    stock = relationship("Stock")



def init_db():
    """
    데이터베이스 스키마와 테이블을 생성합니다.
    
    새로운 설계:
    - 각 모델 클래스에 스키마가 명시적으로 지정되어 있음 (__table_args__ = {'schema': 'live'})
    - create_all()이 올바르게 live 스키마에 테이블을 생성
    - simulation 스키마는 live 테이블 구조를 복제
    """
    try:
        logger.info("데이터베이스 초기화 시작...")
        
        # 1. 스키마 생성 (명시적 실행)
        with engine.connect() as connection:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS live"))
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS simulation"))
            connection.commit()
            logger.info("스키마 생성 완료: live, simulation")
        
        # 2. 'live' 스키마에 모든 테이블 생성
        # 각 모델이 자신의 스키마를 알고 있으므로, create_all이 올바르게 동작
        logger.info("--- 'live' 스키마 테이블 생성 중... ---")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        logger.info("'live' 스키마 테이블 생성 완료: stocks, candles, daily_analysis_results, financial_analysis_results")
        
        # 3. 'simulation' 스키마 테이블 복제 (Raw SQL)
        logger.info("--- 'simulation' 스키마 테이블 생성 중 (Raw SQL 복제 방식)... ---")
        with engine.connect() as connection:
            # stocks 테이블 복제
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation.stocks (LIKE live.stocks INCLUDING ALL)
            """))
            logger.info("  - simulation.stocks 생성 완료")
            
            # candles 테이블 복제
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation.candles (LIKE live.candles INCLUDING ALL)
            """))
            logger.info("  - simulation.candles 생성 완료")
            
            # daily_analysis_results 테이블 복제
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation.daily_analysis_results (LIKE live.daily_analysis_results INCLUDING ALL)
            """))
            logger.info("  - simulation.daily_analysis_results 생성 완료")
            
            # financial_analysis_results 테이블 복제
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS simulation.financial_analysis_results (LIKE live.financial_analysis_results INCLUDING ALL)
            """))
            logger.info("  - simulation.financial_analysis_results 생성 완료")
            
            connection.commit()
        
        logger.info("'simulation' 스키마 테이블 복제 완료.")
        logger.info("데이터베이스 초기화 성공.")

    except Exception as e:
        logger.error(f"데이터베이스 초기화 중 오류 발생: {e}")
        raise
        
def get_db():
    """
    데이터베이스 세션을 생성하고 반환하는 의존성 함수
    FastAPI 등에서 사용할 수 있도록 제네레이터 패턴 사용
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


if __name__ == "__main__":
    print(f"Attempting to connect to database: {DB_HOST}:{DB_PORT}/{DB_NAME} as user {DB_USER}")
    init_db()
    
    # 간단한 테스트 쿼리 실행
    try:
        db = SessionLocal()
        stock_count = db.query(Stock).count()
        candle_count = db.query(Candle).count()
        print(f"Current data: {stock_count} stocks, {candle_count} candles")
        db.close()
    except Exception as e:
        print(f"Error during data count query: {e}")