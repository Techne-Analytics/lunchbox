import json
import os
from pathlib import Path

# Set test defaults before any lunchbox imports (Settings() runs at import time)
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import lunchbox.models  # noqa: F401 — registers models with Base
from lunchbox.auth.dependencies import get_current_user
from lunchbox.db import Base, get_db
from lunchbox.main import app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox_test"
)

engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    try:
        Base.metadata.create_all(bind=engine)
    except OperationalError as e:
        import warnings

        warnings.warn(f"Test DB not available, DB tests will be skipped: {e}")
        yield
        return
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    try:
        session = TestSession()
        session.connection()  # verify DB is reachable
    except OperationalError as e:
        pytest.skip(f"Test DB not available: {e}")
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_client(db):
    """TestClient with an authenticated user. Yields (client, user)."""
    from tests.factories import create_user

    user = create_user(db)

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        yield c, user
    app.dependency_overrides.clear()


@pytest.fixture
def second_user_client(db):
    """Second authenticated user for isolation tests. Yields (client, user)."""
    from tests.factories import create_user

    user = create_user(
        db, google_id="second-user", email="other@example.com", name="Other"
    )

    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: user

    with TestClient(app) as c:
        yield c, user
    app.dependency_overrides.clear()


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "schoolcafe"


@pytest.fixture
def schoolcafe_fixture():
    """Load a SchoolCafe fixture by name. Returns loader function."""

    def _load(name: str) -> dict:
        path = FIXTURES_DIR / f"{name}.json"
        return json.loads(path.read_text())

    return _load
