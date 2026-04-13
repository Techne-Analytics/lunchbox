# Vercel Migration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Lunchbox from Docker Compose to Vercel serverless with Neon Postgres, removing all Docker and APScheduler infrastructure.

**Architecture:** Single Vercel Function (FastAPI) + Neon Postgres (via Vercel integration) + Vercel Cron (daily sync). All routes served from one entry point. NullPool for serverless DB connections. SimpleSpanProcessor for telemetry.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy + NullPool, Alembic, Neon Postgres, Vercel Functions, Vercel Cron, OpenTelemetry (HTTP/protobuf, SimpleSpanProcessor)

**Spec:** [docs/superpowers/specs/2026-04-13-vercel-migration-design.md](../specs/2026-04-13-vercel-migration-design.md)

---

## File Map

| Action | File | Purpose |
|--------|------|---------|
| Modify | `src/lunchbox/config.py` | Remove scheduler settings, add guardrails + cron_secret |
| Modify | `src/lunchbox/db.py` | Use NullPool for serverless |
| Modify | `src/lunchbox/telemetry/setup.py` | SimpleSpanProcessor, remove metrics, split init |
| Modify | `src/lunchbox/main.py` | Remove scheduler + StaticFiles, module-level telemetry |
| Modify | `src/lunchbox/api/sync.py` | Add cron endpoint with guardrails |
| Modify | `src/lunchbox/api/subscriptions.py` | Add subscription cap checks |
| Modify | `src/lunchbox/sync/engine.py` | Add row count guardrail |
| Modify | `pyproject.toml` | Remove apscheduler, move uvicorn to dev |
| Modify | `alembic/env.py` | Read DIRECT_DATABASE_URL |
| Modify | `.github/workflows/ci.yml` | Remove Docker build step |
| Create | `vercel.json` | Functions, rewrites, cron config |
| Create | `requirements.txt` | Generated from pyproject.toml |
| Create | `public/static/style.css` | Moved from src for Vercel static serving |
| Create | `tests/unit/test_cron.py` | Cron endpoint tests |
| Create | `tests/unit/test_guardrails.py` | Subscription cap + row count tests |
| Move | `docker-compose.yml` → `docker/docker-compose.dev.yml` | Local dev only |
| Delete | `Dockerfile` | No longer needed |
| Delete | `src/lunchbox/scheduler/jobs.py` | Replaced by cron endpoint |
| Delete | `src/lunchbox/scheduler/__init__.py` | Directory removed |
| Delete | `tests/unit/test_scheduler.py` | Replaced by test_cron.py |
| Update | `CLAUDE.md` | Reflect Vercel architecture |
| Update | `CONTRIBUTING.md` | Update dev setup |

---

## Chunk 1: Core Infrastructure (config, db, dependencies)

### Task 1: Update config.py — remove scheduler settings, add guardrails

**Files:**
- Modify: `src/lunchbox/config.py`

- [ ] **Step 1: Update Settings class**

Replace the entire file with:

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://lunchbox:lunchbox@localhost:5432/lunchbox"
    secret_key: str
    base_url: str = "http://localhost:8000"

    google_client_id: str = ""
    google_client_secret: str = ""

    otel_exporter_otlp_endpoint: str = ""
    otel_exporter_otlp_headers: str = ""
    otel_service_name: str = "lunchbox"

    # Sync defaults
    days_to_fetch: int = 7
    skip_weekends: bool = True

    # Vercel Cron auth
    cron_secret: str = ""

    # Guardrails
    max_syncs_per_day: int = 10
    max_subscriptions_per_user: int = 5
    max_subscriptions_global: int = 20
    max_menu_items: int = 50000

    model_config = {"env_prefix": "", "case_sensitive": False}


settings = Settings()
```

Removed: `sync_hour`, `sync_minute`, `timezone` (cron schedule lives in `vercel.json` now).
Added: `cron_secret`, `max_syncs_per_day`, `max_subscriptions_per_user`, `max_subscriptions_global`, `max_menu_items`.

- [ ] **Step 2: Verify import works**

Run: `SECRET_KEY=test python -c "from lunchbox.config import settings; print(settings.cron_secret, settings.max_syncs_per_day)"`
Expected: ` 10`

- [ ] **Step 3: Commit**

```bash
git add src/lunchbox/config.py
git commit -m "refactor: remove scheduler settings, add guardrail config for Vercel"
```

### Task 2: Update db.py — NullPool for serverless

**Files:**
- Modify: `src/lunchbox/db.py`

- [ ] **Step 1: Update engine creation**

Replace the entire file with:

```python
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import NullPool

