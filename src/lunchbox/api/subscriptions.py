import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.db import get_db
from lunchbox.models import Subscription, User

router = APIRouter(prefix="/api/subscriptions", tags=["subscriptions"])


class MealConfig(BaseModel):
    meal_type: str
    serving_line: str
    sort_order: int


class SubscriptionCreate(BaseModel):
    school_id: str
    school_name: str
    grade: str
    meal_configs: list[MealConfig]
    display_name: str
    included_categories: list[str] | None = None
    excluded_items: list[str] | None = None
    alert_minutes: int | None = None
    show_as_busy: bool = False
    event_type: str = "all_day"


class SubscriptionUpdate(BaseModel):
    display_name: str | None = None
    grade: str | None = None
    meal_configs: list[MealConfig] | None = None
    included_categories: list[str] | None = None
    excluded_items: list[str] | None = None
    alert_minutes: int | None = None
    show_as_busy: bool | None = None
    event_type: str | None = None
    is_active: bool | None = None


@router.get("")
def list_subscriptions(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    subs = db.query(Subscription).filter(Subscription.user_id == user.id).all()
    return [
        {
            "id": str(s.id),
            "display_name": s.display_name,
            "school_name": s.school_name,
            "feed_url": f"/cal/{s.feed_token}.ics",
            "is_active": s.is_active,
        }
        for s in subs
    ]


@router.post("", status_code=201)
def create_subscription(
    data: SubscriptionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sub = Subscription(
        user_id=user.id,
        school_id=data.school_id,
        school_name=data.school_name,
        grade=data.grade,
        meal_configs=[mc.model_dump() for mc in data.meal_configs],
        display_name=data.display_name,
        included_categories=data.included_categories,
        excluded_items=data.excluded_items,
        alert_minutes=data.alert_minutes,
        show_as_busy=data.show_as_busy,
        event_type=data.event_type,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return {"id": str(sub.id), "feed_url": f"/cal/{sub.feed_token}.ics"}


@router.get("/{subscription_id}")
def get_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {
        "id": str(sub.id),
        "display_name": sub.display_name,
        "school_name": sub.school_name,
        "school_id": sub.school_id,
        "grade": sub.grade,
        "meal_configs": sub.meal_configs,
        "included_categories": sub.included_categories,
        "excluded_items": sub.excluded_items,
        "alert_minutes": sub.alert_minutes,
        "show_as_busy": sub.show_as_busy,
        "event_type": sub.event_type,
        "feed_url": f"/cal/{sub.feed_token}.ics",
        "is_active": sub.is_active,
    }


@router.patch("/{subscription_id}")
def update_subscription(
    subscription_id: uuid.UUID,
    data: SubscriptionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "meal_configs" and value is not None:
            value = [mc if isinstance(mc, dict) else mc.model_dump() for mc in value]
        setattr(sub, field, value)

    db.commit()
    return {"status": "updated"}


@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    db.delete(sub)
    db.commit()


@router.post("/{subscription_id}/regenerate-token")
def regenerate_feed_token(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    sub.feed_token = uuid.uuid4()
    db.commit()
    return {"feed_url": f"/cal/{sub.feed_token}.ics"}
