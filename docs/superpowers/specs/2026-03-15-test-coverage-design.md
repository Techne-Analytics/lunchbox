# Test Coverage Design

Comprehensive test plan for Lunchbox, prioritized by SRE blast-radius: silent failure cost determines test order. Tests use real Postgres (via `TEST_DATABASE_URL`), `respx` for HTTP mocking, and captured SchoolCafe fixture files for contract tests.

**Scope:** Everything except telemetry (low value — absence is immediately visible in Grafana).

**Approach:** Hybrid — light test infrastructure first, then tests in blast-radius order.

## Existing Coverage

~28 tests across 9 files. Strong in parsing/calendar generation, weak everywhere else.

| Area | Coverage | Notes |
|------|----------|-------|
| Menu client parsing | Excellent | 17 tests, drift detection, fallbacks |
| iCal calendar generation | Good | 8 tests, filters, alarms, categories |
| Sync date logic | Covered | 3 tests, weekend skipping |
| API endpoints | 2/10 | Only subscription create + list |
| Auth | Basic | Happy path only |
| Models | Minimal | Creation only, no constraints |
| Web routes | Zero | — |
| Health endpoint | Covered | 1 test |
| Scheduler | Zero | — |

## 1. Test Infrastructure

### Model Factory — `tests/factories.py`

Plain functions (no framework). Each creates an ORM object with sensible defaults, inserts into the test DB, and returns it.

```python
create_user(db, **overrides) -> User
create_subscription(db, user, **overrides) -> Subscription
create_menu_item(db, subscription, **overrides) -> MenuItem
create_sync_log(db, subscription, **overrides) -> SyncLog
```

Defaults should produce valid, minimal objects. Overrides let tests customize specific fields.

### Auth Fixtures — `tests/conftest.py`

- `authenticated_client(db)` — creates a user via factory, patches `get_current_user` to return that user, yields `(TestClient, User)` tuple. Must clean up `app.dependency_overrides` in teardown.
- `second_user_client(db)` — separate user for isolation tests. Same teardown requirement.

### HTTP Mock Helper — `tests/conftest.py`

Fixture wrapping `respx` that loads JSON from `tests/fixtures/schoolcafe/` by filename:

```python
mock_schoolcafe(respx_mock, "normal_lunch")  # sets up route to return fixture
```

## 2. Data Integrity Tests

Priority: highest. Silent data corruption is the hardest failure to detect and recover from.

### `tests/unit/test_model_constraints.py`

- **Unique constraints** — duplicate `google_id` on User → `IntegrityError`; duplicate `feed_token` on Subscription → `IntegrityError`
- **FK constraints** — Subscription with nonexistent `user_id` → `IntegrityError`
- **Cascade deletes** — delete Subscription → MenuItems and SyncLogs gone; delete User → Subscriptions and children gone
- **feed_token auto-generation** — new Subscription gets UUID token without explicit assignment
- **Timestamp auto-population** — `created_at` and `updated_at` set on insert

### `tests/unit/test_sync_upsert.py`

- **Upsert replaces** — syncing same (subscription, date, meal_type) replaces old MenuItems, no duplicates
- **Partial upsert** — one date fails, other dates' items still persisted
- **Empty result** — syncing a date with no menu items deletes old items for that date (not a no-op). This is intentional cache invalidation: the sync engine DELETEs then INSERTs inside a savepoint, so an empty API response means old stale items are cleared.

## 3. Sync Engine Error Matrix

Priority: high. The sync engine is the most complex background process and most likely to fail silently.

### `tests/unit/test_sync_engine_errors.py`

- **All dates fail** — every API call raises → SyncLog status="error", error_message populated, zero MenuItems
- **Mixed success/failure** — 3 dates requested, 1 fails → status="partial", items_fetched reflects successful dates only
- **API timeout** — `httpx.TimeoutException` → caught, logged, doesn't crash sync
- **API HTTP error** — 500/503 from SchoolCafe → graceful handling
- **Empty response** — valid JSON, no items → status="success", items_fetched=0
- **Duration tracking** — duration_ms populated and > 0

### `tests/unit/test_sync_all.py`

- **sync_all() isolation** — one subscription's sync failure does not prevent others from syncing
- **sync_all() filters active** — only `is_active=True` subscriptions are synced
- **sync_all() empty** — no active subscriptions → no-op, no error

### `tests/unit/test_menu_client_http.py` (contract tests)

All use `respx` + fixture files. No live API calls.

- **Successful fetch** — `get_daily_menu()` with fixture → parsed `MenuItemData` list
- **search_schools() happy path** — fixture → `SchoolInfo` list
- **search_schools() empty** — no matching districts → empty list
- **HTTP 404/500** — returns empty or raises gracefully
- **Timeout** — `httpx.TimeoutException` propagates to caller
- **Schema drift** — drifted fixture → still parses with warnings

