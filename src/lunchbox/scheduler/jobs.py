import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from lunchbox.config import settings
from lunchbox.db import SessionLocal
from lunchbox.sync.engine import sync_all
from lunchbox.sync.menu_client import SchoolCafeClient

logger = logging.getLogger(__name__)

scheduler = BackgroundScheduler(timezone=settings.timezone)


def daily_sync_job():
    """Run sync for all active subscriptions."""
    logger.info("Starting daily sync")
    db = SessionLocal()
    with SchoolCafeClient() as client:
        try:
            sync_all(
                db,
                client,
                days=settings.days_to_fetch,
                skip_weekends=settings.skip_weekends,
            )
        except Exception:
            logger.exception("Daily sync failed")
        finally:
            db.close()


def start_scheduler():
    scheduler.add_job(
        daily_sync_job,
        CronTrigger(hour=settings.sync_hour, minute=settings.sync_minute),
        id="daily_sync",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started: sync at %02d:%02d %s",
        settings.sync_hour,
        settings.sync_minute,
        settings.timezone,
    )


def stop_scheduler():
    scheduler.shutdown(wait=False)
