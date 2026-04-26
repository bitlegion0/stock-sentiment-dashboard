"""
components.py
-------------
Reusable Streamlit UI components. Minimal clean design.
"""

import streamlit as st
import pandas as pd

GREEN = "#1D9E75"
RED   = "#E24B4A"
AMBER = "#EF9F27"
MUTED = "rgba(128,128,128,0.5)"


# ── KPI cards ──────────────────────────────────────────────────────────────────

def kpi_cards(signals_df: pd.DataFrame, mood: dict):
    col1, col2, col3, col4 = st.columns(4, gap="small")

    mood_icon = "●" if mood["mood"] == "Positive" else "●"
    mood_color = GREEN if mood["mood"] == "Positive" else RED if mood["mood"] == "Negative" else AMBER

    with col1:
        st.metric(
            label="Market mood",
            value=mood["mood"],
            delta=f"Score {mood['score']:+.4f}",
        )

    with col2:
        buys  = (signals_df["signal"] == "BUY").sum()
        total = len(signals_df)
        st.metric(
            label="Bullish stocks",
            value=f"{buys} / {total}",
            delta=f"{round(buys/total*100)}% of portfolio" if total else "—",
        )

    with col3:
        buy_df = signals_df[signals_df["signal"] == "BUY"]
        if not buy_df.empty:
            top = buy_df.sort_values("sentiment_score", ascending=False).iloc[0]
            st.metric(label="Top BUY", value=top["name"],
                      delta=f"Sentiment {top['sentiment_score']:+.3f}")
        else:
            st.metric(label="Top BUY", value="—", delta="No BUY signals")

    with col4:
        sell_df = signals_df[signals_df["signal"] == "SELL"]
        if not sell_df.empty:
            top = sell_df.sort_values("sentiment_score").iloc[0]
            st.metric(label="Top SELL", value=top["name"],
                      delta=f"Sentiment {top['sentiment_score']:+.3f}",
                      delta_color="inverse")
        else:
            oversold = signals_df.sort_values("rsi").iloc[0]
            st.metric(label="Watch (low RSI)", value=oversold["name"],
                      delta=f"RSI {oversold['rsi']:.1f}")


# ── Signal table ───────────────────────────────────────────────────────────────

def signal_table(signals_df: pd.DataFrame):
    if signals_df.empty:
        st.info("No signals yet. Run the pipeline first.")
        return

    df = signals_df[["name","close","rsi","rsi_zone","above_sma","sentiment_score","signal"]].copy()
    df.columns = ["Stock","Close (₹)","RSI","RSI Zone","Above SMA20","Sentiment","Signal"]

    def style_signal(val):
        if val == "BUY":
            return "background-color:#E1F5EE; color:#0F6E56; font-weight:500"
        elif val == "SELL":
            return "background-color:#FCEBEB; color:#A32D2D; font-weight:500"
        return "background-color:#FAEEDA; color:#854F0B; font-weight:500"

    def style_sentiment(val):
        if val > 0.05:  return "color:#1D9E75"
        if val < -0.05: return "color:#E24B4A"
        return "color:#EF9F27"

    def style_rsi(val):
        if val > 70: return "color:#E24B4A"
        if val < 30: return "color:#1D9E75"
        return ""

    styled = (
        df.style
        .map(style_signal,    subset=["Signal"])
        .map(style_sentiment, subset=["Sentiment"])
        .map(style_rsi,       subset=["RSI"])
        .format({
            "Close (₹)": "₹{:,.2f}",
            "RSI":        "{:.1f}",
            "Sentiment":  "{:+.3f}",
        })
    )
    st.dataframe(styled, use_container_width=True, height=380)


# ── Stock detail panel ─────────────────────────────────────────────────────────

def stock_detail_panel(signals_df: pd.DataFrame, ticker: str, name: str):
    row = signals_df[signals_df["ticker"] == ticker]
    if row.empty:
        st.info(f"No data for {name}")
        return

    row    = row.iloc[0]
    signal = row["signal"]
    color  = GREEN if signal == "BUY" else RED if signal == "SELL" else AMBER
    bg     = "#E1F5EE" if signal == "BUY" else "#FCEBEB" if signal == "SELL" else "#FAEEDA"
    tc     = "#0F6E56" if signal == "BUY" else "#A32D2D" if signal == "SELL" else "#854F0B"

    st.markdown(f"""
    <div style="background:{bg}; border-radius:10px; padding:14px 16px;
                text-align:center; margin-bottom:14px;">
        <div style="font-size:26px; font-weight:500; color:{tc}; letter-spacing:0.05em">{signal}</div>
        <div style="font-size:11px; color:{tc}; opacity:0.7; margin-top:2px">{name}</div>
    </div>
    """, unsafe_allow_html=True)

    st.metric("Close",     f"₹{row['close']:,.2f}")
    st.metric("RSI (14)",  f"{row['rsi']:.1f}", delta=row["rsi_zone"], delta_color="off")
    st.metric("SMA 20",    f"₹{row['sma_20']:,.2f}",
              delta="Above ✓" if row["above_sma"] else "Below ✗",
              delta_color="normal" if row["above_sma"] else "inverse")
    st.metric("Sentiment", f"{row['sentiment_score']:+.3f}",
              delta="Positive" if row["sentiment_score"] > 0.05 else
                    "Negative" if row["sentiment_score"] < -0.05 else "Neutral",
              delta_color="normal" if row["sentiment_score"] > 0.05 else
                          "inverse" if row["sentiment_score"] < -0.05 else "off")

    if "reasons" in row and row["reasons"]:
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('<p style="font-size:11px;font-weight:500;opacity:0.45;text-transform:uppercase;letter-spacing:0.05em">Why this signal</p>', unsafe_allow_html=True)
        for reason in row["reasons"]:
            st.markdown(f'<p style="font-size:12px;opacity:0.7;margin:2px 0">· {reason}</p>', unsafe_allow_html=True)


# ── Headline feed ──────────────────────────────────────────────────────────────

def headline_feed(headlines: list):
    if not headlines:
        st.info("No headlines found. Run the scraper to fetch news.")
        return

    for h in headlines:
        compound = h.get("compound", 0)
        label    = h.get("label", "Neutral")
        color    = GREEN if label == "Positive" else RED if label == "Negative" else AMBER

        st.markdown(f"""
        <div style="border-left:2px solid {color}; padding:8px 14px;
                    margin-bottom:8px; border-radius:0 6px 6px 0;
                    background:rgba(128,128,128,0.04)">
            <div style="font-size:13px; line-height:1.5;">{h['headline']}</div>
            <div style="font-size:10px; opacity:0.45; margin-top:4px;">
                {h.get('source','').replace('_',' ').title()} ·
                <span style="color:{color}">{compound:+.3f}</span> ·
                {h.get('fetched_at','')[:16]}
            </div>
        </div>
        """, unsafe_allow_html=True)
