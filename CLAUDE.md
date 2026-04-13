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

## Setup (new clone)

```bash
git config core.hooksPath .githooks  # enable pre-push lint + tests
```

## Key Commands

```bash
pip install -e ".[dev]"     # install with dev deps
alembic upgrade head        # run migrations
pytest                      # run tests
ruff check . && ruff format .  # lint + format
vercel --prod               # deploy to production
vercel logs <url>           # check function logs
```

### Migrations (Neon)

```bash
# Pull Vercel env vars, then run Alembic against unpooled URL
vercel env pull .env.vercel
source .env.vercel && alembic upgrade head
rm .env.vercel  # don't commit secrets
```

## Deployment

- Hosted on Vercel (auto-deploys on push to main)
- Database: Neon Postgres (Vercel integration)
- Cron: Vercel Cron hits `/api/sync/cron` weekdays at noon UTC
- Static files: served from `public/` directory

## Environment Variables (Vercel)

Required in Vercel dashboard (production):
- `DATABASE_URL` — auto-injected by Neon integration
- `SECRET_KEY` — `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `CRON_SECRET` — same generation method
- `BASE_URL` — `https://lunchbox-ebon.vercel.app`
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — from Google Cloud Console
- `OTEL_EXPORTER_OTLP_ENDPOINT` / `OTEL_EXPORTER_OTLP_HEADERS` — from Grafana Cloud

## Sensitive Files — DO NOT COMMIT

- `.env` — secrets, API keys, OAuth credentials
- Any `token.json` or `client_secret.json`

## External APIs

- **SchoolCafe** (schoolcafe.com) — menu data. We do not control this API. Parse defensively, self-heal on schema drift.
- **Google OAuth** — login only (`openid`, `email`, `profile`). No calendar write scopes.
- **Grafana Cloud OTLP** — telemetry export.

## Gotchas

- **Vercel env vars:** Use `printf` not `echo` when piping to `vercel env add` (echo adds trailing newline)
- **TemplateResponse:** Starlette new API requires `TemplateResponse(request, name, context)` not `TemplateResponse(name, {"request": request, ...})`
- **vercel.json:** Use `builds`/`routes` format, not `functions`/`rewrites` — the modern format errors with `@vercel/python`
- **NullPool:** Required for serverless — default QueuePool exhausts Neon connections
- **Cron auth:** Vercel sends `Authorization: Bearer <CRON_SECRET>`, not `x-vercel-cron-auth`
- **OTel headers:** Use space not `%20` in `Authorization=Basic <token>` value
