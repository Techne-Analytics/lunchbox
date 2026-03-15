from lunchbox.auth.dependencies import get_current_user
from lunchbox.main import app
from lunchbox.models import Subscription, User


def test_create_subscription(client, db):
    user = User(google_id="api-create", email="t@t.com", name="Test")
    db.add(user)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.post(
        "/api/subscriptions",
        json={
            "school_id": "abc-123",
            "school_name": "Test School",
            "grade": "05",
            "meal_configs": [
                {
                    "meal_type": "Lunch",
                    "serving_line": "Traditional Lunch",
                    "sort_order": 0,
                }
            ],
            "display_name": "Test School - 5th Grade",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "feed_url" in data
    assert data["feed_url"].startswith("/cal/")

    app.dependency_overrides.pop(get_current_user, None)


def test_list_subscriptions(client, db):
    user = User(google_id="api-list", email="t@t.com", name="Test")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="Test",
    )
    db.add(sub)
    db.flush()

    app.dependency_overrides[get_current_user] = lambda: user

    response = client.get("/api/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Test"

    app.dependency_overrides.pop(get_current_user, None)
