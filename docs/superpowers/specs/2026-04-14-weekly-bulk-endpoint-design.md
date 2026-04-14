# Weekly Bulk Endpoint Integration

**Date:** 2026-04-14
**Issue:** #63
**Scope:** `src/lunchbox/sync/menu_client.py`, `src/lunchbox/sync/engine.py`, `src/lunchbox/sync/providers.py`, tests

## Problem

Current sync makes one API call per (subscription, date, meal_type). For 20 subscriptions × 7 days × 2 meals = 280 SchoolCafe calls per cron run. SchoolCafe offers a weekly bulk endpoint we don't use.

**Discovered response format** for `CalendarView/GetWeeklyMenuitemsByGrade`:

```json
{
  "4/13/2026": {
    "ENTREES": [...same shape as daily endpoint...],
    "GRAINS": [...],
    "VEGETABLES": [...],
    "FRUITS": [...],
    "MILK": [...],
    "CONDIMENTS": [...]
  },
  "4/14/2026": {...},
  ...
}
```

- Returns Mon-Fri (5 weekday entries) when called with any weekday date
- Date keys are US format `M/D/YYYY` (note: not zero-padded — could be `4/13/2026` or `12/3/2026`)
- Inner per-date structure is identical to the daily endpoint

## Design

### `SchoolCafeClient.get_weekly_menu()`

```python
def get_weekly_menu(
    self,
    school_id: str,
    week_date: date,
    meal_type: str,
    serving_line: str,
    grade: str,
) -> dict[date, list[MenuItemData]]:
```

Returns `{date: [MenuItemData]}` for each day in the week. The `week_date` parameter accepts any date in the target week — SchoolCafe returns the corresponding Mon-Fri.

Implementation:
1. Call `self._request()` with `CalendarView/GetWeeklyMenuitemsByGrade` and same params as daily
2. Validate response is a dict (return `{}` if not, with warning log)
3. For each `(date_str, day_data)` pair:
   - Parse date with `datetime.strptime(date_str, "%m/%d/%Y").date()` — on `ValueError`, log warning and skip that date
   - Validate `day_data` is a dict — log warning and skip if not
   - Run existing `_detect_drift(day_data)` and log warnings
   - Run existing `_parse_response(day_data)` to get `list[MenuItemData]`
   - Add to result dict
4. Return result

### `MenuProvider` Protocol update

Add `get_weekly_menu()` to the `MenuProvider` Protocol in `providers.py`. Existing `get_daily_menu()` remains for backwards compatibility and ad-hoc single-day fetches.

### `sync_subscription()` refactor

Replace the inner loop:

```python
# Before:
for sync_date in dates:
    for meal_config in subscription.meal_configs:
        items = client.get_daily_menu(school_id, sync_date, meal_type, ...)
        # ... upsert per (sync_date, meal_type)

# After:
week_dates_by_meal: dict[tuple[str, str], dict[date, list[MenuItemData]]] = {}
for meal_config in subscription.meal_configs:
    meal_type = meal_config["meal_type"]
    serving_line = meal_config["serving_line"]
    try:
        week_data = client.get_weekly_menu(
            school_id=subscription.school_id,
            week_date=dates[0],
            meal_type=meal_type,
            serving_line=serving_line,
            grade=subscription.grade,
        )
        week_dates_by_meal[(meal_type, serving_line)] = week_data
    except Exception as e:
        logger.error("Weekly fetch failed for %s %s: %s", meal_type, subscription.display_name, e)
        errors.append(f"{meal_type} weekly: {e}")

for sync_date in dates:
    for meal_config in subscription.meal_configs:
        meal_type = meal_config["meal_type"]
        serving_line = meal_config["serving_line"]
        week_data = week_dates_by_meal.get((meal_type, serving_line), {})
        items = week_data.get(sync_date, [])
        # ... existing upsert logic for (sync_date, meal_type)
```

The per-date upsert (delete-then-insert with savepoint) is unchanged. Only the fetch source moves.

### Error handling

- **Whole weekly call fails**: catch exception, log, append to `errors`. The week's sync for that meal_type fails as a unit. With 3 retries in `_request()`, transient failures are absorbed.
- **Partial week (one date malformed)**: `get_weekly_menu()` skips bad dates internally and returns others. The engine sees `week_data.get(sync_date, [])` returning `[]` for missing dates — same path as "no menu today".
- **Empty response**: same as before — empty list per date triggers cache-invalidation delete.

### Concurrency / consistency

`days_to_fetch=7` means we call once per meal_type per subscription. Multiple meal_types (Lunch, Breakfast) make separate calls. The throttle (`min_request_delay=0.1`) still applies between calls.

If `days_to_fetch > 5`, the week endpoint covers Mon-Fri only. Days outside the current week (e.g., next Monday) won't be fetched. **Mitigation**: if `len(dates) > 5` or any `sync_date.weekday() < dates[0].weekday()`, fall back to fetching multiple weeks. For now, since `days_to_fetch=7` and we skip weekends, all dates fall in one week — this is a non-issue at default config. Document the limit in the method docstring.

### What changes

| File | Change |
|------|--------|
| `src/lunchbox/sync/menu_client.py` | Add `get_weekly_menu()` method (~30 lines), reuses `_request`, `_detect_drift`, `_parse_response` |
| `src/lunchbox/sync/providers.py` | Add `get_weekly_menu` to `MenuProvider` Protocol |
| `src/lunchbox/sync/engine.py` | Refactor `sync_subscription()` inner loop to fetch weekly first, then iterate dates from cached data |
| `tests/unit/test_menu_client_http.py` | Add weekly endpoint tests (4 new) |
| `tests/unit/test_sync_engine.py` | Update existing tests if they assert call counts; add 1 test verifying weekly is used |
| `tests/fixtures/schoolcafe/` | Add `weekly_lunch.json` fixture |

### Tests

| Test | Verifies |
|------|----------|
| `test_weekly_returns_dict_by_date` | Happy path: 5 weekday entries, items parsed correctly |
| `test_weekly_handles_partial_dates` | If one date's `day_data` is non-dict, others still return |
| `test_weekly_invalid_date_key_skipped` | Bad date key like `"foo"` logged + skipped, others returned |
| `test_weekly_non_dict_response_returns_empty` | Top-level non-dict returns `{}` |
| `test_weekly_malformed_json_returns_empty` | JSON decode error returns `{}` |
| `test_sync_uses_weekly_endpoint` | Engine calls `get_weekly_menu` once per meal_config, not once per date |

### Out of scope

- `get_holidays()` — separate concern, deferred
- Monthly endpoint — weekly suffices for `days_to_fetch=7`
- Removing `get_daily_menu()` — kept for backwards compat and single-day use

### Performance

| Metric | Before | After |
|--------|--------|-------|
| API calls per subscription per cron | 14 (7 days × 2 meals) | 2 (1 week × 2 meals) |
| API calls at 20 subscriptions | 280 | 40 |
| Throttle baseline (0.1s × calls) | 28s | 4s |

Headroom inside the 60s Vercel function timeout grows substantially.
