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
   - Run existing `_detect_drift(day_data)` (module-level function, no `self.`) and log warnings
   - Run existing `self._parse_response(day_data)` (instance method) to get `list[MenuItemData]`
   - Add to result dict
4. Return result

**Note:** `_detect_drift` is a module-level function in `menu_client.py`. `_parse_response` is an instance method on `SchoolCafeClient`. Use the correct call form for each.

### `MenuProvider` Protocol update

Add `get_weekly_menu()` to the `MenuProvider` Protocol in `providers.py`. Existing `get_daily_menu()` remains for backwards compatibility and ad-hoc single-day fetches.

### `sync_subscription()` refactor

The weekly endpoint returns Mon-Fri for the week containing the requested date. With `days_to_fetch=7` and `skip_weekends=True`, dates may span two weeks. We need to fetch each unique week.

```python
# Group dates by ISO week (year, week_number)
from collections import defaultdict
weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
for d in dates:
    iso_year, iso_week, _ = d.isocalendar()
    weeks[(iso_year, iso_week)].append(d)

# Fetch one weekly call per (week, meal_config). Use first date in the week as week_date.
fetched: dict[tuple[str, str, int, int], dict[date, list[MenuItemData]]] = {}
for (iso_year, iso_week), week_dates in weeks.items():
    for meal_config in subscription.meal_configs:
        meal_type = meal_config["meal_type"]
        serving_line = meal_config["serving_line"]
        try:
            week_data = client.get_weekly_menu(
                school_id=subscription.school_id,
                week_date=week_dates[0],
                meal_type=meal_type,
                serving_line=serving_line,
                grade=subscription.grade,
            )
            fetched[(meal_type, serving_line, iso_year, iso_week)] = week_data
        except Exception as e:
            logger.error(
                "Weekly fetch failed for %s week %d-%d (%s): %s",
                meal_type, iso_year, iso_week, subscription.display_name, e,
            )
            # Append one error per missed (date, meal_type) so status accounting stays consistent
            for d in week_dates:
                errors.append(f"{meal_type} {d}: weekly fetch failed: {e}")

# Per-date upsert (delete-then-insert with savepoint) — UNCHANGED logic, only fetch source differs
for sync_date in dates:
    for meal_config in subscription.meal_configs:
        meal_type = meal_config["meal_type"]
        serving_line = meal_config["serving_line"]
        iso_year, iso_week, _ = sync_date.isocalendar()
        week_data = fetched.get((meal_type, serving_line, iso_year, iso_week), {})
        items = week_data.get(sync_date, [])
        # ... existing nested savepoint + delete + insert logic
        total_items += len(items)
```

**Why one error per (date, meal_type)** when a weekly call fails: keeps `len(errors) == total_expected` math intact for status reporting (`engine.py:112`). A full-failure week with 5 dates × 2 meals correctly reports `status="error"`, not `"partial"`.

### Error handling

- **Whole weekly call fails**: catch exception, log, append to `errors`. The week's sync for that meal_type fails as a unit. With 3 retries in `_request()`, transient failures are absorbed.
- **Partial week (one date malformed)**: `get_weekly_menu()` skips bad dates internally and returns others. The engine sees `week_data.get(sync_date, [])` returning `[]` for missing dates — same path as "no menu today".
- **Empty response**: same as before — empty list per date triggers cache-invalidation delete.

### Concurrency / consistency

`days_to_fetch=7` means we call once per meal_type per subscription. Multiple meal_types (Lunch, Breakfast) make separate calls. The throttle (`min_request_delay=0.1`) still applies between calls.

The weekly endpoint covers Mon-Fri for the requested week. With `days_to_fetch=7` and `skip_weekends=True`, dates span 7 weekdays = the rest of this week + start of next week. The engine groups dates by ISO week and makes one weekly call per (week, meal_config). For typical config (7 weekdays, 2 meals, 1 subscription), this is 4 calls total: 2 weeks × 2 meals.

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
| API calls per subscription per cron | 14 (7 days × 2 meals) | up to 4 (≤2 weeks × 2 meals) |
| API calls at 20 subscriptions | 280 | up to 80 |
| Throttle baseline (0.1s × calls) | 28s | up to 8s |

3.5x reduction in API calls at default config, with headroom inside the 60s Vercel function timeout growing substantially.
