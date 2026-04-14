# Endpoint Hardening

**Date:** 2026-04-14
**Issues:** #48 (schools search), #49 (OAuth None guard), #50 (meal_configs warning), #51 (sync trigger)
**Scope:** Four small fixes across four files

## Problem

Four API endpoints have missing error handling, found by pr-toolkit on PR #44. Each can cause raw 500s or silent failures in production.

## Fixes

### #48: Schools search error handling

**File:** `src/lunchbox/api/schools.py`

Wrap `SchoolCafeClient` call in try/except. Return `[]` on failure (graceful degradation for user-facing search). Add logger, log at exception level.

```python
import logging
logger = logging.getLogger(__name__)

@router.get("")
def search_schools(q: str) -> list[dict]:
    try:
        with SchoolCafeClient() as client:
            schools = client.search_schools(q)
    except Exception:
        logger.exception("School search failed for query: %s", q)
        return []
    return [{"school_id": s.school_id, "school_name": s.school_name} for s in schools]
```

### #49: OAuth callback None guard

**File:** `src/lunchbox/auth/router.py`

After the `IntegrityError` fallback SELECT (line 61), the `user` variable can be `None`. If so, `db.refresh(user)` on line 67 crashes with `AttributeError`. Add a None check before `db.refresh()`.

```python
except IntegrityError:
    db.rollback()
    user = db.query(User).filter(User.google_id == google_id).first()
    if not user:
        return RedirectResponse(url="/?error=auth_failed")
```

### #50: Missing meal_configs warning

**File:** `src/lunchbox/sync/engine.py`

At the top of `sync_subscription()`, before `started_at` and `get_sync_dates()`, check if `meal_configs` is falsy. This must be early because `len(subscription.meal_configs)` on line 95 crashes with `TypeError` when `meal_configs` is `None`. Log a warning and return a SyncLog with `status="skipped"` so it appears in sync history.

```python
if not subscription.meal_configs:
    logger.warning(
        "Subscription %s has no meal configs, skipping",
        subscription.display_name,
    )
    log = SyncLog(
        subscription_id=subscription.id,
        status="skipped",
        dates_synced=0,
        items_fetched=0,
        error_message="No meal configs configured",
        duration_ms=0,
    )
    db.add(log)
    db.commit()
    return log
```

### #51: Sync trigger error handling

**File:** `src/lunchbox/api/sync.py`

Wrap the `SchoolCafeClient` + `sync_subscription` block in `trigger_sync()` with try/except. Log exception, raise `HTTPException(500)` with user-friendly detail.

```python
try:
    with SchoolCafeClient() as client:
        log = sync_subscription(db, sub, client, ...)
except Exception:
    logger.exception("Sync trigger failed for subscription %s", subscription_id)
    raise HTTPException(status_code=500, detail="Sync failed, please try again later")
```

## What stays the same

- `cron_sync()` already has error handling — no changes
- `sync_history()` — no changes
- `sync_subscription()` and `sync_all()` internal logic — unchanged
- `SchoolCafeClient` — already hardened in #59-61
