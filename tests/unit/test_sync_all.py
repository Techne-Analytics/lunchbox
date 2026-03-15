from unittest.mock import MagicMock, patch

from lunchbox.sync.engine import sync_all
from tests.factories import create_subscription, create_user


class TestSyncAll:
    def test_one_failure_does_not_block_others(self, db):
        user = create_user(db)
        sub1 = create_subscription(db, user, display_name="Sub1")
        _sub2 = create_subscription(db, user, display_name="Sub2")
        db.commit()

        call_count = 0

        def mock_sync(db, sub, client, **kwargs):
            nonlocal call_count
            call_count += 1
            if sub.id == sub1.id:
                raise Exception("Sub1 failed")

        mock_client = MagicMock()

        with (
            patch("lunchbox.sync.engine.sync_subscription", side_effect=mock_sync),
            patch("lunchbox.sync.engine.logger") as mock_logger,
        ):
            sync_all(db, mock_client, days=1, skip_weekends=False)

        assert call_count == 2
        # Verify the failure was logged, not silently swallowed
        mock_logger.exception.assert_called_once()

    def test_only_active_subscriptions_synced(self, db):
        user = create_user(db)
        active = create_subscription(db, user, display_name="Active", is_active=True)
        inactive = create_subscription(
            db, user, display_name="Inactive", is_active=False
        )
        db.commit()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = []

        with patch("lunchbox.sync.engine.sync_subscription") as mock_sync:
            sync_all(db, mock_client, days=1, skip_weekends=False)

        synced_ids = {call.args[1].id for call in mock_sync.call_args_list}
        assert active.id in synced_ids
        assert inactive.id not in synced_ids

    def test_empty_no_subscriptions(self, db):
        mock_client = MagicMock()
        sync_all(db, mock_client, days=1, skip_weekends=False)
