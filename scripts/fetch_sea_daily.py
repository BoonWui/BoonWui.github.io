"""Append SEA India's daily vegetable oil rates to data/sea_daily_prices.csv.

Source: The Solvent Extractors' Association of India publishes a "Quotes" table on its home page
(https://seaofindia.com/) with the day's rates, e.g. CPO C&F Mumbai (US$/t) and CPO ex-Kandla (Rs/t).
Each table row is <value> | <label>. The rates are dated at the top of the table ("6th Nov 26").
USD/INR comes from the ECB euro reference rates (INR per EUR / USD per EUR) for the same or the latest earlier
day: https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip

Run: python scripts/fetch_sea_daily.py            # fetch and append if SEA shows a new date
     python scripts/fetch_sea_daily.py --file x.html   # parse a saved page (tests)
"""
import argparse
import csv
import html as htmlmod
import io
import re
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sea_daily_prices.csv"
SEA = "https://seaofindia.com/"
ECB = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip"
UA = {"User-Agent": "Mozilla/5.0 (compatible; palm-oil-monitor; +https://github.com/BoonWui/BoonWui.github.io)"}

# column -> (label as SEA prints it, lower-case and with spaces squeezed; unit)
ITEMS = {
    "rbd_fob_usd": ("rbd palmolein fob malaysia/ indonesia", "usd"),
    "rbd_cf_mumbai_id_usd": ("rbd palmolein c&f mumbai (indonesia)", "usd"),
    "rbd_cf_mumbai_my_usd": ("rbd palmolein c& f mumbai (malaysia)", "usd"),
    "cpo_fob_id_usd": ("crude palm oil (cpo) fob indonesia", "usd"),
    "cpo_cf_mumbai_usd": ("crude palm oil (cpo) c&f mumbai", "usd"),
    "soy_cif_mumbai_usd": ("soya degum (crude) cif mumbai", "usd"),
    "sun_cif_mumbai_usd": ("sunflower oil (crude) cif mumbai", "usd"),
    "rbd_local_inr": ("rbd palmolein (imported oil)", "inr"),
    "soy_local_inr": ("crude degummed soyabean oil (ex-mumbai) (imported oil)", "inr"),
    "cpo_kandla_inr": ("crude palm oil (5%)(ex-kandla) (imported oil)", "inr"),
}
FIELDS = ["date"] + list(ITEMS) + ["usdinr_ecb"]
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def norm(t):
    return re.sub(r"\s+", " ", htmlmod.unescape(re.sub(r"<[^>]+>", " ", t))).strip().lower()


def get_with_retry(url, tries=3, wait=20, timeout=60):
    """GET with a few retries: runners sometimes fail DNS or TLS for a moment."""
    import time
    import requests
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tries - 1:
                raise
            time.sleep(wait)


def parse(page):
    """Return {'date': 'YYYY-MM-DD', column: value or None} from the SEA home page HTML."""
    m = re.search(r'class="quotes-title">\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{2,4})', page)
    if not m:
        raise ValueError("SEA quotes date not found")
    d, mon, y = int(m.group(1)), MONTHS[m.group(2).lower()], int(m.group(3))
    date = f"{2000 + y if y < 100 else y}-{mon:02d}-{d:02d}"
    i = page.find('class="quotes-title"')
    table = page[i:page.find("</table>", i)]
    rows = re.findall(r"<tr[^>]*>(.*?)</tr>", table, re.S)
    found = {}
    for r in rows:
        cells = [norm(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", r, re.S)]
        if len(cells) < 2:
            continue
        val, label = cells[0], re.sub(r"\s+", " ", cells[1])
        num = re.search(r"(\d[\d,]*(?:\.\d+)?)", val)
        found[label] = float(num.group(1).replace(",", "")) if num and "nq" not in val else None
    out = {"date": date}
    for col, (label, _) in ITEMS.items():
        out[col] = found.get(label)
    if out["cpo_cf_mumbai_usd"] is None or out["cpo_kandla_inr"] is None:
        raise ValueError("SEA table layout changed: CPO C&F Mumbai or ex-Kandla not found")
    return out


def usdinr(date, raw=None):
    """INR per USD from the ECB reference rates on `date` or the latest earlier day."""
    raw = raw or get_with_retry(ECB, timeout=120).content
    z = zipfile.ZipFile(io.BytesIO(raw))
    rows = list(csv.reader(io.TextIOWrapper(z.open(z.namelist()[0]), encoding="utf-8")))
    h = [x.strip() for x in rows[0]]
    iu, ii = h.index("USD"), h.index("INR")
    for r in rows[1:]:  # newest first
        if r[0] <= date and r[iu].strip() not in ("", "N/A") and r[ii].strip() not in ("", "N/A"):
            return round(float(r[ii]) / float(r[iu]), 4)
    return None


def load():
    if not OUT.exists():
        return []
    with open(OUT, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--file")
    a = ap.parse_args(argv)
    try:
        if a.file:
            page = Path(a.file).read_text(encoding="utf-8", errors="ignore")
        else:
            page = get_with_retry(SEA).text
        row = parse(page)
        row["usdinr_ecb"] = usdinr(row["date"])
    except Exception as e:
        print(f"ERROR: {e}")
        return 2
    rows = load()
    if any(r["date"] == row["date"] for r in rows):
        print(f"SEA rates for {row['date']} already saved.")
        return 0
    rows.append({k: ("" if row.get(k) is None else row[k]) for k in FIELDS})
    rows.sort(key=lambda r: r["date"])
    save(rows)
    print(f"Saved SEA rates for {row['date']}: CPO C&F Mumbai ${row['cpo_cf_mumbai_usd']:,.0f}, "
          f"ex-Kandla Rs{row['cpo_kandla_inr']:,.0f}, USD/INR {row['usdinr_ecb']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
