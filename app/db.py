from __future__ import annotations

from sqlalchemy import create_engine, event
from sqlalchemy import text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings


class Base(DeclarativeBase):
    pass


engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    future=True,
)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, class_=Session)


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    with engine.begin() as connection:
        columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(sites)")).fetchall()
        }
        if "extra_headers" not in columns:
            connection.execute(
                text("ALTER TABLE sites ADD COLUMN extra_headers TEXT NOT NULL DEFAULT ''")
            )
