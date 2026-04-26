"""
test_week1.py
-------------
Run this after Week 1 setup to verify everything is working.
Usage: python test_week1.py
"""

import sys
from pathlib import Path


from data.fetcher import init_db, fetch_prices, save_prices, load_prices, NIFTY_20
import sqlite3
import pandas as pd


def test_db_init():
    print("Testing DB initialisation...")
    init_db()
    from data.fetcher import DB_PATH, get_connection
    assert DB_PATH.exists(), "DB file was not created"
    with get_connection() as conn:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
    assert "prices" in table_names
    assert "headlines" in table_names
    assert "signals" in table_names
    print("  DB init OK — tables:", table_names)


def test_fetch_single_ticker():
    print("Testing price fetch for single ticker (TCS.NS)...")
    df = fetch_prices(["TCS.NS"], days=10)
    assert not df.empty, "No data returned for TCS.NS"
    assert "close" in df.columns
    assert df["close"].notna().all()
    print(f"  Fetched {len(df)} rows for TCS.NS")
    print(f"  Latest close: ₹{df['close'].iloc[-1]:,.2f}")


def test_save_and_load():
    print("Testing save + load roundtrip...")
    df = fetch_prices(["INFY.NS"], days=5)
    save_prices(df)
    loaded = load_prices("INFY.NS", days=10)
    assert not loaded.empty, "Could not load saved prices"
    print(f"  Saved {len(df)} rows, loaded {len(loaded)} rows")


def test_ticker_list():
    print("Testing full ticker list has 20 entries...")
    assert len(NIFTY_20) == 20
    assert all(t.endswith(".NS") for t in NIFTY_20), "All tickers must end with .NS"
    print("  Ticker list OK")


if __name__ == "__main__":
    print("\n=== Week 1 Tests ===\n")
    tests = [test_db_init, test_ticker_list, test_fetch_single_ticker, test_save_and_load]
    passed = 0
    for test in tests:
        try:
            test()
            passed += 1
            print("  PASS\n")
        except Exception as e:
            print(f"  FAIL: {e}\n")

    print(f"Results: {passed}/{len(tests)} passed")
    if passed == len(tests):
        print("\nWeek 1 setup is complete. Run: python data/pipeline.py")
