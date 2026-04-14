# SchoolCafe Client Hardening Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add retry with exponential backoff, rate limiting, and response validation to the SchoolCafe API client.

**Architecture:** A centralized `_request()` method on `SchoolCafeClient` handles throttling, HTTP calls, and retry logic. Response validation is added at the caller level (`get_daily_menu()` and `search_schools()`). All changes are in `menu_client.py` + tests.

**Tech Stack:** Python 3.11, httpx, respx (test mocking), pytest

**Spec:** `docs/superpowers/specs/2026-04-13-schoolcafe-client-hardening-design.md`
**Issues:** #59 (retry), #60 (rate limiting), #61 (response validation)

---

## File Structure

| File | Role |
|------|------|
| `src/lunchbox/sync/menu_client.py` | All implementation changes — `_request()`, `_throttle()`, constructor params, response validation |
| `tests/unit/test_menu_client_http.py` | All new HTTP-level tests + updates to existing retry-affected tests |

No new files created. No other files modified.

---

## Chunk 1: Retry + Throttle Infrastructure

### Task 1: Update constructor and add throttle

**Files:**
- Modify: `src/lunchbox/sync/menu_client.py:81-89` (constructor)
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write failing test for constructor params**

Add to `tests/unit/test_menu_client_http.py`:

```python
class TestClientConfig:
    def test_default_constructor(self):
        client = SchoolCafeClient()
        assert client._max_retries == 3
        assert client._retry_delays == (1, 2, 4)
        assert client._min_request_delay == 0.1

    def test_custom_constructor(self):
        client = SchoolCafeClient(
            timeout=10, max_retries=1, retry_delays=(0.5,), min_request_delay=0
        )
        assert client._max_retries == 1
        assert client._retry_delays == (0.5,)
        assert client._min_request_delay == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_menu_client_http.py::TestClientConfig -v`
Expected: FAIL — `AttributeError: 'SchoolCafeClient' object has no attribute '_max_retries'`

- [ ] **Step 3: Update constructor with new params**

In `src/lunchbox/sync/menu_client.py`, replace the `__init__` method:

```python
def __init__(
    self,
    timeout: int = 30,
    max_retries: int = 3,
    retry_delays: tuple[float, ...] = (1, 2, 4),
    min_request_delay: float = 0.1,
):
    self._client = httpx.Client(
        timeout=timeout, headers={"Accept": "application/json"}
    )
    self._max_retries = max_retries
    self._retry_delays = retry_delays
    self._min_request_delay = min_request_delay
    self._last_request_time = 0.0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_menu_client_http.py::TestClientConfig -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py
git commit -m "feat: add constructor params for retry and throttle config (#59, #60)"
```

---

### Task 2: Add `_throttle()` and `_request()` with retry logic

**Files:**
- Modify: `src/lunchbox/sync/menu_client.py` (add methods after constructor)
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write failing test — retry succeeds on second attempt**

Add to `tests/unit/test_menu_client_http.py`:

```python
class TestRetry:
    @respx.mock
    def test_retry_succeeds_on_second_attempt(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json=data),
        ]

        with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
            items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert len(items) > 0
        assert route.call_count == 2

    @respx.mock
    def test_retry_exhausted_raises(self):
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ]

        with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert route.call_count == 4  # 1 initial + 3 retries

    @respx.mock
    def test_4xx_not_retried(self):
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.mock(return_value=httpx.Response(404))

        with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
            with pytest.raises(httpx.HTTPStatusError):
                client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert route.call_count == 1  # no retries

    @respx.mock
    def test_timeout_retried(self, schoolcafe_fixture):
        data = schoolcafe_fixture("normal_lunch")
        route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
        route.side_effect = [
            httpx.TimeoutException("timed out"),
            httpx.Response(200, json=data),
        ]

        with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
            items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert len(items) > 0
        assert route.call_count == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_menu_client_http.py::TestRetry -v`
Expected: FAIL — retry tests fail because `get_daily_menu()` still calls `self._client.get()` directly

- [ ] **Step 3: Implement `_throttle()` and `_request()`**

First, add imports and constant at the **top of `menu_client.py`** (module level):

```python
import json
import time
```

Add after the `CATEGORY_ALIASES` dict (module level):

```python
RETRY_AFTER_CAP = 10  # seconds — max we'll honor from Retry-After header
```

Then add these methods to the `SchoolCafeClient` class, after `__init__`:

