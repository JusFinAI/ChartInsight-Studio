"""SQLAlchemy ORM models for ChartInsight Backend.

These mirror the tables created by the DataPipeline under the 'live' schema:
 - live.stocks
 - live.candles

No DDL (create_all) is performed here; tables are assumed to exist
as they are managed by the DataPipeline/Airflow.
"""

from __future__ import annotations

from sqlalchemy import (
    Column,
    String,
    Text,
    BigInteger,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.database import Base


class Stock(Base):
    __tablename__ = "stocks"
    __table_args__ = {"schema": "live"}

    stock_code = Column(String(20), primary_key=True, index=True)
    stock_name = Column(String(100), index=True)
    list_count = Column(String(20), nullable=True)
    audit_info = Column(String(50), nullable=True)
    reg_day = Column(String(8), nullable=True)
    last_price = Column(String(20), nullable=True)
    state = Column(Text, nullable=True)
    market_code = Column(String(20), nullable=True)
    market_name = Column(String(50), nullable=True)
    industry_name = Column(String(100), nullable=True)
    company_size_name = Column(String(50), nullable=True)
    company_class_name = Column(String(50), nullable=True)
    order_warning = Column(String(20), nullable=True)
    nxt_enable = Column(String(1), nullable=True)

    candles = relationship(
        "Candle",
        back_populates="stock",
        cascade="all, delete-orphan",
    )


class Candle(Base):
    __tablename__ = "candles"

    id = Column(BigInteger, primary_key=True, index=True, autoincrement=True)
    stock_code = Column(
        String(20),
        ForeignKey("live.stocks.stock_code"),
        index=True,
        nullable=False,
    )
    timestamp = Column(DateTime(timezone=True), index=True, nullable=False)
    timeframe = Column(String(10), index=True, nullable=False)
    open = Column(Numeric(15, 4), nullable=False)
    high = Column(Numeric(15, 4), nullable=False)
    low = Column(Numeric(15, 4), nullable=False)
    close = Column(Numeric(15, 4), nullable=False)
    volume = Column(BigInteger, nullable=False)

    stock = relationship("Stock", back_populates="candles")

    __table_args__ = (
        UniqueConstraint(
            "stock_code", "timestamp", "timeframe", name="_stock_timestamp_timeframe_uc"
        ),
        Index(
            "idx_stock_timeframe_timestamp",
            "stock_code",
            "timeframe",
            "timestamp",
        ),
        Index("idx_timestamp_timeframe", "timestamp", "timeframe"),
        {"schema": "live"},
    )


