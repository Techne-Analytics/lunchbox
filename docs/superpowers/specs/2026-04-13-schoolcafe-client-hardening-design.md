# SchoolCafe Client Hardening

**Date:** 2026-04-13
**Issues:** #59 (retry), #60 (rate limiting), #61 (response validation)
**Scope:** `src/lunchbox/sync/menu_client.py` + tests

## Problem

The SchoolCafe API client has no resilience against transient failures. A single 503 or timeout loses a day's menu data. No throttling between requests risks hitting rate limits during bulk syncs (~280 calls per cron run). Malformed or unexpected responses crash the parser.

## Design

### Core: `_request()` method

A private method on `SchoolCafeClient` that centralizes HTTP concerns: throttle, request, retry.

```
caller -> _request() -> throttle -> HTTP call -> return response
                          ^                         |
                          +-- retry (5xx/429/timeout) --+
```

Both `get_daily_menu()` and `search_schools()` use `_request()` instead of calling `self._client.get()` directly.

**Throttle:** Sleep if less than `min_request_delay` seconds since the last request. Uses `time.monotonic()` for clock stability.

**Retry logic:**
- On HTTP 5xx or `httpx.TimeoutException`: wait `retry_delays[attempt]` seconds, retry
- On HTTP 429: use `Retry-After` header if present (capped at 60s), otherwise use standard delay, retry
- On HTTP 4xx (not 429): raise immediately, no retry
- After `max_retries` exhausted: raise the last exception

**Not retried:** `httpx.ConnectError`, `httpx.RequestError` subclasses other than timeout (network is down, DNS failure — retrying won't help within the sync window).

### Response validation in `get_daily_menu()`

After `_request()` returns successfully:

1. Wrap `response.json()` in `try/except json.JSONDecodeError` — log warning, return `[]`
2. Check `isinstance(data, dict)` — log warning if not, return `[]`
3. Existing drift detection and `_parse_response()` proceed as before

`search_schools()` already handles non-list responses gracefully (checks `if not districts`), so it only needs the `JSONDecodeError` guard.

### Constructor parameters

```python
class SchoolCafeClient:
    def __init__(
        self,
        timeout: int = 30,
        max_retries: int = 3,
        retry_delays: tuple[float, ...] = (1, 2, 4),
        min_request_delay: float = 0.1,
    ):
```

All new params have defaults matching the issue specs. Tests can pass `max_retries=0` to disable retries or `min_request_delay=0` to skip throttling.

### What changes

| File | Change |
|------|--------|
| `src/lunchbox/sync/menu_client.py` | Add `_request()`, `_throttle()`. Update `get_daily_menu()` and `search_schools()` to use `_request()`. Add JSON/dict validation in `get_daily_menu()`. Add `JSONDecodeError` guard in `search_schools()`. New constructor params. |
| `tests/unit/test_menu_client_http.py` | Update `test_http_500_raises` and `test_timeout_raises` to use `max_retries=0`. Add new tests for retry, throttle, 429, and validation. |

### What stays the same

- `_parse_response()`, `_detect_drift()`, `_extract_item_name()`, `_normalize_category()` — untouched
- `engine.py` — no changes (already catches client exceptions)
- `providers.py` — `MenuProvider` protocol unchanged (no signature changes)
- All existing parsing tests in `test_menu_client.py` — unaffected

### New tests

| Test | What it verifies |
|------|-----------------|
| `test_retry_succeeds_on_second_attempt` | 500 then 200 returns data |
| `test_retry_exhausted_raises` | 3x 500 raises `HTTPStatusError` |
| `test_4xx_not_retried` | 404 raises immediately (1 request, not 4) |
| `test_429_respects_retry_after` | 429 with `Retry-After: 1` header retries after delay |
| `test_timeout_retried` | Timeout then 200 returns data |
| `test_malformed_json_returns_empty` | Non-JSON response body returns `[]` |
| `test_non_dict_response_returns_empty` | JSON array response returns `[]` |
| `test_null_response_returns_empty` | JSON null response returns `[]` |
| `test_search_malformed_json_returns_empty` | search_schools handles bad JSON |

Existing tests `test_http_500_raises` and `test_timeout_raises` updated to pass `max_retries=0` so they keep their current assertion (immediate raise).

### Error budget

With 3 retries and delays of (1, 2, 4), worst case per request is 7 seconds. For 280 requests, if every request maxes out retries, total sync time = ~33 minutes. The Vercel function timeout is 60 seconds, but the engine already catches per-request failures — so individual timeouts don't kill the whole sync. The throttle adds 0.1s * 280 = 28 seconds baseline. Acceptable for a daily cron job.
