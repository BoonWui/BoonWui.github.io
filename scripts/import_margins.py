"""India and China palm oil import margins, from free web data, written to data/import_margins.json.

Method (from the site owner's import-margin workbook), all per tonne:
  India (crude palm oil):  value = (CIF Mumbai + duty rate x government tariff value) x USD/INR
                           landed = value + 1,203 rupees port handling + 5% VAT on (value + port)
                           margin = ex-Kandla local price - landed          (shown in US$)
  China (refined olein):   CNF = RBD olein FOB + ~US$20 freight (estimate)
                           cost = CNF x 1.09 duty x 1.09 VAT + 100 yuan port handling
                           margin = Dalian palm oil (main contract) - cost  (shown in US$)
Inputs: SEA India daily quotes (data/sea_daily_prices.csv, plus data/sea_daily_history.csv from web-archive copies),
India's tariff value and duty history (data/india_import_terms.json, from SEA), USD/CNY (data/bmd_fcpo.json) and
Dalian palm oil daily closes (Sina Finance, continuous main contract P0).
"""
import csv
import json
import re
import time
from bisect import bisect_right
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "import_margins.json"
KLINE = "https://stock2.finance.sina.com.cn/futures/api/jsonp.php/var%20x=/InnerFuturesNewService.getDailyKLine"
H = {"Referer": "https://finance.sina.com.cn/", "User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)"}
IN_VAT, IN_PORT_INR = 0.05, 1203
CN_DUTY, CN_VAT, CN_PORT_CNY, CN_FREIGHT = 0.09, 0.09, 100, 20


def asof(series, date):
    """Value of a [[date, value], ...] series (sorted) in force on `date`."""
    keys = [d for d, _ in series]
    i = bisect_right(keys, date) - 1
    return series[i][1] if i >= 0 else None


def sea_rows():
    rows = {}
    for name in ("sea_daily_history.csv", "sea_daily_prices.csv"):   # daily file wins on the same date
        f = DATA / name
        if f.exists():
            with open(f, encoding="utf-8", newline="") as fh:
                for r in csv.DictReader(fh):
                    rows[r["date"]] = r
    return [rows[d] for d in sorted(rows)]


def num(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None


def dalian(tries=4):
    for k in range(tries):
        try:
            t = requests.get(KLINE, params={"symbol": "P0"}, headers=H, timeout=60).text
            rows = json.loads(re.search(r"\((\[.*\])\)", t, re.S).group(1))
            return {r["d"]: float(r["c"]) for r in rows if float(r["c"]) > 0}
        except Exception as e:
            print("Dalian prices not read:", str(e)[:80])
            time.sleep(15 * (k + 1))
    return {}


def main():
    terms = json.loads((DATA / "india_import_terms.json").read_text(encoding="utf-8"))
    tariff = terms.get("tariff_history") or [[terms["tariff_effective"], terms["tariff_value_usd"]["cpo"]]]
    duty = terms.get("duty_history") or [[terms["duty_effective"], terms["duty"]["cpo"]]]
    ex = json.loads((DATA / "bmd_fcpo.json").read_text(encoding="utf-8")).get("extra", {})
    cny = sorted(ex.get("usdcny") or [])
    dce = dalian()
    dce_dates = sorted(dce)
    india, china = [], []
    for r in sea_rows():
        d = r["date"]
        cif, kandla, fx = num(r.get("cpo_cf_mumbai_usd")), num(r.get("cpo_kandla_inr")), num(r.get("usdinr_ecb"))
        tv, rate = asof(tariff, d), asof(duty, d)
        if cif and kandla and fx and tv and rate is not None:
            value = (cif + rate * tv) * fx
            landed = value + IN_PORT_INR + IN_VAT * (value + IN_PORT_INR)
            india.append([d, round(cif), round(landed / fx, 1), round(kandla / fx, 1), round((kandla - landed) / fx, 1), rate, tv])
        fob, fxc = num(r.get("rbd_fob_usd")), asof(cny, d)
        i = bisect_right(dce_dates, d) - 1
        if fob and fxc and i >= 0 and (datetime.fromisoformat(d) - datetime.fromisoformat(dce_dates[i])).days <= 4:
            cnf = fob + CN_FREIGHT
            cost = cnf * (1 + CN_DUTY) * (1 + CN_VAT) + CN_PORT_CNY / fxc
            local = dce[dce_dates[i]] / fxc
            china.append([d, round(cnf), round(cost, 1), round(local, 1), round(local - cost, 1)])
    out = {
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "fields_india": ["date", "cif_usd", "landed_usd", "kandla_usd", "margin_usd", "duty", "tariff_value_usd"],
        "fields_china": ["date", "cnf_usd", "cost_usd", "dalian_usd", "margin_usd"],
        "india": india, "china": china,
        "india_terms": {"tariff_effective": terms.get("tariff_effective"), "duty_effective": terms.get("duty_effective"),
                        "changes": terms.get("changes", [])},
    }
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(len(india), "India days,", len(china), "China days; latest",
          india[-1] if india else None, china[-1] if china else None)


if __name__ == "__main__":
    main()
