"""Market Simulator: Monte Carlo price paths calibrated to real prices (Streamlit).

Runs two ways from this one file:
- on a Streamlit server (`streamlit run app.py`): any Yahoo Finance symbol, downloaded live with yfinance;
- in the browser via stlite (Pyodide), as on https://boonwui.github.io/market-simulator/: about 110 Bursa Malaysia and
  US stocks from the portfolio's self-updating data files, because a browser cannot call Yahoo Finance directly.
"""
import json
import sys
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

IN_BROWSER = sys.platform == "emscripten"

st.set_page_config(page_title="Market Simulator", page_icon="📈", layout="wide")
st.title("Market Simulator")
st.warning("**Disclaimer:** Data may be delayed, incomplete or inaccurate. For education and research only; use at your own risk. **Not financial advice.**")
st.caption("Monte Carlo price paths calibrated to real price history · by [BoonWui](https://boonwui.github.io)"
           + (" · running entirely in your browser with Python (Pyodide)" if IN_BROWSER else ""))


@st.cache_data
def browser_universe() -> dict:
    """Symbols and closes from the portfolio's data files, mounted into the browser's file system."""
    out = {}
    for market, label in (("bursa", "Bursa Malaysia"), ("sp500", "US")):
        p = Path("data") / f"{market}.json"
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        idx = pd.to_datetime(d["dates"])
        names = {d["index"]["symbol"]: f"{d['index']['name']} (index)"}
        names.update({s["symbol"]: f"{s['code']} · {s['name']}" for s in d["stocks"]})
        for sym, name in names.items():
            if sym in d["close"]:
                out[f"{label}: {name}"] = pd.Series(d["close"][sym], index=idx, dtype="float64").dropna()
    return out


@st.cache_data(ttl=3600, show_spinner="Downloading prices…")
def yahoo(sym: str, period: str) -> pd.Series:
    import yfinance as yf
    df = yf.download(sym, period=period, auto_adjust=True, progress=False)
    close = df["Close"]
    if isinstance(close, pd.DataFrame):
        close = close.iloc[:, 0]
    return close.dropna()


LOOKBACK_DAYS = {"6mo": 126, "1y": 252, "2y": 504, "3y": 756, "5y": 1260}
with st.sidebar:
    st.header("Inputs")
    if IN_BROWSER:
        uni = browser_universe()
        keys = list(uni)
        default = next((i for i, k in enumerate(keys) if "S&P 500" in k), 0)
        choice = st.selectbox("Stock or index", keys, index=default)
        lookback = st.select_slider("History used for calibration", ["6mo", "1y", "2y", "3y"], value="2y")
        ticker = choice.split(": ", 1)[1].split(" · ")[0]
    else:
        ticker = st.text_input("Ticker", "AAPL", help="Any Yahoo Finance symbol, e.g. AAPL, 1155.KL, BTC-USD, CL=F").strip().upper()
        lookback = st.select_slider("History used for calibration", ["6mo", "1y", "2y", "5y"], value="2y")
    model = st.radio("Model", ["GBM", "Heston"], horizontal=True)
    days = st.slider("Days to simulate", 20, 504, 252)
    paths = st.slider("Paths", 500, 10000, 2000 if IN_BROWSER else 3000, step=500)
    seed = st.number_input("Random seed", 1, 10**6, 42)
    if model == "Heston":
        kappa = st.slider("Reversion speed κ", 0.1, 10.0, 2.0)
        xi = st.slider("Vol of vol ξ", 0.05, 1.5, 0.5)
        rho = st.slider("Correlation ρ", -0.95, 0.95, -0.6)

try:
    px = uni[choice].iloc[-LOOKBACK_DAYS[lookback]:] if IN_BROWSER else yahoo(ticker, lookback)
except Exception as exc:  # network or symbol errors
    st.error(f"Could not load {ticker}: {exc}")
    st.stop()
if len(px) < 30:
    st.error(f"Not enough price history for {ticker}. Check the symbol.")
    st.stop()

