import uuid

from lunchbox.models import MenuItem, Subscription, User


def test_feed_returns_ical(client, db):
    user = User(google_id="feed-test", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    feed_token = uuid.uuid4()
    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="Test School",
        grade="05",
        meal_configs=[],
        display_name="Test School",
        feed_token=feed_token,
    )
    db.add(sub)
    db.flush()

    item = MenuItem(
        subscription_id=sub.id,
        school_id="abc",
        menu_date="2026-03-16",
        meal_type="Lunch",
        serving_line="Traditional",
        grade="05",
        category="Entrees",
        item_name="Pizza",
    )
    db.add(item)
    db.commit()

    response = client.get(f"/cal/{feed_token}.ics")
    assert response.status_code == 200
    assert "text/calendar" in response.headers["content-type"]
    assert "VCALENDAR" in response.text
    assert "Pizza" in response.text


def test_feed_not_found(client):
    fake_token = uuid.uuid4()
    response = client.get(f"/cal/{fake_token}.ics")
    assert response.status_code == 404


def test_feed_invalid_token(client):
    response = client.get("/cal/not-a-uuid.ics")
    assert response.status_code == 404
