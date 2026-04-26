"""
signals.py
----------
Combines technical indicators (RSI, SMA) with sentiment scores
to generate a BUY / HOLD / SELL signal for each ticker.

Signal logic (transparent and interview-explainable):
──────────────────────────────────────────────────────
Score each ticker out of 3 points:

  Technical:
    +1 if RSI < 50       (not overbought, room to grow)
    +1 if close > SMA20  (price above trend line = uptrend)

  Sentiment:
    +1 if avg_sentiment > 0.05  (positive news)
    -1 if avg_sentiment < -0.05 (negative news)

Final signal:
    score >= 2  → BUY
    score <= -1 → SELL
    otherwise   → HOLD
"""

import sys
import logging
import sqlite3
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "data"))
from fetcher import get_connection, load_prices, NIFTY_20, TICKER_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ── Technical indicators ───────────────────────────────────────────────────────

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Compute RSI(14) for a price series.
    RSI > 70 = overbought (potential sell)
    RSI < 30 = oversold   (potential buy)
    """
    delta  = series.diff()
    gain   = delta.clip(lower=0)
    loss   = -delta.clip(upper=0)

    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi.round(2)


def compute_sma(series: pd.Series, window: int = 20) -> pd.Series:
    """20-day Simple Moving Average."""
    return series.rolling(window=window, min_periods=1).mean().round(2)


def compute_technicals(ticker: str, days: int = 90) -> dict | None:
    """
    Compute latest RSI and SMA20 for a ticker.
    Returns dict with: ticker, close, rsi, sma_20, above_sma
    Returns None if not enough data.
    """
    df = load_prices(ticker=ticker, days=days)

    if df.empty or len(df) < 5:
        logger.warning("%s — not enough price data (%d rows)", ticker, len(df))
        return None

    df = df.sort_values("date").reset_index(drop=True)
    close_series = df["close"]

    rsi    = compute_rsi(close_series)
    sma_20 = compute_sma(close_series, window=20)

    latest_close  = float(close_series.iloc[-1])
    latest_rsi    = float(rsi.iloc[-1])
    latest_sma    = float(sma_20.iloc[-1])
    latest_date   = df["date"].iloc[-1]

    return {
        "ticker":    ticker,
        "date":      latest_date,
        "close":     round(latest_close, 2),
        "rsi":       round(latest_rsi, 2),
        "sma_20":    round(latest_sma, 2),
        "above_sma": latest_close > latest_sma,
        "rsi_zone":  "Overbought" if latest_rsi > 70 else
                     "Oversold"   if latest_rsi < 30 else "Neutral",
        # Full series for charting
        "close_series": close_series.tolist(),
        "rsi_series":   rsi.tolist(),
        "sma_series":   sma_20.tolist(),
        "dates":        df["date"].tolist(),
    }


# ── Signal generation ──────────────────────────────────────────────────────────

def generate_signal(technicals: dict, sentiment_score: float) -> dict:
    """
    Combine technical + sentiment into a single signal.
    Transparent scoring so you can explain it in interviews.
    """
    score    = 0
    reasons  = []

    # Technical scoring
    rsi = technicals["rsi"]
    if rsi < 50:
        score += 1
        reasons.append(f"RSI {rsi} (below 50 — not overbought)")
    else:
        reasons.append(f"RSI {rsi} (above 50 — momentum weakening)")

    if technicals["above_sma"]:
        score += 1
        reasons.append(f"Price ₹{technicals['close']} above SMA20 ₹{technicals['sma_20']} (uptrend)")
    else:
        reasons.append(f"Price ₹{technicals['close']} below SMA20 ₹{technicals['sma_20']} (downtrend)")

    # Sentiment scoring
    if sentiment_score > 0.05:
        score += 1
        reasons.append(f"Positive news sentiment ({sentiment_score:+.3f})")
    elif sentiment_score < -0.05:
        score -= 1
        reasons.append(f"Negative news sentiment ({sentiment_score:+.3f})")
    else:
        reasons.append(f"Neutral news sentiment ({sentiment_score:+.3f})")

    # Final signal
    if score >= 2:
        signal = "BUY"
    elif score <= -1:
        signal = "SELL"
    else:
        signal = "HOLD"

    return {
        "ticker":          technicals["ticker"],
        "name":            TICKER_NAMES.get(technicals["ticker"], technicals["ticker"]),
        "date":            technicals["date"],
        "close":           technicals["close"],
        "rsi":             technicals["rsi"],
        "rsi_zone":        technicals["rsi_zone"],
        "sma_20":          technicals["sma_20"],
        "above_sma":       technicals["above_sma"],
        "sentiment_score": round(sentiment_score, 4),
        "score":           score,
        "signal":          signal,
        "reasons":         reasons,
    }


# ── Main pipeline ──────────────────────────────────────────────────────────────

def compute_all_signals(sentiment_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute signals for all 20 tickers.
    sentiment_df must have columns: ticker, avg_sentiment
    Returns DataFrame with full signal details.
    """
    # Build sentiment lookup dict
    sentiment_map = dict(
        zip(sentiment_df["ticker"], sentiment_df["avg_sentiment"])
    )

    signals = []
    for ticker in NIFTY_20:
        tech = compute_technicals(ticker)
        if tech is None:
            logger.warning("Skipping %s — no technical data", ticker)
            continue

        sentiment_score = sentiment_map.get(ticker, 0.0)
        signal = generate_signal(tech, sentiment_score)
        signals.append(signal)

    df = pd.DataFrame(signals)

    if df.empty:
        logger.error("No signals generated!")
        return df

    # Sort: BUY first, then HOLD, then SELL
    order = {"BUY": 0, "HOLD": 1, "SELL": 2}
    df["_order"] = df["signal"].map(order)
    df = df.sort_values(["_order", "sentiment_score"], ascending=[True, False])
    df = df.drop(columns=["_order"]).reset_index(drop=True)

    buys  = (df["signal"] == "BUY").sum()
    holds = (df["signal"] == "HOLD").sum()
    sells = (df["signal"] == "SELL").sum()
    logger.info("Signals: BUY=%d | HOLD=%d | SELL=%d", buys, holds, sells)

    return df


