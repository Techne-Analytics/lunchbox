# Vercel Migration Design

Migrate Lunchbox from Docker Compose (local server) to Vercel (serverless) with Neon Postgres. Remove Docker, APScheduler, and self-hosted infrastructure entirely.

## Context

Lunchbox is a FastAPI web app that syncs school lunch menus from SchoolCafe to subscribable iCal calendar feeds. It currently runs as a Docker Compose stack (Postgres + Python app) on a local machine with no public URL. This makes end-to-end testing impossible — calendar apps can't subscribe to `localhost` feeds.

## Goals

- Public HTTPS URL for iCal feed subscriptions and OAuth callbacks
- Zero infrastructure management
- Automatic deploys on push to main
- Vercel Pro plan (60s function timeout, Vercel Cron support)

## Architecture

### Three components, one platform

1. **Vercel Function** — the FastAPI app deployed as a single Python serverless function. All routes (API, web, auth, feeds) served from one entry point.
2. **Neon Postgres** — managed via Vercel's built-in integration. Connection string auto-injected as `DATABASE_URL`. Uses Neon's built-in connection pooler.
3. **Vercel Cron** — a `cron` entry in `vercel.json` that hits `GET /api/sync/cron` daily at 6 AM CT (weekdays only). Protected by `CRON_SECRET` header.

### What gets removed

- `Dockerfile` — deleted
- `docker-compose.yml` — moved to `docker/docker-compose.dev.yml` for local Postgres dev
- `APScheduler` — replaced by Vercel Cron + endpoint
- `apscheduler` dependency — removed from `pyproject.toml`
- `src/lunchbox/scheduler/` directory — deleted entirely
- `start_scheduler()` / `stop_scheduler()` — removed from lifespan

### What stays the same

- All FastAPI routes, models, auth, templates, sync engine, menu client, telemetry
- SQLAlchemy + Alembic
- Cookie-based sessions (already serverless-friendly)
- Test suite (conftest already handles missing Postgres gracefully)

## Database

### Neon Postgres via Vercel integration

One click in the Vercel dashboard adds Neon and injects env vars. Free tier includes:
- 0.5 GB storage
- 190 compute hours/month (auto-suspends when idle)
- Built-in connection pooler (PgBouncer)

### Connection pooling

Neon provides two connection strings:
- **Direct** — for migrations (Alembic)
- **Pooled** — for the app (serverless-safe)