from lunchbox.config import settings

engine = create_engine(settings.database_url, poolclass=NullPool)
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

Only change: added `poolclass=NullPool` import and parameter.

- [ ] **Step 2: Commit**

```bash
git add src/lunchbox/db.py
git commit -m "refactor: use NullPool for serverless DB connections"
```

### Task 3: Update pyproject.toml — remove apscheduler, move uvicorn to dev

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Edit dependencies**

Remove `"apscheduler>=3.10.0",` from `[project] dependencies`.
Move `"uvicorn[standard]>=0.30.0",` from `[project] dependencies` to `[project.optional-dependencies] dev`.

The `dependencies` list becomes:

```toml
dependencies = [
    "fastapi>=0.115.0",
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
    "markupsafe>=2.1.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-exporter-otlp>=1.20.0",
    "opentelemetry-instrumentation-fastapi>=0.44b0",
    "opentelemetry-instrumentation-sqlalchemy>=0.44b0",
    "opentelemetry-instrumentation-httpx>=0.44b0",
]
```

The `dev` list becomes:

```toml
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
    "pip-audit>=2.7.0",
    "pip-tools>=7.0.0",
    "httpx>=0.27.0",
    "ruff>=0.4.0",
    "respx>=0.22.0",
    "uvicorn[standard]>=0.30.0",
]
```

- [ ] **Step 2: Generate requirements.txt**

Run: `pip-compile pyproject.toml -o requirements.txt`

If `pip-tools` is not installed: `pip install pip-tools` first.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml requirements.txt
git commit -m "refactor: remove apscheduler, move uvicorn to dev, generate requirements.txt"
```

### Task 4: Update alembic/env.py — use DIRECT_DATABASE_URL

**Files:**
- Modify: `alembic/env.py`

- [ ] **Step 1: Update database URL resolution**

Replace lines 12-21 with:

```python
# Prefer DIRECT_DATABASE_URL for migrations (bypasses Neon connection pooler).
# Falls back to DATABASE_URL for local dev.
database_url = (
    os.environ.get("DIRECT_DATABASE_URL")
    or os.environ.get("DATABASE_URL")
    or config.get_main_option("sqlalchemy.url")
)
if not database_url:
    raise RuntimeError(
        "DATABASE_URL is not set and sqlalchemy.url in alembic.ini is empty. "
        "Set DATABASE_URL in your environment or copy .env.example to .env."
    )
config.set_main_option("sqlalchemy.url", database_url)
```

- [ ] **Step 2: Commit**

```bash
git add alembic/env.py
git commit -m "refactor: prefer DIRECT_DATABASE_URL for Alembic migrations"
```

---

## Chunk 2: Telemetry & App Entry Point

### Task 5: Rewrite telemetry/setup.py for serverless

**Files:**
- Modify: `src/lunchbox/telemetry/setup.py`

- [ ] **Step 1: Rewrite for serverless**

Replace the entire file with:

```python
import logging

from opentelemetry import trace
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor

from lunchbox.config import settings

logger = logging.getLogger(__name__)


