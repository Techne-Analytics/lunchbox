# Weekly Bulk Endpoint Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add weekly bulk endpoint to SchoolCafe client and refactor sync engine to use it, reducing API calls 3.5x at default config.

**Architecture:** New `get_weekly_menu()` method on `SchoolCafeClient` returns `dict[date, list[MenuItemData]]` for a Mon-Fri week. Engine groups dates by ISO week and makes one weekly call per (week, meal_config). Per-date upsert logic unchanged.

**Tech Stack:** Python 3.11, httpx, respx (test mocking), pytest

**Spec:** `docs/superpowers/specs/2026-04-14-weekly-bulk-endpoint-design.md`
**Issue:** #63

---

## File Structure

| File | Role |
|------|------|
| `src/lunchbox/sync/menu_client.py` | Add `get_weekly_menu()` method on `SchoolCafeClient` |
| `src/lunchbox/sync/providers.py` | Add `get_weekly_menu` to `MenuProvider` Protocol |
| `src/lunchbox/sync/engine.py` | Refactor `sync_subscription()` inner loop to fetch weekly per (ISO week, meal_config) |
| `tests/fixtures/schoolcafe/weekly_lunch.json` | New fixture matching real weekly response shape |
| `tests/unit/test_menu_client_http.py` | Add weekly endpoint tests (5 new) |
| `tests/unit/test_sync_engine.py` | Update existing tests + add weekly integration test |

No new files in src/. One new fixture file. Two test files modified.

---

## Chunk 1: Weekly Endpoint on Client

### Task 1: Add weekly fixture file

**Files:**
- Create: `tests/fixtures/schoolcafe/weekly_lunch.json`

- [ ] **Step 1: Create fixture matching real response shape**

Create `tests/fixtures/schoolcafe/weekly_lunch.json`:

```json
{
  "4/13/2026": {
    "ENTREES": [
      {"MenuItemDescription": "Pizza", "Category": "ENTREES"},
      {"MenuItemDescription": "Burger", "Category": "ENTREES"}
    ],
    "FRUITS": [
      {"MenuItemDescription": "Apple", "Category": "FRUITS"}
    ]
  },
  "4/14/2026": {
    "ENTREES": [
      {"MenuItemDescription": "Tacos", "Category": "ENTREES"}
    ],
    "FRUITS": [
      {"MenuItemDescription": "Orange", "Category": "FRUITS"}
    ]
  },
  "4/15/2026": {
    "ENTREES": [
      {"MenuItemDescription": "Chicken Nuggets", "Category": "ENTREES"}
    ],
    "FRUITS": [
      {"MenuItemDescription": "Pear", "Category": "FRUITS"}
    ]
  }
}
```

- [ ] **Step 2: Commit**

```bash
git add tests/fixtures/schoolcafe/weekly_lunch.json
git commit -m "test: add weekly_lunch fixture for SchoolCafe weekly endpoint (#63)"
```

---

### Task 2: Add `get_weekly_menu()` to `SchoolCafeClient`

**Files:**
- Modify: `src/lunchbox/sync/menu_client.py`
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write failing tests**

Add a new `TestGetWeeklyMenu` class to `tests/unit/test_menu_client_http.py`:

