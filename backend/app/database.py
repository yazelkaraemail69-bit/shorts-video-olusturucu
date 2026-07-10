from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

settings = get_settings()

# SQLite dosya yolunu oluştur
if settings.database_url.startswith("sqlite:///./"):
    db_relative = settings.database_url.replace("sqlite:///./", "")
    Path(db_relative).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:  # noqa: ARG001
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from sqlalchemy import inspect, text

    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # SQLite: yeni kolonlar için hafif migrate
    if settings.database_url.startswith("sqlite"):
        insp = inspect(engine)
        if "video_jobs" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("video_jobs")}
            if "critique_report" not in cols:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE video_jobs ADD COLUMN critique_report TEXT"))
        if "scenarios" in insp.get_table_names():
            cols = {c["name"] for c in insp.get_columns("scenarios")}
            if "copy_unlocked" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE scenarios ADD COLUMN copy_unlocked BOOLEAN NOT NULL DEFAULT 0"
                        )
                    )
            if "discussion_log" not in cols:
                with engine.begin() as conn:
                    conn.execute(
                        text(
                            "ALTER TABLE scenarios ADD COLUMN discussion_log TEXT NOT NULL DEFAULT '[]'"
                        )
                    )