def setup_telemetry(engine=None) -> None:
    """Configure OpenTelemetry traces. No-op if OTLP endpoint not set.

    Call at module level before app creation. Metrics removed for serverless
    (Grafana derives metrics from traces).
    """
    if not settings.otel_exporter_otlp_endpoint:
        logger.info("OTLP endpoint not configured, telemetry disabled")
        return

    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )

    resource = Resource.create({"service.name": settings.otel_service_name})

    # Traces — SimpleSpanProcessor for serverless (synchronous export per span)
    tracer_provider = TracerProvider(resource=resource)
    tracer_provider.add_span_processor(SimpleSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(tracer_provider)

    # Auto-instrumentation (SQLAlchemy + HTTPX)
    if engine:
        SQLAlchemyInstrumentor().instrument(engine=engine)
    HTTPXClientInstrumentor().instrument()

    logger.info(
        "OpenTelemetry configured, exporting to %s",
        settings.otel_exporter_otlp_endpoint,
    )


def instrument_app(app) -> None:
    """Instrument FastAPI app. Call after app creation."""
    if not settings.otel_exporter_otlp_endpoint:
        return
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    FastAPIInstrumentor.instrument_app(app)


def get_tracer(name: str = "lunchbox") -> trace.Tracer:
    return trace.get_tracer(name)
```

Key changes:
- Removed `metrics` imports, `MeterProvider`, `PeriodicExportingMetricReader`, `get_meter()`
- `BatchSpanProcessor` → `SimpleSpanProcessor`
- Split into `setup_telemetry(engine)` (module-level) and `instrument_app(app)` (after app creation)
- Removed `app` parameter from `setup_telemetry`

- [ ] **Step 2: Commit**

```bash
git add src/lunchbox/telemetry/setup.py
git commit -m "refactor: serverless telemetry — SimpleSpanProcessor, remove metrics, split init"
```

### Task 6: Rewrite main.py — remove scheduler, StaticFiles, module-level telemetry

**Files:**
- Modify: `src/lunchbox/main.py`

- [ ] **Step 1: Rewrite main.py**

Replace the entire file with:

```python
from starlette.middleware.sessions import SessionMiddleware

from lunchbox.api.router import api_router
from lunchbox.auth.router import router as auth_router
from lunchbox.config import settings
from lunchbox.db import engine
from lunchbox.telemetry.setup import instrument_app, setup_telemetry
from lunchbox.web.router import router as web_router

# Module-level telemetry init (Vercel may not dispatch ASGI lifespan events)
setup_telemetry(engine=engine)

from fastapi import FastAPI  # noqa: E402 — must be after telemetry init

app = FastAPI(title="Lunchbox")
app.add_middleware(
    SessionMiddleware, secret_key=settings.secret_key, max_age=30 * 24 * 3600
)

# Instrument FastAPI after app creation
instrument_app(app)

app.include_router(auth_router)
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
```

Removed: `asynccontextmanager`, `Path`, `StaticFiles`, `lifespan`, `start_scheduler`, `stop_scheduler`.
Static files now served by Vercel from `public/` directory.

- [ ] **Step 2: Commit**

```bash
git add src/lunchbox/main.py
git commit -m "refactor: remove scheduler and StaticFiles from main, module-level telemetry"
```

---

## Chunk 3: Cron Endpoint & Guardrails

### Task 7: Add cron endpoint to api/sync.py

**Files:**
- Modify: `src/lunchbox/api/sync.py`

- [ ] **Step 1: Add cron endpoint and imports**

Add these imports at the top (after existing imports):

```python
import logging
from datetime import date, datetime, timezone

from lunchbox.models import MenuItem
from lunchbox.sync.engine import sync_all
```

Add the cron endpoint after the existing `sync_history` function:

```python
logger = logging.getLogger(__name__)


@router.get("/cron")
def cron_sync(request: Request, db: Session = Depends(get_db)) -> dict:
    """Vercel Cron endpoint — syncs all active subscriptions."""
    # Validate cron secret
    if not settings.cron_secret:
        raise HTTPException(status_code=403, detail="CRON_SECRET not configured")

    cron_auth = request.headers.get("x-vercel-cron-auth", "")
    if cron_auth != settings.cron_secret:
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    # Guardrail: max syncs per day
    today = date.today()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    syncs_today = (
        db.query(SyncLog)
        .filter(SyncLog.started_at >= today_start)
        .count()
    )
    if syncs_today >= settings.max_syncs_per_day:
        logger.warning("Sync skipped: %d syncs today (max %d)", syncs_today, settings.max_syncs_per_day)
        return {"status": "skipped", "reason": "max_syncs_per_day reached"}

    # Guardrail: max menu items
    total_items = db.query(MenuItem).count()
    if total_items >= settings.max_menu_items:
        logger.warning("Sync skipped: %d menu items (max %d)", total_items, settings.max_menu_items)
        return {"status": "skipped", "reason": "max_menu_items reached"}

    # Run sync
    with SchoolCafeClient() as client:
        sync_all(
            db,
            client,
            days=settings.days_to_fetch,
            skip_weekends=settings.skip_weekends,
        )

    return {"status": "ok"}
```

Also add `Request` to the FastAPI imports at the top:

```python
from fastapi import APIRouter, Depends, HTTPException, Request
```

- [ ] **Step 2: Commit**

```bash
git add src/lunchbox/api/sync.py
git commit -m "feat: add Vercel Cron sync endpoint with guardrails"
```

### Task 8: Add subscription cap checks to api/subscriptions.py

**Files:**
- Modify: `src/lunchbox/api/subscriptions.py`

- [ ] **Step 1: Add cap checks to create_subscription**

Add this block at the beginning of the `create_subscription` function body (after line 68, before the `sub = Subscription(...)` line):

```python
    # Guardrail: subscription caps
    user_count = (
        db.query(Subscription)
        .filter(Subscription.user_id == user.id, Subscription.is_active.is_(True))
        .count()
    )
    if user_count >= settings.max_subscriptions_per_user:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {settings.max_subscriptions_per_user} active subscriptions per user",
        )

    global_count = (
        db.query(Subscription)
        .filter(Subscription.is_active.is_(True))
        .count()
    )
    if global_count >= settings.max_subscriptions_global:
        raise HTTPException(
            status_code=400,
            detail="Maximum active subscriptions reached",
        )
