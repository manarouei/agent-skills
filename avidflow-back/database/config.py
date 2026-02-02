from typing import Generator, AsyncGenerator
from contextlib import contextmanager
import psycopg
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from config import settings
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine
from sqlalchemy.ext.asyncio import create_async_engine



Base = declarative_base()

def get_async_engine() -> AsyncEngine:
    engine = create_async_engine(settings.DATABASE_URL)
    return engine

def make_sync_url(url: str) -> str:
    """Convert async URL to sync URL for psycopg3."""
    if url.startswith("postgresql+asyncpg"):
        return url.replace("postgresql+asyncpg", "postgresql+psycopg")
    return url


# --- Engines (created once) ---
async_engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

sync_engine = create_engine(
    make_sync_url(settings.DATABASE_URL),
    pool_pre_ping=True,
    connect_args={"prepare_threshold": None},
    module=psycopg,
)


# --- Session factories ---
AsyncSessionLocal = sessionmaker(
    async_engine, class_=AsyncSession, expire_on_commit=False
)

SyncSessionLocal = sessionmaker(
    bind=sync_engine, autocommit=False, autoflush=False
)


# --- Dependencies ---
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide an async SQLAlchemy session (FastAPI dependency)."""
    async with AsyncSessionLocal() as session:
        yield session


def get_sync_session() -> Generator[Session, None, None]:
    """Provide a sync SQLAlchemy session (FastAPI dependency)."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()

@contextmanager
def get_sync_session_manual() -> Session:
    """Sync session for scripts, tasks, tests"""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()