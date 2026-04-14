from unittest.mock import MagicMock, patch

from tests.factories import create_subscription, create_sync_log


class TestCronEndpoint:
    def test_cron_rejects_missing_secret(self, client):
        response = client.get("/api/sync/cron")
        assert response.status_code == 403

    def test_cron_rejects_wrong_secret(self, client):
        response = client.get(
            "/api/sync/cron",
            headers={"authorization": "Bearer wrong"},
        )
        assert response.status_code == 403

    def test_cron_succeeds_with_correct_secret(self, client, db):
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
            mock_instance.get_weekly_menu.return_value = {}
            mock_instance.__enter__ = MagicMock(return_value=mock_instance)
            mock_instance.__exit__ = MagicMock(return_value=False)
            MockClient.return_value = mock_instance

            response = client.get(
                "/api/sync/cron",
                headers={"authorization": "Bearer test-secret"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "ok"

    def test_cron_returns_500_on_sync_exception(self, client, db):
        with (
            patch("lunchbox.api.sync.settings") as mock_settings,
            patch("lunchbox.api.sync.SchoolCafeClient") as MockClient,
            patch("lunchbox.api.sync.sync_all", side_effect=Exception("boom")),
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

            response = client.get(
                "/api/sync/cron",
                headers={"authorization": "Bearer test-secret"},
            )

        assert response.status_code == 500
        assert "Sync failed" in response.json()["detail"]

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

    def test_cron_skips_when_max_syncs_reached(self, authenticated_client, db):
        client, user = authenticated_client
        sub = create_subscription(db, user)
        for _ in range(10):
            create_sync_log(db, sub)
        db.commit()

        with patch("lunchbox.api.sync.settings") as mock_settings:
            mock_settings.cron_secret = "test-secret"
            mock_settings.max_syncs_per_day = 10
            mock_settings.max_menu_items = 50000

            response = client.get(
                "/api/sync/cron",
                headers={"authorization": "Bearer test-secret"},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "skipped"
