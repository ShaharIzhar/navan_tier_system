from __future__ import annotations

from collections.abc import Iterator

from sqlmodel import Session, SQLModel, create_engine

from . import config

_engine = None


def get_engine(url: str | None = None):
    global _engine
    if _engine is None or url is not None:
        db_url = url or config.DATABASE_URL
        _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    return _engine


def init_db(url: str | None = None):
    engine = get_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session() -> Iterator[Session]:
    with Session(get_engine()) as session:
        yield session
