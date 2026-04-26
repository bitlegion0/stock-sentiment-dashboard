"""
scraper.py
----------
Scrapes financial news headlines from Moneycontrol and Economic Times.
Maps each headline to the relevant Nifty ticker(s) by keyword matching.
Stores results in the headlines table in SQLite.
"""

import requests
import sqlite3
import logging
import time
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

from fetcher import get_connection, TICKER_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_DELAY = 2  # seconds between requests — be polite to servers

# Map clean ticker names → keywords to match in headlines
# Add synonyms so we catch "Tata Consultancy" as well as "TCS"
TICKER_KEYWORDS = {
    "RELIANCE.NS":   ["reliance", "ril", "mukesh ambani", "jio"],
    "TCS.NS":        ["tcs", "tata consultancy"],
    "HDFCBANK.NS":   ["hdfc bank", "hdfcbank"],
    "INFY.NS":       ["infosys", "infy"],
    "ICICIBANK.NS":  ["icici bank", "icicibank"],
    "HINDUNILVR.NS": ["hindustan unilever", "hul"],
    "ITC.NS":        ["itc"],
    "SBIN.NS":       ["sbi", "state bank"],
    "BHARTIARTL.NS": ["bharti airtel", "airtel"],
    "KOTAKBANK.NS":  ["kotak bank", "kotak mahindra"],
    "AXISBANK.NS":   ["axis bank"],
    "LT.NS":         ["larsen", "l&t", "lt"],
    "ASIANPAINT.NS": ["asian paints"],
    "MARUTI.NS":     ["maruti", "suzuki"],
    "SUNPHARMA.NS":  ["sun pharma", "sun pharmaceutical"],
    "TITAN.NS":      ["titan"],
    "ULTRACEMCO.NS": ["ultratech cement", "ultratech"],
    "WIPRO.NS":      ["wipro"],
    "HCLTECH.NS":    ["hcl tech", "hcltech"],
    "BAJFINANCE.NS": ["bajaj finance"],
}

# ── Scraping ───────────────────────────────────────────────────────────────────

def scrape_moneycontrol() -> list[dict]:
    """
    Scrape market news headlines from Moneycontrol.
    Returns a list of {headline, source} dicts.
    """
    headlines = []
    urls = [
        "https://www.moneycontrol.com/news/business/markets/",
        "https://www.moneycontrol.com/news/business/stocks/",
    ]

    for url in urls:
        try:
            logger.info("Scraping %s", url)
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # Moneycontrol uses <li class="clearfix"> for news items
            # and <h2> or <p class="news-title"> for the headline text
            for tag in soup.select("li.clearfix h2, li.clearfix p.news-title, .news_list li h2"):
                text = tag.get_text(strip=True)
                if len(text) > 20:  # ignore tiny/empty snippets
                    headlines.append({"headline": text, "source": "moneycontrol"})

            time.sleep(REQUEST_DELAY)

        except requests.RequestException as e:
            logger.warning("Failed to scrape %s: %s", url, e)

    logger.info("Scraped %d headlines from Moneycontrol", len(headlines))
    return headlines


def scrape_economic_times() -> list[dict]:
    """
    Scrape market news headlines from Economic Times markets section.
    Returns a list of {headline, source} dicts.
    """
    headlines = []
    urls = [
        "https://economictimes.indiatimes.com/markets/stocks/news",
    ]

    for url in urls:
        try:
            logger.info("Scraping %s", url)
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # ET uses <a class="eachStory"> containers
            for item in soup.select(".eachStory h3, .story-box h3, .topStory h2"):
                text = item.get_text(strip=True)
                if len(text) > 20:
                    headlines.append({"headline": text, "source": "economic_times"})

            time.sleep(REQUEST_DELAY)

        except requests.RequestException as e:
            logger.warning("Failed to scrape %s: %s", url, e)

    logger.info("Scraped %d headlines from Economic Times", len(headlines))
    return headlines


# ── Ticker mapping ─────────────────────────────────────────────────────────────

def map_headlines_to_tickers(raw_headlines: list[dict]) -> list[dict]:
    """
    For each headline, check if it mentions a stock by keyword.
    Returns enriched list with 'ticker' field.
    Headlines that match no ticker get ticker=None (market-wide news).
    """
    enriched = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in raw_headlines:
        text_lower = item["headline"].lower()
        matched_tickers = []

        for ticker, keywords in TICKER_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                matched_tickers.append(ticker)

        if matched_tickers:
            # If headline matches multiple tickers, create one row per ticker
            for ticker in matched_tickers:
                enriched.append({
                    "ticker":     ticker,
                    "headline":   item["headline"],
                    "source":     item["source"],
                    "fetched_at": now,
                })
        else:
            # Market-wide news — still useful for overall market sentiment
            enriched.append({
                "ticker":     None,
                "headline":   item["headline"],
                "source":     item["source"],
                "fetched_at": now,
            })

    ticker_matched = sum(1 for h in enriched if h["ticker"])
    logger.info(
        "Mapped %d headlines → %d ticker-specific, %d market-wide",
        len(raw_headlines),
        ticker_matched,
        len(enriched) - ticker_matched,
    )
    return enriched


# ── Saving ─────────────────────────────────────────────────────────────────────

def save_headlines(headlines: list[dict]):
    """Insert headlines into DB. Always inserts (no dedup — fresh news each run)."""
    if not headlines:
        logger.warning("No headlines to save.")
        return

    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO headlines (ticker, headline, source, fetched_at)
               VALUES (:ticker, :headline, :source, :fetched_at)""",
            headlines,
        )
    logger.info("Saved %d headlines to DB", len(headlines))


def load_headlines(ticker: str = None, limit: int = 50) -> list[dict]:
    """Load recent headlines from DB, optionally filtered by ticker."""
    with get_connection() as conn:
        if ticker:
            rows = conn.execute(
                """SELECT * FROM headlines
                   WHERE ticker=?
                   ORDER BY fetched_at DESC LIMIT ?""",
                (ticker, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT * FROM headlines
                   ORDER BY fetched_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
    return [dict(r) for r in rows]


# ── Entry point ────────────────────────────────────────────────────────────────

def run():
    mc_headlines = scrape_moneycontrol()
    et_headlines = scrape_economic_times()
    all_headlines = mc_headlines + et_headlines

    if not all_headlines:
        logger.warning("No headlines scraped — check if site structure has changed.")
        return

    enriched = map_headlines_to_tickers(all_headlines)
    save_headlines(enriched)
    logger.info("Headline scrape complete. Total saved: %d", len(enriched))


if __name__ == "__main__":
    run()
