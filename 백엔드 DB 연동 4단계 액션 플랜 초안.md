





```prompt
You are an expert AI software developer tasked with reviewing a development plan.

My project is "ChartInsight Studio," a full-stack application with a FastAPI backend. A senior AI coach, who doesn't have direct file system access, has provided a 4-step action plan to refactor my backend. The goal is to switch the data source from an external API to our internal PostgreSQL database.

Your task is to review this plan against my actual project's file structure and code, then refine it into a final, validated implementation guide.

Here is the 4-step action plan drafted by the coach:

---
## \#\# ChartInsight Studio: 백엔드 DB 연동 4단계 액션 플랜 (초안)

**목표**: `backend` 애플리케이션의 데이터 소스를 외부 키움증권 API 호출에서 내부 `postgres-tradesmart` DB (`live.candles` 테이블) 직접 조회 방식으로 전환한다.

### \#\#\# 1단계: DB 연결 설정 (`backend/src/database.py` 생성)

FastAPI 애플리케이션이 PostgreSQL 데이터베이스와 통신할 수 있는 기반을 마련합니다.

**✅ 액션:** `backend/src` 디렉토리 내에 `database.py` 파일을 생성하고 아래 코드를 작성합니다.

```python
# backend/src/database.py

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# Docker 환경 변수에서 DB 접속 정보 가져오기
DB_USER = os.getenv("POSTGRES_TRADESMART_USER", "default_user")
DB_PASSWORD = os.getenv("POSTGRES_TRADESMART_PASSWORD", "default_password")
DB_HOST = os.getenv("POSTGRES_HOST", "localhost") # Docker Compose에서는 서비스 이름(postgres-tradesmart)
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "tradesmart_db")

DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# SQLAlchemy 엔진 생성
engine = create_engine(DATABASE_URL)

# DB 세션 생성을 위한 SessionLocal 클래스
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 모델의 기본 클래스
Base = declarative_base()

# FastAPI 의존성 주입을 위한 함수
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### \#\#\# 2단계: ORM 모델 정의 (`backend/src/models.py` 생성)

DB의 `live.candles` 테이블 구조를 파이썬 클래스로 정의하여 SQLAlchemy가 테이블과 상호작용할 수 있도록 합니다.

**✅ 액션:** `backend/src` 디렉토리 내에 `models.py` 파일을 생성하고 아래 코드를 작성합니다.

```python
# backend/src/models.py

from sqlalchemy import Column, String, Numeric, DateTime, BigInteger
from .database import Base

class Candle(Base):
    __tablename__ = "candles"

    # DataPipeline의 모델과 완벽히 일치해야 함
    id = Column(BigInteger, primary_key=True, index=True)
    stock_code = Column(String(20), index=True, nullable=False)
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    open = Column(Numeric(15, 4), nullable=False)
    high = Column(Numeric(15, 4), nullable=False)
    low = Column(Numeric(15, 4), nullable=False)
    close = Column(Numeric(15, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)

    # live 스키마를 명시적으로 지정하는 것이 매우 중요!
    __table_args__ = {'schema': 'live'}
```

### \#\#\# 3단계: 데이터 조회 로직 분리 (`backend/src/crud.py` 생성)

데이터베이스에서 `Candle` 데이터를 조회하는 실제 로직을 별도의 파일로 분리하여 코드의 가독성과 유지보수성을 높입니다.

**✅ 액션:** `backend/src` 디렉토리 내에 `crud.py` 파일을 생성하고 아래 코드를 작성합니다.

```python
# backend/src/crud.py

from sqlalchemy.orm import Session
from . import models

def get_candles(db: Session, stock_code: str, timeframe: str, limit: int = 500):
    """
    특정 종목/타임프레임에 해당하는 캔들 데이터를 최신순으로 조회합니다.
    """
    return db.query(models.Candle)\
        .filter(models.Candle.stock_code == stock_code, models.Candle.timeframe == timeframe)\
        .order_by(models.Candle.timestamp.desc())\
        .limit(limit)\
        .all()
```

### \#\#\# 4단계: API 엔드포인트 수정

기존에 외부 API를 호출하던 API 엔드포인트가 새로 만든 DB 조회 로직을 사용하도록 수정합니다.

**✅ 액션:** Trading Radar 데이터를 반환하는 라우터 파일(예: `backend/src/routers/chart_data.py`)을 찾아 아래와 같이 수정합니다.

```python
# backend/src/routers/chart_data.py (또는 유사한 파일)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import crud, models # crud와 models 임포트
from ..database import get_db # get_db 의존성 임포트

# (기존 router = APIRouter(...) 코드는 그대로 사용)
router = APIRouter(prefix="/api/v1/pattern-analysis", tags=["pattern-analysis"])


# Trading Radar 데이터 제공 엔드포인트
@router.get("/trading-radar-data")
# Pydantic 스키마를 사용하여 응답 모델을 정의하는 것이 좋지만, 우선은 list를 반환
async def get_trading_radar_data(
    symbol: str,
    timeframe: str,
    db: Session = Depends(get_db) # DB 세션 주입
):
    # --- 기존 외부 API 호출 또는 캐시 로직 제거 ---

    # 1. DB에서 데이터 조회
    # (주의: 프론트엔드에서 'd'로 보내주는지, 'D'로 보내주는지 확인 필요.
    #  여기서는 일단 소문자 'd'를 대문자 'D'로 변환하는 로직을 가정)
    db_timeframe_map = {'1d': 'D', '1w': 'W', '5m': 'M5', '30m': 'M30', '1h': 'H1'}
    db_timeframe = db_timeframe_map.get(timeframe, timeframe.upper())

    candles = crud.get_candles(db=db, stock_code=symbol, timeframe=db_timeframe)

    if not candles:
        raise HTTPException(
            status_code=404,
            detail=f"데이터를 찾을 수 없습니다: symbol={symbol}, timeframe={db_timeframe}"
        )

    # 2. 조회된 데이터를 프론트엔드에 반환
    # (조회된 데이터는 시간순이므로, 차트 라이브러리가 요구하는 순서에 맞게 필요시 정렬)
    return sorted(candles, key=lambda x: x.timestamp)
```

-----
---

Please perform the following instructions:

1.  **Validate File Paths**: Review all proposed file paths (e.g., `backend/src/database.py`, `models.py`, `crud.py`, and the router file). If my project uses a different directory structure, please correct the paths in the final plan.

2.  **Check Code Snippets**: Scrutinize the provided Python code snippets. Based on the full context of my project, check for potential import errors, inconsistencies with existing code patterns, or any logical flaws. For example, ensure the environment variable names for the database connection are correct.

3.  **Verify Model Compatibility**: This is critical. Carefully compare the proposed `Candle` model in `backend/src/models.py` with the existing `Candle` model in `DataPipeline/src/database.py`. They must be perfectly compatible to avoid data mapping errors. Also, confirm the `__table_args__ = {'schema': 'live'}` is correctly specified.

4.  **Correct the API Endpoint**: Identify the actual FastAPI router file and function that provides data for the "Trading Radar." The plan assumes a path and function signature. If mine is different (e.g., different path, function name, or parameter names like `symbol` vs `stock_code`), provide the corrected, refactored code snippet for that specific endpoint.

5.  **Final Output**: Your output should be a **revised and validated version of the 4-step action plan**. If the coach's plan is perfect, simply state that. If it requires modifications, present the corrected plan step-by-step, clearly highlighting the changes you made and the reasons for them. The final plan should be a "copy-paste-ready" implementation guide for me to follow.
```

모든 답변 및 작성은  한국어로 해줘