import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lunchbox.db import Base, get_db
from lunchbox.main import app
import lunchbox.models  # noqa: F401 — registers models with Base

TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox_test"
)

engine = create_engine(TEST_DATABASE_URL)
TestSession = sessionmaker(bind=engine)


@pytest.fixture(scope="session", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestSession()
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