```python
def _throttle(self):
    elapsed = time.monotonic() - self._last_request_time
    if self._min_request_delay > 0 and elapsed < self._min_request_delay:
        time.sleep(self._min_request_delay - elapsed)

def _request(self, url: str, **kwargs) -> httpx.Response:
    last_exc = None

    for attempt in range(self._max_retries + 1):
        self._throttle()
        self._last_request_time = time.monotonic()

        try:
            response = self._client.get(url, **kwargs)
            response.raise_for_status()
            return response
        except httpx.TimeoutException as e:
            last_exc = e
            if attempt == self._max_retries:
                raise
            delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
            logger.warning("Request timeout (attempt %d/%d), retrying in %.1fs", attempt + 1, self._max_retries, delay)
            time.sleep(delay)
        except httpx.HTTPStatusError as e:
            last_exc = e
            status = e.response.status_code
            if status == 429:
                retry_after = e.response.headers.get("Retry-After")
                if retry_after:
                    try:
                        delay = min(float(retry_after), RETRY_AFTER_CAP)
                    except ValueError:
                        delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
                else:
                    delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
            elif status >= 500:
                delay = self._retry_delays[min(attempt, len(self._retry_delays) - 1)]
            else:
                raise  # 4xx (not 429) — don't retry

            if attempt == self._max_retries:
                raise
            logger.warning("HTTP %d (attempt %d/%d), retrying in %.1fs", status, attempt + 1, self._max_retries, delay)
            time.sleep(delay)

    raise last_exc  # unreachable but satisfies type checker
```

- [ ] **Step 4: Wire `get_daily_menu()` to use `_request()`**

Replace the HTTP call in `get_daily_menu()`:

```python
# Replace:
#   response = self._client.get(
#       f"{self.BASE_URL}/CalendarView/GetDailyMenuitemsByGrade",
#       params=params,
#   )
#   response.raise_for_status()
#   data = response.json()

# With:
response = self._request(
    f"{self.BASE_URL}/CalendarView/GetDailyMenuitemsByGrade",
    params=params,
)
data = response.json()
```

- [ ] **Step 5: Update existing tests that now retry**

These tests must be updated BEFORE running the suite, since `get_daily_menu()` now retries.

In `tests/unit/test_menu_client_http.py`, update `TestGetDailyMenu`:

```python
# test_http_500_raises — use max_retries=0
@respx.mock
def test_http_500_raises(self):
    respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
        return_value=httpx.Response(500)
    )

    with SchoolCafeClient(max_retries=0) as client:
        with pytest.raises(httpx.HTTPStatusError):
            client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

# test_timeout_raises — use max_retries=0
@respx.mock
def test_timeout_raises(self):
    respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
        side_effect=httpx.TimeoutException("timed out")
    )

    with SchoolCafeClient(max_retries=0) as client:
        with pytest.raises(httpx.TimeoutException):
            client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")
```

- [ ] **Step 6: Wire `search_schools()` to use `_request()`**

Replace both HTTP calls in `search_schools()`:

```python
# Replace both self._client.get() + raise_for_status() pairs with:
response = self._request(
    f"{self.BASE_URL}/GetISDByShortName",
    params={"shortname": query},
)
districts = response.json()

# ... existing district_id logic ...

response = self._request(
    f"{self.BASE_URL}/GetSchoolsList",
    params={"districtId": district_id},
)
schools = response.json()
```

- [ ] **Step 7: Run retry tests and full suite**

Run: `pytest tests/unit/test_menu_client_http.py tests/unit/test_menu_client.py -v`
Expected: All tests PASS (retry tests pass, existing tests pass with max_retries=0)

- [ ] **Step 8: Commit**

```bash
git add src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py
git commit -m "feat: add retry with exponential backoff and throttle to SchoolCafe client (#59, #60)"
```

---

### Task 3: Add 429 tests

**Files:**
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write 429 with Retry-After test**

Add to `TestRetry` class:

```python
@respx.mock
def test_429_respects_retry_after(self, schoolcafe_fixture):
    data = schoolcafe_fixture("normal_lunch")
    route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
    route.side_effect = [
        httpx.Response(429, headers={"Retry-After": "0"}),
        httpx.Response(200, json=data),
    ]

    with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
        items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

    assert len(items) > 0
    assert route.call_count == 2

@respx.mock
def test_429_without_retry_after(self, schoolcafe_fixture):
    data = schoolcafe_fixture("normal_lunch")
    route = respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade")
    route.side_effect = [
        httpx.Response(429),  # no Retry-After header
        httpx.Response(200, json=data),
    ]

    with SchoolCafeClient(max_retries=3, retry_delays=(0, 0, 0), min_request_delay=0) as client:
        items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

    assert len(items) > 0
    assert route.call_count == 2
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_menu_client_http.py::TestRetry::test_429_respects_retry_after tests/unit/test_menu_client_http.py::TestRetry::test_429_without_retry_after -v`
Expected: PASS (both)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_menu_client_http.py
git commit -m "test: add 429 rate limit tests with and without Retry-After header (#60)"
```

---

## Chunk 2: Response Validation

### Task 4: Add response validation to `get_daily_menu()`

**Files:**
- Modify: `src/lunchbox/sync/menu_client.py:91-119` (`get_daily_menu` method)
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write failing tests for response validation**

Add to `tests/unit/test_menu_client_http.py`:

```python
class TestResponseValidation:
    @respx.mock
    def test_malformed_json_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, content=b"not json at all")
        )

        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert items == []

    @respx.mock
    def test_non_dict_response_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=["not", "a", "dict"])
        )

        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert items == []

    @respx.mock
    def test_null_response_returns_empty(self):
        respx.get(f"{BASE_URL}/CalendarView/GetDailyMenuitemsByGrade").mock(
            return_value=httpx.Response(200, json=None)
        )

        with SchoolCafeClient(max_retries=0) as client:
            items = client.get_daily_menu("s1", date(2026, 3, 16), "Lunch", "Trad", "05")

        assert items == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_menu_client_http.py::TestResponseValidation -v`
Expected: FAIL — `JSONDecodeError` or unexpected behavior (no guards in place)

- [ ] **Step 3: Add validation to `get_daily_menu()`**

In `get_daily_menu()`, replace the response parsing section after `_request()`:

```python
response = self._request(
    f"{self.BASE_URL}/CalendarView/GetDailyMenuitemsByGrade",
    params=params,
)

