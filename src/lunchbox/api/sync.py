import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import Subscription, SyncLog, User
from lunchbox.sync.engine import sync_subscription
from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/sync", tags=["sync"])


@router.post("/trigger/{subscription_id}")
def trigger_sync(
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

    with SchoolCafeClient() as client:
        log = sync_subscription(
            db,
            sub,
            client,
            days=settings.days_to_fetch,
            skip_weekends=settings.skip_weekends,
        )

    return {
        "status": log.status,
        "items_fetched": log.items_fetched,
        "duration_ms": log.duration_ms,
    }


@router.get("/history/{subscription_id}")
def sync_history(
    subscription_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    sub = (
        db.query(Subscription)
        .filter(Subscription.id == subscription_id, Subscription.user_id == user.id)
        .first()
    )
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")

    logs = (
        db.query(SyncLog)
        .filter(SyncLog.subscription_id == subscription_id)
        .order_by(SyncLog.started_at.desc())
        .limit(20)
        .all()
    )
    return [
        {
            "id": str(log.id),
            "status": log.status,
            "dates_synced": log.dates_synced,
            "items_fetched": log.items_fetched,
            "duration_ms": log.duration_ms,
            "trace_id": log.trace_id,
            "started_at": log.started_at.isoformat() if log.started_at else None,
        }
        for log in logs
    ]