## 4. API Endpoint Tests

Priority: high. System boundary — breakage directly affects users and feed consumers.

### `tests/integration/test_api_subscriptions.py` (expand existing)

- **GET /{id}** — returns detail; 404 nonexistent; 404 other user's (isolation)
- **PATCH /{id}** — updates meal_configs, excluded_items, display_name; 404 other user's; validates field types
- **DELETE /{id}** — 204; gone from DB; cascades MenuItems/SyncLogs; 404 other user's
- **POST /{id}/regenerate-token** — new token differs from old; old feed URL stops working; 404 other user's

### `tests/integration/test_api_schools.py` (new)

- **GET /api/schools?q=springfield** — returns `[{school_id, school_name}]` (respx + fixture)
- **GET /api/schools?q=** — empty query → empty list or 400
- **SchoolCafe down** — respx returns 500 → graceful error response

### `tests/integration/test_api_sync.py` (new)

- **POST /api/sync/trigger/{id}** — triggers sync, returns sync log; 404 other user's
- **GET /api/sync/history/{id}** — last 20 logs DESC by started_at; 404 other user's
- **Empty history** — no syncs yet → empty list

### `tests/integration/test_feeds_api.py` (expand existing)

- **Cache headers** — ETag present and is a hash; Last-Modified from latest fetched_at; Cache-Control set
- **Inactive subscription** — `is_active=False` → 404
- **Same data, same ETag** — two requests, no change → identical ETag

## 5. Auth Edge Cases

Priority: medium-high. Security boundary.

### `tests/integration/test_auth.py` (expand existing)

- **Callback — new user** — creates User with google_id, email, name; sets session
- **Callback — returning user** — same google_id → no duplicate, updates email/name if changed
- **Callback — race condition** — simulate by mocking `db.commit` to raise `IntegrityError` on first call, verifying fallback to SELECT. Do not attempt real concurrency (flaky).
- **Callback — missing email** — graceful handling
- **Session expiry** — no user_id in session → 401
- **User deleted from DB** — valid session, user row gone → 401 not 500

## 6. Scheduler

Priority: medium. A dead scheduler is a silent outage — menus stop updating and nobody notices.

### `tests/unit/test_scheduler.py` (new)

- **start_scheduler()** — creates scheduler, registers daily_sync_job, scheduler is running
- **stop_scheduler()** — scheduler shuts down without error. Note: current code does not set `_scheduler = None` after shutdown — test should drive a code fix to add this cleanup, then assert it.
- **stop when not started** — no-op, no crash
- **daily_sync_job() exception** — `sync_all` raises → logged, scheduler survives
- **Job registration** — cron trigger uses settings.sync_hour and settings.sync_minute

No timer-based tests. Verify wiring and exception resilience only.

## 7. Web Smoke Tests

Priority: lowest. Presentation layer — failures are immediately visible to users.

### `tests/integration/test_web.py` (new)

- **GET /** — unauthenticated → 200 (landing page)
- **GET /** — authenticated → 302 to /dashboard
- **GET /dashboard** — authenticated → 200, contains subscription data
- **GET /dashboard** — unauthenticated → 401 or redirect
- **GET /subscriptions/new** — authenticated → 200, form renders
- **GET /subscriptions/{id}** — owner → 200; other user → 302 redirect to /dashboard (actual behavior is redirect, not 404)
- **GET /subscriptions/{id}/preview** — authenticated → 200, grouped items

Status codes and basic content checks only. No DOM assertions.

## Summary

| Layer | New tests | Files |
|-------|-----------|-------|
| Infrastructure | — (helpers, no tests) | 2 support files |
| Data integrity | ~9 | 2 test files |
| Sync engine errors | ~6 | 1 test file |
| sync_all | ~3 | 1 test file |
| Contract (menu client HTTP) | ~6 | 1 test file |
| API endpoints | ~18 | 4 test files (2 new, 2 expand) |
| Auth edge cases | ~6 | 1 test file (expand) |
| Scheduler | ~5 | 1 test file |
| Web smoke | ~7 | 1 test file |
| **Total** | **~60** | **12 test files + 2 support files** |

Combined with existing ~28 tests → ~88 tests total. Prioritized by SRE blast radius (silent failure cost). No telemetry tests (absence visible in Grafana). All HTTP mocking via `respx` + captured fixture files.

## Dependencies

- `respx` — add to dev dependencies
- `TEST_DATABASE_URL` — already required by existing conftest
- Existing SchoolCafe fixtures in `tests/fixtures/schoolcafe/` — expand as needed for schools search responses

## Out of Scope

- Telemetry/OTel wiring tests
- End-to-end tests against live SchoolCafe API
- Load/performance testing
- Browser-level UI testing
