"""Database session utilities for background workers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from titan_backend.core.config import settings

_sync_engine = None
_sync_session_factory = None


def get_sync_engine() -> Any:
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            settings.get_sync_database_url(),
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _sync_engine


def get_sync_session_factory() -> Any:
    global _sync_session_factory
    if _sync_session_factory is None:
        engine = get_sync_engine()
        _sync_session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    return _sync_session_factory


@contextmanager
def get_sync_db_session() -> Generator[Session, None, None]:
    factory = get_sync_session_factory()
    session = factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
