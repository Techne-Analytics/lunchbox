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
- Neon Postgres (via Vercel)
- HTMX (server-rendered UI)
- Vercel (serverless hosting + cron)
- OpenTelemetry → Grafana Cloud

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for workflow, branch naming, commit conventions, and dev setup.

## Design

See [docs/superpowers/specs/2026-04-13-vercel-migration-design.md](docs/superpowers/specs/2026-04-13-vercel-migration-design.md) for the current architecture spec.

## License

Personal use.
