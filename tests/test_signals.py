"""
test_signals.py
---------------
Unit tests for sentiment scoring and signal generation.
Run with: python -m tests.test_signals

Tests use known inputs so results are deterministic —
no network calls, no DB dependency.
"""

import sys
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from signals import compute_rsi, compute_sma, generate_signal
from sentiment import score_headline, label_score


# ── RSI tests ─────────────────────────────────────────────────────────────────

def test_rsi_overbought():
    """Strongly rising prices → RSI should be high (>70)."""
    print("Testing RSI overbought detection...")
    prices = pd.Series([
        100, 98, 103, 101, 106, 104, 110, 108, 115, 113,
        120, 118, 126, 124, 133, 131, 141, 139, 150, 148,
        160, 158, 171, 169, 183, 181, 196, 194, 210, 208
    ], dtype=float)
    rsi = compute_rsi(prices, period=14)
    latest = rsi.dropna().iloc[-1]
    assert latest > 70, f"Expected RSI > 70 for rising prices, got {latest}"
    print(f"  RSI = {latest:.1f} (overbought ✓)")


def test_rsi_oversold():
    """Strongly falling prices → RSI should be low (<30)."""
    print("Testing RSI oversold detection...")
    prices = pd.Series([292, 273, 255, 238, 222, 207, 193, 180, 168, 157,
                        147, 138, 130, 123, 117, 112, 108, 105, 102, 100])
    rsi = compute_rsi(prices, period=14)
    latest = rsi.iloc[-1]
    assert latest < 30, f"Expected RSI < 30 for falling prices, got {latest}"
    print(f"  RSI = {latest:.1f} (oversold ✓)")


def test_rsi_range():
    """RSI must always be between 0 and 100."""
    print("Testing RSI always in [0, 100]...")
    prices = pd.Series(np.random.uniform(100, 500, 50))
    rsi = compute_rsi(prices)
    assert rsi.dropna().between(0, 100).all(), "RSI out of [0,100] range"
    print("  All RSI values in valid range ✓")


# ── SMA tests ─────────────────────────────────────────────────────────────────

def test_sma_flat():
    """SMA of constant series should equal that constant."""
    print("Testing SMA on flat prices...")
    prices = pd.Series([100.0] * 30)
    sma = compute_sma(prices, window=20)
    assert abs(sma.iloc[-1] - 100.0) < 0.01, f"Expected SMA=100, got {sma.iloc[-1]}"
    print("  SMA = 100.0 (correct ✓)")


def test_sma_window():
    """SMA(5) of [1,2,3,4,5,6,7,8,9,10] last value should be 8.0."""
    print("Testing SMA(5) calculation...")
    prices = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], dtype=float)
    sma = compute_sma(prices, window=5)
    assert abs(sma.iloc[-1] - 8.0) < 0.01, f"Expected 8.0, got {sma.iloc[-1]}"
    print(f"  SMA(5) last value = {sma.iloc[-1]} ✓")


# ── Sentiment tests ────────────────────────────────────────────────────────────

def test_positive_headline():
    print("Testing positive headline scoring...")
    score = score_headline("Reliance posts record profits, shares surge to all-time high")
    assert score["compound"] > 0.05, f"Expected positive score, got {score['compound']}"
    print(f"  compound = {score['compound']:.4f} (positive ✓)")


def test_negative_headline():
    print("Testing negative headline scoring...")
    score = score_headline("TCS misses earnings badly, shares crash on weak guidance")
    assert score["compound"] < -0.05, f"Expected negative score, got {score['compound']}"
    print(f"  compound = {score['compound']:.4f} (negative ✓)")


def test_sentiment_labels():
    print("Testing sentiment label mapping...")
    assert label_score(0.5)   == "Positive"
    assert label_score(-0.5)  == "Negative"
    assert label_score(0.0)   == "Neutral"
    assert label_score(0.04)  == "Neutral"   # below threshold
    assert label_score(-0.04) == "Neutral"   # above negative threshold
    print("  All labels correct ✓")


# ── Signal generation tests ───────────────────────────────────────────────────

def _make_tech(rsi, close, sma):
    """Helper: build a minimal technicals dict."""
    return {
        "ticker":   "TEST.NS",
        "date":     "2026-04-24",
        "close":    close,
        "rsi":      rsi,
        "sma_20":   sma,
        "above_sma": close > sma,
        "rsi_zone": "Neutral",
    }


def test_signal_buy():
    """Low RSI + above SMA + positive sentiment → BUY."""
    print("Testing BUY signal generation...")
    tech   = _make_tech(rsi=40, close=110, sma=100)  # above SMA
    result = generate_signal(tech, sentiment_score=0.2)
    assert result["signal"] == "BUY", f"Expected BUY, got {result['signal']}"
    assert result["score"] == 3
    print(f"  Signal = {result['signal']} (score={result['score']}) ✓")


def test_signal_sell():
    """High RSI + below SMA + negative sentiment → SELL."""
    print("Testing SELL signal generation...")
    tech   = _make_tech(rsi=72, close=90, sma=100)   # below SMA
    result = generate_signal(tech, sentiment_score=-0.3)
    assert result["signal"] == "SELL", f"Expected SELL, got {result['signal']}"
    print(f"  Signal = {result['signal']} (score={result['score']}) ✓")


def test_signal_hold():
    """Mixed signals → HOLD."""
    print("Testing HOLD signal generation...")
    tech   = _make_tech(rsi=55, close=95, sma=100)   # below SMA, RSI > 50
    result = generate_signal(tech, sentiment_score=0.01)  # neutral sentiment
    assert result["signal"] == "HOLD", f"Expected HOLD, got {result['signal']}"
    print(f"  Signal = {result['signal']} (score={result['score']}) ✓")


def test_signal_has_reasons():
    """Every signal must include human-readable reasons."""
    print("Testing signal includes reasons...")
    tech   = _make_tech(rsi=45, close=105, sma=100)
    result = generate_signal(tech, sentiment_score=0.1)
    assert len(result["reasons"]) == 3, f"Expected 3 reasons, got {len(result['reasons'])}"
    print(f"  Reasons: {result['reasons']}")
    print("  Reasons present ✓")


# ── Runner ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    tests = [
        test_rsi_overbought,
        test_rsi_oversold,
        test_rsi_range,
        test_sma_flat,
        test_sma_window,
        test_positive_headline,
        test_negative_headline,
        test_sentiment_labels,
        test_signal_buy,
        test_signal_sell,
        test_signal_hold,
        test_signal_has_reasons,
    ]

    print("\n=== Week 2 Tests ===\n")
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
        print("\nWeek 2 complete! Run: python analysis/signals.py")
