"""Build data/putwrite.json for the Put-Write Desk page.

- Daily S&P 500 index, VIX and 13-week T-bill yield since 1990 (for the page's back-test).
- SPY's latest price and 200-day average.
- SPY put chains for every expiry 14 to 70 days out, strikes 70% to 102% of the price
  (bid, ask, last, implied volatility, open interest, volume).
All from Yahoo Finance via yfinance.
"""
import json
import math
import time
import datetime as dt
from pathlib import Path

import yfinance as yf

OUT = Path(__file__).resolve().parent.parent / "data" / "putwrite.json"


def retry(fn, tries=4):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # network hiccups
            if i == tries - 1:
                raise
            print("retry:", e)
            time.sleep(5 * (i + 1))


def num(x, d=2):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(x) else round(x, d)


def main():
    hist = retry(lambda: yf.download(["^GSPC", "^VIX", "^IRX"], start="1990-01-01", interval="1d",
                                     auto_adjust=False, progress=False)["Close"])
    hist = hist.dropna()
    spy_t = yf.Ticker("SPY")
    spy = retry(lambda: spy_t.history(period="2y", auto_adjust=False))["Close"].dropna()
    price = float(spy.iloc[-1])
    sma200 = float(spy.iloc[-200:].mean())
    today = dt.date.today()
    chains = []
    for e in retry(lambda: spy_t.options):
        dte = (dt.date.fromisoformat(e) - today).days
        if dte < 14 or dte > 70:
            continue
        puts = retry(lambda: spy_t.option_chain(e).puts)
        rows = []
        for _, r in puts.iterrows():
            k = float(r["strike"])
            if k < price * 0.70 or k > price * 1.02:
                continue
            rows.append([k, num(r["bid"]), num(r["ask"]), num(r["lastPrice"]), num(r["impliedVolatility"], 4),
                         int(r["openInterest"]) if num(r["openInterest"], 0) is not None else 0,
                         int(r["volume"]) if num(r["volume"], 0) is not None else 0])
        if rows:
            chains.append({"exp": e, "dte": dte, "puts": rows})
        time.sleep(0.5)
    data = {
        "updated": dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        "source": "Yahoo Finance via yfinance (S&P 500 index, VIX, 13-week T-bill, SPY options)",
        "spy": {"price": round(price, 2), "date": spy.index[-1].strftime("%Y-%m-%d"), "sma200": round(sma200, 2),
                "closes": [round(float(x), 2) for x in spy.iloc[-260:]]},
        "vix": {"last": round(float(hist["^VIX"].iloc[-1]), 2), "date": hist.index[-1].strftime("%Y-%m-%d")},
        "chain_cols": ["strike", "bid", "ask", "last", "iv", "oi", "vol"],
        "chains": chains,
        "hist": {
            "d": [x.strftime("%Y-%m-%d") for x in hist.index],
            "spx": [round(float(x), 2) for x in hist["^GSPC"]],
            "vix": [round(float(x), 2) for x in hist["^VIX"]],
            "irx": [round(float(x), 3) for x in hist["^IRX"]],
        },
    }
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print("wrote", OUT, len(data["hist"]["d"]), "days,", len(chains), "expiries")


if __name__ == "__main__":
    main()