def save_signals(signals_df: pd.DataFrame):
    """Save signals to the DB signals table."""
    if signals_df.empty:
        return

    with get_connection() as conn:
        for _, row in signals_df.iterrows():
            conn.execute(
                """INSERT OR REPLACE INTO signals
                   (ticker, date, rsi, sma_20, sentiment_score, signal)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (row["ticker"], row["date"], row["rsi"],
                 row["sma_20"], row["sentiment_score"], row["signal"])
            )
    logger.info("Saved %d signals to DB", len(signals_df))


def load_latest_signals() -> pd.DataFrame:
    """Load the most recent signal per ticker from DB."""
    with get_connection() as conn:
        df = pd.read_sql_query(
            """SELECT s.*
               FROM signals s
               INNER JOIN (
                   SELECT ticker, MAX(date) as max_date
                   FROM signals GROUP BY ticker
               ) latest ON s.ticker = latest.ticker AND s.date = latest.max_date
               ORDER BY signal, ticker""",
            conn
        )
    return df


# ── Entry point ────────────────────────────────────────────────────────────────

def run(sentiment_df: pd.DataFrame = None) -> pd.DataFrame:
    if sentiment_df is None:
        # Import here to avoid circular imports
        sys.path.insert(0, str(Path(__file__).parent))
        from sentiment import run as run_sentiment
        sentiment_df = run_sentiment()

    logger.info("Generating signals for %d tickers…", len(NIFTY_20))
    signals_df = compute_all_signals(sentiment_df)
    save_signals(signals_df)
    return signals_df


if __name__ == "__main__":
    from sentiment import run as run_sentiment
    sentiment_df = run_sentiment()
    signals_df = run(sentiment_df)

    print("\nSignals:")
    cols = ["name", "close", "rsi", "rsi_zone", "above_sma", "sentiment_score", "signal"]
    print(signals_df[cols].to_string(index=False))
