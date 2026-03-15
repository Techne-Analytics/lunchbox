# Lunchbox: Design Spec

**Date:** 2026-03-14
**Status:** Approved
**Goal:** Rebuild the school lunch menu calendar sync as a proper web app with iCal feed output, observability, and a path to multi-user.

## Context

The current project is a Docker Compose stack running n8n + a Python scheduled task. It fetches school menus from SchoolCafe (Denver Public Schools) and writes events to a Google Calendar via the Calendar API. It works, but:

- n8n is unnecessary overhead for a single scheduled Python job
- Google Calendar write API requires per-user OAuth with calendar scopes, token refresh, and credential health monitoring
- No tests, no CI, no observability
- Single-user, hardcoded school/meal config in environment variables
- No web UI for configuration

## What We're Building

**Lunchbox** — a FastAPI web app that syncs school lunch/breakfast menus to subscribable iCal calendar feeds.

### Core User Flow

1. Sign in with Google
2. Add a subscription: pick district, school, grade, meal types
3. Configure filters (categories, excluded items) and calendar display settings
4. Get a `.ics` subscribe URL
5. Paste URL into any calendar app (Google, Apple, Outlook)
6. Menus sync daily; calendar stays up to date

## Architecture

### Modular Monolith

Single FastAPI application with clean internal modules. One container, one process, Postgres for storage.

**Why:** The app syncs menus once a day. Splitting into multiple services adds complexity without benefit at this scale. Module boundaries give the same separation, and services can be extracted later if multi-user growth demands it.

### Project Structure

```
lunchbox/
├── docker-compose.yml          # Postgres + Lunchbox app
├── Dockerfile
├── pyproject.toml              # deps, pytest config, ruff config
├── alembic/                    # DB migrations
│   └── versions/
├── src/
│   └── lunchbox/
│       ├── __init__.py
│       ├── main.py             # FastAPI app factory, lifespan (scheduler + OTel)
│       ├── config.py           # Pydantic Settings (env-based config)
│       ├── db.py               # SQLAlchemy engine, session factory
│       │
│       ├── models/             # SQLAlchemy ORM models
│       │   ├── user.py         # User (Google ID, email, name)
│       │   ├── subscription.py # School + meal + calendar config per user
│       │   ├── menu_item.py    # Stored menu data
│       │   └── sync_log.py     # Sync execution history
│       │
│       ├── auth/               # Google OAuth login
│       │   ├── router.py       # /auth/login, /auth/callback, /auth/logout
│       │   └── dependencies.py # get_current_user dependency
│       │
│       ├── api/                # REST API (JSON)
│       │   ├── router.py
│       │   ├── schools.py      # GET /api/schools — proxy SchoolCafe
│       │   ├── subscriptions.py# CRUD /api/subscriptions
│       │   ├── sync.py         # POST /api/sync/trigger, GET /api/sync/history
│       │   └── feeds.py        # GET /cal/{token}.ics
│       │
│       ├── web/                # HTMX frontend (server-rendered)
│       │   ├── router.py
│       │   ├── templates/      # Jinja2 templates
│       │   └── static/         # CSS, minimal JS
│       │
│       ├── sync/               # Core sync engine
│       │   ├── engine.py       # Orchestrator: fetch menu → store in DB
│       │   ├── menu_client.py  # SchoolCafe API (resilient, self-healing)
│       │   └── providers.py    # MenuProvider interface for future sources
│       │
│       ├── scheduler/          # APScheduler job definitions
│       │   └── jobs.py
│       │
│       └── telemetry/          # OpenTelemetry setup
│           └── setup.py        # Tracer/meter provider, Grafana OTLP exporter
│
├── tests/
│   ├── conftest.py             # Fixtures: test DB, test client, captured responses
│   ├── fixtures/               # Captured SchoolCafe responses
│   ├── unit/
│   │   ├── test_menu_client.py
│   │   ├── test_sync_engine.py
│   │   └── test_models.py
│   └── integration/
│       ├── test_api.py
│       └── test_auth.py
│
├── CLAUDE.md
├── CONTRIBUTING.md
└── .github/
    └── workflows/
        └── pr.yml              # ruff + pytest + pr-toolkit
```

## Data Model

### users

| Column     | Type      | Notes                    |
|------------|-----------|--------------------------|
| id         | UUID (PK) |                          |
| google_id  | String    | Unique, from Google OAuth|
| email      | String    |                          |
| name       | String    |                          |
| created_at | Timestamp |                          |
| updated_at | Timestamp |                          |

### subscriptions

One subscription = one school + one grade + selected meals → one `.ics` feed URL.

