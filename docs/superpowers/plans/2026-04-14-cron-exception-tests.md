# Cron Exception Tests Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 2 missing exception-resilience tests to the cron endpoint test suite.

**Architecture:** Add tests to existing `tests/unit/test_cron.py`. Mock `SchoolCafeClient` and `sync_all` to trigger error paths in `cron_sync()`.

**Tech Stack:** Python 3.11, pytest, unittest.mock

**Spec:** `docs/superpowers/specs/2026-04-14-cron-exception-tests-design.md`

---

## Task 1: Add cron exception tests

**Files:**
- Modify: `tests/unit/test_cron.py`

- [ ] **Step 1: Write `test_cron_returns_500_on_sync_exception`**

```python
def test_cron_returns_500_on_sync_exception(self, client, db):
    with (
        patch("lunchbox.api.sync.settings") as mock_settings,
        patch("lunchbox.api.sync.SchoolCafeClient") as MockClient,
    ):
        mock_settings.cron_secret = "test-secret"
        mock_settings.max_syncs_per_day = 10
        mock_settings.max_menu_items = 50000
        mock_settings.days_to_fetch = 1
        mock_settings.skip_weekends = False

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_instance

        with patch("lunchbox.api.sync.sync_all", side_effect=Exception("boom")):
            response = client.get(
                "/api/sync/cron",
                headers={"authorization": "Bearer test-secret"},
            )

    assert response.status_code == 500
    assert "Sync failed" in response.json()["detail"]
```

- [ ] **Step 2: Write `test_cron_returns_500_when_all_syncs_fail`**

```python
def test_cron_returns_500_when_all_syncs_fail(self, authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    db.commit()

    def mock_sync_all(db_session, client, **kwargs):
        create_sync_log(db_session, sub, status="error", error_message="API down")
        db_session.commit()

    with (
        patch("lunchbox.api.sync.settings") as mock_settings,
        patch("lunchbox.api.sync.SchoolCafeClient") as MockClient,
        patch("lunchbox.api.sync.sync_all", side_effect=mock_sync_all),
    ):
        mock_settings.cron_secret = "test-secret"
        mock_settings.max_syncs_per_day = 10
        mock_settings.max_menu_items = 50000

        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_instance

        response = client.get(
            "/api/sync/cron",
            headers={"authorization": "Bearer test-secret"},
        )

    assert response.status_code == 500
    assert "failed" in response.json()["detail"].lower()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/unit/test_cron.py -v`
Expected: 6 tests pass (4 existing + 2 new)

- [ ] **Step 4: Commit**

```
git commit -m "test: add cron exception resilience tests (#42)"
```
