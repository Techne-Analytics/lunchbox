from unittest.mock import patch

from tests.factories import create_subscription, create_user


class TestSubscriptionCaps:
    def test_per_user_cap(self, authenticated_client, db):
        client, user = authenticated_client
        for i in range(5):
            create_subscription(db, user, display_name=f"Sub {i}")
        db.commit()

        with patch("lunchbox.api.subscriptions.settings") as mock_settings:
            mock_settings.max_subscriptions_per_user = 5
            mock_settings.max_subscriptions_global = 20

            response = client.post(
                "/api/subscriptions",
                json={
                    "school_id": "test",
                    "school_name": "Test",
                    "grade": "05",
                    "meal_configs": [
                        {"meal_type": "Lunch", "serving_line": "Trad", "sort_order": 0}
                    ],
                    "display_name": "Over Limit",
                },
            )

        assert response.status_code == 400
        assert "Maximum" in response.json()["detail"]

    def test_global_cap(self, authenticated_client, db):
        client, user = authenticated_client
        for i in range(20):
            other = create_user(db, google_id=f"global-cap-{i}")
            create_subscription(db, other, display_name=f"Global {i}")
        db.commit()

        with patch("lunchbox.api.subscriptions.settings") as mock_settings:
            mock_settings.max_subscriptions_per_user = 5
            mock_settings.max_subscriptions_global = 20

            response = client.post(
                "/api/subscriptions",
                json={
                    "school_id": "test",
                    "school_name": "Test",
                    "grade": "05",
                    "meal_configs": [
                        {"meal_type": "Lunch", "serving_line": "Trad", "sort_order": 0}
                    ],
                    "display_name": "Over Global Limit",
                },
            )

        assert response.status_code == 400