ret = np.log(px / px.shift(1)).dropna()
mu, sigma, s0 = float(ret.mean() * 252), float(ret.std() * np.sqrt(252)), float(px.iloc[-1])
rng = np.random.default_rng(int(seed))
dt = 1 / 252

S = np.full(paths, s0)
v = np.full(paths, sigma**2)
out = np.empty((days + 1, paths))
out[0] = s0
for t in range(1, days + 1):
    z1 = rng.standard_normal(paths)
    if model == "Heston":
        z2 = rho * z1 + np.sqrt(1 - rho**2) * rng.standard_normal(paths)
        vp = np.maximum(v, 0)
        S = S * np.exp((mu - 0.5 * vp) * dt + np.sqrt(vp * dt) * z1)
        v = v + kappa * (sigma**2 - vp) * dt + xi * np.sqrt(vp * dt) * z2  # full-truncation Euler
    else:
        S = S * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * z1)
    out[t] = S

final = out[-1]
pct = np.percentile(out, [5, 25, 50, 75, 95], axis=1)

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Last price", f"{s0:,.2f}")
c2.metric("Median at end", f"{np.median(final):,.2f}", f"{(np.median(final) / s0 - 1) * 100:+.1f}%")
fmt = "{:,.0f}" if s0 >= 100 else "{:,.2f}"
c3.metric("5th–95th percentile", f"{fmt.format(pct[0, -1])}–{fmt.format(pct[4, -1])}")
c4.metric("Chance of a loss", f"{(final < s0).mean() * 100:.1f}%")
c5.metric("Calibrated volatility", f"{sigma * 100:.1f}%", f"drift {mu * 100:+.1f}% a year", delta_color="off")

GREEN, BLUE = "#1f6f4a", "#2d64a8"
x = np.arange(days + 1)
bands = pd.DataFrame({"day": x, "p5": pct[0], "p25": pct[1], "p50": pct[2], "p75": pct[3], "p95": pct[4]})
sample = pd.DataFrame(out[:, : min(12, paths)], columns=[f"path {i + 1}" for i in range(min(12, paths))]).assign(day=x)
sample = sample.melt("day", var_name="path", value_name="price")
base = alt.Chart(bands).encode(x=alt.X("day:Q", title="Trading days ahead"))
fan = alt.layer(
    base.mark_area(opacity=0.15, color=GREEN).encode(y=alt.Y("p5:Q", title="Price", scale=alt.Scale(zero=False)), y2="p95:Q"),
    base.mark_area(opacity=0.30, color=GREEN).encode(y="p25:Q", y2="p75:Q"),
    alt.Chart(sample).mark_line(strokeWidth=0.7, opacity=0.45, color=BLUE).encode(x="day:Q", y="price:Q", detail="path:N"),
    base.mark_line(strokeWidth=3, color=GREEN).encode(y="p50:Q", tooltip=[alt.Tooltip("day:Q"), alt.Tooltip("p5:Q", format=",.2f"), alt.Tooltip("p50:Q", format=",.2f"), alt.Tooltip("p95:Q", format=",.2f")]),
).properties(height=440, title=f"{ticker}: {paths:,} simulated paths ({model}); shaded 25–75th and 5–95th percentiles")
st.altair_chart(fan, use_container_width=True)

left, right = st.columns(2)
with left:
    st.subheader("Where prices end up")
    hist = alt.Chart(pd.DataFrame({"final": final})).mark_bar(color=GREEN).encode(
        x=alt.X("final:Q", bin=alt.Bin(maxbins=60), title="Final price"), y=alt.Y("count():Q", title="Paths"))
    st.altair_chart(hist.properties(height=320), use_container_width=True)
with right:
    st.subheader("History used")
    st.line_chart(px.rename("Price"), height=320)

st.caption("A model of uncertainty, not a forecast. Calibrated drift from past returns is a weak guide to the future. Not financial advice.")