Update `db.py` — use `NullPool` for serverless (one connection per invocation, Neon's PgBouncer handles multiplexing):

```python
from sqlalchemy.pool import NullPool

engine = create_engine(
    settings.database_url,
    poolclass=NullPool,
    pool_pre_ping=True,
)
```

### Alembic migration config

Add `DIRECT_DATABASE_URL` (or `DATABASE_URL_UNPOOLED`, which Neon/Vercel auto-injects) to config. Update `alembic/env.py` to read from `DIRECT_DATABASE_URL` for migrations, falling back to `DATABASE_URL`.

### Migrations

Run `alembic upgrade head` manually after first deploy or via a one-time endpoint. Build step has no DB access on Vercel.

### Data migration

Start fresh — current data is one test subscription and some sync logs. No export needed.

## Cron & Sync

### Replace APScheduler with Vercel Cron

In `vercel.json`:

```json
{
  "crons": [
    {
      "path": "/api/sync/cron",
      "schedule": "0 12 * * 1-5"
    }
  ]
}
```

That's noon UTC on weekdays (6 AM CST / 7 AM CDT — close enough for a daily menu sync).

### New endpoint: `GET /api/sync/cron`

- Vercel sends `x-vercel-cron-auth` header matching `CRON_SECRET` env var
- Endpoint validates the secret, then calls `sync_all(db, client)`
- Returns JSON summary of what synced
- 60-second timeout on Vercel Pro — plenty for sync (~5 seconds per subscription)

### What changes

- `scheduler/` directory — deleted entirely
- `main.py` lifespan — remove scheduler calls, keep telemetry only
- `config.py` — remove `sync_hour`, `sync_minute`, `timezone`; add `cron_secret`
- `api/sync.py` — add `GET /api/sync/cron` endpoint

### What stays

- `sync/engine.py` — `sync_subscription()` and `sync_all()` unchanged
- `sync/menu_client.py` — unchanged
- `POST /api/sync/trigger/{id}` — manual trigger still works

## Guardrails

Prevent runaway usage that could trigger Neon billing or Vercel overages.

### Sync rate limiting

Cron endpoint counts today's SyncLog records before running. If above `max_syncs_per_day` (default: 10), return early with a warning log.

### Subscription caps

- Max 5 active subscriptions per user (checked on create)
- Max 20 active subscriptions globally (checked on create)
- Constants in `config.py`, easy to raise later

### Database row cap

Before each sync, count total menu_items. If over 50,000, skip sync and log a warning. Current usage at 20 subscriptions would be ~4,200 rows — 50K is a generous ceiling.

### Config

```python
# config.py
cron_secret: str = ""
max_syncs_per_day: int = 10
max_subscriptions_per_user: int = 5
max_subscriptions_global: int = 20
max_menu_items: int = 50000
```

All guardrails log warnings via OTel so they show up in Grafana.

## Deployment & Project Structure

### `vercel.json`

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

Uses modern Vercel config format (`functions`/`rewrites` instead of legacy `builds`/`routes`).

### Dependencies

Vercel's `@vercel/python` runtime installs from `requirements.txt`. Add a step to generate it:

```bash
pip install pip-tools
pip-compile pyproject.toml -o requirements.txt
```

Commit `requirements.txt` to the repo. Regenerate when dependencies change.

### Static files

Move `src/lunchbox/web/static/` to `public/static/`. Remove `StaticFiles` mount from `main.py`. Vercel serves files in `public/` at the root URL path automatically (no rewrite needed — `public/static/style.css` is served at `/static/style.css`).

### Telemetry in serverless

Move `setup_telemetry()` from the lifespan context manager to module-level initialization in `main.py` (Vercel may not dispatch ASGI lifespan events). Use `SimpleSpanProcessor` instead of `BatchSpanProcessor` to ensure spans are exported synchronously per-request (batch processor buffers data that may be lost when the function freezes). Accept minor latency cost (~5ms per span).

### psycopg2 compatibility

`psycopg2-binary` should work on Vercel's Amazon Linux build environment. If it fails on first deploy, switch to `psycopg[binary]` (psycopg3) and update the connection URL scheme to `postgresql+psycopg://`.

### Google OAuth

Update redirect URI to `https://lunchbox.techneanalytics.io/auth/callback`. Set `BASE_URL=https://lunchbox.techneanalytics.io` in Vercel env vars.

### DNS

Point `lunchbox.techneanalytics.io` CNAME to `cname.vercel-dns.com` in Cloudflare. Vercel handles the SSL cert.

## File Changes

| Action | File | Change |
|--------|------|--------|
| Delete | `Dockerfile` | No longer needed |
| Move | `docker-compose.yml` → `docker/docker-compose.dev.yml` | Local dev only |
| Create | `vercel.json` | Functions, rewrites, cron |
| Create | `requirements.txt` | Generated from pyproject.toml for Vercel |
| Create | `public/static/style.css` | Moved from src |
| Modify | `src/lunchbox/main.py` | Remove scheduler + StaticFiles; move telemetry to module level |
| Modify | `src/lunchbox/db.py` | Use NullPool, add pool_pre_ping |
| Modify | `src/lunchbox/config.py` | Remove scheduler settings, add guardrails + cron_secret |
| Modify | `src/lunchbox/telemetry/setup.py` | Use SimpleSpanProcessor for serverless |
| Modify | `src/lunchbox/api/sync.py` | Add `GET /api/sync/cron` endpoint with guardrails |
| Modify | `src/lunchbox/api/subscriptions.py` | Add subscription cap checks |
| Modify | `src/lunchbox/sync/engine.py` | Add row count guardrail |
| Modify | `pyproject.toml` | Remove apscheduler |
| Modify | `alembic/env.py` | Read DIRECT_DATABASE_URL for migrations |
| Modify | `.github/workflows/ci.yml` | Remove Docker build step, update for non-Docker setup |
| Delete | `src/lunchbox/scheduler/jobs.py` | Replaced by cron endpoint |
| Delete | `src/lunchbox/scheduler/__init__.py` | Directory removed |
| Update | `tests/unit/test_scheduler.py` | Delete, replace with cron endpoint tests |
| Update | `CLAUDE.md` | Reflect new architecture |
| Update | `CONTRIBUTING.md` | Update dev setup instructions |
| Update | `README.md` | Update deployment section |

## Test Impact

- ~5 scheduler tests deleted
- ~3 cron endpoint tests added (auth, guardrails, success)
- ~2 subscription cap tests added
- All other tests unchanged (~95 tests remain as-is)

## Out of Scope

- Multi-region deployment
- Custom domain email (e.g., noreply@lunchbox.techneanalytics.io)
- CDN for static assets beyond Vercel's built-in
- Database backups beyond Neon's built-in point-in-time recovery
