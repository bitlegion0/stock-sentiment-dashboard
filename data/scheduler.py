"""
scheduler.py
------------
Runs the data pipeline automatically every day at 6:30 AM IST.
Start with: python data/scheduler.py
Keep this running on Railway — it will auto-refresh data daily.
"""

import sys
import logging
from pathlib import Path
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

sys.path.insert(0, str(Path(__file__).parent))
from pipeline import run_pipeline
from fetcher import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "scheduler.log"),
    ],
)
logger = logging.getLogger(__name__)

IST = pytz.timezone("Asia/Kolkata")


def job():
    logger.info("Scheduled pipeline run starting…")
    try:
        run_pipeline()
        logger.info("Scheduled pipeline run complete.")
    except Exception as e:
        logger.error("Scheduled run failed: %s", e, exc_info=True)


if __name__ == "__main__":
    logger.info("Initialising DB…")
    init_db()

    logger.info("Running pipeline once on startup…")
    job()

    scheduler = BlockingScheduler(timezone=IST)

    # Run every day at 6:30 AM IST (after NSE pre-open)
    scheduler.add_job(
        job,
        CronTrigger(hour=6, minute=30, timezone=IST),
        id="daily_pipeline",
        name="Daily NSE data + sentiment pipeline",
        replace_existing=True,
    )

    # Also run at 3:45 PM IST (after NSE market close)
    scheduler.add_job(
        job,
        CronTrigger(hour=15, minute=45, timezone=IST),
        id="market_close_pipeline",
        name="Post-market pipeline",
        replace_existing=True,
    )

    logger.info("Scheduler started. Jobs: 6:30 AM IST + 3:45 PM IST daily.")
    logger.info("Press Ctrl+C to stop.")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")