```

Also add `from lunchbox.config import settings` to imports if not already present (check — it's not currently imported in this file).

- [ ] **Step 2: Commit**

```bash
git add src/lunchbox/api/subscriptions.py
git commit -m "feat: add subscription cap guardrails on create"
```

---

## Chunk 4: Remove Scheduler, Add Vercel Config, Move Files

### Task 9: Delete scheduler directory and tests

**Files:**
- Delete: `src/lunchbox/scheduler/jobs.py`
- Delete: `src/lunchbox/scheduler/__init__.py`
- Delete: `tests/unit/test_scheduler.py`

- [ ] **Step 1: Remove files**

```bash
rm -rf src/lunchbox/scheduler/
rm tests/unit/test_scheduler.py
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "refactor: remove APScheduler — replaced by Vercel Cron endpoint"
```

### Task 10: Move Docker files, delete Dockerfile

**Files:**
- Move: `docker-compose.yml` → `docker/docker-compose.dev.yml`
- Delete: `Dockerfile`

- [ ] **Step 1: Move and delete**

```bash
mkdir -p docker
git mv docker-compose.yml docker/docker-compose.dev.yml
git rm Dockerfile
```

- [ ] **Step 2: Commit**

```bash
git commit -m "refactor: move docker-compose to docker/ for local dev, delete Dockerfile"
```

### Task 11: Move static files to public/

**Files:**
- Create: `public/static/style.css` (moved from `src/lunchbox/web/static/style.css`)

- [ ] **Step 1: Move static files**

```bash
mkdir -p public/static
cp src/lunchbox/web/static/style.css public/static/style.css
git rm src/lunchbox/web/static/style.css
```

Note: Keep the `src/lunchbox/web/static/` directory if other files might go there later, or remove it if empty. Check first.

- [ ] **Step 2: Commit**

```bash
git add public/ src/lunchbox/web/static/
git commit -m "refactor: move static files to public/ for Vercel serving"
```

### Task 12: Create vercel.json

**Files:**
- Create: `vercel.json`

- [ ] **Step 1: Create vercel.json**

```json
{
  "functions": {
    "src/lunchbox/main.py": {
      "runtime": "@vercel/python",
      "maxDuration": 60
    }
  },
  "rewrites": [
    { "source": "/(.*)", "destination": "/src/lunchbox/main.py" }
  ],
  "crons": [
    { "path": "/api/sync/cron", "schedule": "0 12 * * 1-5" }
  ]
}
```

- [ ] **Step 2: Commit**

```bash
git add vercel.json
git commit -m "feat: add vercel.json with function config, rewrites, and cron"
```

### Task 13: Update CI workflow — remove Docker build step

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Remove Docker build step**

Delete lines 61-62 (the `Verify Docker build` step):

```yaml
      - name: Verify Docker build
        run: docker build -t lunchbox:test .
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "chore: remove Docker build step from CI (Dockerfile deleted)"
```

---

## Chunk 5: Tests

### Task 14: Add cron endpoint tests

**Files:**
- Create: `tests/unit/test_cron.py`

- [ ] **Step 1: Write cron tests**

```python
from unittest.mock import MagicMock, patch

from tests.factories import create_subscription, create_sync_log, create_user