try:
    data = response.json()
except json.JSONDecodeError:
    logger.warning("SchoolCafe returned invalid JSON for %s %s", school_id, menu_date)
    return []

if not isinstance(data, dict):
    logger.warning("SchoolCafe returned non-dict response: %s", type(data).__name__)
    return []

drift_warnings = _detect_drift(data)
for warning in drift_warnings:
    logger.warning("SchoolCafe schema drift: %s", warning)

return self._parse_response(data)
```

Add `import json` at the top of the file if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_menu_client_http.py::TestResponseValidation -v`
Expected: PASS (all 3)

- [ ] **Step 5: Commit**

```bash
git add src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py
git commit -m "fix: validate SchoolCafe response before parsing (#61)"
```

---

### Task 5: Add response validation to `search_schools()`

**Files:**
- Modify: `src/lunchbox/sync/menu_client.py:147-176` (`search_schools` method)
- Test: `tests/unit/test_menu_client_http.py`

- [ ] **Step 1: Write failing test for search validation**

Add to `TestResponseValidation`:

```python
@respx.mock
def test_search_malformed_json_returns_empty(self):
    respx.get(f"{BASE_URL}/GetISDByShortName").mock(
        return_value=httpx.Response(200, content=b"not json")
    )

    with SchoolCafeClient(max_retries=0) as client:
        result = client.search_schools("test")

    assert result == []

@respx.mock
def test_search_non_list_districts_returns_empty(self):
    respx.get(f"{BASE_URL}/GetISDByShortName").mock(
        return_value=httpx.Response(200, json={"error": "bad request"})
    )

    with SchoolCafeClient(max_retries=0) as client:
        result = client.search_schools("test")

    assert result == []

@respx.mock
def test_search_non_list_schools_returns_empty(self, schoolcafe_fixture):
    districts = schoolcafe_fixture("search_districts")
    respx.get(f"{BASE_URL}/GetISDByShortName").mock(
        return_value=httpx.Response(200, json=districts)
    )
    respx.get(f"{BASE_URL}/GetSchoolsList").mock(
        return_value=httpx.Response(200, json={"error": "bad"})
    )

    with SchoolCafeClient(max_retries=0) as client:
        result = client.search_schools("springfield")

    assert result == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_menu_client_http.py::TestResponseValidation::test_search_malformed_json_returns_empty tests/unit/test_menu_client_http.py::TestResponseValidation::test_search_non_list_districts_returns_empty tests/unit/test_menu_client_http.py::TestResponseValidation::test_search_non_list_schools_returns_empty -v`
Expected: FAIL — `JSONDecodeError` or `TypeError`

- [ ] **Step 3: Add validation to `search_schools()`**

Replace `search_schools()`:

```python
def search_schools(self, query: str) -> list[SchoolInfo]:
    response = self._request(
        f"{self.BASE_URL}/GetISDByShortName",
        params={"shortname": query},
    )

    try:
        districts = response.json()
    except json.JSONDecodeError:
        logger.warning("SchoolCafe returned invalid JSON for school search: %s", query)
        return []

    if not isinstance(districts, list) or not districts:
        return []

    district_id = districts[0].get("ISDId")
    if not district_id:
        return []

    response = self._request(
        f"{self.BASE_URL}/GetSchoolsList",
        params={"districtId": district_id},
    )

    try:
        schools = response.json()
    except json.JSONDecodeError:
        logger.warning("SchoolCafe returned invalid JSON for schools list")
        return []

    if not isinstance(schools, list):
        return []

    return [
        SchoolInfo(
            school_id=s.get("SchoolId", ""),
            school_name=s.get("SchoolName", ""),
        )
        for s in schools
        if s.get("SchoolId")
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_menu_client_http.py::TestResponseValidation -v`
Expected: PASS (all 6 validation tests)

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/unit/test_menu_client_http.py tests/unit/test_menu_client.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py
git commit -m "fix: add response validation to search_schools (#61)"
```

---

### Task 6: Final verification and lint

- [ ] **Step 1: Run ruff**

Run: `ruff check src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py && ruff format --check src/lunchbox/sync/menu_client.py tests/unit/test_menu_client_http.py`
Expected: Clean

- [ ] **Step 2: Run full unit test suite**

Run: `pytest tests/unit/ -v`
Expected: All tests PASS, no regressions

- [ ] **Step 3: Commit any lint fixes if needed**

```bash
git add -u && git commit -m "chore: lint fixes"
```
(Skip if nothing to fix.)
