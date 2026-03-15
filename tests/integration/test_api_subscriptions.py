from tests.factories import (
    create_menu_item,
    create_subscription,
    create_sync_log,
    create_user,
)


def test_create_subscription(authenticated_client, db):
    client, user = authenticated_client

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


def test_list_subscriptions(authenticated_client, db):
    client, user = authenticated_client
    create_subscription(db, user, display_name="Test")
    db.commit()

    response = client.get("/api/subscriptions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert any(s["display_name"] == "Test" for s in data)


def test_get_subscription(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    db.commit()

    response = client.get(f"/api/subscriptions/{sub.id}")
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == sub.display_name
    assert data["school_id"] == sub.school_id


def test_get_subscription_not_found(authenticated_client):
    client, _ = authenticated_client
    import uuid

    response = client.get(f"/api/subscriptions/{uuid.uuid4()}")
    assert response.status_code == 404


def test_get_subscription_isolation(authenticated_client, db):
    """User cannot access another user's subscription."""
    client, _ = authenticated_client
    other_user = create_user(db, google_id="other-user")
    other_sub = create_subscription(db, other_user)
    db.commit()

    response = client.get(f"/api/subscriptions/{other_sub.id}")
    assert response.status_code == 404


def test_update_subscription(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    db.commit()

    response = client.patch(
        f"/api/subscriptions/{sub.id}",
        json={"display_name": "Updated Name", "excluded_items": ["Ketchup"]},
    )
    assert response.status_code == 200

    db.refresh(sub)
    assert sub.display_name == "Updated Name"
    assert sub.excluded_items == ["Ketchup"]


def test_update_subscription_isolation(authenticated_client, db):
    client, _ = authenticated_client
    other_user = create_user(db, google_id="other-update")
    other_sub = create_subscription(db, other_user)
    db.commit()

    response = client.patch(
        f"/api/subscriptions/{other_sub.id}",
        json={"display_name": "Hacked"},
    )
    assert response.status_code == 404


def test_delete_subscription(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    create_menu_item(db, sub)
    create_sync_log(db, sub)
    db.commit()

    response = client.delete(f"/api/subscriptions/{sub.id}")
    assert response.status_code == 204

    from lunchbox.models import MenuItem, Subscription, SyncLog

    assert db.query(Subscription).filter(Subscription.id == sub.id).first() is None
    assert db.query(MenuItem).filter(MenuItem.subscription_id == sub.id).count() == 0
    assert db.query(SyncLog).filter(SyncLog.subscription_id == sub.id).count() == 0


def test_delete_subscription_isolation(authenticated_client, db):
    client, _ = authenticated_client
    other_user = create_user(db, google_id="other-delete")
    other_sub = create_subscription(db, other_user)
    db.commit()

    response = client.delete(f"/api/subscriptions/{other_sub.id}")
    assert response.status_code == 404


def test_regenerate_token(authenticated_client, db):
    client, user = authenticated_client
    sub = create_subscription(db, user)
    old_token = sub.feed_token
    db.commit()

    response = client.post(f"/api/subscriptions/{sub.id}/regenerate-token")
    assert response.status_code == 200
    data = response.json()
    assert "feed_url" in data

    db.refresh(sub)
    assert sub.feed_token != old_token
    assert str(sub.feed_token) in data["feed_url"]


def test_regenerate_token_isolation(authenticated_client, db):
    client, _ = authenticated_client
    other_user = create_user(db, google_id="other-regen")
    other_sub = create_subscription(db, other_user)
    db.commit()

    response = client.post(f"/api/subscriptions/{other_sub.id}/regenerate-token")
    assert response.status_code == 404
