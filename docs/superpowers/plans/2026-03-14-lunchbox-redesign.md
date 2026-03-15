# Lunchbox Redesign Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the school lunch menu sync as a FastAPI web app with iCal feed output, Postgres storage, HTMX UI, OpenTelemetry observability, and a path to multi-user.

**Architecture:** Modular monolith — single FastAPI app with clean internal modules (auth, sync, api, web, scheduler, telemetry). Postgres for storage. iCal feeds instead of Google Calendar API writes. OpenTelemetry auto-instrumentation + manual spans exported to Grafana Cloud via OTLP.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, PostgreSQL, HTMX, Jinja2, APScheduler, OpenTelemetry, Ruff, pytest

**Spec:** `docs/superpowers/specs/2026-03-14-lunchbox-redesign-design.md`

---

## Chunk 1: Foundation (Issues #2, #3)

### Task 1: Remove n8n and legacy code (Issue #2)

**Files:**
- Delete: `workflows/school-lunch-menu-calendar.json`
- Delete: `n8n_data/` (entire directory)
- Delete: `tasks/` (entire directory — will be replaced by `src/lunchbox/`)
- Delete: `tasks_data/debug/` (debug output)
- Modify: `docker-compose.yml` (remove n8n service)
- Delete: `docs/WORKFLOW_SETUP.md`
- Delete: `docs/BUILD_WORKFLOW_MANUALLY.md`
- Delete: `docs/MCP_BROWSER_AUTOMATION.md`
- Delete: `docs/TASKS_PYTHON.md`
- Keep: `docs/api-discovery.md` (SchoolCafe API docs, still relevant)
- Keep: `docs/GOOGLE_CALENDAR_SETUP.md` (OAuth setup, still relevant for login)
- Keep: `docs/PUBLISH_OAUTH_APP.md` (still relevant)
- Keep: `tasks_data/client_secret.json` and `tasks_data/token.json` (still needed for OAuth)

- [ ] **Step 1: Delete n8n workflow and data**

```bash
rm -rf workflows/
rm -rf n8n_data/
rm -rf tasks_data/debug/
```

- [ ] **Step 2: Delete legacy Python task runner**

```bash
rm -rf tasks/
```

- [ ] **Step 3: Delete n8n-specific docs**

```bash
rm docs/WORKFLOW_SETUP.md
rm docs/BUILD_WORKFLOW_MANUALLY.md
rm docs/MCP_BROWSER_AUTOMATION.md
rm docs/TASKS_PYTHON.md
```

- [ ] **Step 4: Remove n8n service from docker-compose.yml**

Remove the entire `n8n` service block and its environment variables. Keep only the top-level structure for now — we'll replace the content in the next task.

- [ ] **Step 5: Remove legacy plans**

```bash
rm docs/plans/2026-01-19-school-lunch-menu-workflow-design.md
rm docs/plans/2026-01-22-direct-api-approach.md
rm docs/plans/2026-01-22-oauth-token-persistence.md
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove n8n, legacy workflow, and old task runner

Clean break from the n8n-based approach. The project is being rebuilt
as a FastAPI web app (Lunchbox). Keeps OAuth credentials, SchoolCafe
API docs, and design specs."
```

---

### Task 2: Scaffold project structure (Issue #3)

**Files:**
- Create: `Dockerfile`
- Create: `docker-compose.yml` (rewrite)
- Create: `pyproject.toml`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/versions/.gitkeep`
- Create: `src/lunchbox/__init__.py`
- Create: `src/lunchbox/main.py` (minimal FastAPI app)
- Create: `src/lunchbox/config.py` (Pydantic Settings)
- Create: `src/lunchbox/db.py` (SQLAlchemy engine/session)
- Create: `tests/__init__.py`
- Create: `tests/conftest.py` (test DB fixture)
- Create: `.env.example`
- Modify: `.gitignore` (update for new structure)
- Modify: `CLAUDE.md` (already updated)
- Modify: `CONTRIBUTING.md` (already written)
- Modify: `README.md` (already written)

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "lunchbox"
version = "0.1.0"
description = "School lunch menus synced to subscribable iCal calendar feeds"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "alembic>=1.13.0",
    "psycopg2-binary>=2.9.0",
    "pydantic-settings>=2.0.0",
    "httpx>=0.27.0",
    "jinja2>=3.1.0",
    "python-multipart>=0.0.9",
    "authlib>=1.3.0",
    "itsdangerous>=2.1.0",
    "icalendar>=5.0.0",
    "apscheduler>=3.10.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp>=1.20.0",
    "opentelemetry-instrumentation-fastapi>=0.44b0",
    "opentelemetry-instrumentation-sqlalchemy>=0.44b0",
    "opentelemetry-instrumentation-httpx>=0.44b0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
]

[tool.ruff]
target-version = "py311"
line-length = 88

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create Dockerfile**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (cached layer)
COPY pyproject.toml .
RUN mkdir -p src/lunchbox && touch src/lunchbox/__init__.py && \
    pip install --no-cache-dir -e .

# Copy source
COPY . .

EXPOSE 8000

CMD ["uvicorn", "lunchbox.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Rewrite docker-compose.yml**

```yaml
services:
  postgres:
    image: postgres:16
    restart: unless-stopped
    environment:
      POSTGRES_DB: lunchbox
      POSTGRES_USER: lunchbox
      POSTGRES_PASSWORD: "${POSTGRES_PASSWORD}"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  app:
    build: .
    restart: unless-stopped
    depends_on:
      - postgres
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: "postgresql://lunchbox:${POSTGRES_PASSWORD}@postgres:5432/lunchbox"
      SECRET_KEY: "${SECRET_KEY}"
      GOOGLE_CLIENT_ID: "${GOOGLE_CLIENT_ID}"
      GOOGLE_CLIENT_SECRET: "${GOOGLE_CLIENT_SECRET}"
      OTEL_EXPORTER_OTLP_ENDPOINT: "${OTEL_EXPORTER_OTLP_ENDPOINT:-}"
      OTEL_EXPORTER_OTLP_HEADERS: "${OTEL_EXPORTER_OTLP_HEADERS:-}"
      OTEL_SERVICE_NAME: "lunchbox"
      BASE_URL: "${BASE_URL:-http://localhost:8000}"
    volumes:
      - ./src:/app/src

volumes:
  postgres_data:
```

- [ ] **Step 4: Create .env.example**

```env
# Database
POSTGRES_PASSWORD=changeme

# App
SECRET_KEY=changeme-generate-with-python-c-import-secrets-secrets.token_hex-32
BASE_URL=http://localhost:8000

# Google OAuth (login only — openid, email, profile scopes)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

# Grafana Cloud OTLP (optional — leave blank to disable telemetry)
OTEL_EXPORTER_OTLP_ENDPOINT=
OTEL_EXPORTER_OTLP_HEADERS=
```

- [ ] **Step 5: Create src/lunchbox/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox"
    secret_key: str = "dev-secret-key-change-in-production"
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_service_name: str = "lunchbox"

    # Sync defaults
    days_to_fetch: int = 7
    skip_weekends: bool = True
    sync_hour: int = 6
    sync_minute: int = 0
    timezone: str = "America/Denver"

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
```

- [ ] **Step 6: Create src/lunchbox/db.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from lunchbox.config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 7: Create src/lunchbox/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: telemetry, scheduler — added in later tasks
    yield
    # Shutdown


