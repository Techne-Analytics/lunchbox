from unittest.mock import MagicMock, patch

from lunchbox.sync.engine import sync_all
from tests.factories import create_subscription, create_user


class TestSyncAll:
    def test_one_failure_does_not_block_others(self, db):
        from lunchbox.models import SyncLog

        user = create_user(db)
        sub1 = create_subscription(db, user, display_name="Sub1")
        sub2 = create_subscription(db, user, display_name="Sub2")
        db.commit()

        mock_client = MagicMock()
        mock_client.get_daily_menu.return_value = []

        # Let sync_subscription run for real. First sub's API calls fail,
        # second sub's succeed. Both should produce SyncLog records.
        call_count = 0

        def failing_then_ok(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 1:
                raise Exception("Sub1 API failure")
            return []

        mock_client.get_daily_menu.side_effect = failing_then_ok

        sync_all(db, mock_client, days=1, skip_weekends=False)

        # Filter to only logs for OUR subscriptions (DB persists across tests)
        our_ids = {sub1.id, sub2.id}
        logs = (
            db.query(SyncLog)
            .filter(SyncLog.subscription_id.in_(our_ids))
            .all()
        )
        assert len(logs) == 2

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
