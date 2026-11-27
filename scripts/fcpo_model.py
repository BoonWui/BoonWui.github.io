"""FCPO Model: one weekly table of every driver the site collects, a learned model, and an honest track record.

1. Weekly table (every Friday): FCPO (Sina), CBOT soybean oil, Brent and USD/MYR (Yahoo Finance, cached in
   data/model_inputs.json), MPOB supply and demand, El Nino (ONI) and CFTC funds in soybean oil, each only from
   the date it was actually published (MPOB ~10th of the next month, ONI ~10th after the season, CFTC on Friday).
2. Model: L2-regularised logistic regression on standardised drivers, giving the probability that FCPO is higher
   4 weeks (and 1 week) later. Plain numpy, no extra library.
   Raw probabilities were over-confident, so each call is shrunk towards 50% by a factor k chosen only from
   earlier calls whose outcome was already known (walk-forward calibration).
3. Walk-forward test: every week from 2022 onward the model is refitted on data up to that Friday only and its
   call is scored later. No look-ahead.
Writes data/fcpo_model.json for the fcpo-model page. Run weekly by .github/workflows/update-fcpo-model.yml.
"""
import json
import time
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "data" / "model_inputs.json"
OUT = ROOT / "data" / "fcpo_model.json"
MIN_TRAIN = 104            # weeks of history before the first out-of-sample call
LAMBDA = 10.0              # L2 penalty on standardised coefficients (chosen out of sample: 2/10/30/100 tested)

# feature id -> (label, driver tree factor id, how to read it)
FEATURES = {
    "mom4":   ("FCPO, last 4 weeks", "mom", "% change"),
    "rev1":   ("FCPO, last week", "mom", "% change"),
    "soy4":   ("Soybean oil, last 4 weeks", "soy", "% change"),
    "soy1":   ("Soybean oil, last week", "soy", "% change"),
    "brent4": ("Brent, last 4 weeks", "oil", "% change"),
    "myr4":   ("USD/MYR, last 4 weeks", "myr", "% change"),
    "spr_z":  ("Palm minus soybean oil (vs its year)", "spr", "z-score"),
    "stk_mm": ("MPOB stocks, month on month", "stk", "% change"),
    "stk_z":  ("MPOB stocks vs 3-year average", "stk", "z-score"),
    "prd_mm": ("MPOB production, month on month", "prd", "% change"),
    "exp_mm": ("MPOB exports, month on month", "exp", "% change"),
    "oni":    ("El Niño index (ONI)", "wx", "°C"),
    "cftc":   ("US funds in soybean oil, week", "cft", "% of positions"),
}


def yahoo(start="2019-06-01"):
    """Daily closes for soybean oil, Brent and USD/MYR; cached so a Yahoo outage does not stop the model."""
    old = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    try:
        import yfinance as yf
        syms = {"soy": "ZL=F", "brent": "BZ=F", "myr": "MYR=X"}
        for i in range(3):
            raw = yf.download(list(syms.values()), start=start, interval="1d", auto_adjust=False, progress=False, threads=False)
            if raw is not None and not raw.empty:
                c = raw["Close"]
                new = {k: [[d.strftime("%Y-%m-%d"), round(float(v), 4)] for d, v in c[y].dropna().items()] for k, y in syms.items() if y in c}
                if all(len(new.get(k, [])) > 500 for k in syms):
                    CACHE.write_text(json.dumps(new, separators=(",", ":")), encoding="utf-8")
                    return new
            time.sleep(10)
    except Exception as e:
        print("Yahoo unavailable:", e)
    return old


