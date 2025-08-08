"""Database connection module for ChartInsight Backend.

This module initializes the SQLAlchemy engine and session factory using
environment variables. It prefers a consolidated DATABASE_URL (as provided
by docker-compose for the backend service), and gracefully falls back to
individual POSTGRES_* env vars if DATABASE_URL is not set.
"""

from __future__ import annotations

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


def _build_url_from_parts() -> str | None:
    """Build a PostgreSQL URL from individual POSTGRES_* env vars.

    Expected vars (docker-compose compatible):
    - POSTGRES_TRADESMART_USER
    - POSTGRES_TRADESMART_PASSWORD
    - POSTGRES_HOST (defaults to 'postgres-tradesmart')
    - POSTGRES_PORT (defaults to '5432')
    - POSTGRES_DB (defaults to 'tradesmart_db')
    """
    user = (
        os.getenv("POSTGRES_TRADESMART_USER")
        or os.getenv("POSTGRES_USER")
    )
    password = (
        os.getenv("POSTGRES_TRADESMART_PASSWORD")
        or os.getenv("POSTGRES_PASSWORD")
    )
    host = os.getenv("POSTGRES_HOST", "postgres-tradesmart")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "tradesmart_db")

    if not (user and password):
        return None

    return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db}"


# Prefer a consolidated DATABASE_URL provided by docker-compose
DATABASE_URL = os.getenv("DATABASE_URL") or _build_url_from_parts()

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set and POSTGRES_* env vars are missing. "
        "Please ensure docker-compose provides DATABASE_URL or POSTGRES_* variables."
    )


# Engine and session factory
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # validates connections from the pool
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


# Declarative base for ORM models
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


