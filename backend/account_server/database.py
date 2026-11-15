from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def build_session_factory(database_url: str) -> sessionmaker[Session]:
    if not database_url.startswith(("postgresql://", "postgresql+psycopg://")):
        raise ValueError("Account Server database must be PostgreSQL")
    engine = create_engine(database_url, pool_pre_ping=True, future=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    setattr(factory, "_jarvis_engine", engine)
    return factory


def dispose_session_factory(factory: sessionmaker[Session]) -> None:
    engine = getattr(factory, "_jarvis_engine", None)
    if engine is not None:
        engine.dispose()


def session_dependency(factory: sessionmaker[Session]) -> Generator[Session, None, None]:
    session = factory()
    try:
        yield session
    finally:
        session.close()

