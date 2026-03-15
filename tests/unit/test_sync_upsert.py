from datetime import date
from unittest.mock import MagicMock

from lunchbox.models import MenuItem
from lunchbox.sync.engine import sync_subscription
from lunchbox.sync.providers import MenuItemData
from tests.factories import create_menu_item, create_subscription, create_user


class TestSyncUpsert:
    def test_upsert_replaces_old_items(self, db):
        """Syncing same date/meal replaces items, not duplicates."""
        user = create_user(db)
        sub = create_subscription(db, user)
        # Pre-existing item for same date/meal
        create_menu_item(
            db,
            sub,
            menu_date=date.today(),
            meal_type="Lunch",
            item_name="OldBurger",
        )
        db.commit()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = [
            MenuItemData(category="Entrees", item_name="NewPizza"),
        ]

        sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        items = db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).all()
        names = [i.item_name for i in items]
        assert "NewPizza" in names
        assert "OldBurger" not in names

    def test_partial_upsert_preserves_successful_dates(self, db):
        """If one date fails, items from other dates are still saved."""
        user = create_user(db)
        sub = create_subscription(db, user)
        db.commit()

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API error")
            return [MenuItemData(category="Entrees", item_name="Taco")]

        mock_client = MagicMock()
        mock_client.get_daily_menu.side_effect = side_effect

        sync_subscription(db, sub, mock_client, days=2, skip_weekends=False)

        items = db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).all()
        assert len(items) == 1
        assert items[0].item_name == "Taco"

    def test_empty_response_clears_old_items(self, db):
        """Empty API response deletes old items for that date (cache invalidation)."""
        user = create_user(db)
        sub = create_subscription(db, user)
        target_date = date.today()
        create_menu_item(
            db,
            sub,
            menu_date=target_date,
            meal_type="Lunch",
            item_name="StaleItem",
        )
        db.commit()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = []  # empty

        sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        items = (
            db.query(MenuItem)
            .filter(
                MenuItem.subscription_id == sub.id,
                MenuItem.menu_date == target_date,
            )
            .all()
        )
        assert len(items) == 0
