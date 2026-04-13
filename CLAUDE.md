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
