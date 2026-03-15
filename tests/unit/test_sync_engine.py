from datetime import date
from unittest.mock import MagicMock

from lunchbox.models import MenuItem, Subscription, User
from lunchbox.sync.engine import get_sync_dates, sync_subscription
from lunchbox.sync.providers import MenuItemData


class TestGetSyncDates:
    def test_basic(self):
        dates = get_sync_dates(3, skip_weekends=False, start=date(2026, 3, 16))
        assert len(dates) == 3
        assert dates[0] == date(2026, 3, 16)

    def test_skip_weekends(self):
        # 2026-03-14 is a Saturday
        dates = get_sync_dates(3, skip_weekends=True, start=date(2026, 3, 14))
        for d in dates:
            assert d.weekday() < 5  # Mon-Fri

    def test_returns_requested_count(self):
        dates = get_sync_dates(5, skip_weekends=True, start=date(2026, 3, 16))
        assert len(dates) == 5


class TestSyncSubscription:
    def test_successful_sync(self, db):
        user = User(google_id="sync-test", email="t@t.com", name="T")
        db.add(user)
        db.flush()

        sub = Subscription(
            user_id=user.id,
            school_id="test-school",
            school_name="Test School",
            grade="05",
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0}
            ],
            display_name="Test School",
        )
        db.add(sub)
        db.flush()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = [
            MenuItemData(category="Entrees", item_name="Pizza"),
            MenuItemData(category="Fruits", item_name="Apple"),
        ]

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "success"
        assert log.items_fetched == 4  # 2 items x 2 days
        assert log.dates_synced == 2

        items = db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).all()
        assert len(items) == 4

    def test_partial_failure(self, db):
        user = User(google_id="sync-partial", email="t@t.com", name="T")
        db.add(user)
        db.flush()

        sub = Subscription(
            user_id=user.id,
            school_id="test-school",
            school_name="Test School",
            grade="05",
            meal_configs=[
                {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0}
            ],
            display_name="Test School",
        )
        db.add(sub)
        db.flush()

        mock_client = MagicMock()
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API down")
            return [MenuItemData(category="Entrees", item_name="Burger")]

        mock_client.get_daily_menu.side_effect = side_effect

        log = sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        assert log.status == "partial"
        assert log.error_message is not None
