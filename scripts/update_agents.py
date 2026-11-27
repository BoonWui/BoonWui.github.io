"""Daily rebuild of the three trading-agent demos from public end-of-day data.

  ai-brokerage/anchors.json   Quorvia AI brokerage: starting prices (site data, ECB, NY Fed)
  rl-trader/index.html        Kestrel RL Trader: FCPO + palm/energy/FX/MPOB data from this repo
  merlin-nasdaq/index.html    Merlin Nasdaq Agent: Nasdaq-100, 50 largest members, Brent, WTI, gold, 10y note (Yahoo Finance)

Inputs kept in the repo: agents/kestrel_template.html, agents/merlin_template.html,
agents/merlin_universe.json (the 50 tickers), data/fcpo_daily.json (daily Bernama FCPO closes,
pushed by the owner's evening job). Each part runs on its own; one failure doesn't stop the others.
Run from the repo root: python scripts/update_agents.py [quorvia] [kestrel] [merlin]
"""
import bisect, csv, io, json, re, sys, traceback, urllib.request, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AG = ROOT / "agents"
UA = {"User-Agent": "boonwui-site-agents/1.0"}
J = lambda o: json.dumps(o, separators=(",", ":"))


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def fcpo_series():
    h = (ROOT / "palm-oil-fundamentals" / "index.html").read_text(encoding="utf-8")
    f = json.loads(re.search(r'"fcpo_d":(\[\[.*?\]\])', h, re.S).group(1))
    daily = ROOT / "data" / "fcpo_daily.json"
    extra = False
    if daily.exists():
        have = {d for d, _ in f}
        for x in json.loads(daily.read_text(encoding="utf-8")):
            if x.get("date") and x.get("close") and x["date"] not in have and x["date"] > f[-1][0]:
                f.append([x["date"], float(x["close"])])
                extra = True
    return sorted(f), extra


def page(head_desc, body):
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">'
            f'<meta name="description" content="{head_desc}"><style>[hidden]{{display:none!important}}</style></head><body>' + body + '<script src="../assets/site.js"></script></body></html>')


