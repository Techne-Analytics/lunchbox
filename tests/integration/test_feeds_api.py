import uuid
from datetime import date

from lunchbox.models import MenuItem, Subscription, User
from tests.factories import create_menu_item, create_subscription, create_user


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
        menu_date=date(2026, 3, 16),
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


def test_feed_cache_headers(client, db):
    user = create_user(db)
    sub = create_subscription(db, user)
    create_menu_item(db, sub)
    db.commit()

    response = client.get(f"/cal/{sub.feed_token}.ics")
    assert response.status_code == 200
    assert "ETag" in response.headers
    assert response.headers["ETag"].startswith('"')
    assert "Last-Modified" in response.headers
    assert response.headers["Cache-Control"] == "max-age=3600"


def test_feed_inactive_subscription(client, db):
    user = create_user(db)
    sub = create_subscription(db, user, is_active=False)
    db.commit()

    response = client.get(f"/cal/{sub.feed_token}.ics")
    assert response.status_code == 404


def test_feed_etag_consistency(client, db):
    """Same data produces same ETag when time is frozen."""
    from unittest.mock import patch
    from datetime import datetime, timezone

    user = create_user(db)
    sub = create_subscription(db, user)
    create_menu_item(db, sub)
    db.commit()

    frozen = datetime(2026, 3, 16, 12, 0, 0, tzinfo=timezone.utc)
    with patch("lunchbox.api.feeds.datetime") as mock_dt:
        mock_dt.now.return_value = frozen
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        r1 = client.get(f"/cal/{sub.feed_token}.ics")
        r2 = client.get(f"/cal/{sub.feed_token}.ics")

    assert r1.headers["ETag"] == r2.headers["ETag"]
