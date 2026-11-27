"""Re-test the FCPO Driver Tree weights against the site's own data. Writes data/fcpo_driver_evidence.json.

Market factors (soybean oil, Brent, ringgit): correlation and R^2 with FCPO weekly log returns over the last 3 years.
MPOB factors (stocks, production, exports): correlation of the month-on-month change with FCPO's change in the month
the report is published (the following month). Run monthly by .github/workflows/update-driver-evidence.yml.
"""
import json
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def main():
    f = load("data/bmd_fcpo.json")
    e = load("energy-monitor/data.json")
    fc = pd.Series({b[0]: b[4] for b in f["bars"]})
    so = pd.Series(dict(f["extra"]["soyoil"]))
    fx = pd.Series(dict(f["extra"]["usdmyr"]))
    br = pd.Series({d: v for d, v in zip(e["dates"], e["brent"]) if v is not None})
    df = pd.concat({"fcpo": fc, "soy": so, "brent": br, "myr": fx}, axis=1)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill().dropna()
    df = df[df.index >= df.index[-1] - pd.Timedelta(days=3 * 365)]
    w = np.log(df.resample("W-FRI").last()).diff().dropna()
    y = w["fcpo"]

    def r2(cols, data, target):
        a = np.column_stack([np.ones(len(target))] + [data[c] for c in cols])
        b = np.linalg.lstsq(a, target, rcond=None)[0]
        return float(1 - (target - a @ b).var() / target.var())

    rows = [
        {"id": "soy", "name": "Soybean oil price (CBOT)", "basis": "weekly returns", "corr": float(w["soy"].corr(y)), "r2": r2(["soy"], w, y)},
        {"id": "oil", "name": "Crude oil (Brent)", "basis": "weekly returns", "corr": float(w["brent"].corr(y)), "r2": r2(["brent"], w, y)},
        {"id": "myr", "name": "Ringgit (USD/MYR)", "basis": "weekly returns", "corr": float(w["myr"].corr(y)), "r2": r2(["myr"], w, y)},
    ]
    p = load("palm-oil-monitor/data.json")
    m = pd.DataFrame(p["mpob"])
    m["month"] = pd.to_datetime(m["month"])
    m = m.set_index("month")
    fm = np.log(df["fcpo"].resample("MS").mean()).diff()
    j = pd.concat([fm.shift(-1).rename("next"), m["stock"].pct_change().rename("stk"),
                   m["prod"].pct_change().rename("prd"), m["exp"].pct_change().rename("exp")], axis=1).dropna()
    j = j[j.index >= df.index[0]]
    for k, name in (("prd", "Malaysian production (MPOB)"), ("stk", "Malaysian stocks (MPOB)"), ("exp", "Malaysian exports (MPOB)")):
        c = float(j[k].corr(j["next"]))
        rows.append({"id": k, "name": name, "basis": "monthly change vs FCPO in the report month", "corr": c, "r2": c * c})
    out = {"tested": date.today().isoformat(), "weeks": int(len(w)), "from": str(w.index[0].date()), "to": str(w.index[-1].date()),
           "months": int(len(j)), "r2_market": r2(["soy", "brent", "myr"], w, y),
           "rows": [{**r, "corr": round(r["corr"], 3), "r2": round(r["r2"], 3)} for r in rows]}
    (ROOT / "data" / "fcpo_driver_evidence.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