| Column                | Type         | Notes                                           |
|-----------------------|--------------|-------------------------------------------------|
| id                    | UUID (PK)    |                                                 |
| user_id               | UUID (FK)    | → users.id                                      |
| provider              | String       | "schoolcafe" for now                            |
| school_id             | String       | Provider-specific school ID                     |
| school_name           | String       | Cached display name                             |
| grade                 | String       | e.g., "05", "K", "12"                           |
| meal_configs          | JSON         | Ordered array of meal type + serving line        |
| included_categories   | JSON         | Array of category names, null = include all      |
| excluded_items        | JSON         | Array of item names to always filter out         |
| feed_token            | UUID (UQ)    | Random, used in /cal/{token}.ics URL            |
| display_name          | String       | User-facing label, e.g., "Shoemaker - 5th Grade"|
| alert_minutes         | Integer      | null = no alert                                 |
| show_as_busy          | Boolean      | Default false (transparent)                     |
| event_type            | String       | "all_day" (default) or "timed"                  |
| event_start_time      | Time         | Only if event_type = "timed"                    |
| event_end_time        | Time         | Only if event_type = "timed"                    |
| is_active             | Boolean      | Default true                                    |
| created_at            | Timestamp    |                                                 |
| updated_at            | Timestamp    |                                                 |

**meal_configs format:**

```json
[
  {"meal_type": "Breakfast", "serving_line": "Grab n Go Breakfast", "sort_order": 0},
  {"meal_type": "Lunch", "serving_line": "Traditional Lunch", "sort_order": 1}
]
```

Alphabetical ordering is used for all-day event display (Breakfast < Lunch works naturally).

### menu_items

| Column          | Type      | Notes                              |
|-----------------|-----------|------------------------------------|
| id              | UUID (PK) |                                    |
| subscription_id | UUID (FK) | → subscriptions.id                 |
| school_id       | String    |                                    |
| menu_date       | Date      |                                    |
| meal_type       | String    |                                    |
| serving_line    | String    |                                    |
| grade           | String    |                                    |
| category        | String    | e.g., "Entrees", "Fruits"          |
| item_name       | String    |                                    |
| fetched_at      | Timestamp |                                    |

Raw data stored unfiltered. Category/item filters applied at iCal generation time so filter changes take effect immediately without re-syncing.

Upsert strategy: bulk delete-and-reinsert per `(subscription_id, menu_date, meal_type)` — delete all items for that combo, then insert the fresh set. Simple, avoids stale items.

### sync_logs

| Column          | Type      | Notes                              |
|-----------------|-----------|------------------------------------|
| id              | UUID (PK) |                                    |
| subscription_id | UUID (FK) | → subscriptions.id                 |
| status          | String    | "success", "partial", "error"      |
| dates_synced    | Integer   |                                    |
| items_fetched   | Integer   |                                    |
| error_message   | String    | Nullable                           |
| duration_ms     | Integer   |                                    |
| trace_id        | String    | OpenTelemetry trace ID             |
| started_at      | Timestamp |                                    |
| completed_at    | Timestamp |                                    |

## iCal Feed Generation

`GET /cal/{feed_token}.ics` — public, no auth required (token is the secret).

Generates a VCALENDAR with VEVENT entries from stored menu_items:

- One VEVENT per meal type per date
- Summary: `Breakfast: Scrambled Eggs, Toast, Apple`
- Description: categorized list with bullets
- VALARM included only if `alert_minutes` is set
- TRANSP:TRANSPARENT when `show_as_busy` is false
- All-day events by default, timed if configured
- Feed token can be regenerated if leaked
- HTTP caching: `Last-Modified` header based on latest `menu_items.fetched_at`, `ETag` based on content hash, `Cache-Control: max-age=3600` to reduce redundant generation (calendar apps poll every 6-12 hours)

## Sync Engine

### Flow

```
scheduler triggers sync (daily, configurable)
  └─ for each active subscription:
      └─ [span: sync.subscription]
          ├─ get target dates (next N weekdays)
          ├─ for each date × meal_config:
          │   ├─ [span: sync.fetch_menu]
          │   │   ├─ call provider API
          │   │   ├─ detect schema drift
          │   │   └─ normalize with fallback extraction
          │   └─ [span: sync.store_items]
          │       └─ upsert menu_items (replace for date+meal)
          └─ write sync_log with trace_id
```

### Self-Healing for SchoolCafe API Drift

We do not control the SchoolCafe API and must assume its schema can change without notice.

**Defensive parsing:**
- Never assume keys exist — `.get()` with defaults everywhere
- Accept unknown category names gracefully (title-case and include them)

**Fallback field extraction:**
1. Primary: `item["MenuItemDescription"]`
2. Fallback: `item["Name"]`, `item["name"]`, `item["description"]`
3. Last resort: `str(item)` if it's a plain string
4. Log which extraction path succeeded for drift visibility

**Schema drift detection:**
- Store response fingerprint (top-level keys, item field names)
- Compare against last known good fingerprint
- Emit `schoolcafe.schema_drift` metric on mismatch
- Still attempt to parse — alert, don't crash

**Graceful degradation:**
- Single date/meal failure → continue with the rest
- Partial data → use what we got
- API down → serve stale data from Postgres (feed still works)

### Menu Provider Interface

```python
class MenuProvider:
    def get_daily_menu(self, school_id, date, meal_type, grade) -> list[MenuItem]
    def search_schools(self, query) -> list[School]
```