```python
class TestGetWeeklyMenu:
    @respx.mock
    def test_returns_dict_by_date(self, schoolcafe_fixture):
        data = schoolcafe_fixture("weekly_lunch")
        respx.get(f"{BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=data)
        )

        with SchoolCafeClient(max_retries=0) as client:
            result = client.get_weekly_menu(
                "s1", date(2026, 4, 13), "Lunch", "Trad", "05"
            )

        assert len(result) == 3
        assert date(2026, 4, 13) in result
        assert date(2026, 4, 14) in result
        assert date(2026, 4, 15) in result
        # First day items
        names_apr13 = {item.item_name for item in result[date(2026, 4, 13)]}
        assert "Pizza" in names_apr13
        assert "Apple" in names_apr13

    @respx.mock
    def test_handles_partial_dates(self):
        # One date has non-dict day_data — should be skipped, others returned
        data = {
            "4/13/2026": {"ENTREES": [{"MenuItemDescription": "Pizza"}]},
            "4/14/2026": "not a dict",
            "4/15/2026": {"ENTREES": [{"MenuItemDescription": "Tacos"}]},
        }
        respx.get(f"{BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=data)
        )

        with SchoolCafeClient(max_retries=0) as client:
            result = client.get_weekly_menu(
                "s1", date(2026, 4, 13), "Lunch", "Trad", "05"
            )

        assert date(2026, 4, 13) in result
        assert date(2026, 4, 15) in result
        assert date(2026, 4, 14) not in result

    @respx.mock
    def test_invalid_date_key_skipped(self):
        data = {
            "4/13/2026": {"ENTREES": [{"MenuItemDescription": "Pizza"}]},
            "not-a-date": {"ENTREES": [{"MenuItemDescription": "Garbage"}]},
        }
        respx.get(f"{BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=data)
        )

        with SchoolCafeClient(max_retries=0) as client:
            result = client.get_weekly_menu(
                "s1", date(2026, 4, 13), "Lunch", "Trad", "05"
            )

        assert date(2026, 4, 13) in result
        assert len(result) == 1

    @respx.mock
    def test_non_dict_response_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=["not", "a", "dict"])
        )

        with SchoolCafeClient(max_retries=0) as client:
            result = client.get_weekly_menu(
                "s1", date(2026, 4, 13), "Lunch", "Trad", "05"
            )

        assert result == {}

    @respx.mock
    def test_malformed_json_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, content=b"not json")
        )

        with SchoolCafeClient(max_retries=0) as client:
            result = client.get_weekly_menu(
                "s1", date(2026, 4, 13), "Lunch", "Trad", "05"
            )

        assert result == {}
```

- [ ] **Step 2: Run tests, verify they fail**

Run: `python -m pytest tests/unit/test_menu_client_http.py::TestGetWeeklyMenu -v`
Expected: FAIL — `AttributeError: 'SchoolCafeClient' object has no attribute 'get_weekly_menu'`

- [ ] **Step 3: Add `get_weekly_menu()` method**

Add to `src/lunchbox/sync/menu_client.py`, inside the `SchoolCafeClient` class, immediately after `get_daily_menu()`:

```python
    def get_weekly_menu(
        self,
        school_id: str,
        week_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> dict[date, list[MenuItemData]]:
        """Fetch a week's menu in one call. Returns dict mapping date to items.

        SchoolCafe returns Mon-Fri for the week containing week_date.
        Date keys in the response are US format (M/D/YYYY).
        """
        params = {
            "SchoolId": school_id,
            "ServingDate": week_date.isoformat(),
            "ServingLine": serving_line,
            "MealType": meal_type,
            "Grade": grade,
            "PersonId": "",
        }

        response = self._request(
            f"{self.BASE_URL}/CalendarView/GetWeeklyMenuitemsByGrade",
            params=params,
        )

        try:
            data = response.json()
        except json.JSONDecodeError:
            logger.warning(
                "SchoolCafe returned invalid JSON for weekly %s %s", school_id, week_date
            )
            return {}

        if not isinstance(data, dict):
            logger.warning(
                "SchoolCafe weekly returned non-dict response: %s",
                type(data).__name__,
            )
            return {}

        result: dict[date, list[MenuItemData]] = {}
        for date_str, day_data in data.items():
            try:
                parsed_date = datetime.strptime(date_str, "%m/%d/%Y").date()
            except (ValueError, TypeError):
                logger.warning(
                    "SchoolCafe weekly: unparseable date key %r, skipping", date_str
                )
                continue

            if not isinstance(day_data, dict):
                logger.warning(
                    "SchoolCafe weekly: non-dict day_data for %s: %s",
                    date_str,
                    type(day_data).__name__,
                )
                continue

            drift_warnings = _detect_drift(day_data)
            for warning in drift_warnings:
                logger.warning("SchoolCafe weekly schema drift: %s", warning)

            result[parsed_date] = self._parse_response(day_data)

        return result
```

Note: `_detect_drift` is a module-level function (no `self.`). `_parse_response` is an instance method (use `self.`).

- [ ] **Step 4: Run tests, verify they pass**

Run: `python -m pytest tests/unit/test_menu_client_http.py::TestGetWeeklyMenu -v`
Expected: 5/5 PASS

- [ ] **Step 5: Run full menu_client test suite to check no regressions**

Run: `python -m pytest tests/unit/test_menu_client_http.py tests/unit/test_menu_client.py -v`
Expected: 41/41 PASS (36 existing + 5 new)

- [ ] **Step 6: Commit**

```bash
git add src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py
git commit -m "feat: add get_weekly_menu to SchoolCafeClient (#63)"
```

