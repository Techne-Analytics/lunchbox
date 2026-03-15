import uuid
from datetime import date

from sqlalchemy.orm import Session

from lunchbox.models import MenuItem, Subscription, SyncLog, User


def create_user(db: Session, **overrides) -> User:
    defaults = {
        "google_id": f"google-{uuid.uuid4().hex[:8]}",
        "email": "test@example.com",
        "name": "Test User",
    }
    defaults.update(overrides)
    user = User(**defaults)
    db.add(user)
    db.flush()
    return user


def create_subscription(db: Session, user: User, **overrides) -> Subscription:
    defaults = {
        "user_id": user.id,
        "school_id": "test-school-001",
        "school_name": "Test Elementary",
        "grade": "05",
        "meal_configs": [
            {"meal_type": "Lunch", "serving_line": "Traditional", "sort_order": 0}
        ],
        "display_name": "Test Elementary - 5th Grade",
        "is_active": True,
    }
    defaults.update(overrides)
    sub = Subscription(**defaults)
    db.add(sub)
    db.flush()
    return sub


def create_menu_item(db: Session, subscription: Subscription, **overrides) -> MenuItem:
    defaults = {
        "subscription_id": subscription.id,
        "school_id": subscription.school_id,
        "menu_date": date(2026, 3, 16),
        "meal_type": "Lunch",
        "serving_line": "Traditional",
        "grade": subscription.grade,
        "category": "Entrees",
        "item_name": "Pizza",
    }
    defaults.update(overrides)
    item = MenuItem(**defaults)
    db.add(item)
    db.flush()
    return item


def create_sync_log(db: Session, subscription: Subscription, **overrides) -> SyncLog:
    defaults = {
        "subscription_id": subscription.id,
        "status": "success",
        "dates_synced": 5,
        "items_fetched": 25,
        "duration_ms": 1200,
    }
    defaults.update(overrides)
    log = SyncLog(**defaults)
    db.add(log)
    db.flush()
    return log
