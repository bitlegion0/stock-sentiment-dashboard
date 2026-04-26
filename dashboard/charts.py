"""
charts.py
---------
All Plotly chart functions. Clean minimal theme.
"""

import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "analysis"))
from signals import compute_rsi, compute_sma

# ── Adaptive theme — works in both light and dark Streamlit ───────────────────

GRID   = "rgba(128,128,128,0.12)"
ZERO   = "rgba(128,128,128,0.3)"
GREEN  = "#1D9E75"
RED    = "#E24B4A"
AMBER  = "#EF9F27"
BLUE   = "#378ADD"
TEXT   = "rgba(128,128,128,0.8)"

BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", size=11, color=TEXT),
    margin=dict(l=8, r=8, t=36, b=8),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor=GRID,
        borderwidth=0.5,
        font=dict(size=11),
    ),
)


def _axis(title="", prefix=""):
    return dict(
        gridcolor=GRID,
        gridwidth=0.5,
        zeroline=False,
        showline=False,
        title=dict(text=title, font=dict(size=11, color=TEXT)),
        tickfont=dict(size=10, color=TEXT),
        tickprefix=prefix,
    )


# ── Candlestick + SMA ─────────────────────────────────────────────────────────

def candlestick_chart(price_df: pd.DataFrame, ticker_name: str) -> go.Figure:
    df = price_df.copy().sort_values("date")
    df["sma_20"] = compute_sma(df["close"], window=20)

    fig = go.Figure()

    fig.add_trace(go.Candlestick(
        x=df["date"],
        open=df["open"], high=df["high"],
        low=df["low"],   close=df["close"],
        name=ticker_name,
        increasing_line_color=GREEN, increasing_fillcolor=GREEN,
        decreasing_line_color=RED,   decreasing_fillcolor=RED,
    ))

    fig.add_trace(go.Scatter(
        x=df["date"], y=df["sma_20"],
        mode="lines", name="SMA 20",
        line=dict(color=BLUE, width=1.5, dash="dot"),
    ))

    fig.update_layout(
        **BASE,
        title=dict(text=f"{ticker_name} · Price & SMA20", font=dict(size=13, color=TEXT), x=0),
        xaxis=dict(**_axis("Date"), rangeslider=dict(visible=False)),
        yaxis=_axis("Price (₹)", "₹"),
        height=360,
    )
    return fig


# ── RSI chart ─────────────────────────────────────────────────────────────────

def rsi_chart(price_df: pd.DataFrame, ticker_name: str) -> go.Figure:
    df  = price_df.copy().sort_values("date")
    rsi = compute_rsi(df["close"], period=14)

    fig = go.Figure()

    fig.add_hrect(y0=70, y1=100, fillcolor=RED,   opacity=0.04, line_width=0)
    fig.add_hrect(y0=0,  y1=30,  fillcolor=GREEN, opacity=0.04, line_width=0)

    fig.add_trace(go.Scatter(
        x=df["date"], y=rsi,
        mode="lines", name="RSI(14)",
        line=dict(color=BLUE, width=1.8),
        fill="tozeroy", fillcolor="rgba(55,138,221,0.05)",
    ))

    fig.add_hline(y=70, line_dash="dot", line_color=RED,   line_width=0.8)
    fig.add_hline(y=30, line_dash="dot", line_color=GREEN, line_width=0.8)
    fig.add_hline(y=50, line_dash="dot", line_color=ZERO,  line_width=0.5)

    fig.update_layout(
        **BASE,
        title=dict(text=f"{ticker_name} · RSI(14)", font=dict(size=13, color=TEXT), x=0),
        xaxis=_axis("Date"),
        yaxis=dict(**_axis("RSI"), range=[0, 100]),
        height=180,
    )
    return fig


# ── Sentiment bar chart ───────────────────────────────────────────────────────

def sentiment_heatmap(sentiment_df: pd.DataFrame) -> go.Figure:
    df = sentiment_df.copy().sort_values("avg_sentiment", ascending=True)
    df["name"] = df["ticker"].str.replace(".NS", "", regex=False)

    colors = [
        GREEN if s > 0.05 else RED if s < -0.05 else AMBER
        for s in df["avg_sentiment"]
    ]

    fig = go.Figure(go.Bar(
        x=df["avg_sentiment"],
        y=df["name"],
        orientation="h",
        marker_color=colors,
        marker_line_width=0,
        text=[f"{s:+.3f}" for s in df["avg_sentiment"]],
        textposition="outside",
        textfont=dict(size=10, color=TEXT),
        hovertemplate="<b>%{y}</b><br>Sentiment: %{x:.4f}<extra></extra>",
    ))

    fig.add_vline(x=0,     line_color=ZERO,  line_width=1)
    fig.add_vline(x=0.05,  line_color=GREEN, line_dash="dot", line_width=0.7)
    fig.add_vline(x=-0.05, line_color=RED,   line_dash="dot", line_width=0.7)

    fig.update_layout(
        **BASE,
        title=dict(text="News sentiment by stock (VADER)", font=dict(size=13, color=TEXT), x=0),
        xaxis=_axis("Sentiment score"),
        yaxis=_axis(),
        height=460,
        showlegend=False,
        bargap=0.35,
    )
    return fig


# ── Signal donut ──────────────────────────────────────────────────────────────

def signal_distribution_chart(signals_df: pd.DataFrame) -> go.Figure:
    counts = signals_df["signal"].value_counts()
    labels = counts.index.tolist()
    values = counts.values.tolist()

    color_map = {"BUY": GREEN, "HOLD": AMBER, "SELL": RED}
    colors    = [color_map.get(l, GRID) for l in labels]

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        hole=0.6,
        marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0)", width=0)),
        textinfo="label+value",
        textfont=dict(size=11, color=TEXT),
        hovertemplate="<b>%{label}</b>: %{value} stocks (%{percent})<extra></extra>",
    ))

    fig.update_layout(
        **BASE,
        height=260,
        showlegend=False,
        
        annotations=[dict(
            text=f"<b>{len(signals_df)}</b><br><span style='font-size:10px'>stocks</span>",
            x=0.5, y=0.5,
            font=dict(size=14, color=TEXT),
            showarrow=False,
        )],
    )
    return fig
