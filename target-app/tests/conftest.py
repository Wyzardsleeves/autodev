"""Test fixtures.

Every test gets a fresh in-memory database. Nothing here ever opens the real
todos.db file, so running the suite is side-effect free and repeatable — which
matters because this suite is the gate an automated agent checks its work against.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import todo_model  # noqa: F401  -- registers Todo on Base.metadata


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        # Without StaticPool every connection would get its own empty in-memory
        # database, so the request under test wouldn't see fixture-seeded rows.
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    """TestClient wired to the throwaway session instead of the real engine."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        # Deliberately not used as a context manager: that would run the lifespan
        # handler, whose create_all() targets the real engine and would bring
        # todos.db into existence. Tables are already made on the test engine.
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
