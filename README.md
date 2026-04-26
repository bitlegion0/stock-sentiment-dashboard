# Indian Stock Sentiment \& Signal Dashboard

A live dashboard that tracks 20 Nifty stocks using real NSE price data and news sentiment analysis to generate BUY / HOLD / SELL signals.

\*\*Live demo:\*\* \[india-stock-sentiment.up.railway.app](https://india-stock-sentiment.up.railway.app)

\---

## What it does

* Pulls live NSE price data for 20 Nifty stocks via yfinance
* Scrapes financial headlines from Moneycontrol and Economic Times
* Runs VADER sentiment analysis on each headline per stock
* Computes RSI(14) and SMA(20) technical indicators
* Combines sentiment + technicals into a transparent BUY / HOLD / SELL signal
* Displays everything in a live Streamlit dashboard
* Auto-refreshes daily via a scheduler (6:30 AM + 3:45 PM IST)

\---

## Signal logic

Each stock is scored out of 3 points:

|Condition|Points|
|-|-|
|RSI < 50 (not overbought)|+1|
|Price above SMA20 (uptrend)|+1|
|Positive news sentiment (>0.05)|+1|
|Negative news sentiment (<-0.05)|-1|

* Score ≥ 2 → **BUY**
* Score ≤ -1 → **SELL**
* Otherwise → **HOLD**

\---

## Tech stack

|Layer|Tools|
|-|-|
|Data|yfinance, BeautifulSoup, SQLite|
|Analysis|Pandas, NumPy, VADER Sentiment|
|Dashboard|Streamlit, Plotly|
|Deployment|Railway, APScheduler|

\---

## Project structure

```
stock-sentiment-dashboard/
├── data/
│   ├── fetcher.py        # NSE price data via yfinance
│   ├── scraper.py        # News headlines scraper
│   ├── pipeline.py       # Runs fetcher + scraper
│   └── scheduler.py      # Daily auto-refresh (APScheduler)
├── analysis/
│   ├── sentiment.py      # VADER sentiment scoring
│   └── signals.py        # RSI, SMA, signal generation
├── dashboard/
│   ├── app.py            # Streamlit entry point
│   ├── charts.py         # Plotly chart components
│   └── components.py     # UI components
├── tests/
│   └── test\_signals.py   # Unit tests (12/12 passing)
├── requirements.txt
├── railway.toml
└── Procfile
```

\---

## Run locally

```bash
# Clone and set up
git clone https://github.com/yourusername/stock-sentiment-dashboard
cd stock-sentiment-dashboard
python -m venv venv
venv\\Scripts\\activate        # Windows
pip install -r requirements.txt

# Fetch data
python data/pipeline.py

# Run dashboard
streamlit run dashboard/app.py
```

\---

## Deploy on Railway

1. Push to GitHub
2. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
3. Select your repo — Railway auto-detects the config
4. Your live URL appears in under 2 minutes

\---

## Built by

**Jeswin Sam** — Data Scientist with a background in finance and NLP.

[LinkedIn](https://linkedin.com/in/jeswin-sam) · [GitHub](https://github.com/jeswin) · [Portfolio](https://jeswinsam.com)

