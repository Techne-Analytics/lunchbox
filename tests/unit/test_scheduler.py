from unittest.mock import MagicMock, patch

import pytest

import lunchbox.scheduler.jobs as jobs_module
from lunchbox.scheduler.jobs import daily_sync_job, start_scheduler, stop_scheduler


@pytest.fixture(autouse=True)
def reset_scheduler():
    """Ensure _scheduler is None before and after each test."""
    jobs_module._scheduler = None
    yield
    if jobs_module._scheduler and jobs_module._scheduler.running:
        jobs_module._scheduler.shutdown(wait=False)
    jobs_module._scheduler = None


class TestScheduler:
    def test_start_creates_running_scheduler(self):
        with patch("lunchbox.scheduler.jobs.settings") as mock_settings:
            mock_settings.timezone = "US/Central"
            mock_settings.sync_hour = 6
            mock_settings.sync_minute = 30

            start_scheduler()

            assert jobs_module._scheduler is not None
            assert jobs_module._scheduler.running

            stop_scheduler()

    def test_stop_clears_scheduler(self):
        with patch("lunchbox.scheduler.jobs.settings") as mock_settings:
            mock_settings.timezone = "US/Central"
            mock_settings.sync_hour = 6
            mock_settings.sync_minute = 30

            start_scheduler()
            stop_scheduler()

            assert jobs_module._scheduler is None

    def test_stop_when_not_started(self):
        """stop_scheduler when nothing is running -- no-op."""
        stop_scheduler()  # should not raise

    def test_daily_sync_job_handles_exception(self):
        """sync_all raising does not kill the scheduler, and error is logged."""
        with patch("lunchbox.scheduler.jobs.sync_all", side_effect=Exception("boom")):
            with patch("lunchbox.scheduler.jobs.SessionLocal") as MockSession:
                with patch("lunchbox.scheduler.jobs.logger") as mock_logger:
                    mock_db = MagicMock()
                    MockSession.return_value = mock_db

                    daily_sync_job()

                    mock_db.close.assert_called_once()
                    mock_logger.exception.assert_called_once()

    def test_job_uses_configured_time(self):
        with patch("lunchbox.scheduler.jobs.settings") as mock_settings:
            mock_settings.timezone = "US/Central"
            mock_settings.sync_hour = 14
            mock_settings.sync_minute = 45

            start_scheduler()

            job = jobs_module._scheduler.get_job("daily_sync")
            assert job is not None
            trigger = job.trigger
            assert str(trigger.fields[5]) == "14"  # hour
            assert str(trigger.fields[6]) == "45"  # minute

            stop_scheduler()
