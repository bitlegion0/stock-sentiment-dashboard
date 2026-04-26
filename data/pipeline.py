"""
pipeline.py
-----------
Master pipeline runner.
Runs fetcher → scraper in sequence.
Called directly for a manual run, or by scheduler.py for daily automation.
"""

import logging
import sys
from pathlib import Path

# Make sure sibling modules are importable
sys.path.insert(0, str(Path(__file__).parent))

from fetcher import run as run_fetcher, init_db
from scraper import run as run_scraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent.parent / "pipeline.log"),
    ],
)
logger = logging.getLogger(__name__)


def run_pipeline():
    logger.info("=" * 50)
    logger.info("Pipeline started")

    try:
        logger.info("Step 1/2 — Fetching stock prices…")
        run_fetcher()
    except Exception as e:
        logger.error("Price fetch failed: %s", e, exc_info=True)

    try:
        logger.info("Step 2/2 — Scraping news headlines…")
        run_scraper()
    except Exception as e:
        logger.error("Headline scrape failed: %s", e, exc_info=True)

    logger.info("Pipeline complete")
    logger.info("=" * 50)


if __name__ == "__main__":
    init_db()
    run_pipeline()
