# DataPipeline/src/database.py

from sqlalchemy import create_engine, Column, String, Text, Integer, Numeric, DateTime, BigInteger, UniqueConstraint, ForeignKey, Index, inspect
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import os

DB_USER = os.getenv("POSTGRES_USER") or os.getenv("POSTGRES_TRADESMART_USER")
DB_PASSWORD = os.getenv("POSTGRES_PASSWORD") or os.getenv("POSTGRES_TRADESMART_PASSWORD")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost") 
DB_PORT = os.getenv("POSTGRES_PORT", "5432")  # Docker 컨테이너 내부 기본 포트
DB_NAME = os.getenv("POSTGRES_DB", "tradesmart_db")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    print("데이터베이스 연결 정보가 환경 변수에 올바르게 설정되지 않았습니다.")
    print(f"현재 설정: HOST={DB_HOST}, PORT={DB_PORT}, USER={DB_USER}, DB={DB_NAME}")
    # 기본값 또는 예외 처리
    # exit() # 또는 기본값을 설정

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = {'schema': 'live'}

    stock_code = Column(String(20), primary_key=True, index=True)  # 종목코드 (기본키)
    stock_name = Column(String(100), index=True)  # 종목명
    list_count = Column(String(20), nullable=True)  # 상장주식수
    audit_info = Column(String(50), nullable=True)  # 감사의견
    reg_day = Column(String(8), nullable=True)  # 등록일
    last_price = Column(String(20), nullable=True)  # 현재가
    state = Column(Text, nullable=True)  # 종목 상태
    market_code = Column(String(20), nullable=True)  # 시장구분코드
    market_name = Column(String(50), nullable=True)  # 시장구분명
    industry_name = Column(String(100), nullable=True)  # 업종명 (upName)
    company_size_name = Column(String(50), nullable=True)  # 기업규모명 (upSizeName)
    company_class_name = Column(String(50), nullable=True)  # 기업구분명 (코스닥만 존재)
    order_warning = Column(String(20), nullable=True)  # 주문경고 여부
    nxt_enable = Column(String(1), nullable=True)  # NXT 가능 여부

    # Stock과 Candle 간의 관계 정의 (ORM 활용)
    # stock.candles로 해당 종목의 모든 캔들 데이터에 접근 가능
    candles = relationship("Candle", back_populates="stock", cascade="all, delete-orphan")


class Candle(Base):
    __tablename__ = "candles"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)  # 자동 증가 Primary Key
    stock_code = Column(String(20), ForeignKey("live.stocks.stock_code"), index=True, nullable=False)  # 외래 키
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)  # KST 포함 시간
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
        {'schema': 'live'}  # 기본 스키마 설정
    )


def init_db_backup():
    """
    데이터베이스 테이블 생성 함수
    테이블이 이미 존재하면 생성하지 않음 (멱등성)
    """
    try:
        # 현재 존재하는 테이블 확인
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        print(f"기존 테이블: {existing_tables}")
        
        # 필요한 테이블 목록
        required_tables = ['stocks', 'candles']
        missing_tables = [table for table in required_tables if table not in existing_tables]
        
        if missing_tables:
            print(f"생성할 테이블: {missing_tables}")
            Base.metadata.create_all(bind=engine)
            
            # 생성 후 재확인
            new_tables = inspector.get_table_names()
            print(f"생성 후 테이블: {new_tables}")
        else:
            print("모든 필요한 테이블이 이미 존재합니다.")
        
        print("Database tables (stocks, candles) created or already exist.")
        
        # 테이블 생성 후 간단한 연결 테스트
        with engine.connect() as connection:
            result = connection.execute("SELECT 1")
            print("Database connection test successful.")
            
    except Exception as e:
        print(f"Error during database initialization: {e}")
        raise

# src/database.py

def init_db():
    """
    데이터베이스 스키마와 테이블을 생성합니다.
    - live, simulation 스키마를 생성합니다.
    - live 스키마에 모든 테이블(stocks, candles)을 생성합니다.
    - simulation 스키마에 candles 테이블을 추가로 생성합니다.
    """
    try:
        print("데이터베이스 초기화 시작...")
        
        # 스키마 생성
        with engine.connect() as connection:
            connection.execute("CREATE SCHEMA IF NOT EXISTS live")
            connection.execute("CREATE SCHEMA IF NOT EXISTS simulation")
            print("스키마 생성 완료: live, simulation")
        
        # 1. 기본 스키마('live')에 모든 테이블 생성
        print("기본('live') 스키마에 테이블 생성 중...")
        # Stock과 Candle의 기본 스키마가 'live'이므로 바로 생성됩니다.
        Base.metadata.create_all(bind=engine)
        
        # 2. 'simulation' 스키마에 'candles' 테이블 명시적 생성
        print("'simulation' 스키마에 'candles' 테이블 생성 중...")
        # Candle 모델의 스키마를 'simulation'으로 일시적으로 변경
        Candle.__table__.schema = 'simulation'
        # 변경된 스키마로 'candles' 테이블만 생성
        Base.metadata.create_all(bind=engine, tables=[Candle.__table__])
        # 다른 코드에 영향을 주지 않도록 스키마를 원래 기본값으로 복원
        Candle.__table__.schema = 'live'
        
        print("테이블 생성이 성공적으로 완료되었습니다.")

    except Exception as e:
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
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