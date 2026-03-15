import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Response
from icalendar import Alarm, Calendar, Event
from sqlalchemy.orm import Session

from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription

router = APIRouter(tags=["feeds"])


def _build_calendar(subscription: Subscription, items: list[MenuItem]) -> Calendar:
    cal = Calendar()
    cal.add("prodid", "-//Lunchbox//Menu Feed//EN")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", subscription.display_name)
    cal.add("method", "PUBLISH")

    # Group items by (date, meal_type)
    grouped: dict[tuple, list[MenuItem]] = {}
    for item in items:
        key = (item.menu_date, item.meal_type)
        grouped.setdefault(key, []).append(item)

    # Sort by date, then meal_type alphabetically (Breakfast < Lunch)
    for (menu_date, meal_type), day_items in sorted(grouped.items()):
        # Apply category filter
        if subscription.included_categories:
            day_items = [
                i for i in day_items if i.category in subscription.included_categories
            ]

        # Apply item exclusion filter
        if subscription.excluded_items:
            excluded_lower = {e.lower() for e in subscription.excluded_items}
            day_items = [
                i for i in day_items if i.item_name.lower() not in excluded_lower
            ]

        if not day_items:
            continue

        # Build summary: "Lunch: Pizza, Burger, Apple"
        item_names = [i.item_name for i in day_items]
        summary = f"{meal_type}: {', '.join(item_names)}"
        if len(summary) > 100:
            summary = summary[:97] + "..."

        # Build description with categories
        categories: dict[str, list[str]] = {}
        for item in day_items:
            categories.setdefault(item.category, []).append(item.item_name)

        description_parts = []
        for cat, names in categories.items():
            description_parts.append(f"**{cat}:**")
            for name in names:
                description_parts.append(f"- {name}")
            description_parts.append("")

        event = Event()
        event.add("summary", summary)
        event.add("description", "\n".join(description_parts))
        event.add("dtstart", menu_date)
        # All-day events: DTEND is exclusive, so next day
        event.add("dtend", menu_date + timedelta(days=1))
        event.add(
            "uid",
            f"{subscription.feed_token}-{menu_date.isoformat()}-{meal_type}@lunchbox",
        )
        event.add("dtstamp", datetime.now(timezone.utc))
        event.add("transp", "OPAQUE" if subscription.show_as_busy else "TRANSPARENT")

        if subscription.alert_minutes:
            alarm = Alarm()
            alarm.add("action", "DISPLAY")
            alarm.add("description", summary)
            alarm.add("trigger", timedelta(minutes=-subscription.alert_minutes))
            event.add_component(alarm)

        cal.add_component(event)

    return cal


@router.get("/cal/{feed_token}.ics")
def get_feed(feed_token: str, db: Session = Depends(get_db)):
    try:
        token_uuid = uuid.UUID(feed_token)
    except ValueError:
        raise HTTPException(status_code=404, detail="Feed not found")

    subscription = (
        db.query(Subscription)
        .filter(
            Subscription.feed_token == token_uuid,
            Subscription.is_active.is_(True),
        )
        .first()
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Feed not found")

    items = (
        db.query(MenuItem)
        .filter(MenuItem.subscription_id == subscription.id)
        .order_by(MenuItem.menu_date, MenuItem.meal_type)
        .all()
    )

    cal = _build_calendar(subscription, items)
    content = cal.to_ical()

    # Caching headers
    etag = hashlib.md5(content).hexdigest()  # noqa: S324
    last_modified = max(
        (i.fetched_at for i in items), default=datetime.now(timezone.utc)
    )

    return Response(
        content=content,
        media_type="text/calendar; charset=utf-8",
        headers={
            "ETag": f'"{etag}"',
            "Last-Modified": last_modified.strftime("%a, %d %b %Y %H:%M:%S GMT"),
            "Cache-Control": "max-age=3600",
        },
    )