app = FastAPI(title="Lunchbox", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 8: Create src/lunchbox/__init__.py**

```python
```

(Empty file.)

- [ ] **Step 9: Set up Alembic**

Create `alembic.ini`:

```ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql://lunchbox:lunchbox@localhost:5432/lunchbox

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

Create `alembic/env.py`:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from lunchbox.config import settings
from lunchbox.db import Base

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

Create `alembic/versions/.gitkeep` (empty file).

- [ ] **Step 10: Create tests/conftest.py**

```python
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from lunchbox.db import Base, get_db
from lunchbox.main import app

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
```

- [ ] **Step 11: Create tests/__init__.py**

(Empty file.)

- [ ] **Step 12: Write and run smoke test**

Create `tests/test_health.py`:

```python
def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

Run: `pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 13: Update .gitignore**

```
# Python
__pycache__/
*.pyc
*.egg-info/
dist/
build/

# Environment
.env

# OAuth credentials
tasks_data/token.json
tasks_data/client_secret.json
tasks_data/

# Database
*.sqlite

# IDE
.vscode/
.idea/

# OS
.DS_Store
Thumbs.db

# Superpowers
.superpowers/
```

- [ ] **Step 14: Commit**

```bash
git add -A
git commit -m "chore: scaffold Lunchbox project structure

FastAPI app factory, Pydantic Settings, SQLAlchemy + Alembic setup,
Docker Compose with Postgres, pytest fixtures, health endpoint.
Includes CLAUDE.md, CONTRIBUTING.md, README.md."
```

---

## Chunk 2: Data Model + SchoolCafe Client (Issues #4, #5)

### Task 3: SQLAlchemy models and initial migration (Issue #4)

**Files:**
- Create: `src/lunchbox/models/__init__.py`
- Create: `src/lunchbox/models/user.py`
- Create: `src/lunchbox/models/subscription.py`
- Create: `src/lunchbox/models/menu_item.py`
- Create: `src/lunchbox/models/sync_log.py`
- Create: `tests/unit/test_models.py`
- Modify: `alembic/env.py` (import models)

- [ ] **Step 1: Create src/lunchbox/models/__init__.py**

```python
from lunchbox.models.menu_item import MenuItem
from lunchbox.models.subscription import Subscription
from lunchbox.models.sync_log import SyncLog
from lunchbox.models.user import User

__all__ = ["User", "Subscription", "MenuItem", "SyncLog"]
```

- [ ] **Step 2: Create src/lunchbox/models/user.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    google_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    subscriptions = relationship("Subscription", back_populates="user")
```

- [ ] **Step 3: Create src/lunchbox/models/subscription.py**

```python
import uuid
from datetime import datetime, time

from sqlalchemy import JSON, Boolean, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    provider: Mapped[str] = mapped_column(String, default="schoolcafe")
    school_id: Mapped[str] = mapped_column(String)
    school_name: Mapped[str] = mapped_column(String)
    grade: Mapped[str] = mapped_column(String)
    meal_configs: Mapped[list] = mapped_column(JSON)
    included_categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    excluded_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    feed_token: Mapped[uuid.UUID] = mapped_column(
        unique=True, index=True, default=uuid.uuid4
    )
    display_name: Mapped[str] = mapped_column(String)
    alert_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    show_as_busy: Mapped[bool] = mapped_column(Boolean, default=False)
    event_type: Mapped[str] = mapped_column(String, default="all_day")
    event_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    event_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="subscriptions")
    menu_items = relationship("MenuItem", back_populates="subscription")
    sync_logs = relationship("SyncLog", back_populates="subscription")
```

- [ ] **Step 4: Create src/lunchbox/models/menu_item.py**

```python
import uuid
from datetime import date, datetime

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class MenuItem(Base):
    __tablename__ = "menu_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    school_id: Mapped[str] = mapped_column(String)
    menu_date: Mapped[date] = mapped_column(Date, index=True)
    meal_type: Mapped[str] = mapped_column(String)
    serving_line: Mapped[str] = mapped_column(String)
    grade: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    item_name: Mapped[str] = mapped_column(String)
    fetched_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    subscription = relationship("Subscription", back_populates="menu_items")
```

- [ ] **Step 5: Create src/lunchbox/models/sync_log.py**

```python
import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lunchbox.db import Base


class SyncLog(Base):
    __tablename__ = "sync_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(String)  # success, partial, error
    dates_synced: Mapped[int] = mapped_column(Integer, default=0)
    items_fetched: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(String, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    trace_id: Mapped[str | None] = mapped_column(String, nullable=True)
    started_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    subscription = relationship("Subscription", back_populates="sync_logs")
```

- [ ] **Step 6: Update alembic/env.py to import models**

Add this import before `target_metadata`:

```python
import lunchbox.models  # noqa: F401 — registers models with Base
```

- [ ] **Step 7: Generate initial migration**

```bash
alembic revision --autogenerate -m "initial schema: users, subscriptions, menu_items, sync_logs"
```

- [ ] **Step 8: Run migration**

```bash
alembic upgrade head
```

- [ ] **Step 9: Write model tests**

Create `tests/unit/__init__.py` (empty).

Create `tests/unit/test_models.py`:

```python
import uuid

from lunchbox.models import MenuItem, Subscription, SyncLog, User


def test_create_user(db):
    user = User(google_id="123", email="test@example.com", name="Test User")
    db.add(user)
    db.flush()
    assert user.id is not None
    assert user.google_id == "123"


def test_create_subscription(db):
    user = User(google_id="456", email="test@example.com", name="Test")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc-123",
        school_name="Test Elementary",
        grade="05",
        meal_configs=[
            {"meal_type": "Lunch", "serving_line": "Traditional Lunch", "sort_order": 0}
        ],
        display_name="Test Elementary - 5th Grade",
    )
    db.add(sub)
    db.flush()

    assert sub.id is not None
    assert sub.feed_token is not None
    assert sub.is_active is True
    assert sub.user_id == user.id


def test_create_menu_item(db):
    user = User(google_id="789", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="School",
    )
    db.add(sub)
    db.flush()

    item = MenuItem(
        subscription_id=sub.id,
        school_id="abc",
        menu_date="2026-03-15",
        meal_type="Lunch",
        serving_line="Traditional Lunch",
        grade="05",
        category="Entrees",
        item_name="Chicken Nuggets",
    )
    db.add(item)
    db.flush()
    assert item.id is not None


def test_create_sync_log(db):
    user = User(google_id="101", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="School",
    )
    db.add(sub)
    db.flush()

    log = SyncLog(
        subscription_id=sub.id,
        status="success",
        dates_synced=5,
        items_fetched=25,
        duration_ms=1500,
    )
    db.add(log)
    db.flush()
    assert log.id is not None
```

- [ ] **Step 10: Run tests**

```bash
pytest tests/unit/test_models.py -v
```

Expected: 4 tests PASS

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: add SQLAlchemy models and initial Alembic migration

Users, subscriptions (with meal configs, category/item filters, calendar
settings), menu_items, and sync_logs. Includes model unit tests."
```

---

### Task 4: SchoolCafe API client with self-healing (Issue #5)

**Files:**
- Create: `src/lunchbox/sync/__init__.py`
- Create: `src/lunchbox/sync/providers.py` (MenuProvider interface)
- Create: `src/lunchbox/sync/menu_client.py` (SchoolCafe implementation)
- Create: `tests/fixtures/schoolcafe/` (captured responses)
- Create: `tests/unit/test_menu_client.py`

- [ ] **Step 1: Capture real SchoolCafe API responses as fixtures**

Create `tests/fixtures/schoolcafe/normal_lunch.json`:

```json
{
  "Entrees": [
    {"MenuItemDescription": "BBQ Chicken Drumstick", "Price": "0.00"},
    {"MenuItemDescription": "Grilled Cheese Sandwich", "Price": "0.00"}
  ],
  "Grains": [
    {"MenuItemDescription": "Drop Biscuit", "Price": "0.00"}
  ],
  "Vegetables": [
    {"MenuItemDescription": "Carrots", "Price": "0.00"}
  ],
  "Fruits": [
    {"MenuItemDescription": "Pear", "Price": "0.00"}
  ],
  "Milk": [
    {"MenuItemDescription": "1% Milk", "Price": "0.00"}
  ],
  "Condiments": [
    {"MenuItemDescription": "Ketchup", "Price": "0.00"}
  ]
}
```

Create `tests/fixtures/schoolcafe/drifted_field_names.json` (simulates schema drift):

```json
{
  "Entrees": [
    {"Name": "Pizza", "name": "Pizza"},
    {"description": "Burger"}
  ],
  "Fruits": [
    "Apple",
    "Banana"
  ]
}
```

Create `tests/fixtures/schoolcafe/empty_response.json`:

```json
{}
```

Create `tests/fixtures/schoolcafe/unknown_categories.json`:

```json
{
  "Hot Entrees": [
    {"MenuItemDescription": "Tacos"}
  ],
  "Cold Entrees": [
    {"MenuItemDescription": "Salad"}
  ],
  "Seasonal Fruits": [
    {"MenuItemDescription": "Watermelon"}
  ]
}
```

- [ ] **Step 2: Create src/lunchbox/sync/__init__.py**

(Empty file.)

- [ ] **Step 3: Create src/lunchbox/sync/providers.py**

```python
from dataclasses import dataclass
from datetime import date
from typing import Protocol


@dataclass
class MenuItemData:
    category: str
    item_name: str


@dataclass
class SchoolInfo:
    school_id: str
    school_name: str


class MenuProvider(Protocol):
    def get_daily_menu(
        self,
        school_id: str,
        menu_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> list[MenuItemData]: ...

    def search_schools(self, query: str) -> list[SchoolInfo]: ...
```

- [ ] **Step 4: Create src/lunchbox/sync/menu_client.py**

```python
import logging

import httpx
from datetime import date

from lunchbox.sync.providers import MenuItemData, SchoolInfo

logger = logging.getLogger(__name__)

# Known category aliases — normalize to title case
CATEGORY_ALIASES: dict[str, str] = {
    "breakfast entrees": "Entrees",
    "entrees": "Entrees",
    "grains": "Grains",
    "vegetables": "Vegetables",
    "fruits": "Fruits",
    "milk": "Milk",
    "condiments": "Condiments",
}


def _extract_item_name(item) -> str | None:
    """Extract item name with fallback strategies for schema drift."""
    if isinstance(item, str):
        return item.strip() or None

    if isinstance(item, dict):
        # Primary field
        for field in ("MenuItemDescription", "Name", "name", "description"):
            value = item.get(field)
            if value and isinstance(value, str):
                return value.strip()

        # Last resort: first string value in the dict
        for value in item.values():
            if isinstance(value, str) and value.strip():
                logger.warning(
                    "menu_client: used fallback extraction, key structure: %s",
                    list(item.keys()),
                )
                return value.strip()

    return None


def _normalize_category(category: str) -> str:
    """Normalize category name, accepting unknowns gracefully."""
    alias = CATEGORY_ALIASES.get(category.lower())
    if alias:
        return alias
    return category.title()


def _detect_drift(data: dict) -> list[str]:
    """Check for schema drift indicators. Returns list of warnings."""
    warnings = []
    for category, items in data.items():
        if not isinstance(items, list):
            warnings.append(f"category '{category}' value is not a list")
            continue
        for item in items[:1]:  # Check first item only
            if isinstance(item, str):
                warnings.append(f"category '{category}' contains plain strings, not dicts")
            elif isinstance(item, dict) and "MenuItemDescription" not in item:
                warnings.append(
                    f"category '{category}' items missing MenuItemDescription, "
                    f"found keys: {list(item.keys())}"
                )
    return warnings


class SchoolCafeClient:
    """Resilient SchoolCafe API client with self-healing parsing."""

    BASE_URL = "https://webapis.schoolcafe.com/api"

    def __init__(self, timeout: int = 30):
        self._client = httpx.Client(
            timeout=timeout, headers={"Accept": "application/json"}
        )

    def get_daily_menu(
        self,
        school_id: str,
        menu_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> list[MenuItemData]:
        params = {
            "SchoolId": school_id,
            "ServingDate": menu_date.isoformat(),
            "ServingLine": serving_line,
            "MealType": meal_type,
            "Grade": grade,
            "PersonId": "",
        }

        response = self._client.get(
            f"{self.BASE_URL}/CalendarView/GetDailyMenuitemsByGrade",
            params=params,
        )
        response.raise_for_status()
        data = response.json()

        drift_warnings = _detect_drift(data)
        for warning in drift_warnings:
            logger.warning("SchoolCafe schema drift: %s", warning)

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[MenuItemData]:
        items = []
        for category, raw_items in data.items():
            if not isinstance(raw_items, list):
                continue

            normalized_category = _normalize_category(category)

            for raw_item in raw_items:
                name = _extract_item_name(raw_item)
                if name:
                    items.append(MenuItemData(category=normalized_category, item_name=name))

        # Deduplicate by (category, item_name)
        seen = set()
        unique = []
        for item in items:
            key = (item.category, item.item_name)
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique

    def search_schools(self, query: str) -> list[SchoolInfo]:
        # Get district ID
        response = self._client.get(
            f"{self.BASE_URL}/GetISDByShortName",
            params={"shortname": query},
        )
        response.raise_for_status()
        districts = response.json()

        if not districts:
            return []

        district_id = districts[0].get("ISDId")
        if not district_id:
            return []

        # Get schools
        response = self._client.get(
            f"{self.BASE_URL}/GetSchoolsList",
            params={"districtId": district_id},
        )
        response.raise_for_status()
        schools = response.json()

        return [
            SchoolInfo(
                school_id=s.get("SchoolId", ""),
                school_name=s.get("SchoolName", ""),
            )
            for s in schools
            if s.get("SchoolId")
        ]

    def close(self):
        self._client.close()
```

- [ ] **Step 5: Write menu client tests**

Create `tests/unit/test_menu_client.py`:

```python
import json
from pathlib import Path

from lunchbox.sync.menu_client import (
    SchoolCafeClient,
    _detect_drift,
    _extract_item_name,
    _normalize_category,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "schoolcafe"


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


class TestExtractItemName:
    def test_standard_field(self):
        assert _extract_item_name({"MenuItemDescription": "Pizza"}) == "Pizza"

    def test_fallback_name_field(self):
        assert _extract_item_name({"Name": "Burger"}) == "Burger"

    def test_fallback_description_field(self):
        assert _extract_item_name({"description": "Taco"}) == "Taco"

    def test_plain_string(self):
        assert _extract_item_name("Apple") == "Apple"

    def test_empty_string(self):
        assert _extract_item_name("") is None

    def test_empty_dict(self):
        assert _extract_item_name({}) is None

    def test_strips_whitespace(self):
        assert _extract_item_name({"MenuItemDescription": "  Pizza  "}) == "Pizza"


class TestNormalizeCategory:
    def test_known_alias(self):
        assert _normalize_category("breakfast entrees") == "Entrees"
        assert _normalize_category("Entrees") == "Entrees"

    def test_unknown_gets_title_cased(self):
        assert _normalize_category("hot entrees") == "Hot Entrees"
        assert _normalize_category("SEASONAL FRUITS") == "Seasonal Fruits"


class TestDetectDrift:
    def test_no_drift(self):
        data = load_fixture("normal_lunch.json")
        assert _detect_drift(data) == []

    def test_missing_standard_field(self):
        data = load_fixture("drifted_field_names.json")
        warnings = _detect_drift(data)
        assert len(warnings) > 0
        assert any("MenuItemDescription" in w for w in warnings)

    def test_plain_strings(self):
        data = load_fixture("drifted_field_names.json")
        warnings = _detect_drift(data)
        assert any("plain strings" in w for w in warnings)


class TestParseResponse:
    def test_normal_response(self):
        data = load_fixture("normal_lunch.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        categories = {i.category for i in items}
        assert "Entrees" in categories
        assert "Fruits" in categories

        names = {i.item_name for i in items}
        assert "BBQ Chicken Drumstick" in names
        assert "Pear" in names

    def test_drifted_response_still_parses(self):
        data = load_fixture("drifted_field_names.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        assert len(items) > 0
        names = {i.item_name for i in items}
        assert "Pizza" in names or "Apple" in names

    def test_empty_response(self):
        data = load_fixture("empty_response.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)
        assert items == []

    def test_unknown_categories(self):
        data = load_fixture("unknown_categories.json")
        client = SchoolCafeClient.__new__(SchoolCafeClient)
        items = client._parse_response(data)

        categories = {i.category for i in items}
        assert "Hot Entrees" in categories
        assert "Seasonal Fruits" in categories
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/unit/test_menu_client.py -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add SchoolCafe API client with self-healing parsing

Resilient client with fallback field extraction, schema drift detection,
and graceful handling of unknown categories. MenuProvider protocol for
future multi-source support. Includes captured fixtures and tests."
```

---

## Chunk 3: Auth + Sync Engine + iCal Feed (Issues #6, #7, #8)

### Task 5: Google OAuth login (Issue #6)

**Files:**
- Create: `src/lunchbox/auth/__init__.py`
- Create: `src/lunchbox/auth/router.py`
- Create: `src/lunchbox/auth/dependencies.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/integration/test_auth.py`
- Modify: `src/lunchbox/main.py` (add session middleware, include auth router)

- [ ] **Step 1: Create src/lunchbox/auth/__init__.py**

(Empty file.)

- [ ] **Step 2: Create src/lunchbox/auth/dependencies.py**

```python
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from lunchbox.db import get_db
from lunchbox.models import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

- [ ] **Step 3: Create src/lunchbox/auth/router.py**

```python
from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import User

router = APIRouter(prefix="/auth", tags=["auth"])

oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)


@router.get("/login")
async def login(request: Request):
    redirect_uri = f"{settings.base_url}/auth/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback")
async def callback(request: Request, db: Session = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get("userinfo", {})

    google_id = userinfo.get("sub")
    if not google_id:
        return RedirectResponse(url="/?error=auth_failed")

    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        user = User(
            google_id=google_id,
            email=userinfo.get("email", ""),
            name=userinfo.get("name", ""),
        )
        db.add(user)
    else:
        user.email = userinfo.get("email", user.email)
        user.name = userinfo.get("name", user.name)

    db.commit()
    db.refresh(user)

    request.session["user_id"] = str(user.id)
    return RedirectResponse(url="/dashboard")


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/")
```

- [ ] **Step 4: Update src/lunchbox/main.py**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600)
app.include_router(auth_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 5: Write auth integration tests**

Create `tests/integration/__init__.py` (empty).

Create `tests/integration/test_auth.py`:

```python
def test_login_redirects_to_google(client):
    response = client.get("/auth/login", follow_redirects=False)
    assert response.status_code == 302
    assert "accounts.google.com" in response.headers.get("location", "")


def test_unauthenticated_returns_401(client):
    # This tests the dependency directly — we'll have protected routes later
    from lunchbox.auth.dependencies import get_current_user
    from fastapi import HTTPException
    from unittest.mock import MagicMock

    request = MagicMock()
    request.session = {}
    db = MagicMock()

    try:
        get_current_user(request, db)
        assert False, "Should have raised"
    except HTTPException as e:
        assert e.status_code == 401


def test_logout_clears_session(client):
    response = client.get("/auth/logout", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers.get("location") == "/"
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add Google OAuth login with session management

Authlib-based Google OAuth flow (openid, email, profile scopes).
Session middleware with 30-day signed cookies. User upsert on login.
get_current_user dependency for protected routes."
```

---

### Task 6: Sync engine (Issue #7)

**Files:**
- Create: `src/lunchbox/sync/engine.py`
- Create: `tests/unit/test_sync_engine.py`

- [ ] **Step 1: Create src/lunchbox/sync/engine.py**

```python
import logging
from datetime import date, timedelta

from sqlalchemy.orm import Session

from lunchbox.models import MenuItem, Subscription, SyncLog
from lunchbox.sync.menu_client import SchoolCafeClient

logger = logging.getLogger(__name__)


def get_sync_dates(days: int, skip_weekends: bool, start: date | None = None) -> list[date]:
    """Generate list of dates to sync, optionally skipping weekends."""
    start = start or date.today()
    dates = []
    current = start
    while len(dates) < days:
        if not skip_weekends or current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def sync_subscription(
    db: Session,
    subscription: Subscription,
    client: SchoolCafeClient,
    days: int = 7,
    skip_weekends: bool = True,
) -> SyncLog:
    """Sync menu data for a single subscription."""
    import time

    started_at = time.time()
    dates = get_sync_dates(days, skip_weekends)
    total_items = 0
    errors = []

    for sync_date in dates:
        for meal_config in subscription.meal_configs:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]

            try:
                items = client.get_daily_menu(
                    school_id=subscription.school_id,
                    menu_date=sync_date,
                    meal_type=meal_type,
                    serving_line=serving_line,
                    grade=subscription.grade,
                )

                # Delete existing items for this date+meal
                db.query(MenuItem).filter(
                    MenuItem.subscription_id == subscription.id,
                    MenuItem.menu_date == sync_date,
                    MenuItem.meal_type == meal_type,
                ).delete()

                # Insert fresh items
                for item in items:
                    db.add(MenuItem(
                        subscription_id=subscription.id,
                        school_id=subscription.school_id,
                        menu_date=sync_date,
                        meal_type=meal_type,
                        serving_line=serving_line,
                        grade=subscription.grade,
                        category=item.category,
                        item_name=item.item_name,
                    ))

                total_items += len(items)

            except Exception as e:
                logger.error(
                    "Failed to sync %s %s for %s: %s",
                    meal_type, sync_date, subscription.display_name, e,
                )
                errors.append(f"{meal_type} {sync_date}: {e}")

    duration_ms = int((time.time() - started_at) * 1000)

    if errors:
        status = "error" if len(errors) == len(dates) * len(subscription.meal_configs) else "partial"
    else:
        status = "success"

    log = SyncLog(
        subscription_id=subscription.id,
        status=status,
        dates_synced=len(dates),
        items_fetched=total_items,
        error_message="; ".join(errors) if errors else None,
        duration_ms=duration_ms,
    )
    db.add(log)
    db.commit()

    return log


def sync_all(db: Session, client: SchoolCafeClient, days: int = 7, skip_weekends: bool = True):
    """Sync all active subscriptions."""
    subscriptions = db.query(Subscription).filter(Subscription.is_active.is_(True)).all()

    for sub in subscriptions:
        logger.info("Syncing %s", sub.display_name)
        try:
            log = sync_subscription(db, sub, client, days, skip_weekends)
            logger.info(
                "Sync complete: %s — %s, %d items",
                sub.display_name, log.status, log.items_fetched,
            )
        except Exception as e:
            logger.exception("Sync failed for %s: %s", sub.display_name, e)
```

- [ ] **Step 2: Write sync engine tests**

Create `tests/unit/test_sync_engine.py`:

```python
from datetime import date
from unittest.mock import MagicMock, patch

from lunchbox.models import MenuItem, Subscription, User
from lunchbox.sync.engine import get_sync_dates, sync_subscription
from lunchbox.sync.providers import MenuItemData


class TestGetSyncDates:
    def test_basic(self):
        dates = get_sync_dates(3, skip_weekends=False, start=date(2026, 3, 16))
        assert len(dates) == 3
        assert dates[0] == date(2026, 3, 16)

    def test_skip_weekends(self):
        # 2026-03-14 is a Saturday
        dates = get_sync_dates(3, skip_weekends=True, start=date(2026, 3, 14))
        for d in dates:
            assert d.weekday() < 5  # Mon-Fri

    def test_returns_requested_count(self):
        dates = get_sync_dates(5, skip_weekends=True, start=date(2026, 3, 16))
        assert len(dates) == 5


class TestSyncSubscription:
    def test_successful_sync(self, db):
        user = User(google_id="sync-test", email="t@t.com", name="T")
        db.add(user)
        db.flush()

        sub = Subscription(
            user_id=user.id,
            school_id="test-school",
            school_name="Test School",
            grade="05",
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0}
            ],
            display_name="Test School",
        )
        db.add(sub)
        db.flush()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = [
            MenuItemData(category="Entrees", item_name="Pizza"),
            MenuItemData(category="Fruits", item_name="Apple"),
        ]

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "success"
        assert log.items_fetched == 4  # 2 items × 2 days
        assert log.dates_synced == 2

        items = db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).all()
        assert len(items) == 4

    def test_partial_failure(self, db):
        user = User(google_id="sync-partial", email="t@t.com", name="T")
        db.add(user)
        db.flush()

        sub = Subscription(
            user_id=user.id,
            school_id="test-school",
            school_name="Test School",
            grade="05",
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0}
            ],
            display_name="Test School",
        )
        db.add(sub)
        db.flush()

        mock_client = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API down")
            return [MenuItemData(category="Entrees", item_name="Burger")]

        mock_client.get_daily_menu.side_effect = side_effect

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "partial"
        assert log.error_message is not None
```

- [ ] **Step 3: Run tests**

```bash
pytest tests/unit/test_sync_engine.py -v
```

Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add sync engine with per-date error handling

Orchestrates menu fetch → DB storage for subscriptions.
Graceful degradation on per-date failures (partial status).
Includes get_sync_dates utility and unit tests."
```

---

### Task 7: iCal feed endpoint (Issue #8)

**Files:**
- Create: `src/lunchbox/api/__init__.py`
- Create: `src/lunchbox/api/feeds.py`
- Create: `tests/unit/test_feeds.py`
- Create: `tests/integration/test_feeds_api.py`
- Modify: `src/lunchbox/main.py` (include API router)

- [ ] **Step 1: Create src/lunchbox/api/__init__.py**

(Empty file.)

- [ ] **Step 2: Create src/lunchbox/api/feeds.py**

```python
import hashlib
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from icalendar import Calendar, Event, Alarm
from sqlalchemy.orm import Session

from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription

router = APIRouter(tags=["feeds"])


def _build_calendar(subscription: Subscription, items: list[MenuItem]) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//Lunchbox//Menu Feed//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", subscription.display_name)
    cal.add("method", "PUBLISH")

    # Group items by (date, meal_type)
    grouped: dict[tuple, list[MenuItem]] = {}
    for item in items:
        key = (item.menu_date, item.meal_type)
        grouped.setdefault(key, []).append(item)

    # Sort by date, then meal_type alphabetically (Breakfast < Lunch)
    for (menu_date, meal_type), day_items in sorted(grouped.items()):
        # Apply category filter
        if subscription.included_categories:
            day_items = [i for i in day_items if i.category in subscription.included_categories]

        # Apply item exclusion filter
        if subscription.excluded_items:
            excluded_lower = {e.lower() for e in subscription.excluded_items}
            day_items = [i for i in day_items if i.item_name.lower() not in excluded_lower]

        if not day_items:
            continue

        # Build summary: "Lunch: Pizza, Burger, Apple"
        item_names = [i.item_name for i in day_items]
        summary = f"{meal_type}: {', '.join(item_names)}"
        if len(summary) > 100:
            summary = summary[:97] + "..."

        # Build description with categories
        categories: dict[str, list[str]] = {}
        for item in day_items:
            categories.setdefault(item.category, []).append(item.item_name)

        description_parts = []
        for cat, names in categories.items():
            description_parts.append(f"**{cat}:**")
            for name in names:
                description_parts.append(f"- {name}")
            description_parts.append("")

        event = Event()
        event.add("summary", summary)
        event.add("description", "\n".join(description_parts))
        event.add("dtstart", menu_date)
        event.add("dtend", menu_date)
        event.add(
            "uid",
            f"{subscription.feed_token}-{menu_date.isoformat()}-{meal_type}@lunchbox",
        )
        event.add("dtstamp", datetime.utcnow())
        event.add("transp", "OPAQUE" if subscription.show_as_busy else "TRANSPARENT")

        if subscription.alert_minutes:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", summary)
            alarm.add("trigger", timedelta(minutes=-subscription.alert_minutes))
            event.add_component(alarm)

        cal.add_component(event)

    return cal


@router.get("/cal/{feed_token}.ics")
def get_feed(feed_token: str, db: Session = Depends(get_db)):
    try:
        token_uuid = uuid.UUID(feed_token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Feed not found")

    subscription = (
        db.query(Subscription)
        .filter(Subscription.feed_token == token_uuid, Subscription.is_active.is_(True))
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Feed not found")

    items = (
        db.query(MenuItem)
        .filter(MenuItem.subscription_id == subscription.id)
        .order_by(MenuItem.menu_date, MenuItem.meal_type)
        .all()
    )

    cal = _build_calendar(subscription, items)
    content = cal.to_ical()

    # Caching headers
    etag = hashlib.md5(content).hexdigest()
    last_modified = max((i.fetched_at for i in items), default=datetime.utcnow())

    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "ETag": f'"{etag}"',
            "Last-Modified": last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Cache-Control": "max-age=3600",
        },
    )
```

- [ ] **Step 3: Update src/lunchbox/main.py**

Add to the imports and router includes:

```python
from lunchbox.api.feeds import router as feeds_router

# After app creation:
app.include_router(feeds_router)
```

- [ ] **Step 4: Write feed unit tests**

Create `tests/unit/test_feeds.py`:

```python
import uuid
from datetime import date, datetime

from lunchbox.api.feeds import _build_calendar
from lunchbox.models import MenuItem, Subscription


def _make_subscription(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        feed_token=uuid.uuid4(),
        display_name="Test School",
        included_categories=None,
        excluded_items=None,
        alert_minutes=None,
        show_as_busy=False,
    )
    defaults.update(overrides)
    sub = Subscription.__new__(Subscription)
    for k, v in defaults.items():
        setattr(sub, k, v)
    return sub


def _make_item(sub_id, menu_date, meal_type, category, item_name):
    item = MenuItem.__new__(MenuItem)
    item.subscription_id = sub_id
    item.menu_date = menu_date
    item.meal_type = meal_type
    item.category = category
    item.item_name = item_name
    item.fetched_at = datetime.utcnow()
    return item


class TestBuildCalendar:
    def test_basic_feed(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Apple"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "VCALENDAR" in ical
        assert "VEVENT" in ical
        assert "Pizza" in ical
        assert "Apple" in ical
        assert "TRANSPARENT" in ical

    def test_category_filter(self):
        sub = _make_subscription(included_categories=["Entrees"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Milk", "1% Milk"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Pizza" in ical
        assert "Milk" not in ical

    def test_excluded_items(self):
        sub = _make_subscription(excluded_items=["PB&J Sandwich"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "PB&J Sandwich"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Pizza" in ical
        assert "PB&J" not in ical

    def test_multiple_meals_sorted(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Breakfast", "Entrees", "Eggs"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        # Both events present
        assert "Lunch: Pizza" in ical
        assert "Breakfast: Eggs" in ical

    def test_busy_flag(self):
        sub = _make_subscription(show_as_busy=True)
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()
        assert "OPAQUE" in ical
```

- [ ] **Step 5: Write feed integration test**

Create `tests/integration/test_feeds_api.py`:

```python
import uuid

from lunchbox.models import MenuItem, Subscription, User


def test_feed_returns_ical(client, db):
    user = User(google_id="feed-test", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    feed_token = uuid.uuid4()
    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="Test School",
        grade="05",
        meal_configs=[],
        display_name="Test School",
        feed_token=feed_token,
    )
    db.add(sub)
    db.flush()

    item = MenuItem(
        subscription_id=sub.id,
        school_id="abc",
        menu_date="2026-03-16",
        meal_type="Lunch",
        serving_line="Traditional",
        grade="05",
        category="Entrees",
        item_name="Pizza",
    )
    db.add(item)
    db.commit()

    response = client.get(f"/cal/{feed_token}.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "VCALENDAR" in response.text
    assert "Pizza" in response.text


def test_feed_not_found(client):
    fake_token = uuid.uuid4()
    response = client.get(f"/cal/{fake_token}.ics")
    assert response.status_code == 404


def test_feed_invalid_token(client):
    response = client.get("/cal/not-a-uuid.ics")
    assert response.status_code == 404
```

- [ ] **Step 6: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: add iCal feed endpoint with filtering and caching

GET /cal/{token}.ics generates VCALENDAR from stored menu data.
Supports category filters, item exclusions, alert settings, busy/free.
ETag + Last-Modified + Cache-Control headers for efficient polling."
```

---

## Chunk 4: API + Web UI + Scheduler + OTel (Issues #9, #10)

### Task 8: Subscription CRUD API + HTMX web UI (Issue #9)

**Files:**
- Create: `src/lunchbox/api/router.py`
- Create: `src/lunchbox/api/subscriptions.py`
- Create: `src/lunchbox/api/schools.py`
- Create: `src/lunchbox/api/sync.py`
- Create: `src/lunchbox/web/__init__.py`
- Create: `src/lunchbox/web/router.py`
- Create: `src/lunchbox/web/templates/base.html`
- Create: `src/lunchbox/web/templates/landing.html`
- Create: `src/lunchbox/web/templates/dashboard.html`
- Create: `src/lunchbox/web/templates/subscription_new.html`
- Create: `src/lunchbox/web/templates/subscription_detail.html`
- Create: `src/lunchbox/web/templates/subscription_preview.html`
- Create: `src/lunchbox/web/static/style.css`
- Create: `tests/integration/test_api.py`
- Modify: `src/lunchbox/main.py` (include all routers, add Jinja2 templates)

- [ ] **Step 1: Create src/lunchbox/api/subscriptions.py**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.db import get_db
from lunchbox.models import Subscription, User

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class MealConfig(BaseModel):
    meal_type: str
    serving_line: str
    sort_order: int


class SubscriptionCreate(BaseModel):
    school_id: str
    school_name: str
    grade: str
    meal_configs: list[MealConfig]
    display_name: str
    included_categories: list[str] | None = None
    excluded_items: list[str] | None = None
    alert_minutes: int | None = None
    show_as_busy: bool = False
    event_type: str = "all_day"


class SubscriptionUpdate(BaseModel):
    display_name: str | None = None
    grade: str | None = None
    meal_configs: list[MealConfig] | None = None
    included_categories: list[str] | None = None
    excluded_items: list[str] | None = None
    alert_minutes: int | None = None
    show_as_busy: bool | None = None
    event_type: str | None = None
    is_active: bool | None = None


@router.get("")
def list_subscriptions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subs = db.query(Subscription).filter(Subscription.user_id == user.id).all()
    return [
        {
            "id": str(s.id),
            "display_name": s.display_name,
            "school_name": s.school_name,
            "feed_url": f"/cal/{s.feed_token}.ics",
            "is_active": s.is_active,
        }
        for s in subs
    ]


@router.post("", status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = Subscription(
        user_id=user.id,
        school_id=data.school_id,
        school_name=data.school_name,
        grade=data.grade,
        meal_configs=[mc.model_dump() for mc in data.meal_configs],
        display_name=data.display_name,
        included_categories=data.included_categories,
        excluded_items=data.excluded_items,
        alert_minutes=data.alert_minutes,
        show_as_busy=data.show_as_busy,
        event_type=data.event_type,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"id": str(sub.id), "feed_url": f"/cal/{sub.feed_token}.ics"}


@router.get("/{subscription_id}")
def get_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return sub


@router.patch("/{subscription_id}")
def update_subscription(
    subscription_id: uuid.UUID,
    data: SubscriptionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "meal_configs" and value is not None:
            value = [mc if isinstance(mc, dict) else mc.model_dump() for mc in value]
        setattr(sub, field, value)

    db.commit()
    return {"status": "updated"}


@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(sub)
    db.commit()


@router.post("/{subscription_id}/regenerate-token")
def regenerate_feed_token(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.feed_token = uuid.uuid4()
    db.commit()
    return {"feed_url": f"/cal/{sub.feed_token}.ics"}
```

- [ ] **Step 2: Create src/lunchbox/api/schools.py**

```python
from fastapi import APIRouter

from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/schools", tags=["schools"])


@router.get("")
def search_schools(q: str):
    client = SchoolCafeClient()
    try:
        schools = client.search_schools(q)
        return [{"school_id": s.school_id, "school_name": s.school_name} for s in schools]
    finally:
        client.close()
```

- [ ] **Step 3: Create src/lunchbox/api/sync.py**

```python
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import Subscription, SyncLog, User
from lunchbox.sync.engine import sync_subscription
from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/trigger/{subscription_id}")
def trigger_sync(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    client = SchoolCafeClient()
    try:
        log = sync_subscription(
            db, sub, client,
            days=settings.days_to_fetch,
            skip_weekends=settings.skip_weekends,
        )
    finally:
        client.close()

    return {
        "status": log.status,
        "items_fetched": log.items_fetched,
        "duration_ms": log.duration_ms,
    }


@router.get("/history/{subscription_id}")
def sync_history(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    logs = (
        db.query(SyncLog)
        .filter(SyncLog.subscription_id == subscription_id)
        .order_by(SyncLog.started_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(l.id),
            "status": l.status,
            "dates_synced": l.dates_synced,
            "items_fetched": l.items_fetched,
            "duration_ms": l.duration_ms,
            "trace_id": l.trace_id,
            "started_at": l.started_at.isoformat() if l.started_at else None,
        }
        for l in logs
    ]
```

- [ ] **Step 4: Create src/lunchbox/api/router.py**

```python
from fastapi import APIRouter

from lunchbox.api.feeds import router as feeds_router
from lunchbox.api.schools import router as schools_router
from lunchbox.api.subscriptions import router as subscriptions_router
from lunchbox.api.sync import router as sync_router

api_router = APIRouter()
api_router.include_router(subscriptions_router)
api_router.include_router(schools_router)
api_router.include_router(sync_router)
api_router.include_router(feeds_router)
```

- [ ] **Step 5: Create HTMX templates**

Create `src/lunchbox/web/__init__.py` (empty).

Create `src/lunchbox/web/templates/base.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Lunchbox{% endblock %}</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@picocss/pico@2/css/pico.min.css">
    <link rel="stylesheet" href="/static/style.css">
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
</head>
<body>
    <nav class="container">
        <ul><li><a href="/"><strong>Lunchbox</strong></a></li></ul>
        <ul>
            {% if user %}
            <li><a href="/dashboard">Dashboard</a></li>
            <li><a href="/auth/logout">Logout</a></li>
            {% else %}
            <li><a href="/auth/login">Sign in</a></li>
            {% endif %}
        </ul>
    </nav>
    <main class="container">
        {% block content %}{% endblock %}
    </main>
</body>
</html>
```

Create `src/lunchbox/web/templates/landing.html`:

```html
{% extends "base.html" %}
{% block content %}
<hgroup>
    <h1>Lunchbox</h1>
    <p>School lunch menus, synced to your calendar.</p>
</hgroup>
<p>Pick your school, choose what to see, get a calendar feed. Works with Google Calendar, Apple Calendar, Outlook — anything that supports iCal.</p>
<a href="/auth/login" role="button">Sign in with Google</a>
{% endblock %}
```

Create `src/lunchbox/web/templates/dashboard.html`:

```html
{% extends "base.html" %}
{% block title %}Dashboard — Lunchbox{% endblock %}
{% block content %}
<hgroup>
    <h1>Your Subscriptions</h1>
    <p>{{ user.name }} ({{ user.email }})</p>
</hgroup>

<a href="/subscriptions/new" role="button">Add Subscription</a>

{% for sub in subscriptions %}
<article>
    <header>
        <strong>{{ sub.display_name }}</strong>
        {% if not sub.is_active %}<mark>Inactive</mark>{% endif %}
    </header>
    <p>Feed URL: <code>{{ base_url }}/cal/{{ sub.feed_token }}.ics</code>
        <button onclick="navigator.clipboard.writeText('{{ base_url }}/cal/{{ sub.feed_token }}.ics')">Copy</button>
    </p>
    <footer>
        <a href="/subscriptions/{{ sub.id }}">Settings</a>
        <button hx-post="/api/sync/trigger/{{ sub.id }}" hx-swap="innerHTML" hx-target="closest article footer">Sync Now</button>
    </footer>
</article>
{% else %}
<p>No subscriptions yet. Add one to get started.</p>
{% endfor %}
{% endblock %}
```

Create `src/lunchbox/web/templates/subscription_new.html`:

```html
{% extends "base.html" %}
{% block title %}New Subscription — Lunchbox{% endblock %}
{% block content %}
<h1>Add Subscription</h1>

<form hx-post="/subscriptions/create" hx-swap="innerHTML" hx-target="body">
    <label>District Code
        <input type="text" name="district" placeholder="DPS" required
               hx-get="/api/schools" hx-trigger="change" hx-target="#school-select"
               hx-include="[name='district']" hx-swap="innerHTML">
    </label>

    <label>School
        <select name="school_id" id="school-select" required>
            <option value="">Search by district first</option>
        </select>
    </label>

    <label>Grade
        <input type="text" name="grade" placeholder="05" required>
    </label>

    <fieldset>
        <legend>Meals</legend>
        <label><input type="checkbox" name="meals" value="Lunch|Traditional Lunch" checked> Lunch</label>
        <label><input type="checkbox" name="meals" value="Breakfast|Grab n Go Breakfast"> Breakfast</label>
    </fieldset>

    <label>Display Name
        <input type="text" name="display_name" placeholder="Shoemaker - 5th Grade" required>
    </label>

    <details>
        <summary>Filters & Calendar Settings</summary>

        <fieldset>
            <legend>Include Categories (leave unchecked for all)</legend>
            <label><input type="checkbox" name="categories" value="Entrees"> Entrees</label>
            <label><input type="checkbox" name="categories" value="Grains"> Grains</label>
            <label><input type="checkbox" name="categories" value="Vegetables"> Vegetables</label>
            <label><input type="checkbox" name="categories" value="Fruits"> Fruits</label>
            <label><input type="checkbox" name="categories" value="Milk"> Milk</label>
            <label><input type="checkbox" name="categories" value="Condiments"> Condiments</label>
        </fieldset>

        <label>Exclude Items (comma-separated)
            <input type="text" name="excluded_items" placeholder="Peanut Butter & Jelly Sandwich, Turkey Sandwich">
        </label>

        <label>Alert (minutes before, blank for none)
            <input type="number" name="alert_minutes" placeholder="">
        </label>

        <label><input type="checkbox" name="show_as_busy"> Show as busy on calendar</label>
    </details>

    <button type="submit">Create Subscription</button>
</form>
{% endblock %}
```

Create `src/lunchbox/web/templates/subscription_detail.html`:

```html
{% extends "base.html" %}
{% block title %}{{ sub.display_name }} — Lunchbox{% endblock %}
{% block content %}
<h1>{{ sub.display_name }}</h1>

<p>Feed URL: <code>{{ base_url }}/cal/{{ sub.feed_token }}.ics</code>
    <button onclick="navigator.clipboard.writeText('{{ base_url }}/cal/{{ sub.feed_token }}.ics')">Copy</button>
</p>

<h2>Settings</h2>
<form hx-patch="/api/subscriptions/{{ sub.id }}" hx-swap="none">
    <label>Display Name
        <input type="text" name="display_name" value="{{ sub.display_name }}">
    </label>

    <label>Grade
        <input type="text" name="grade" value="{{ sub.grade }}">
    </label>

    <fieldset>
        <legend>Include Categories</legend>
        {% for cat in ["Entrees", "Grains", "Vegetables", "Fruits", "Milk", "Condiments"] %}
        <label>
            <input type="checkbox" name="categories" value="{{ cat }}"
                   {% if not sub.included_categories or cat in sub.included_categories %}checked{% endif %}>
            {{ cat }}
        </label>
        {% endfor %}
    </fieldset>

    <label>Exclude Items (comma-separated)
        <input type="text" name="excluded_items"
               value="{{ (sub.excluded_items or []) | join(', ') }}">
    </label>

    <label>Alert (minutes before)
        <input type="number" name="alert_minutes" value="{{ sub.alert_minutes or '' }}">
    </label>

    <label><input type="checkbox" name="show_as_busy" {% if sub.show_as_busy %}checked{% endif %}> Show as busy</label>

    <button type="submit">Save</button>
</form>

<h2>Actions</h2>
<button hx-post="/api/sync/trigger/{{ sub.id }}" hx-swap="innerHTML" hx-target="#sync-result">Sync Now</button>
<span id="sync-result"></span>

<button hx-post="/api/subscriptions/{{ sub.id }}/regenerate-token" hx-swap="outerHTML" hx-confirm="Regenerate feed URL? You'll need to re-subscribe in your calendar app.">Regenerate Feed URL</button>

<button hx-delete="/api/subscriptions/{{ sub.id }}" hx-confirm="Delete this subscription?" hx-swap="none" onclick="window.location='/dashboard'">Delete</button>

<h2>Sync History</h2>
<div hx-get="/api/sync/history/{{ sub.id }}" hx-trigger="load" hx-swap="innerHTML">
    Loading...
</div>
{% endblock %}
```

Create `src/lunchbox/web/templates/subscription_preview.html`:

```html
{% extends "base.html" %}
{% block title %}Preview — {{ sub.display_name }}{% endblock %}
{% block content %}
<h1>Preview: {{ sub.display_name }}</h1>
<a href="/subscriptions/{{ sub.id }}">Back to settings</a>

{% for date, meals in grouped_items.items() %}
<article>
    <header><strong>{{ date }}</strong></header>
    {% for meal_type, items in meals.items() %}
    <h3>{{ meal_type }}</h3>
    <ul>
        {% for item in items %}
        <li><strong>{{ item.category }}:</strong> {{ item.item_name }}</li>
        {% endfor %}
    </ul>
    {% endfor %}
</article>
{% endfor %}

{% if not grouped_items %}
<p>No menu data yet. Try syncing first.</p>
{% endif %}
{% endblock %}
```

- [ ] **Step 6: Create src/lunchbox/web/static/style.css**

```css
/* Minimal overrides — Pico CSS handles the heavy lifting */
code {
    font-size: 0.85em;
    word-break: break-all;
}

button[onclick*="clipboard"] {
    font-size: 0.8em;
    padding: 0.25em 0.5em;
    margin-left: 0.5em;
}

mark {
    background-color: #fbbf24;
    padding: 0.1em 0.4em;
    border-radius: 4px;
}
```

- [ ] **Step 7: Create src/lunchbox/web/router.py**

```python
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription, User

router = APIRouter(tags=["web"])
_here = Path(__file__).parent
templates = Jinja2Templates(directory=str(_here / "templates"))


@router.get("/", response_class=HTMLResponse)
def landing(request: Request):
    user = None
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse("landing.html", {"request": request, "user": user})


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    subscriptions = db.query(Subscription).filter(Subscription.user_id == user.id).all()
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "user": user, "subscriptions": subscriptions, "base_url": settings.base_url},
    )


@router.get("/subscriptions/new", response_class=HTMLResponse)
def new_subscription(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse(
        "subscription_new.html", {"request": request, "user": user}
    )


@router.get("/subscriptions/{subscription_id}", response_class=HTMLResponse)
def subscription_detail(
    subscription_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        return RedirectResponse(url="/dashboard")
    return templates.TemplateResponse(
        "subscription_detail.html",
        {"request": request, "user": user, "sub": sub, "base_url": settings.base_url},
    )


@router.get("/subscriptions/{subscription_id}/preview", response_class=HTMLResponse)
def subscription_preview(
    subscription_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        return RedirectResponse(url="/dashboard")

    items = (
        db.query(MenuItem)
        .filter(MenuItem.subscription_id == sub.id)
        .order_by(MenuItem.menu_date, MenuItem.meal_type)
        .all()
    )

    # Group by date → meal_type → items
    grouped: dict = {}
    for item in items:
        date_str = item.menu_date.isoformat()
        grouped.setdefault(date_str, {}).setdefault(item.meal_type, []).append(item)

    return templates.TemplateResponse(
        "subscription_preview.html",
        {"request": request, "user": user, "sub": sub, "grouped_items": grouped},
    )
```

- [ ] **Step 8: Update src/lunchbox/main.py with all routers**

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.router import api_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.db import engine
from lunchbox.scheduler.jobs import start_scheduler, stop_scheduler
from lunchbox.telemetry.setup import setup_telemetry
from lunchbox.web.router import router as web_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_telemetry(app=app, engine=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="Lunchbox", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600)

app.mount("/static", StaticFiles(directory=str(Path(__file__).parent / "web" / "static")), name="static")

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 9: Write API integration tests**

Create `tests/integration/test_api.py`:

```python
import uuid

from lunchbox.models import Subscription, User


def _create_authenticated_user(client, db):
    """Helper: create user and set session."""
    user = User(google_id="api-test", email="t@t.com", name="Test")
    db.add(user)
    db.commit()
    db.refresh(user)

    # Simulate login by setting session
    with client.session_transaction() if hasattr(client, 'session_transaction') else nullcontext():
        pass
    # For TestClient, we'll need to set the session cookie
    # This is handled by the test fixture overriding get_current_user
    return user


def test_create_subscription(client, db):
    # Override auth for testing
    from lunchbox.auth.dependencies import get_current_user
    from lunchbox.main import app

    user = User(google_id="api-create", email="t@t.com", name="Test")
    db.add(user)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post("/api/subscriptions", json={
        "school_id": "abc-123",
        "school_name": "Test School",
        "grade": "05",
        "meal_configs": [
            {"meal_type": "Lunch", "serving_line": "Traditional Lunch", "sort_order": 0}
        ],
        "display_name": "Test School - 5th Grade",
    })

    assert response.status_code == 201
    data = response.json()
    assert "feed_url" in data
    assert data["feed_url"].startswith("/cal/")

    app.dependency_overrides.clear()


def test_list_subscriptions(client, db):
    from lunchbox.auth.dependencies import get_current_user
    from lunchbox.main import app

    user = User(google_id="api-list", email="t@t.com", name="Test")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="Test",
    )
    db.add(sub)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Test"

    app.dependency_overrides.clear()
```

- [ ] **Step 10: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS

- [ ] **Step 11: Commit**

```bash
git add -A
git commit -m "feat: add subscription CRUD API and HTMX web UI

REST API for subscription management (create, list, update, delete,
regenerate token). School search proxies SchoolCafe API. Manual sync
trigger and sync history endpoints.

HTMX frontend: landing page, dashboard, subscription wizard,
detail/edit page, menu preview. Pico CSS for styling."
```

---

### Task 9: Scheduler + OpenTelemetry (Issue #10)

**Files:**
- Create: `src/lunchbox/telemetry/__init__.py`
- Create: `src/lunchbox/telemetry/setup.py`
- Create: `src/lunchbox/scheduler/__init__.py`
- Create: `src/lunchbox/scheduler/jobs.py`
- Modify: `src/lunchbox/main.py` (add telemetry + scheduler to lifespan)
- Modify: `src/lunchbox/sync/engine.py` (add spans and metrics)
- Modify: `src/lunchbox/sync/menu_client.py` (add drift metrics)
- Modify: `src/lunchbox/api/feeds.py` (add feed metrics)

- [ ] **Step 1: Create src/lunchbox/telemetry/__init__.py**

(Empty file.)

- [ ] **Step 2: Create src/lunchbox/telemetry/setup.py**

```python
import logging

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from lunchbox.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(app=None, engine=None):
    """Configure OpenTelemetry. No-op if OTLP endpoint not set."""
    if not settings.otel_exporter_otlp_endpoint:
        logger.info("OTLP endpoint not configured, telemetry disabled")
        return

    resource = Resource.create({"service.name": settings.otel_service_name})

    # Traces
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter())
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Auto-instrumentation
    if app:
        FastAPIInstrumentor.instrument_app(app)
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    logger.info("OpenTelemetry configured, exporting to %s", settings.otel_exporter_otlp_endpoint)


def get_tracer(name: str = "lunchbox"):
    return trace.get_tracer(name)


def get_meter(name: str = "lunchbox"):
    return metrics.get_meter(name)
```

- [ ] **Step 3: Create src/lunchbox/scheduler/__init__.py**

(Empty file.)

- [ ] **Step 4: Create src/lunchbox/scheduler/jobs.py**

```python
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from lunchbox.config import settings
from lunchbox.db import SessionLocal
from lunchbox.sync.engine import sync_all
from lunchbox.sync.menu_client import SchoolCafeClient

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.timezone)


def daily_sync_job():
    """Run sync for all active subscriptions."""
    logger.info("Starting daily sync")
    db = SessionLocal()
    client = SchoolCafeClient()
    try:
        sync_all(db, client, days=settings.days_to_fetch, skip_weekends=settings.skip_weekends)
    except Exception:
        logger.exception("Daily sync failed")
    finally:
        client.close()
        db.close()


def start_scheduler():
    scheduler.add_job(
        daily_sync_job,
        CronTrigger(hour=settings.sync_hour, minute=settings.sync_minute),
        id="daily_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started: sync at %02d:%02d %s", settings.sync_hour, settings.sync_minute, settings.timezone)


def stop_scheduler():
    scheduler.shutdown(wait=False)
```

- [ ] **Step 5: Add spans and metrics to sync engine**

Modify `src/lunchbox/sync/engine.py` — add at top:

```python
from lunchbox.telemetry.setup import get_meter, get_tracer

tracer = get_tracer()
meter = get_meter()

sync_run_counter = meter.create_counter("sync.run", description="Sync runs by status")
items_fetched_counter = meter.create_counter("sync.items_fetched", description="Menu items fetched")
sync_duration_histogram = meter.create_histogram("sync.duration_seconds", description="Sync duration")
```

Wrap `sync_subscription` body in:

```python
with tracer.start_as_current_span("sync.subscription", attributes={
    "subscription.id": str(subscription.id),
    "school.name": subscription.school_name,
}) as span:
    # ... existing body ...
    # Before return, add:
    span.set_attribute("sync.status", status)
    span.set_attribute("sync.items_fetched", total_items)
    log.trace_id = span.get_span_context().trace_id

    sync_run_counter.add(1, {"status": status})
    items_fetched_counter.add(total_items, {"school": subscription.school_name})
    sync_duration_histogram.record(duration_ms / 1000, {"school": subscription.school_name})
```

Wrap each date fetch in:

```python
with tracer.start_as_current_span("sync.fetch_menu", attributes={
    "menu.date": sync_date.isoformat(),
    "menu.meal_type": meal_type,
}):
```

- [ ] **Step 6: Add drift metrics to menu_client.py**

Add at top of `src/lunchbox/sync/menu_client.py`:

```python
from lunchbox.telemetry.setup import get_meter

meter = get_meter()
drift_counter = meter.create_counter("schoolcafe.schema_drift", description="Schema drift events")
fallback_counter = meter.create_counter("schoolcafe.fallback_extraction", description="Fallback extraction used")
```

In `_extract_item_name`, when fallback is used, add:

```python
fallback_counter.add(1, {"strategy": "fallback_field"})
```

In `get_daily_menu`, when drift is detected:

```python
for warning in drift_warnings:
    drift_counter.add(1, {"warning": warning[:50]})
```

- [ ] **Step 7: Add feed metrics to feeds.py**

Add at top of `src/lunchbox/api/feeds.py`:

```python
from lunchbox.telemetry.setup import get_meter

meter = get_meter()
feed_requests = meter.create_counter("feed.requests", description="Feed requests")
feed_generation = meter.create_histogram("feed.generation_seconds", description="Feed generation time")
```

In `get_feed`, wrap the generation in timing and increment counter.

- [ ] **Step 8: Verify main.py lifespan**

`main.py` (from Task 8, Step 8) already includes the telemetry and scheduler setup in its lifespan. Verify the imports are present:

```python
from lunchbox.db import engine
from lunchbox.scheduler.jobs import start_scheduler, stop_scheduler
from lunchbox.telemetry.setup import setup_telemetry
```

- [ ] **Step 9: Run all tests**

```bash
pytest tests/ -v
```

Expected: All tests PASS (telemetry is no-op without OTLP endpoint)

- [ ] **Step 10: Commit**

```bash
git add -A
git commit -m "feat: add OpenTelemetry instrumentation and APScheduler

Auto-instrumentation for FastAPI, SQLAlchemy, HTTPX. Manual spans on
sync runs, menu fetches. Metrics: sync.run, sync.items_fetched,
sync.duration_seconds, schoolcafe.schema_drift, feed.requests.

APScheduler runs daily sync at configured time. No-op if OTLP
endpoint not set."
```

---

## Chunk 5: CI + Polish (Issue #11)

### Task 10: GitHub Actions CI + final polish (Issue #11)

**Files:**
- Create: `.github/workflows/pr.yml`
- Verify: all tests pass
- Verify: ruff clean

- [ ] **Step 1: Create .github/workflows/pr.yml**

```yaml
name: PR Check

on:
  pull_request:
    branches: [main]

jobs:
  check:
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: lunchbox_test
          POSTGRES_USER: lunchbox
          POSTGRES_PASSWORD: test
        ports:
          - 5432:5432
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Lint
        run: |
          ruff check .
          ruff format --check .

      - name: Test
        env:
          DATABASE_URL: postgresql://lunchbox:test@localhost:5432/lunchbox_test
        run: pytest -v

      # pr-toolkit review is required before merge — run manually or via
      # Claude Code in the PR. This CI job covers lint + test gates.
```

- [ ] **Step 2: Run full test suite locally**

```bash
ruff check . && ruff format --check .
pytest tests/ -v
```

Expected: All lint clean, all tests PASS

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: add GitHub Actions CI workflow

Runs ruff lint/format check and pytest against Postgres service
container on every PR to main."
```

- [ ] **Step 4: Push to GitHub and verify**

Note: This initial push to `main` is the one exception to the PR rule — it bootstraps the repo. All subsequent changes go through PRs.

```bash
git remote set-url origin https://github.com/Techne-Analytics/lunchbox.git
git push -u origin main
```
