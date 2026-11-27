"""CFTC Commitments of Traders: managed-money long / short for 25 commodity markets.

Writes data/cftc_managed_money.json for the cftc-positions page.
Sources (both free, no key):
  * CFTC Public Reporting: Disaggregated, futures-and-options combined (dataset kh3c-gbw2), US exchanges.
  * ICE Futures Europe COT history CSVs (www.ice.com/publicdocs/futures/COTHist<year>.csv): Brent and Gasoil,
    "Futures and Options" (combined) rows, same layout as the CFTC report.
Futures-and-options combined is the series LSEG/Reuters shows as MLNG / MSHT, so the numbers match it.
Data are as of Tuesday, released Friday 15:30 US Eastern.
"""
import csv
import io
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "cftc_managed_money.json"
YEARS = 3
CFTC_URL = "https://publicreporting.cftc.gov/resource/kh3c-gbw2.json"
ICE_URL = "https://www.ice.com/publicdocs/futures/COTHist{year}.csv"
UA = {"User-Agent": "Mozilla/5.0 (compatible; boonwui-research/1.0)"}

# id, display name, group, source, code (CFTC contract code or ICE market name prefix)
MARKETS = [
    ("wti",    "WTI crude (NYMEX)",       "Energy",     "cftc", "067651"),
    ("wtiice", "WTI crude (ICE)",         "Energy",     "cftc", "067411"),
    ("brent",  "Brent crude (ICE)",       "Energy",     "ice",  "ICE Brent Crude Futures and Options"),
    ("gasoil", "Gasoil (ICE)",            "Energy",     "ice",  "ICE Gasoil Futures and Options"),
    ("rbob",   "RBOB gasoline",           "Energy",     "cftc", "111659"),
    ("ulsd",   "NY Harbor ULSD",          "Energy",     "cftc", "022651"),
    ("natgas", "Natural gas (NYMEX)",     "Energy",     "cftc", "023651"),
    ("gold",   "Gold",                    "Metals",     "cftc", "088691"),
    ("silver", "Silver",                  "Metals",     "cftc", "084691"),
    ("plat",   "Platinum",                "Metals",     "cftc", "076651"),
    ("pall",   "Palladium",               "Metals",     "cftc", "075651"),
    ("copper", "Copper (COMEX)",          "Metals",     "cftc", "085692"),
    ("soy",    "Soybeans",                "Oilseeds",   "cftc", "005602"),
    ("soyoil", "Soybean oil",             "Oilseeds",   "cftc", "007601"),
    ("soymeal","Soybean meal",            "Oilseeds",   "cftc", "026603"),
    ("corn",   "Corn",                    "Grains",     "cftc", "002602"),
    ("wheat",  "Wheat (Chicago SRW)",     "Grains",     "cftc", "001602"),
    ("kcwheat","Wheat (Kansas HRW)",      "Grains",     "cftc", "001612"),
    ("sugar",  "Sugar No. 11",            "Softs",      "cftc", "080732"),
    ("cocoa",  "Cocoa (New York)",        "Softs",      "cftc", "073732"),
    ("coffee", "Coffee C",                "Softs",      "cftc", "083731"),
    ("cotton", "Cotton No. 2",            "Softs",      "cftc", "033661"),
    ("lcattle","Live cattle",             "Livestock",  "cftc", "057642"),
    ("fcattle","Feeder cattle",           "Livestock",  "cftc", "061641"),
    ("hogs",   "Lean hogs",               "Livestock",  "cftc", "054642"),
]


def get(url, params=None, tries=5):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=90)
            if r.status_code == 200:
                return r
            print(f"  HTTP {r.status_code} {url}")
        except requests.RequestException as e:
            print(f"  retry {i + 1}: {e.__class__.__name__}")
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"could not fetch {url}")


def cftc_rows(start):
    codes = [m[4] for m in MARKETS if m[3] == "cftc"]
    rows, offset = [], 0
    while True:
        r = get(CFTC_URL, {
            "$select": "cftc_contract_market_code,report_date_as_yyyy_mm_dd,open_interest_all,m_money_positions_long_all,m_money_positions_short_all",
            "$where": "report_date_as_yyyy_mm_dd >= '%sT00:00:00' AND cftc_contract_market_code in(%s)" % (start, ",".join("'%s'" % c for c in codes)),
            "$order": "report_date_as_yyyy_mm_dd", "$limit": 5000, "$offset": offset})
        page = r.json()
        rows += page
        if len(page) < 5000:
            return rows
        offset += 5000


def ice_rows(start):
    out = []
    for year in range(int(start[:4]), date.today().year + 1):
        try:
            text = get(ICE_URL.format(year=year)).content.decode("utf-8-sig")
        except RuntimeError as e:
            print(f"  ICE {year}: {e}")
            continue
        for r in csv.DictReader(io.StringIO(text)):
            if r.get("FutOnly_or_Combined", "").strip() != "Combined":
                continue
            d = datetime.strptime(r["As_of_Date_Form_MM/DD/YYYY"].strip()[:10], "%m/%d/%Y").date().isoformat()
            if d >= start:
                out.append((r["Market_and_Exchange_Names"].strip(), d, r["Open_Interest_All"], r["M_Money_Positions_Long_All"], r["M_Money_Positions_Short_All"]))
    return out


def num(x):
    try:
        return int(float(str(x).replace(",", "")))
    except ValueError:
        return None


def main():
    start = (date.today() - timedelta(days=365 * YEARS + 14)).isoformat()
    hist = {m[0]: {} for m in MARKETS}
    by_code = {m[4]: m[0] for m in MARKETS if m[3] == "cftc"}
    for r in cftc_rows(start):
        mid = by_code.get(r.get("cftc_contract_market_code"))
        if mid:
            hist[mid][r["report_date_as_yyyy_mm_dd"][:10]] = [num(r.get("m_money_positions_long_all")), num(r.get("m_money_positions_short_all")), num(r.get("open_interest_all"))]
    ice = [m for m in MARKETS if m[3] == "ice"]
    for name, d, oi, lg, sh in ice_rows(start):
        for m in ice:
            if name.startswith(m[4]):
                hist[m[0]][d] = [num(lg), num(sh), num(oi)]
    markets = []
    for mid, name, group, src, code in MARKETS:
        h = [[d] + v for d, v in sorted(hist[mid].items()) if v[0] is not None and v[1] is not None]
        print(f"  {name:<24} {len(h)} weeks, last {h[-1][0] if h else '-'}")
        markets.append({"id": mid, "name": name, "group": group, "source": "ICE Futures Europe" if src == "ice" else "CFTC", "code": code, "hist": h})
    latest = max((m["hist"][-1][0] for m in markets if m["hist"]), default=None)
    if not latest:
        raise SystemExit("No data fetched")
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    if old.get("markets") == markets:
        print("Nothing new; file left unchanged.")
        return
    OUT.write_text(json.dumps({
        "updated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "latest": latest,
        "report": "Disaggregated Commitments of Traders, futures and options combined, managed money",
        "markets": markets,
    }, separators=(",", ":")), encoding="utf-8")
    print(f"Latest report {latest}. Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
