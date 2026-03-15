# Contributing to Lunchbox

## Development Workflow

**Trunk-based development.** `main` is the only long-lived branch.

### Every change follows this flow:

1. **Open a GitHub issue** — everything starts as an issue. Bugs, features, chores, docs.
2. **Branch from `main`** — `<type>/<issue-number>-<short-description>` (e.g., `feat/12-add-filters`)
3. **Write code** — atomic, semantic commits (see below)
4. **Open a PR to `main`** — reference the issue (`Closes #12`)
5. **PR review** — all PRs must run the pr-toolkit to review and make changes before merging
6. **Merge** — squash or rebase, keep history clean

**No exceptions.** All commits into `main` go through a PR, no matter how small.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

| Prefix       | When to use                          |
|--------------|--------------------------------------|
| `feat:`      | New feature                          |
| `fix:`       | Bug fix                              |
| `docs:`      | Documentation only                   |
| `refactor:`  | Code change that neither fixes nor adds |
| `test:`      | Adding or updating tests             |
| `chore:`     | Build, CI, tooling, dependencies     |

**Atomic commits.** Each commit is one logical change. If you can split it, split it.

## Branch Naming

```
<type>/<issue-number>-<short-description>
```

Examples:
- `feat/12-add-filters`
- `fix/34-schema-drift-handling`
- `chore/5-ci-workflow`
- `docs/8-contributing-guide`

## Pull Requests

- Title: short, imperative (`Add category filters`, not `Added category filters`)
- Body: reference the issue, describe what changed and why
- All PRs must pass CI (ruff lint + pytest)
- All PRs must run pr-toolkit review before merge

## Dev Setup

```bash
# Start Postgres
docker compose up -d postgres

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Run tests
pytest

# Lint and format
ruff check .
ruff format .
```

## Testing

- Unit tests for core logic (menu parsing, sync engine, feed generation)
- Integration tests for API endpoints and auth
- Contract tests with captured API response fixtures
- Tests must pass without external API access
- Run `pytest` before pushing

## Code Style

- Ruff for linting and formatting (project defaults, no config debates)
- Type hints on public function signatures
- No unnecessary comments — if the code needs a comment, consider rewriting it first
