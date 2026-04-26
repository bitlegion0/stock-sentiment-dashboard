"""
app.py
------
Main Streamlit entry point for the Indian Stock Sentiment Dashboard.
Run with: streamlit run dashboard/app.py
"""

import sys
import streamlit as st
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))
sys.path.insert(0, str(Path(__file__).parent.parent / "data"))

from sentiment import compute_ticker_sentiment, compute_market_mood, get_ticker_headlines
from signals import compute_all_signals
from fetcher import NIFTY_20, load_prices
from charts import candlestick_chart, rsi_chart, sentiment_heatmap, signal_distribution_chart
from components import kpi_cards, signal_table, headline_feed, stock_detail_panel

st.set_page_config(
    page_title="India Stock Sentiment",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 1rem; max-width: 1200px; }
    div[data-testid="stMetric"] {
        border: 0.5px solid rgba(128,128,128,0.2);
        border-radius: 10px;
        padding: 14px 16px;
    }
    div[data-testid="stMetric"] label {
        font-size: 11px !important;
        font-weight: 500 !important;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        opacity: 0.5;
    }
    div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
        font-size: 20px !important;
        font-weight: 500 !important;
    }
    section[data-testid="stSidebar"] { border-right: 0.5px solid rgba(128,128,128,0.15); }
    .section-title {
        font-size: 11px;
        font-weight: 500;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        opacity: 0.45;
        margin-bottom: 10px;
        padding-bottom: 8px;
        border-bottom: 0.5px solid rgba(128,128,128,0.15);
    }
    .rule-item { font-size: 13px; opacity: 0.7; padding: 3px 0; }
    .stButton button {
        border: 0.5px solid rgba(128,128,128,0.3) !important;
        background: transparent !important;
        font-size: 13px !important;
    }
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600)
def load_dashboard_data():
    sentiment_df = compute_ticker_sentiment(days=3)
    signals_df   = compute_all_signals(sentiment_df)
    mood         = compute_market_mood(sentiment_df)
    return sentiment_df, signals_df, mood


with st.sidebar:
    st.markdown("#### 📈 India Stock Sentiment")
    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    ticker_display  = [t.replace(".NS", "") for t in NIFTY_20]
    selected_name   = st.selectbox("Select stock", ticker_display, index=0)
    selected_ticker = selected_name + ".NS"
    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
    if st.button("↻  Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Signal logic</div>', unsafe_allow_html=True)
    st.markdown("""
<div class="rule-item">RSI &lt; 50 → +1</div>
<div class="rule-item">Price &gt; SMA20 → +1</div>
<div class="rule-item">Positive sentiment → +1</div>
<div style="height:8px"></div>
<div class="rule-item"><strong>Score ≥ 2 → BUY</strong></div>
<div class="rule-item"><strong>Score ≤ −1 → SELL</strong></div>
<div class="rule-item"><strong>Otherwise → HOLD</strong></div>
""", unsafe_allow_html=True)
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.caption("NSE via yfinance · Moneycontrol / ET")


with st.spinner("Loading market data…"):
    sentiment_df, signals_df, mood = load_dashboard_data()

kpi_cards(signals_df, mood)
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1], gap="medium")
with col1:
    st.markdown('<div class="section-title">Signal summary — all 20 stocks</div>', unsafe_allow_html=True)
    signal_table(signals_df)
with col2:
    st.markdown('<div class="section-title">Distribution</div>', unsafe_allow_html=True)
    st.plotly_chart(signal_distribution_chart(signals_df), use_container_width=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown(f'<div class="section-title">{selected_name} — price chart</div>', unsafe_allow_html=True)

price_df = load_prices(ticker=selected_ticker, days=90)
if not price_df.empty:
    col1, col2 = st.columns([3, 1], gap="medium")
    with col1:
        st.plotly_chart(candlestick_chart(price_df, selected_name), use_container_width=True)
        st.plotly_chart(rsi_chart(price_df, selected_name), use_container_width=True)
    with col2:
        stock_detail_panel(signals_df, selected_ticker, selected_name)
else:
    st.warning(f"No price data for {selected_name}. Run the pipeline first.")

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown('<div class="section-title">News sentiment — all stocks</div>', unsafe_allow_html=True)
st.plotly_chart(sentiment_heatmap(sentiment_df), use_container_width=True)

st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
st.markdown(f'<div class="section-title">Latest headlines — {selected_name}</div>', unsafe_allow_html=True)
headline_feed(get_ticker_headlines(selected_ticker, limit=10))

st.markdown("<div style='height:24px'></div>", unsafe_allow_html=True)
st.caption("Built by Jeswin Sam · NSE data via yfinance · Sentiment via VADER")