# ---------------------------------------------------------------- Quorvia
def quorvia():
    N = 130
    tail = lambda pairs: [[d, v] for d, v in pairs if v is not None][-N:]
    out, notes = {}, []
    fc, extra = fcpo_series()
    out["fcpo"] = {"src": "the site's fundamentals page (FCPO 3rd month, RM/t)" + (", plus daily closes from Bernama market reports" if extra else ""), "asof": fc[-1][0], "series": tail(fc)}
    en = json.loads((ROOT / "energy-monitor" / "data.json").read_text(encoding="utf-8"))
    out["brent"] = {"src": en["sources"]["brent"], "series": tail(zip(en["dates"], en["brent"]))}
    out["usdmyr"] = {"src": en["sources"]["usdmyr"], "series": tail(zip(en["dates"], en["usdmyr"]))}
    sp = json.loads((ROOT / "sp500-monitor" / "data.json").read_text(encoding="utf-8"))
    out["spx"] = {"src": "S&P 500 index daily close (the site's S&P monitor)", "series": tail(zip(sp["dates"], sp["close"]["^GSPC"]))}
    out["ust10"] = {"src": "US 10-year Treasury yield (the site's S&P monitor)", "series": tail(zip(sp["dates"], sp["close"]["^TNX"]))}
    try:
        root = ET.fromstring(get("https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"))
        days = sorted((c.get("time"), {x.get("currency"): float(x.get("rate")) for x in c}) for c in root.iter() if c.get("time"))
        fx = {}
        for d, r in days:
            usd = r.get("USD")
            if not usd:
                continue
            row = {"EURUSD": usd}
            if "GBP" in r: row["GBPUSD"] = usd / r["GBP"]
            if "AUD" in r: row["AUDUSD"] = usd / r["AUD"]
            for ccy, pair in (("JPY", "USDJPY"), ("SGD", "USDSGD"), ("CNY", "USDCNH"), ("INR", "USDINR")):
                if ccy in r: row[pair] = r[ccy] / usd
            for k, v in row.items():
                fx.setdefault(k, []).append([d, round(v, 3 if k in ("USDJPY", "USDINR") else 5)])
        out["fx"] = {"src": "ECB euro reference rates (14:15 CET), crossed through EUR; USD/CNH uses the onshore CNY rate", "pairs": fx}
    except Exception as e:
        notes.append(f"ECB FX failed: {e}")
    try:
        j = json.loads(get(f"https://markets.newyorkfed.org/api/rates/secured/sofr/last/{N}.json"))
        out["sofr"] = {"src": "SOFR, Federal Reserve Bank of New York", "series": sorted([[x["effectiveDate"], x["percentRate"]] for x in j["refRates"]])}
    except Exception as e:
        notes.append(f"SOFR failed: {e}")
    try:
        rows = list(csv.DictReader(io.StringIO(get(f"https://data-api.ecb.europa.eu/service/data/EST/B.EU000A2X2A25.WT?lastNObservations={N}&format=csvdata").decode())))
        out["estr"] = {"src": "Euro short-term rate (€STR), ECB", "series": sorted([[r["TIME_PERIOD"], float(r["OBS_VALUE"])] for r in rows])}
    except Exception as e:
        notes.append(f"ESTR failed: {e}")
    out["built"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    (ROOT / "ai-brokerage" / "anchors.json").write_text(J(out), encoding="utf-8")
    print("quorvia: FCPO", out["fcpo"]["series"][-1], "|", "; ".join(notes) or "all sources ok")


# ---------------------------------------------------------------- Kestrel
def kestrel():
    f, _ = fcpo_series()
    dates = [d for d, _ in f]

    def ffill(src_dates, vals):
        pairs = [(d, v) for d, v in zip(src_dates, vals) if v is not None]
        ds = [p[0] for p in pairs]
        out = []
        for d in dates:
            i = bisect.bisect_right(ds, d) - 1
            out.append(round(pairs[i][1], 4) if i >= 0 else None)
        return out

    def nxt(m, day):
        y, mo = map(int, m.split("-"))
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
        return f"{y:04d}-{mo:02d}-{day:02d}"

    en = json.loads((ROOT / "energy-monitor" / "data.json").read_text(encoding="utf-8"))
    sp = json.loads((ROOT / "sp500-monitor" / "data.json").read_text(encoding="utf-8"))
    S = {"FCPO": [v for _, v in f], "BRENT": ffill(en["dates"], en["brent"]), "USDMYR": ffill(en["dates"], en["usdmyr"]),
         "SPX": ffill(sp["dates"], sp["close"]["^GSPC"]), "UST10": ffill(sp["dates"], sp["close"]["^TNX"])}
    rows = list(csv.DictReader(open(ROOT / "data" / "mpob_malaysia.csv", encoding="utf-8")))
    for key, col in [("MPOB_STOCK", "end_stocks_t"), ("MPOB_PROD", "production_t"), ("MPOB_EXP", "exports_t")]:
        S[key] = ffill([nxt(r["month"], 10) for r in rows], [float(r[col]) for r in rows])
    pm = json.loads((ROOT / "palm-oil-monitor" / "data.json").read_text(encoding="utf-8"))["prices"]
    S["SOYOIL"] = ffill([nxt(p["month"], 5) for p in pm], [p.get("soy") for p in pm])
    bad = {k: sum(v is None for v in vals) for k, vals in S.items() if any(v is None for v in vals)}
    assert not bad, f"missing values: {bad}"
    data = {"dates": dates, "s": S, "src": {
        "FCPO": "Bursa FCPO 3rd-month close (site fundamentals page + Bernama daily closes)", "BRENT": "EIA Brent spot, US$/bbl",
        "USDMYR": "Bank Negara Malaysia USD/MYR", "SPX": "S&P 500 close", "UST10": "US 10-year Treasury yield, %",
        "MPOB_STOCK": "MPOB end-month stocks, t (usable from the 10th of the next month)", "MPOB_PROD": "MPOB production, t (same release lag)",
        "MPOB_EXP": "MPOB exports, t (same release lag)", "SOYOIL": "World Bank soybean oil, US$/t monthly (usable from the 5th of the next month)"}}
    tpl = (AG / "kestrel_template.html").read_text(encoding="utf-8")
    assert tpl.count("/*DATA*/null") == 1
    (ROOT / "rl-trader" / "index.html").write_text(page(
        "Kestrel RL Trader: an agentic reinforcement-learning agent that builds its own indicators from real FCPO, energy, FX and MPOB data, trains a Q-learning policy and replays its trades. Simulated, no orders.",
        tpl.replace("/*DATA*/null", J(data))), encoding="utf-8")
    print("kestrel:", len(dates), "days to", dates[-1], "FCPO", S["FCPO"][-1])


# ---------------------------------------------------------------- Merlin
def merlin():
    import warnings
    warnings.filterwarnings("ignore")
    import yfinance as yf
    import pandas as pd
    uni = json.loads((AG / "merlin_universe.json").read_text(encoding="utf-8"))
    top, caps = uni["tickers"], dict(uni.get("caps", {}))
    for t in top:
        try:
            c = yf.Ticker(t).fast_info.get("marketCap")
            if c:
                caps[t] = round(c / 1e9, 1)
        except Exception:
            pass
    macro = ["^NDX", "^VIX", "^TNX", "BZ=F", "CL=F", "GC=F", "ZN=F"]
    # From 2016; stocks that listed later keep empty (null) history before their first trading day.
    raw = yf.download(macro + top, start="2016-01-01", interval="1d", auto_adjust=True, progress=False)
    px = raw["Close"].dropna(subset=["^NDX"])
    idx = px.index
    px = px.ffill()
    missing = [t for t in macro + top if t not in px.columns or px[t].isna().all()]
    assert not missing, f"no prices for {missing}"
    assert len(px) > 2000, f"download looks short ({len(px)} days)"
    hi, lo, vo = raw["High"].reindex(idx), raw["Low"].reindex(idx), raw["Volume"].reindex(idx)
    tradable = ["^NDX", "BZ=F", "CL=F", "GC=F", "ZN=F"] + top
    num = lambda v, d: None if pd.isna(v) else round(float(v), d)
    data = {"dates": [d.strftime("%Y-%m-%d") for d in idx], "caps": {t: caps.get(t) for t in top},
            "s": {k: [num(v, 4) for v in px[k]] for k in macro + top},
            # daily high-low range as a share of the close, and volume in millions (both per tradable instrument)
            "r": {k: [num((h - l) / c, 4) if pd.notna(h) and pd.notna(l) and pd.notna(c) and c else None for h, l, c in zip(hi[k], lo[k], raw["Close"][k].reindex(idx))] for k in tradable},
            "v": {k: [num(v / 1e6, 3) if pd.notna(v) and v > 0 else None for v in vo[k]] for k in tradable}}
    tpl = (AG / "merlin_template.html").read_text(encoding="utf-8")
    assert tpl.count("/*DATA*/null") == 1
    (ROOT / "merlin-nasdaq" / "index.html").write_text(page(
        "Merlin Nasdaq Agent: an agentic reinforcement-learning trader for the Nasdaq-100, its 50 largest stocks, crude oil, gold and US bonds. Builds its own indicators, runs a long/short book and replays every trade. Simulated, no orders.",
        tpl.replace("/*DATA*/null", J(data))), encoding="utf-8")
    uni["caps"] = data["caps"]
    (AG / "merlin_universe.json").write_text(json.dumps(uni, indent=1), encoding="utf-8")
    print("merlin:", len(data["dates"]), "days to", data["dates"][-1], "NDX", data["s"]["^NDX"][-1])


if __name__ == "__main__":
    want = sys.argv[1:] or ["quorvia", "kestrel", "merlin"]
    ok = 0
    for name in want:
        try:
            {"quorvia": quorvia, "kestrel": kestrel, "merlin": merlin}[name]()
            ok += 1
        except Exception:
            print(f"{name} FAILED")
            traceback.print_exc()
    sys.exit(0 if ok else 1)