`SchoolCafeProvider` is the first implementation. The interface supports adding other sources (Nutrislice, MealViewer, etc.) without changing the sync engine.

## Authentication

Google OAuth for login only. Scopes: `openid`, `email`, `profile`.

No Google Calendar API scopes needed — we serve iCal feeds, not write to Calendar API.

Session-based auth with signed cookies (itsdangerous or Starlette session middleware). Session lifetime: 30 days, sliding expiry.

## Observability

### OpenTelemetry → Grafana Cloud

**Auto-instrumentation (zero code):**
- FastAPI: every HTTP request traced with method, route, status, duration
- SQLAlchemy: every DB query traced
- Requests: every outbound HTTP call traced (SchoolCafe API)
- Built-in metrics: request latency histograms, error rates

**Manual instrumentation (light touch):**
- `sync.subscription` span per sync run
- `sync.fetch_menu` and `sync.store_items` spans per date
- `schoolcafe.schema_drift` counter
- `schoolcafe.fallback_extraction` counter
- `feed.generation_seconds` histogram
- `feed.requests` counter
- `sync.items_fetched` counter
- `sync.run` counter with status attribute

**Configuration:**
```
OTEL_EXPORTER_OTLP_ENDPOINT=https://otlp-gateway-....grafana.net/otlp
OTEL_EXPORTER_OTLP_HEADERS=Authorization=Basic <base64>
OTEL_SERVICE_NAME=lunchbox
```

**Trace linking:** sync_logs stores trace_id for direct links from the web UI to Grafana trace view.

**Dashboards:**
1. Lunchbox Overview — sync success rate, last sync per subscription, feed requests
2. SchoolCafe Health — API latency, error rate, schema drift events
3. Alerts — consecutive sync failures, schema drift, API error spike

## Web UI

Server-rendered Jinja2 templates with HTMX. No JS build step.

**Pages:**
- `/` — landing page, "Sign in with Google"
- `/dashboard` — subscription list, sync status, feed URLs
- `/subscriptions/new` — wizard: school → grade → meals → filters → calendar settings
- `/subscriptions/{id}` — edit settings, feed URL, sync history, manual sync trigger
- `/subscriptions/{id}/preview` — HTML preview of current calendar data

**Stack:** HTMX (CDN) + Pico CSS or similar classless framework. Alpine.js only if needed.

## Testing

**Unit tests:**
- Menu client parsing (with captured real responses as fixtures)
- Sync engine logic (menu normalization, filtering, event building)
- iCal feed generation
- Model validation

**Integration tests:**
- API endpoints (CRUD subscriptions, trigger sync, feed generation)
- Auth flow (mock Google OAuth)
- Database operations

**Contract tests:**
- Captured SchoolCafe API responses as fixtures
- Tests validate parsing against real response shapes
- Schema drift detection tests (mutated fixtures)

**No end-to-end tests against live APIs.** Tests must be fast, reliable, and runnable in CI without external dependencies.

## CI/CD

### GitHub Actions — `.github/workflows/pr.yml`

```yaml
on: pull_request
jobs:
  check:
    steps:
      - ruff check . && ruff format --check .
      - pytest (unit + integration against test Postgres via service container)
      - pr-toolkit review
```

One workflow, one job. Docker image builds and deploy added when moving to Fly.io.

## Development Workflow

1. **Everything starts as a GitHub issue** — bugs, features, tasks
2. **Branch from `main`** — `<type>/<issue-number>-<short-description>` (e.g., `feat/12-add-filters`)
3. **Atomic, semantic commits** — `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`. Each commit is one logical change.
4. **PR to `main`** — reference the issue (`Closes #12`)
5. **pr-toolkit review** — required before merge
6. **Merge** — squash or rebase, clean history

**Trunk-based development.** `main` is the only long-lived branch. All commits into `main` go through a PR, no matter how small.

## Migration from Current Project

1. Remove n8n service, workflow JSON, and n8n-related docs entirely
2. Remove n8n_data directory
3. Restructure into `src/lunchbox/` layout
4. Port `menu_api.py` → `sync/menu_client.py` with self-healing additions
5. Port sync logic from `app.py` → `sync/engine.py` (simplified: no Calendar API writes)
6. Add Postgres, Alembic, SQLAlchemy models
7. Add FastAPI app, auth, API routes, HTMX templates
8. Add OpenTelemetry setup
9. Add tests with captured fixtures
10. Add CI workflow
11. Write CONTRIBUTING.md

## Deployment

**Now:** Docker Compose on personal server (Postgres + Lunchbox app). HTTPS via reverse proxy (Caddy, nginx, or Cloudflare tunnel — whatever the server already uses). Required for Google OAuth callbacks and public feed URLs.
**Future:** Fly.io (Postgres addon + single machine). The modular monolith maps to one Fly machine. Alembic migrations run on deploy. Same OTLP config points to Grafana Cloud.

## Out of Scope (For Now)

- Multiple menu providers (interface is ready, only SchoolCafe implemented)
- Email notifications
- Public signup (admin creates accounts)
- Mobile app
- Menu change detection / diff notifications