---

### Task 3: Add `get_weekly_menu` to MenuProvider Protocol

**Files:**
- Modify: `src/lunchbox/sync/providers.py`

- [ ] **Step 1: Add method signature to Protocol**

Edit `src/lunchbox/sync/providers.py`. Add to the `MenuProvider` Protocol after `get_daily_menu`:

```python
    def get_weekly_menu(
        self,
        school_id: str,
        week_date: date,
        meal_type: str,
        serving_line: str,
        grade: str,
    ) -> dict[date, list[MenuItemData]]: ...
```

- [ ] **Step 2: Run lint to verify Protocol still parses**

Run: `python -m ruff check src/lunchbox/sync/providers.py`
Expected: Clean

- [ ] **Step 3: Commit**

```bash
git add src/lunchbox/sync/providers.py
git commit -m "feat: add get_weekly_menu to MenuProvider protocol (#63)"
```

---

## Chunk 2: Engine Refactor

### Task 4: Refactor `sync_subscription()` to use weekly endpoint

**Files:**
- Modify: `src/lunchbox/sync/engine.py`
- Test: `tests/unit/test_sync_engine.py`

- [ ] **Step 1: Write failing test for weekly fetch behavior**

Add to `tests/unit/test_sync_engine.py` (in `TestSyncSubscription` class — check if it exists, if not create it):

```python
class TestSyncSubscriptionWeekly:
    def test_uses_weekly_endpoint_once_per_meal_config(self, db):
        """sync_subscription should call get_weekly_menu, not get_daily_menu."""
        from datetime import date as _date
        from tests.factories import create_subscription, create_user

        user = create_user(db)
        sub = create_subscription(
            db,
            user,
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Trad", "sort_order": 0},
                {"meal_type": "Breakfast", "serving_line": "GnG", "sort_order": 1},
            ],
        )
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.return_value = {
            _date.today(): [MenuItemData(category="Entrees", item_name="Pizza")],
        }

        sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        # 2 meal configs × 1 week = 2 calls (not 2 days × 2 meals = 4)
        assert mock_client.get_weekly_menu.call_count == 2
        assert mock_client.get_daily_menu.call_count == 0
```

If `MenuItemData` import is missing at the top of the file, add: `from lunchbox.sync.providers import MenuItemData`

- [ ] **Step 2: Run test, verify it fails**