def series(pairs):
    s = pd.Series({d: v for d, v in pairs})
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def build_table():
    fc = json.loads((ROOT / "data" / "bmd_fcpo.json").read_text(encoding="utf-8"))
    y = yahoo()
    daily = pd.concat({"fcpo": series([(b[0], b[4]) for b in fc["bars"]]), "soy": series(y["soy"]),
                       "brent": series(y["brent"]), "myr": series(y["myr"])}, axis=1).sort_index().ffill()
    wk = daily.resample("W-FRI").last().dropna(subset=["fcpo"])
    lg = np.log(wk)
    t = pd.DataFrame(index=wk.index)
    t["mom4"] = lg["fcpo"].diff(4)
    t["rev1"] = lg["fcpo"].diff(1)
    t["soy4"] = lg["soy"].diff(4)
    t["soy1"] = lg["soy"].diff(1)
    t["brent4"] = lg["brent"].diff(4)
    t["myr4"] = lg["myr"].diff(4)
    spread = wk["fcpo"] / wk["myr"] - wk["soy"] * 22.0462          # palm US$/t minus soybean oil US$/t
    t["spr_z"] = (spread - spread.rolling(52, min_periods=26).mean()) / spread.rolling(52, min_periods=26).std()
    # MPOB: month M is known from the 10th of month M+1
    pm = json.loads((ROOT / "palm-oil-monitor" / "data.json").read_text(encoding="utf-8"))
    m = pd.DataFrame(pm["mpob"])
    m["avail"] = pd.to_datetime(m["month"]) + pd.offsets.MonthBegin(1) + pd.Timedelta(days=9)
    m["stk_mm"] = m["stock"].pct_change()
    m["stk_z"] = (m["stock"] - m["stock"].rolling(36, min_periods=12).mean()) / m["stock"].rolling(36, min_periods=12).std()
    m["prd_mm"] = m["prod"].pct_change()
    m["exp_mm"] = m["exp"].pct_change()
    mm = m.set_index("avail")[["stk_mm", "stk_z", "prd_mm", "exp_mm"]]
    # ONI season centred on month i is complete one month later and published ~10th of the month after that
    o = pd.DataFrame(pm["oni"])
    o["avail"] = [pd.Timestamp(int(r.year), int(r.i), 1) + pd.offsets.MonthBegin(2) + pd.Timedelta(days=9) for r in o.itertuples()]
    oo = o.set_index("avail")[["anom"]].rename(columns={"anom": "oni"})
    # CFTC: Tuesday positions, published that Friday
    cf = json.loads((ROOT / "data" / "cftc_managed_money.json").read_text(encoding="utf-8"))
    so = [x for x in cf["markets"] if x["id"] == "soyoil"][0]["hist"]
    c = pd.DataFrame(so, columns=["d", "l", "s", "oi"] + (["px"] if len(so[0]) > 4 else []))
    c["avail"] = pd.to_datetime(c["d"]) + pd.Timedelta(days=3)
    c["cftc"] = ((c["l"] - c["s"]).diff()) / (c["l"] + c["s"])
    cc = c.set_index("avail")[["cftc"]]
    for frame in (mm, oo, cc):
        frame = frame.sort_index()
        joined = pd.merge_asof(t.reset_index().rename(columns={"index": "date", t.index.name or "index": "date"}).sort_values("date"),
                               frame.reset_index().rename(columns={frame.index.name or "avail": "avail"}).sort_values("avail"),
                               left_on="date", right_on="avail", direction="backward")
        for col in frame.columns:
            t[col] = joined[col].values
    t["fwd4"] = lg["fcpo"].shift(-4) - lg["fcpo"]
    t["fwd1"] = lg["fcpo"].shift(-1) - lg["fcpo"]
    return t, wk


