import uuid
from datetime import date, datetime, timezone

from lunchbox.api.feeds import _build_calendar
from lunchbox.models import MenuItem, Subscription


def _make_subscription(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        feed_token=uuid.uuid4(),
        display_name="Test School",
        included_categories=None,
        excluded_items=None,
        alert_minutes=None,
        show_as_busy=False,
    )
    defaults.update(overrides)
    sub = Subscription.__new__(Subscription)
    for k, v in defaults.items():
        setattr(sub, k, v)
    return sub


def _make_item(sub_id, menu_date, meal_type, category, item_name):
    item = MenuItem.__new__(MenuItem)
    item.subscription_id = sub_id
    item.menu_date = menu_date
    item.meal_type = meal_type
    item.category = category
    item.item_name = item_name
    item.fetched_at = datetime.now(timezone.utc)
    return item


class TestBuildCalendar:
    def test_basic_feed(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Apple"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "VCALENDAR" in ical
        assert "VEVENT" in ical
        assert "Pizza" in ical
        assert "Apple" in ical
        assert "TRANSPARENT" in ical

    def test_category_filter(self):
        sub = _make_subscription(included_categories=["Entrees"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Milk", "1% Milk"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Pizza" in ical
        assert "Milk" not in ical

    def test_excluded_items(self):
        sub = _make_subscription(excluded_items=["PB&J Sandwich"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "PB&J Sandwich"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Pizza" in ical
        assert "PB&J" not in ical

    def test_multiple_meals_sorted(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Breakfast", "Entrees", "Eggs"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Lunch: Pizza" in ical
        assert "Breakfast: Eggs" in ical

    def test_busy_flag(self):
        sub = _make_subscription(show_as_busy=True)
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()
        assert "OPAQUE" in ical

    def test_excluded_items_case_insensitive(self):
        sub = _make_subscription(excluded_items=["pb&j sandwich"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "PB&J Sandwich"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "PB&J" not in ical
        assert "Pizza" in ical

    def test_alarm_when_alert_minutes_set(self):
        sub = _make_subscription(alert_minutes=15)
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()
        assert "VALARM" in ical
        assert "TRIGGER" in ical