Run: `python -m pytest tests/unit/test_sync_engine.py::TestSyncSubscriptionWeekly -v`
Expected: FAIL or SKIPPED (DB unavailable locally — that's fine; CI will catch it)

- [ ] **Step 3: Refactor `sync_subscription()` inner loop**

In `src/lunchbox/sync/engine.py`, replace the inner `for sync_date in dates:` block (currently at approximately lines 57-104) with the weekly-fetch + date-iteration pattern.

Add `from collections import defaultdict` to the imports at the top.

Replace this block:

```python
    for sync_date in dates:
        for meal_config in subscription.meal_configs:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]

            try:
                items = client.get_daily_menu(
                    school_id=subscription.school_id,
                    menu_date=sync_date,
                    meal_type=meal_type,
                    serving_line=serving_line,
                    grade=subscription.grade,
                )

                # Savepoint so DB errors don't corrupt the session
                nested = db.begin_nested()
                try:
                    db.query(MenuItem).filter(
                        MenuItem.subscription_id == subscription.id,
                        MenuItem.menu_date == sync_date,
                        MenuItem.meal_type == meal_type,
                    ).delete()

                    for item in items:
                        db.add(
                            MenuItem(
                                subscription_id=subscription.id,
                                school_id=subscription.school_id,
                                menu_date=sync_date,
                                meal_type=meal_type,
                                serving_line=serving_line,
                                grade=subscription.grade,
                                category=item.category,
                                item_name=item.item_name,
                            )
                        )
                    nested.commit()
                except Exception:
                    nested.rollback()
                    raise

                total_items += len(items)

            except Exception as e:
                logger.error(
                    "Failed to sync %s %s for %s: %s",
                    meal_type,
                    sync_date,
                    subscription.display_name,
                    e,
                )
                errors.append(f"{meal_type} {sync_date}: {e}")
```

With:

```python
    # Group dates by ISO week so we make one bulk call per (week, meal_config)
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        weeks[(iso_year, iso_week)].append(d)

    # Fetch weekly data once per (week, meal_config)
    fetched: dict[tuple[str, str, int, int], dict[date, list]] = {}
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
                    meal_type,
                    iso_year,
                    iso_week,
                    subscription.display_name,
                    e,
                )
                # One error per missed (date, meal_type) so status accounting stays consistent
                for d in week_dates:
                    errors.append(f"{meal_type} {d}: weekly fetch failed: {e}")

    # Per-date upsert from the cached weekly data
    for sync_date in dates:
        for meal_config in subscription.meal_configs:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]
            iso_year, iso_week, _ = sync_date.isocalendar()
            week_data = fetched.get((meal_type, serving_line, iso_year, iso_week))

            # Skip dates that had a fetch failure (already recorded in errors)
            if week_data is None:
                continue

            items = week_data.get(sync_date, [])

            # Savepoint so DB errors don't corrupt the session
            nested = db.begin_nested()
            try:
                db.query(MenuItem).filter(
                    MenuItem.subscription_id == subscription.id,
                    MenuItem.menu_date == sync_date,
                    MenuItem.meal_type == meal_type,
                ).delete()

                for item in items:
                    db.add(
                        MenuItem(
                            subscription_id=subscription.id,
                            school_id=subscription.school_id,
                            menu_date=sync_date,
                            meal_type=meal_type,
                            serving_line=serving_line,
                            grade=subscription.grade,
                            category=item.category,
                            item_name=item.item_name,
                        )
                    )
                nested.commit()
            except Exception as e:
                nested.rollback()
                logger.error(
                    "DB upsert failed for %s %s (%s): %s",
                    meal_type,
                    sync_date,
                    subscription.display_name,
                    e,
                )
                errors.append(f"{meal_type} {sync_date}: db error: {e}")
                continue

            total_items += len(items)
```

- [ ] **Step 4: Run unit tests**

Run: `python -m pytest tests/unit/test_sync_engine.py tests/unit/test_sync_engine_errors.py tests/unit/test_sync_upsert.py tests/unit/test_sync_all.py -v`
Expected: All pass or skip (DB-dependent skip locally is OK, but no failures)

- [ ] **Step 5: Update existing sync_engine tests that use `get_daily_menu` mock**

The existing tests in 4 sync test files mock `get_daily_menu` returning a list per call. After the refactor, the engine calls `get_weekly_menu` returning `dict[date, list]` per (week, meal_config). Existing tests need updating.

Per-test changes (use this as a checklist):

**`tests/unit/test_sync_engine.py:46`** — `test_successful_sync`:
Replace `mock_client.get_daily_menu.return_value = [MenuItemData(...)]` with:
```python
mock_client.get_weekly_menu.return_value = {
    d: [MenuItemData(category="Entrees", item_name="Pizza")]
    for d in get_sync_dates(days, skip_weekends=False)
}
```
(Import `from lunchbox.sync.engine import get_sync_dates` if needed.)

**`tests/unit/test_sync_engine.py:88`** — `test_partial_failure` using `side_effect`:
Convert from "fail on Nth daily call" to "fail on Nth weekly call". Since 1 weekly call covers 5 dates, the assertion changes:
- Old: 1 day fails, 1 day succeeds → 1 item saved
- New: 1 weekly call fails, but covers a whole week → all dates in that week have 0 items
- Rewrite the test to use 2 weekly calls (e.g., 2 meal_configs, only 1 fails) and assert items from the successful meal are saved while the failing meal contributes errors.

**`tests/unit/test_sync_engine_errors.py:18`** — `test_all_dates_fail_status_error`:
Change `mock_client.get_daily_menu.side_effect = Exception("API down")` to `mock_client.get_weekly_menu.side_effect = Exception("API down")`. The assertion `status == "error"` should still hold — when ALL weekly calls fail, every (date, meal_config) gets an error appended via the `for d in week_dates:` loop.

**`tests/unit/test_sync_engine_errors.py:46`** — `test_mixed_failure_status_partial`:
Old logic: "fail on call 1, succeed on call 2" produces partial success. New logic: 1 weekly call covers a whole week. To produce partial status, need 2 meal_configs and have only one fail: `mock_client.get_weekly_menu.side_effect = [Exception("fail"), {date.today(): []}]`. Adjust assertions accordingly.

**`tests/unit/test_sync_engine_errors.py:62`** — `test_timeout_handled_gracefully`:
`mock_client.get_weekly_menu.side_effect = httpx.TimeoutException(...)`. Same pattern as #18.

**`tests/unit/test_sync_engine_errors.py:75`** — `test_http_500_handled_gracefully`:
`mock_client.get_weekly_menu.side_effect = httpx.HTTPStatusError(...)`. Same pattern.

**`tests/unit/test_sync_engine_errors.py:92`** — `test_empty_response_status_success`:
Change `mock_client.get_daily_menu.return_value = []` to `mock_client.get_weekly_menu.return_value = {}`. Returning an empty dict means no dates have data. Assertion `status == "success"` still holds (no errors appended).

**`tests/unit/test_sync_engine_errors.py:105`** — `test_duration_ms_populated`:
Same as #92: `mock_client.get_weekly_menu.return_value = {}`.

**`tests/unit/test_sync_upsert.py:26`** — `test_upsert_replaces_old_items`:
```python
mock_client.get_weekly_menu.return_value = {
    date.today(): [MenuItemData(category="Entrees", item_name="NewPizza")],
}
```

**`tests/unit/test_sync_upsert.py:53`** — `test_partial_upsert_preserves_successful_dates`:
Old logic relied on per-call failures across dates. With weekly fetch, this test pattern doesn't apply directly. Rewrite: use 2 meal_configs, fail one weekly call, assert items from the successful meal are saved on all dates while the failing meal has none.

**`tests/unit/test_sync_upsert.py:76`** — `test_empty_response_clears_old_items`:
```python
mock_client.get_weekly_menu.return_value = {date.today(): []}
```
The empty list per date triggers cache invalidation (delete + insert nothing).

**`tests/unit/test_sync_all.py:17`** — `test_only_active_subscriptions_synced`:
`mock_client.get_weekly_menu.return_value = {}`.

**`tests/unit/test_sync_all.py:30`** — `test_one_failure_does_not_block_others`:
The `failing_then_ok` side_effect was triggered per-date. Update to per-week:
```python
def failing_then_ok(*args, **kwargs):
    nonlocal call_count
    call_count += 1
    if call_count == 1:
        raise Exception("first sub fails")
    return {date.today(): []}
mock_client.get_weekly_menu.side_effect = failing_then_ok
```
Adjust call_count thresholds based on how many subscriptions and meal_configs the test sets up.

**`tests/unit/test_sync_all.py:48`** — `test_empty_no_subscriptions`:
`mock_client.get_weekly_menu.return_value = {}`.

**Verify after changes:** `grep -n "get_daily_menu" tests/unit/test_sync_*.py tests/unit/test_sync_all.py` should return no results (all mocks switched to `get_weekly_menu`). `get_daily_menu` should only appear in `test_menu_client_http.py` (where it tests the client itself).

- [ ] **Step 6: Run full unit test suite**

Run: `python -m pytest tests/unit/ -v`
Expected: All pass or skip — no failures

- [ ] **Step 7: Run lint and format**

Run: `python -m ruff check src/lunchbox/sync/engine.py tests/unit/test_sync_engine.py && python -m ruff format src/lunchbox/sync/engine.py tests/unit/test_sync_engine.py`
Expected: Clean

- [ ] **Step 8: Commit**

```bash
git add src/lunchbox/sync/engine.py tests/unit/test_sync_engine.py tests/unit/test_sync_engine_errors.py tests/unit/test_sync_upsert.py tests/unit/test_sync_all.py
git commit -m "refactor: use weekly bulk endpoint in sync_subscription (#63)"
```

---

## Chunk 3: Verification

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

Run: `python -m pytest tests/unit/ -v`
Expected: All tests pass or skip (DB skips OK), no failures

- [ ] **Step 2: Run lint and format on all touched files**

Run: `python -m ruff check . && python -m ruff format --check .`
Expected: Clean

- [ ] **Step 3: Verify call count reduction with a manual smoke run**

Read `src/lunchbox/sync/engine.py` and confirm:
- One `client.get_weekly_menu(...)` call per (ISO week, meal_config)
- Zero `client.get_daily_menu(...)` calls in `sync_subscription()`
- Per-date upsert logic preserved (delete-then-insert with savepoint)
- Status accounting still works: `total_expected = len(dates) * len(meal_configs)`

- [ ] **Step 4: Commit any final fixups if needed**

If lint or format made changes:
```bash
git add -u
git commit -m "chore: lint and format fixes"
```
