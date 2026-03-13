"""数据库引擎与会话获取。"""

import os
from pathlib import Path
from typing import Generator

from sqlmodel import Session, create_engine
from sqlmodel import SQLModel

from config import settings


def _ensure_db_dir() -> None:
    url = settings.database_url
    if url.startswith("sqlite:///"):
        path = url.replace("sqlite:///", "")
        if path != ":memory:":
            dir_path = Path(path).parent
            dir_path.mkdir(parents=True, exist_ok=True)


_ensure_db_dir()
engine = create_engine(settings.database_url, echo=False, connect_args={"check_same_thread": False})


def init_db() -> None:
    SQLModel.metadata.create_all(engine)
    _migrate_skills_columns()


def _migrate_skills_columns() -> None:
    """为已有 skills 表添加 source_type、source_path 列（若不存在）。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        try:
            r = conn.execute(text("PRAGMA table_info(skills)"))
            cols = [row[1] for row in r]
        except Exception:
            return
        if "source_type" not in cols:
            conn.execute(text("ALTER TABLE skills ADD COLUMN source_type VARCHAR(32) DEFAULT 'builtin'"))
        if "source_path" not in cols:
            conn.execute(text("ALTER TABLE skills ADD COLUMN source_path VARCHAR(512)"))
        conn.commit()
        # 将已有行的 NULL 设为 builtin
        conn.execute(text("UPDATE skills SET source_type = 'builtin' WHERE source_type IS NULL"))
        conn.commit()


def get_session() -> Generator[Session, None, None]:
    session = Session(engine)
    try:
        yield session
    finally:
        session.close()
