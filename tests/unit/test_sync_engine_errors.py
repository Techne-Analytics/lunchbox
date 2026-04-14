from unittest.mock import MagicMock

import httpx

from lunchbox.models import MenuItem
from lunchbox.sync.engine import sync_subscription
from lunchbox.sync.providers import MenuItemData
from tests.factories import create_subscription, create_user


class TestSyncErrors:
    def test_all_dates_fail_status_error(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.side_effect = Exception("API down")

        log = sync_subscription(db, sub, mock_client, days=3, skip_weekends=False)

        assert log.status == "error"
        assert log.error_message is not None
        assert log.items_fetched == 0
        # dates_synced reports total requested, not successful — by design
        assert log.dates_synced == 3
        assert (
            db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).count() == 0
        )

    def test_mixed_failure_status_partial(self, db):
        from datetime import date, timedelta

        user = create_user(db)
        sub = create_subscription(
            db,
            user,
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0},
                {
                    "meal_type": "Breakfast",
                    "serving_line": "Traditional",
                    "sort_order": 1,
                },
            ],
        )
        db.commit()

        today = date.today()
        week_data = {
            today: [MenuItemData(category="Entrees", item_name="Burger")],
            today + timedelta(days=1): [
                MenuItemData(category="Entrees", item_name="Burger")
            ],
        }

        mock_client = MagicMock()
        mock_client.get_weekly_menu.side_effect = [
            Exception("Intermittent failure"),
            week_data,
        ]

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "partial"
        assert log.items_fetched == 2
        # dates_synced reports total requested, not successful — by design
        assert log.dates_synced == 2
        assert "Intermittent failure" in log.error_message

    def test_timeout_handled_gracefully(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.side_effect = httpx.TimeoutException("timed out")

        log = sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        assert log.status == "error"
        assert "timed out" in log.error_message

    def test_http_500_handled_gracefully(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.side_effect = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=httpx.Request("GET", "https://example.com"),
            response=httpx.Response(500),
        )

        log = sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        assert log.status == "error"
        assert log.error_message is not None

    def test_empty_response_status_success(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.return_value = {}

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "success"
        assert log.items_fetched == 0

    def test_duration_ms_populated(self, db):
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        mock_client = MagicMock()
        mock_client.get_weekly_menu.return_value = {}

        log = sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        assert log.duration_ms is not None
        assert log.duration_ms >= 0
