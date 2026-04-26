"""
sentiment.py
------------
Runs VADER sentiment analysis on scraped headlines.
Computes a daily sentiment score per ticker and an overall market mood.

Score ranges:
  compound > 0.05  → Positive
  compound < -0.05 → Negative
  in between       → Neutral

Returns scores between -1.0 (most negative) and +1.0 (most positive).
"""

import sys
import sqlite3
import logging
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Make data/ importable
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
from fetcher import get_connection, NIFTY_20

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ── Analyser (initialise once — expensive to recreate) ────────────────────────

_analyser = SentimentIntensityAnalyzer()


# ── Core scoring ───────────────────────────────────────────────────────────────

def score_headline(text: str) -> dict:
    """
    Score a single headline.
    Returns VADER scores: neg, neu, pos, compound
    """
    return _analyser.polarity_scores(text)


def label_score(compound: float) -> str:
    """Convert compound score to human-readable label."""
    if compound >= 0.05:
        return "Positive"
    elif compound <= -0.05:
        return "Negative"
    else:
        return "Neutral"


# ── Ticker-level sentiment ─────────────────────────────────────────────────────

def compute_ticker_sentiment(days: int = 3) -> pd.DataFrame:
    """
    For each ticker, compute the average compound sentiment score
    from headlines scraped in the last N days.

    Returns DataFrame with columns:
        ticker, avg_sentiment, headline_count, label
    """
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    with get_connection() as conn:
        df = pd.read_sql_query(
            """SELECT ticker, headline, fetched_at
               FROM headlines
               WHERE ticker IS NOT NULL
               AND fetched_at >= ?
               ORDER BY fetched_at DESC""",
            conn, params=(cutoff,)
        )

    if df.empty:
        logger.warning("No headlines found in last %d days — using all available", days)
        with get_connection() as conn:
            df = pd.read_sql_query(
                """SELECT ticker, headline, fetched_at
                   FROM headlines
                   WHERE ticker IS NOT NULL
                   ORDER BY fetched_at DESC""",
                conn
            )

    if df.empty:
        logger.warning("No headlines at all — returning neutral scores for all tickers")
        return pd.DataFrame([{
            "ticker": t,
            "avg_sentiment": 0.0,
            "headline_count": 0,
            "label": "Neutral"
        } for t in NIFTY_20])

    # Score every headline
    df["compound"] = df["headline"].apply(
        lambda h: score_headline(h)["compound"]
    )

    # Aggregate per ticker
    result = (
        df.groupby("ticker")
        .agg(
            avg_sentiment=("compound", "mean"),
            headline_count=("compound", "count"),
        )
        .reset_index()
    )

    result["avg_sentiment"] = result["avg_sentiment"].round(4)
    result["label"] = result["avg_sentiment"].apply(label_score)

    # Add tickers that had zero headlines (neutral by default)
    present = set(result["ticker"])
    missing = [t for t in NIFTY_20 if t not in present]
    if missing:
        neutral_rows = pd.DataFrame([{
            "ticker": t,
            "avg_sentiment": 0.0,
            "headline_count": 0,
            "label": "Neutral"
        } for t in missing])
        result = pd.concat([result, neutral_rows], ignore_index=True)

    logger.info(
        "Sentiment computed for %d tickers | Positive: %d | Neutral: %d | Negative: %d",
        len(result),
        (result["label"] == "Positive").sum(),
        (result["label"] == "Neutral").sum(),
        (result["label"] == "Negative").sum(),
    )

    return result.sort_values("ticker").reset_index(drop=True)


def compute_market_mood(sentiment_df: pd.DataFrame) -> dict:
    """
    Compute overall market mood from ticker sentiments.
    Returns dict with mood label and score.
    """
    if sentiment_df.empty:
        return {"mood": "Neutral", "score": 0.0, "bullish_pct": 50.0}

    avg   = sentiment_df["avg_sentiment"].mean()
    bulls = (sentiment_df["label"] == "Positive").sum()
    total = len(sentiment_df)

    return {
        "mood":        label_score(avg),
        "score":       round(float(avg), 4),
        "bullish_pct": round(bulls / total * 100, 1),
    }


def get_ticker_headlines(ticker: str, limit: int = 10) -> list[dict]:
    """Return recent scored headlines for a specific ticker."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT headline, source, fetched_at
               FROM headlines
               WHERE ticker = ?
               ORDER BY fetched_at DESC
               LIMIT ?""",
            (ticker, limit)
        ).fetchall()

    results = []
    for r in rows:
        scores = score_headline(r["headline"])
        results.append({
            "headline":   r["headline"],
            "source":     r["source"],
            "fetched_at": r["fetched_at"],
            "compound":   scores["compound"],
            "label":      label_score(scores["compound"]),
        })
    return results


# ── Entry point ────────────────────────────────────────────────────────────────

def run() -> pd.DataFrame:
    logger.info("Computing sentiment scores…")
    df = compute_ticker_sentiment()
    mood = compute_market_mood(df)
    logger.info("Market mood: %s (score=%.4f, bullish=%.1f%%)",
                mood["mood"], mood["score"], mood["bullish_pct"])
    return df


if __name__ == "__main__":
    df = run()
    print("\nSentiment scores:")
    print(df.to_string(index=False))