class TestCronEndpoint:
    def test_cron_rejects_missing_secret(self, client):
        response = client.get("/api/sync/cron")
        assert response.status_code == 403

    def test_cron_rejects_wrong_secret(self, client):
        response = client.get(
            "/api/sync/cron",
            headers={"x-vercel-cron-auth": "wrong"},
        )
        assert response.status_code == 403

    def test_cron_succeeds_with_correct_secret(self, client, db):
        with (
            patch("lunchbox.api.sync.settings") as mock_settings,
            patch("lunchbox.api.sync.SchoolCafeClient") as MockClient,
        ):
            mock_settings.cron_secret = "test-secret"
            mock_settings.max_syncs_per_day = 10
            mock_settings.max_menu_items = 50000
            mock_settings.days_to_fetch = 1
            mock_settings.skip_weekends = False

            mock_instance = MagicMock()
            mock_instance.get_daily_menu.return_value = []
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.get(
                "/api/sync/cron",
                headers={"x-vercel-cron-auth": "test-secret"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_cron_skips_when_max_syncs_reached(self, authenticated_client, db):
        client, user = authenticated_client
        sub = create_subscription(db, user)
        # Create enough sync logs to hit the limit
        for _ in range(10):
            create_sync_log(db, sub)
        db.commit()

        with patch("lunchbox.api.sync.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            mock_settings.max_syncs_per_day = 10
            mock_settings.max_menu_items = 50000

            response = client.get(
                "/api/sync/cron",
                headers={"x-vercel-cron-auth": "test-secret"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "skipped"
```

- [ ] **Step 2: Run lint**

Run: `ruff check tests/unit/test_cron.py && ruff format tests/unit/test_cron.py`

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_cron.py
git commit -m "test: add Vercel Cron endpoint tests (auth, guardrails, success)"
```

### Task 15: Add subscription cap tests

**Files:**
- Create: `tests/unit/test_guardrails.py`

- [ ] **Step 1: Write guardrail tests**

```python
from unittest.mock import patch

from tests.factories import create_subscription, create_user


class TestSubscriptionCaps:
    def test_per_user_cap(self, authenticated_client, db):
        client, user = authenticated_client
        # Create max subscriptions
        for i in range(5):
            create_subscription(db, user, display_name=f"Sub {i}")
        db.commit()

        with patch("lunchbox.api.subscriptions.settings") as mock_settings:
            mock_settings.max_subscriptions_per_user = 5
            mock_settings.max_subscriptions_global = 20

            response = client.post(
                "/api/subscriptions",
                json={
                    "school_id": "test",
                    "school_name": "Test",
                    "grade": "05",
                    "meal_configs": [{"meal_type": "Lunch", "serving_line": "Trad", "sort_order": 0}],
                    "display_name": "Over Limit",
                },
            )

        assert response.status_code == 400
        assert "Maximum" in response.json()["detail"]

    def test_global_cap(self, authenticated_client, db):
        client, user = authenticated_client
        # Create subscriptions under different users to hit global cap
        for i in range(20):
            other = create_user(db, google_id=f"global-cap-{i}")
            create_subscription(db, other, display_name=f"Global {i}")
        db.commit()

        with patch("lunchbox.api.subscriptions.settings") as mock_settings:
            mock_settings.max_subscriptions_per_user = 5
            mock_settings.max_subscriptions_global = 20

            response = client.post(
                "/api/subscriptions",
                json={
                    "school_id": "test",
                    "school_name": "Test",
                    "grade": "05",
                    "meal_configs": [{"meal_type": "Lunch", "serving_line": "Trad", "sort_order": 0}],
                    "display_name": "Over Global Limit",
                },
            )

        assert response.status_code == 400
```

- [ ] **Step 2: Run lint**

Run: `ruff check tests/unit/test_guardrails.py && ruff format tests/unit/test_guardrails.py`

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_guardrails.py
git commit -m "test: add subscription cap guardrail tests"
```

---

## Chunk 6: Documentation & Final Verification

### Task 16: Update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update CLAUDE.md**

Replace the full file to reflect Vercel architecture:

```markdown
# Lunchbox

FastAPI web app that syncs school lunch/breakfast menus from SchoolCafe to subscribable iCal calendar feeds.

## Key Docs — Read These First

- **[CONTRIBUTING.md](CONTRIBUTING.md)** — development workflow, commit conventions, PR rules. Follow this exactly.
- **[README.md](README.md)** — project overview and quick start.
- **[Design Spec](docs/superpowers/specs/2026-04-13-vercel-migration-design.md)** — current architecture (Vercel + Neon).

## Rules

- **All changes go through PRs.** No direct commits to `main`, no matter how small.
- **Everything starts as a GitHub issue.** Branch from `main`, PR back to `main`.
- **Semantic commits.** `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`.
- **Atomic commits.** One logical change per commit.
- **All PRs run pr-toolkit** for review before merging.
- **Branch naming:** `<type>/<issue-number>-<short-description>`

## Tech Stack

- Python 3.11 / FastAPI / SQLAlchemy / Alembic
- Neon Postgres (via Vercel integration)
- HTMX + Jinja2 (server-rendered UI)
- OpenTelemetry → Grafana Cloud
- Vercel (serverless hosting)
- Vercel Cron (daily sync)
- Ruff (lint + format)
- pytest (tests)

## Project Structure

```
src/lunchbox/
├── main.py             # FastAPI app, module-level telemetry init
├── config.py           # Pydantic Settings + guardrail limits
├── db.py               # SQLAlchemy engine (NullPool) / session
├── models/             # ORM models (user, subscription, menu_item, sync_log)
├── auth/               # Google OAuth login
├── api/                # REST API + iCal feed + cron endpoint
├── web/                # HTMX frontend (Jinja2 templates)
├── sync/               # Menu fetch + sync engine
└── telemetry/          # OpenTelemetry setup (traces only, no metrics)
```

## Key Commands

```bash
docker compose -f docker/docker-compose.dev.yml up -d postgres  # local DB
pip install -e ".[dev]"     # install with dev deps
alembic upgrade head        # run migrations
pytest                      # run tests
ruff check . && ruff format .  # lint + format
```

## Deployment

- Hosted on Vercel (auto-deploys on push to main)
- Database: Neon Postgres (Vercel integration)
- Cron: Vercel Cron hits `/api/sync/cron` weekdays at noon UTC
- Static files: served from `public/` directory

## Sensitive Files — DO NOT COMMIT

- `.env` — secrets, API keys, OAuth credentials
- Any `token.json` or `client_secret.json`

## External APIs

- **SchoolCafe** (schoolcafe.com) — menu data. We do not control this API. Parse defensively, self-heal on schema drift.
- **Google OAuth** — login only (`openid`, `email`, `profile`). No calendar write scopes.
- **Grafana Cloud OTLP** — telemetry export.
```

- [ ] **Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for Vercel architecture"
```

### Task 17: Update CONTRIBUTING.md dev setup

**Files:**
- Modify: `CONTRIBUTING.md`

- [ ] **Step 1: Update Dev Setup section**

Replace lines 53-76 with:

```markdown
## Dev Setup

```bash
# Start local Postgres (for integration tests)
docker compose -f docker/docker-compose.dev.yml up -d postgres

# Install dependencies
pip install -e ".[dev]"

# Enable pre-push hook (lint + unit tests before every push)
git config core.hooksPath .githooks

# Run migrations
alembic upgrade head

# Run tests
pytest

# Lint and format
ruff check .
ruff format .

# Local dev server (not needed for Vercel deploy)
uvicorn lunchbox.main:app --reload
```

The pre-push hook runs `ruff check`, `ruff format --check`, and `pytest tests/unit/` before every push. CI runs the full integration test suite on push to main.

### Deployment

Push to main auto-deploys to Vercel. Environment variables are managed in the Vercel dashboard. Run migrations manually after schema changes: set `DIRECT_DATABASE_URL` and run `alembic upgrade head`.
```

- [ ] **Step 2: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: update CONTRIBUTING.md for Vercel dev workflow"
```

### Task 18: Run full verification

- [ ] **Step 1: Run lint**

Run: `ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 2: Collect tests**

Run: `pytest --collect-only -q`
Expected: ~100 tests collected (scheduler tests gone, cron + guardrail tests added)

- [ ] **Step 3: Run unit tests**

Run: `pytest tests/unit/ -v --tb=short`
Expected: Non-DB tests pass, DB tests skip

- [ ] **Step 4: Verify no stale imports**

Run: `python -c "from lunchbox.main import app; print('OK')"`
Expected: OK (no import errors from removed scheduler module)
