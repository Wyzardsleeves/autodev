"""Database engine, session factory, and the FastAPI session dependency."""

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

# Resolved from this file, not the working directory: the suite gets run from
# inside git worktrees, and a CWD-relative path would quietly open the wrong file.
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "todos.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# check_same_thread=False: FastAPI runs sync dependencies in a threadpool, so the
# connection is used from a thread other than the one that created it.
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass


def get_db():
    """Yield a session per request, closing it once the response is sent."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
