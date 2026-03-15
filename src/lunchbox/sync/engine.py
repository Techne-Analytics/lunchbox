import logging
import time
from datetime import date, timedelta

from sqlalchemy.orm import Session

from lunchbox.models import MenuItem, Subscription, SyncLog
from lunchbox.sync.menu_client import SchoolCafeClient

logger = logging.getLogger(__name__)


def get_sync_dates(
    days: int, skip_weekends: bool, start: date | None = None
) -> list[date]:
    """Generate list of dates to sync, optionally skipping weekends."""
    start = start or date.today()
    dates = []
    current = start
    while len(dates) < days:
        if not skip_weekends or current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def sync_subscription(
    db: Session,
    subscription: Subscription,
    client: SchoolCafeClient,
    days: int = 7,
    skip_weekends: bool = True,
) -> SyncLog:
    """Sync menu data for a single subscription."""
    started_at = time.time()
    dates = get_sync_dates(days, skip_weekends)
    total_items = 0
    errors = []

    for sync_date in dates:
        for meal_config in subscription.meal_configs or []:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]

            try:
                items = client.get_daily_menu(
                    school_id=subscription.school_id,
                    menu_date=sync_date,
                    meal_type=meal_type,
                    serving_line=serving_line,
                    grade=subscription.grade,
                )

                # Savepoint so DB errors don't corrupt the session
                nested = db.begin_nested()
                try:
                    db.query(MenuItem).filter(
                        MenuItem.subscription_id == subscription.id,
                        MenuItem.menu_date == sync_date,
                        MenuItem.meal_type == meal_type,
                    ).delete()

                    for item in items:
                        db.add(
                            MenuItem(
                                subscription_id=subscription.id,
                                school_id=subscription.school_id,
                                menu_date=sync_date,
                                meal_type=meal_type,
                                serving_line=serving_line,
                                grade=subscription.grade,
                                category=item.category,
                                item_name=item.item_name,
                            )
                        )
                    nested.commit()
                except Exception:
                    nested.rollback()
                    raise

                total_items += len(items)

            except Exception as e:
                logger.error(
                    "Failed to sync %s %s for %s: %s",
                    meal_type,
                    sync_date,
                    subscription.display_name,
                    e,
                )
                errors.append(f"{meal_type} {sync_date}: {e}")

    duration_ms = int((time.time() - started_at) * 1000)

    total_expected = len(dates) * len(subscription.meal_configs)
    if errors:
        status = "error" if len(errors) == total_expected else "partial"
    else:
        status = "success"

    log = SyncLog(
        subscription_id=subscription.id,
        status=status,
        dates_synced=len(dates),
        items_fetched=total_items,
        error_message="; ".join(errors) if errors else None,
        duration_ms=duration_ms,
    )
    db.add(log)
    db.commit()

    return log


def sync_all(
    db: Session,
    client: SchoolCafeClient,
    days: int = 7,
    skip_weekends: bool = True,
):
    """Sync all active subscriptions."""
    subscriptions = (
        db.query(Subscription).filter(Subscription.is_active.is_(True)).all()
    )

    for sub in subscriptions:
        logger.info("Syncing %s", sub.display_name)
        try:
            log = sync_subscription(db, sub, client, days, skip_weekends)
            logger.info(
                "Sync complete: %s — %s, %d items",
                sub.display_name,
                log.status,
                log.items_fetched,
            )
        except Exception:
            logger.exception("Sync failed for %s", sub.display_name)
