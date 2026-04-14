import logging
import time
from collections import defaultdict
from datetime import date, timedelta

import httpx
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
    if not subscription.meal_configs:
        logger.warning(
            "Subscription %s has no meal configs, skipping",
            subscription.display_name,
        )
        log = SyncLog(
            subscription_id=subscription.id,
            status="skipped",
            dates_synced=0,
            items_fetched=0,
            error_message="No meal configs configured",
            duration_ms=0,
        )
        db.add(log)
        db.commit()
        return log

    started_at = time.time()
    dates = get_sync_dates(days, skip_weekends)
    total_items = 0
    errors = []

    # Group dates by ISO week so we make one bulk call per (week, meal_config)
    weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
    for d in dates:
        iso_year, iso_week, _ = d.isocalendar()
        weeks[(iso_year, iso_week)].append(d)

    # Fetch weekly data once per (week, meal_config)
    fetched: dict[tuple[str, str, int, int], dict[date, list]] = {}
    for (iso_year, iso_week), week_dates in weeks.items():
        # Anchor on the ISO Monday of the week — safer than passing an arbitrary
        # mid-week date in case SchoolCafe interprets week_date as the start.
        monday = week_dates[0] - timedelta(days=week_dates[0].weekday())
        for meal_config in subscription.meal_configs:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]
            try:
                week_data = client.get_weekly_menu(
                    school_id=subscription.school_id,
                    week_date=monday,
                    meal_type=meal_type,
                    serving_line=serving_line,
                    grade=subscription.grade,
                )
                fetched[(meal_type, serving_line, iso_year, iso_week)] = week_data
            except (httpx.HTTPError, ValueError) as e:
                logger.error(
                    "Weekly fetch failed for %s week %d-%d (%s): %s",
                    meal_type,
                    iso_year,
                    iso_week,
                    subscription.display_name,
                    e,
                )
                # One error per missed (date, meal_type) so status accounting stays consistent
                for d in week_dates:
                    errors.append(f"{meal_type} {d}: weekly fetch failed: {e}")

    # Per-date upsert from the cached weekly data
    for sync_date in dates:
        for meal_config in subscription.meal_configs:
            meal_type = meal_config["meal_type"]
            serving_line = meal_config["serving_line"]
            iso_year, iso_week, _ = sync_date.isocalendar()
            week_data = fetched.get((meal_type, serving_line, iso_year, iso_week))

            # Skip dates that had a fetch failure (already recorded in errors)
            if week_data is None:
                continue

            # If the weekly response doesn't include this date (weekend, holiday,
            # or unexpected truncation), preserve existing data rather than
            # silently wiping it. Cache-invalidation-by-delete only fires when
            # SchoolCafe explicitly returns an empty list for the date.
            if sync_date not in week_data:
                continue

            items = week_data[sync_date]

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
            except Exception as e:
                nested.rollback()
                logger.error(
                    "DB upsert failed for %s %s (%s): %s",
                    meal_type,
                    sync_date,
                    subscription.display_name,
                    e,
                )
                errors.append(f"{meal_type} {sync_date}: db error: {e}")
                continue

            total_items += len(items)

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
