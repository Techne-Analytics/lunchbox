# Cron Exception Resilience Tests

**Date:** 2026-04-14
**Issue:** #42 (partial — scheduler wiring is obsolete on Vercel, only exception tests remain)
**Scope:** `tests/unit/test_cron.py`

## Problem

The cron endpoint has error handling (try/except around `sync_all`, "all syncs failed" check) but neither path is tested. The original issue asked for APScheduler wiring tests, but the project migrated to Vercel Cron — no scheduler exists. Only the exception resilience tests are still needed.

## Tests to add

### `test_cron_returns_500_on_sync_exception`

Mock `SchoolCafeClient` to raise an exception. Assert the cron endpoint returns HTTP 500 with `"Sync failed"` detail. Verifies the try/except at `api/sync.py:132-143`.

### `test_cron_returns_500_when_all_syncs_fail`

Create a subscription, mock `sync_all` to produce only "error" SyncLogs, assert the cron endpoint returns HTTP 500 with `"All N syncs failed"`. Verifies the all-fail check at `api/sync.py:149-151`.

## What stays the same

- Existing 4 tests (auth rejection, wrong secret, success, guardrail skip)
- `api/sync.py` — no code changes, only new tests
