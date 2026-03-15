from unittest.mock import MagicMock, patch

from tests.factories import create_subscription, create_sync_log, create_user


class TestSyncTrigger:
    def test_trigger_sync(self, authenticated_client, db):
        client, user = authenticated_client
        sub = create_subscription(db, user)
        db.commit()

        with patch("lunchbox.api.sync.SchoolCafeClient") as MockClient:
            mock_instance = MagicMock()
            mock_instance.get_daily_menu.return_value = []
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.post(f"/api/sync/trigger/{sub.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("success", "partial", "error")
        assert "items_fetched" in data

    def test_trigger_sync_isolation(self, authenticated_client, db):
        client, _ = authenticated_client
        other_user = create_user(db, google_id="other-sync")
        other_sub = create_subscription(db, other_user)
        db.commit()

        response = client.post(f"/api/sync/trigger/{other_sub.id}")
        assert response.status_code == 404


class TestSyncHistory:
    def test_sync_history(self, authenticated_client, db):
        client, user = authenticated_client
        sub = create_subscription(db, user)
        create_sync_log(db, sub, status="success", items_fetched=10)
        create_sync_log(db, sub, status="partial", items_fetched=5)
        db.commit()

        response = client.get(f"/api/sync/history/{sub.id}")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_sync_history_isolation(self, authenticated_client, db):
        client, _ = authenticated_client
        other_user = create_user(db, google_id="other-history")
        other_sub = create_subscription(db, other_user)
        db.commit()

        response = client.get(f"/api/sync/history/{other_sub.id}")
        assert response.status_code == 404

    def test_sync_history_empty(self, authenticated_client, db):
        client, user = authenticated_client
        sub = create_subscription(db, user)
        db.commit()

        response = client.get(f"/api/sync/history/{sub.id}")
        assert response.status_code == 200
        assert response.json() == []
