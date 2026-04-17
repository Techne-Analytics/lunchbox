import uuid
from datetime import date, datetime, timezone
from types import SimpleNamespace

from lunchbox.api.feeds import _build_calendar


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
    return SimpleNamespace(**defaults)


def _make_item(sub_id, menu_date, meal_type, category, item_name):
    return SimpleNamespace(
        subscription_id=sub_id,
        menu_date=menu_date,
        meal_type=meal_type,
        category=category,
        item_name=item_name,
        fetched_at=datetime.now(timezone.utc),
    )


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

    def test_excluded_items_substring_match(self):
        sub = _make_subscription(excluded_items=["Yogurt"])
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Strawberry Yogurt"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Yogurt Cup"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Pizza" in ical
        assert "Yogurt" not in ical

    def test_summary_entrees_only(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Apple"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Milk", "1% Milk"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        assert "Lunch: Pizza" in ical
        # Non-entrees should be in description, not title
        assert "Lunch: Pizza, Apple" not in ical
        assert "Apple" in ical  # still in description

    def test_summary_fallback_when_no_entrees(self):
        sub = _make_subscription()
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Fruits", "Apple"),
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Grains", "Roll"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()

        # iCal escapes commas as \,
        assert "Lunch: Apple\\, Roll" in ical

    def test_alarm_when_alert_minutes_set(self):
        sub = _make_subscription(alert_minutes=15)
        items = [
            _make_item(sub.id, date(2026, 3, 16), "Lunch", "Entrees", "Pizza"),
        ]
        cal = _build_calendar(sub, items)
        ical = cal.to_ical().decode()
        assert "VALARM" in ical
        assert "TRIGGER" in ical
