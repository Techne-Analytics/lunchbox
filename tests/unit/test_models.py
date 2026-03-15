from datetime import date

from lunchbox.models import MenuItem, Subscription, SyncLog, User


def test_create_user(db):
    user = User(google_id="123", email="test@example.com", name="Test User")
    db.add(user)
    db.flush()
    assert user.id is not None
    assert user.google_id == "123"


def test_create_subscription(db):
    user = User(google_id="456", email="test@example.com", name="Test")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc-123",
        school_name="Test Elementary",
        grade="05",
        meal_configs=[
            {"meal_type": "Lunch", "serving_line": "Traditional Lunch", "sort_order": 0}
        ],
        display_name="Test Elementary - 5th Grade",
    )
    db.add(sub)
    db.flush()

    assert sub.id is not None
    assert sub.feed_token is not None
    assert sub.is_active is True
    assert sub.user_id == user.id


def test_create_menu_item(db):
    user = User(google_id="789", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="School",
    )
    db.add(sub)
    db.flush()

    item = MenuItem(
        subscription_id=sub.id,
        school_id="abc",
        menu_date=date(2026, 3, 15),
        meal_type="Lunch",
        serving_line="Traditional Lunch",
        grade="05",
        category="Entrees",
        item_name="Chicken Nuggets",
    )
    db.add(item)
    db.flush()
    assert item.id is not None


def test_create_sync_log(db):
    user = User(google_id="101", email="t@t.com", name="T")
    db.add(user)
    db.flush()

    sub = Subscription(
        user_id=user.id,
        school_id="abc",
        school_name="School",
        grade="05",
        meal_configs=[],
        display_name="School",
    )
    db.add(sub)
    db.flush()

    log = SyncLog(
        subscription_id=sub.id,
        status="success",
        dates_synced=5,
        items_fetched=25,
        duration_ms=1500,
    )
    db.add(log)
    db.flush()
    assert log.id is not None
