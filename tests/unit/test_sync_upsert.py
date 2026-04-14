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
        mock_client.get_weekly_menu.return_value = {
            date.today(): [MenuItemData(category="Entrees", item_name="NewPizza")],
        }

        sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

        items = db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).all()
        names = [i.item_name for i in items]
        assert "NewPizza" in names
        assert "OldBurger" not in names

    def test_partial_upsert_preserves_successful_dates(self, db):
        """If one meal_config's weekly fetch fails, items from the other are still saved."""
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

        mock_client = MagicMock()
        mock_client.get_weekly_menu.side_effect = [
            Exception("API error"),
            {date.today(): [MenuItemData(category="Entrees", item_name="Taco")]},
        ]

        sync_subscription(db, sub, mock_client, days=1, skip_weekends=False)

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
        mock_client.get_weekly_menu.return_value = {}  # empty

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
