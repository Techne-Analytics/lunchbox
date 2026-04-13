import hmac
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from lunchbox.auth.dependencies import get_current_user
from lunchbox.config import settings
from lunchbox.db import get_db
from lunchbox.models import MenuItem, Subscription, SyncLog, User
from lunchbox.sync.engine import sync_all, sync_subscription
from lunchbox.sync.menu_client import SchoolCafeClient

router = APIRouter(prefix="/api/sync", tags=["sync"])

logger = logging.getLogger(__name__)


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

    # Guardrail: max menu items
    total_items = db.query(MenuItem).count()
    if total_items >= settings.max_menu_items:
        raise HTTPException(status_code=400, detail="Menu item limit reached")

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


@router.get("/cron")
def cron_sync(request: Request, db: Session = Depends(get_db)) -> dict:
    """Vercel Cron endpoint — syncs all active subscriptions."""
    # Validate cron secret
    if not settings.cron_secret:
        raise HTTPException(status_code=403, detail="CRON_SECRET not configured")

    cron_auth = request.headers.get("x-vercel-cron-auth", "")
    if not hmac.compare_digest(cron_auth, settings.cron_secret):
        raise HTTPException(status_code=403, detail="Invalid cron secret")

    # Guardrail: max syncs per day
    today = datetime.now(timezone.utc).date()
    today_start = datetime(today.year, today.month, today.day, tzinfo=timezone.utc)
    syncs_today = db.query(SyncLog).filter(SyncLog.started_at >= today_start).count()
    if syncs_today >= settings.max_syncs_per_day:
        logger.warning(
            "Sync skipped: %d syncs today (max %d)",
            syncs_today,
            settings.max_syncs_per_day,
        )
        return {"status": "skipped", "reason": "max_syncs_per_day reached"}

    # Guardrail: max menu items
    total_items = db.query(MenuItem).count()
    if total_items >= settings.max_menu_items:
        logger.warning(
            "Sync skipped: %d menu items (max %d)",
            total_items,
            settings.max_menu_items,
        )
        return {"status": "skipped", "reason": "max_menu_items reached"}

    # Run sync
    try:
        with SchoolCafeClient() as client:
            sync_all(
                db,
                client,
                days=settings.days_to_fetch,
                skip_weekends=settings.skip_weekends,
            )
    except Exception:
        logger.exception("Cron sync failed")
        raise HTTPException(status_code=500, detail="Sync failed")

    # Check if any syncs actually succeeded
    new_logs = db.query(SyncLog).filter(SyncLog.started_at >= today_start).all()
    failed = sum(1 for log in new_logs if log.status == "error")
    total = len(new_logs) - syncs_today  # only count logs from this run
    if total > 0 and failed == total:
        logger.error("All %d syncs failed in cron run", total)
        raise HTTPException(status_code=500, detail=f"All {total} syncs failed")

    return {"status": "ok", "synced": total - failed, "failed": failed}
