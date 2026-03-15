# Lunchbox

School lunch and breakfast menus, synced to your calendar.

Lunchbox fetches menus from SchoolCafe (Denver Public Schools) and publishes them as subscribable iCal feeds. Add the feed URL to Google Calendar, Apple Calendar, Outlook, or any calendar app that supports `.ics` subscriptions.

## How It Works

1. Sign in with Google
2. Pick your school, grade, and meal types
3. Configure what you want to see (filter categories, exclude items)
4. Get a subscribe URL
5. Add it to your calendar app — menus update daily

## Features

- iCal feed per school — works with any calendar app
- Filter by category (Entrees only, Entrees + Fruits, etc.)
- Exclude specific items (PB&J, always-available items)
- Calendar display settings (alerts, busy/free, all-day or timed events)
- Multiple subscriptions for families with kids at different schools
- Self-healing sync — handles SchoolCafe API changes gracefully
- Observability via OpenTelemetry → Grafana Cloud

## Tech Stack

- Python 3.11 / FastAPI
- PostgreSQL
- HTMX (server-rendered UI)
- Docker Compose
- OpenTelemetry → Grafana Cloud

## Quick Start

```bash
# Clone and configure
cp .env.example .env    # edit with your settings

# Start everything
docker compose up -d

# Run migrations
docker compose exec app alembic upgrade head

# Open http://localhost:8000
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, branch naming, commit conventions, and dev setup.

## Design

See [docs/superpowers/specs/2026-03-14-lunchbox-redesign-design.md](docs/superpowers/specs/2026-03-14-lunchbox-redesign-design.md) for the full design spec.

## License

Personal use.