def fit(X, y, lam=LAMBDA, iters=50):
    """L2 logistic regression by Newton steps. X already standardised; intercept not penalised."""
    n, k = X.shape
    A = np.column_stack([np.ones(n), X])
    w = np.zeros(k + 1)
    P = np.eye(k + 1) * lam
    P[0, 0] = 0
    for _ in range(iters):
        p = 1 / (1 + np.exp(-A @ w))
        g = A.T @ (p - y) + P @ w
        H = A.T @ (A * (p * (1 - p))[:, None]) + P
        step = np.linalg.solve(H, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return w


def model_at(t, i, target, feats):
    """Fit on rows before i whose target is already known, predict row i."""
    tr = t.iloc[:i].dropna(subset=[target])
    tr = tr.iloc[:-4] if target == "fwd4" else tr        # the last 4 weeks' 4-week outcome is not known yet
    mu, sd = tr[feats].mean(), tr[feats].std().replace(0, 1)
    Z = ((tr[feats] - mu) / sd).fillna(0).values
    w = fit(Z, (tr[target] > 0).astype(float).values)
    z = ((t.iloc[i][feats] - mu) / sd).fillna(0).values
    p = float(1 / (1 + np.exp(-(w[0] + w[1:] @ z))))
    return p, w, mu, sd, z


def main():
    t, wk = build_table()
    feats = list(FEATURES)
    t = t[t.index >= "2020-03-01"]
    track = []
    for i in range(MIN_TRAIN, len(t)):
        p4, *_ = model_at(t, i, "fwd4", feats)
        p1, *_ = model_at(t, i, "fwd1", feats)
        r = t.iloc[i]
        track.append({"d": t.index[i].strftime("%Y-%m-%d"), "p4": round(p4, 4), "p1": round(p1, 4),
                      "a4": None if pd.isna(r["fwd4"]) else round(float(r["fwd4"]), 5),
                      "a1": None if pd.isna(r["fwd1"]) else round(float(r["fwd1"]), 5),
                      "mom": None if pd.isna(r["mom4"]) else round(float(r["mom4"]), 5)})
    # walk-forward calibration: shrink towards 50% by k fitted on calls already scored at the time
    grid = np.linspace(0, 1, 21)

    def calibrate(key, act, lag):
        ks = []
        for j, x in enumerate(track):
            known = [y for y in track[:max(0, j - lag)] if y[act] is not None]
            k = 0.5 if len(known) < 52 else float(grid[np.argmin([np.mean([(0.5 + g * (y[key] - 0.5) - (y[act] > 0)) ** 2 for y in known]) for g in grid])])
            x[key + "c"] = round(0.5 + k * (x[key] - 0.5), 4)
            ks.append(k)
        return ks[-1] if ks else 0.5
    k4, k1 = calibrate("p4", "a4", 4), calibrate("p1", "a1", 1)
    i = len(t) - 1
    p4, w4, mu, sd, z = model_at(t, i, "fwd4", feats)
    p1, w1, *_ = model_at(t, i, "fwd1", feats)
    p4c, p1c = 0.5 + k4 * (p4 - 0.5), 0.5 + k1 * (p1 - 0.5)

    def score(key, act, since=None):
        key = key + "c"
        rows = [x for x in track if x[act] is not None and (since is None or x["d"] >= since)]
        if not rows:
            return {}
        hit = np.mean([(x[key] > 0.5) == (x[act] > 0) for x in rows])
        up = np.mean([x[act] > 0 for x in rows])
        mom = np.mean([((x["mom"] or 0) > 0) == (x[act] > 0) for x in rows])
        conf = [x for x in rows if abs(x[key] - 0.5) >= 0.1]
        brier = np.mean([(x[key] - (x[act] > 0)) ** 2 for x in rows])
        return {"n": len(rows), "hit": round(float(hit), 3), "always_up": round(float(max(up, 1 - up)), 3), "momentum": round(float(mom), 3),
                "brier": round(float(brier), 4), "confident_n": len(conf),
                "confident_hit": round(float(np.mean([(x[key] > 0.5) == (x[act] > 0) for x in conf])), 3) if conf else None}

    last_year = (t.index[-1] - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    contrib = {f: round(float(w4[1 + k] * z[k]), 4) for k, f in enumerate(feats)}
    share = {}
    for k, f in enumerate(feats):
        share[FEATURES[f][1]] = share.get(FEATURES[f][1], 0) + abs(w4[1 + k])
    tot = sum(share.values()) or 1
    latest_raw = {f: (None if pd.isna(t.iloc[i][f]) else round(float(t.iloc[i][f]), 5)) for f in feats}
    out = {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "asof": t.index[i].strftime("%Y-%m-%d"),
        "fcpo": round(float(wk["fcpo"].iloc[-1])),
        "p4": round(p4c, 4), "p1": round(p1c, 4), "p4_raw": round(p4, 4), "p1_raw": round(p1, 4), "k4": k4, "k1": k1, "lambda": LAMBDA,
        "features": [{"id": f, "label": FEATURES[f][0], "tree": FEATURES[f][1], "unit": FEATURES[f][2],
                      "raw": latest_raw[f], "mean": round(float(mu[f]), 6), "sd": round(float(sd[f]), 6),
                      "coef": round(float(w4[1 + k]), 4), "coef1": round(float(w1[1 + k]), 4), "contrib": contrib[f]} for k, f in enumerate(feats)],
        "intercept": round(float(w4[0]), 4), "intercept1": round(float(w1[0]), 4),
        "tree_weights": {k: round(v / tot * 100, 1) for k, v in sorted(share.items(), key=lambda kv: -kv[1])},
        "stats": {"4w": score("p4", "a4"), "4w_last_year": score("p4", "a4", last_year), "1w": score("p1", "a1"), "1w_last_year": score("p1", "a1", last_year)},
        "track": track,
        "train_weeks": int(len(t.dropna(subset=["fwd4"]))),
        "first_test": track[0]["d"] if track else None,
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"as of {out['asof']}: P(FCPO higher in 4 weeks) = {p4c:.0%} (raw {p4:.0%}, k={k4}), 1 week = {p1c:.0%}")
    print("stats:", json.dumps(out["stats"]))
    print("model weights by driver:", out["tree_weights"])


if __name__ == "__main__":
    main()
