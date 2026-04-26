"""
fetcher.py
----------
Fetches daily OHLCV price data for 20 Nifty stocks using yfinance
and stores it in the local SQLite database.
"""

import yfinance as yf
import pandas as pd
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "dashboard.db"

NIFTY_20 = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS",
    "HINDUNILVR.NS", "ITC.NS", "SBIN.NS", "BHARTIARTL.NS", "KOTAKBANK.NS",
    "AXISBANK.NS", "LT.NS", "ASIANPAINT.NS", "MARUTI.NS", "SUNPHARMA.NS",
    "TITAN.NS", "ULTRACEMCO.NS", "WIPRO.NS", "HCLTECH.NS", "BAJFINANCE.NS",
]

TICKER_NAMES = {t: t.replace(".NS", "") for t in NIFTY_20}


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS prices (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker    TEXT    NOT NULL,
                date      TEXT    NOT NULL,
                open      REAL,
                high      REAL,
                low       REAL,
                close     REAL,
                volume    INTEGER,
                UNIQUE(ticker, date)
            );
            CREATE TABLE IF NOT EXISTS headlines (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker     TEXT,
                headline   TEXT    NOT NULL,
                source     TEXT,
                fetched_at TEXT    NOT NULL
            );
            CREATE TABLE IF NOT EXISTS signals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker          TEXT    NOT NULL,
                date            TEXT    NOT NULL,
                rsi             REAL,
                sma_20          REAL,
                sentiment_score REAL,
                signal          TEXT,
                UNIQUE(ticker, date)
            );
        """)
    logger.info("Database initialised at %s", DB_PATH)


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize yfinance DataFrame columns regardless of library version."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c[0] if isinstance(c, (list, tuple)) else str(c) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    return df


def fetch_single_ticker(ticker: str, days: int = 90) -> pd.DataFrame:
    end   = datetime.today()
    start = end - timedelta(days=days)
    try:
        raw = yf.download(
            tickers=ticker,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            auto_adjust=True,
            progress=False,
        )
        if raw.empty:
            logger.warning("%s — no data returned", ticker)
            return pd.DataFrame()

        raw = _flatten_columns(raw)

        required = {"Open", "High", "Low", "Close", "Volume"}
        missing  = required - set(raw.columns)
        if missing:
            logger.warning("%s — missing columns: %s | got: %s", ticker, missing, list(raw.columns))
            return pd.DataFrame()

        raw = raw.dropna(subset=["Close"])
        raw.index = pd.to_datetime(raw.index)

        records = []
        for date, row in raw.iterrows():
            records.append({
                "ticker": ticker,
                "date":   date.strftime("%Y-%m-%d"),
                "open":   round(float(row["Open"]),  2),
                "high":   round(float(row["High"]),  2),
                "low":    round(float(row["Low"]),   2),
                "close":  round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })
        return pd.DataFrame(records)
    except Exception as e:
        logger.error("Error fetching %s: %s", ticker, e)
        return pd.DataFrame()


def fetch_prices(tickers: list = None, days: int = 90) -> pd.DataFrame:
    if tickers is None:
        tickers = NIFTY_20
    logger.info("Downloading price data for %d tickers (%d days)…", len(tickers), days)
    all_frames = []
    for ticker in tickers:
        df = fetch_single_ticker(ticker, days=days)
        if not df.empty:
            all_frames.append(df)
    if not all_frames:
        logger.error("No price data fetched for any ticker!")
        return pd.DataFrame()
    result = pd.concat(all_frames, ignore_index=True)
    logger.info("Fetched %d rows across %d tickers", len(result), result["ticker"].nunique())
    return result


def save_prices(df: pd.DataFrame):
    if df.empty:
        logger.warning("No price data to save.")
        return
    with get_connection() as conn:
        inserted = 0
        for _, row in df.iterrows():
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO prices
                       (ticker, date, open, high, low, close, volume)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (row["ticker"], row["date"], row["open"],
                     row["high"], row["low"], row["close"], row["volume"]),
                )
                inserted += conn.execute("SELECT changes()").fetchone()[0]
            except Exception as e:
                logger.error("Insert failed %s/%s: %s", row["ticker"], row["date"], e)
    logger.info("Saved %d new price rows to DB", inserted)


def load_prices(ticker: str = None, days: int = 60) -> pd.DataFrame:
    cutoff = (datetime.today() - timedelta(days=days)).strftime("%Y-%m-%d")
    with get_connection() as conn:
        if ticker:
            df = pd.read_sql_query(
                "SELECT * FROM prices WHERE ticker=? AND date>=? ORDER BY date",
                conn, params=(ticker, cutoff)
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM prices WHERE date>=? ORDER BY ticker, date",
                conn, params=(cutoff,)
            )
    return df


def run():
    init_db()
    df = fetch_prices()
    save_prices(df)
    logger.info("Price fetch complete.")


if __name__ == "__main__":
    run()
