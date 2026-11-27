"""India import terms for palm oil, read from the Solvent Extractors' Association of India (SEA) website.

Writes data/india_import_terms.json with:
  - the latest government tariff value (US$/t) for crude palm oil and RBD palmolein, and the date it took effect
    (SEA "Tariff Structure" PDF, linked from https://seaofindia.com/tariff-structure/)
  - the effective import duty on crude palm oil and RBD palmolein (SEA "Import duty on Edible Oils" PDF, linked from
    https://seaofindia.com/import-duty-on-edible-oils/)
Used by the palm-world page for India's landed cost and import margin. Keeps the previous file if a page or PDF
cannot be read, so a site change never breaks the page.
"""
import io
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "india_import_terms.json"
UA = {"User-Agent": "Mozilla/5.0 (compatible; palm-oil-monitor; +https://github.com/BoonWui/BoonWui.github.io)"}
PAGES = {"tariff": "https://seaofindia.com/tariff-structure/", "duty": "https://seaofindia.com/import-duty-on-edible-oils/"}


def pdf_text(page_url):
    html = requests.get(page_url, headers=UA, timeout=60).text
    links = re.findall(r'href="([^"]+\.pdf)"', html, re.I)
    if not links:
        raise ValueError(f"no PDF link on {page_url}")
    data = requests.get(links[0], headers=UA, timeout=90).content
    return links[0], "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)


def parse_tariff(t):
    """First table: header dates, then rows 'Crude Palm Oil 1219 1229 ... 1141'. The last number is the newest."""
    first = t.split("Oils w.e.f.")[1] if "Oils w.e.f." in t else t
    block = first.split("Oils w.e.f.")[0]
    dates = re.findall(r"(\d{1,2})\s*\.\s*(\d{1,2})\s*\.?\s*\n?\s*(\d{2})", block)
    def row(name):
        m = re.search(name + r"\s+([\d,\s]+)", block)
        nums = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", m.group(1))] if m else []
        return nums[-1] if nums else None
    d = dates[-1] if dates else None
    eff = f"20{d[2]}-{int(d[1]):02d}-{int(d[0]):02d}" if d else None
    return {"cpo": row(r"Crude Palm Oil"), "rbd_palmolein": row(r"RBD Palmolein"), "effective": eff}


def parse_tariff_history(t):
    """Every table in the PDF: [[effective date, crude palm oil tariff value US$/t], ...], oldest first."""
    out = {}
    for block in t.split("Oils w.e.f.")[1:]:
        if "Crude Palm Oil" not in block:
            continue
        head, rest = block.split("Crude Palm Oil", 1)
        dates = []
        for chunk in re.split(r"w\.e\.f\.?", head):
            nums = re.findall(r"\d+", chunk)
            if not nums:
                continue
            if len(nums) == 2 and len(nums[0]) in (3, 4):          # "3101." + "26" -> 31.01.26
                nums = [nums[0][:-2], nums[0][-2:], nums[1]]
            if len(nums) < 3:
                continue
            d, m, y = int(nums[0]), int(nums[1]), int(nums[2][-2:])
            if 1 <= d <= 31 and 1 <= m <= 12:
                dates.append(f"20{y:02d}-{m:02d}-{d:02d}")
        vals = [int(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", rest.split("\n")[0])]
        if dates and len(vals) == len(dates):
            out.update(zip(dates, vals))
    return [[d, out[d]] for d in sorted(out)]


# Effective import duty on crude palm oil (basic duty + agri cess + social welfare surcharge), per SEA India.
# Newer changes are added automatically from SEA's duty PDF.
DUTY_SEED = [["2023-01-01", 0.055], ["2024-09-14", 0.275], ["2025-05-31", 0.165], ["2026-09-24", 0.11]]


def parse_duty(t):
    """Row 'Crude Palm Oil 5.00% 5% 10% 11.00% ...': the 4th percentage is the current effective duty."""
    out = {}
    for key, name in (("cpo", r"Crude Palm Oil"), ("rbd_palmolein", r"RBD Palmolein")):
        m = re.search(name + r"\s+([^\n]+)", t)
        pcts = re.findall(r"(\d+(?:\.\d+)?)%|--", m.group(1)) if m else []
        vals = [float(x) if x else None for x in pcts]
        if len(vals) >= 4 and vals[3] is not None:
            out[key] = vals[3] / 100
    m = re.search(r"w\.e\.f\.\s*(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)\.?,?\s+(\d{4})", t)
    if m:
        try:
            out["effective"] = datetime.strptime(f"{m.group(1)} {m.group(2)[:3]} {m.group(3)}", "%d %b %Y").date().isoformat()
        except ValueError:
            pass
    return out


def main():
    old = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
    new = dict(old)
    try:
        url, t = pdf_text(PAGES["tariff"])
        tv = parse_tariff(t)
        if tv["cpo"] and 500 < tv["cpo"] < 3000:
            new["tariff_value_usd"] = {"cpo": tv["cpo"], "rbd_palmolein": tv["rbd_palmolein"]}
            new["tariff_effective"] = tv["effective"]
            new["tariff_source"] = url
            hist = parse_tariff_history(t)
            if len(hist) > 10:
                new["tariff_history"] = hist
    except Exception as e:
        print("tariff value not updated:", e)
    try:
        url, t = pdf_text(PAGES["duty"])
        du = parse_duty(t)
        if du.get("cpo") is not None and 0 <= du["cpo"] < 1:
            new["duty"] = {"cpo": du["cpo"], "rbd_palmolein": du.get("rbd_palmolein")}
            new["duty_effective"] = du.get("effective")
            new["duty_source"] = url
            dh = {d: r for d, r in (old.get("duty_history") or DUTY_SEED)}
            if du.get("effective"):
                dh[du["effective"]] = du["cpo"]
            new["duty_history"] = [[d, dh[d]] for d in sorted(dh)]
    except Exception as e:
        print("duty not updated:", e)
    # change log for alerts: the date India last changed the tariff value or the duty
    for key, eff, val in (("tariff", "tariff_effective", "tariff_value_usd"), ("duty", "duty_effective", "duty")):
        if new.get(eff) and (old.get(eff) != new.get(eff) or old.get(val) != new.get(val)) and old.get(eff):
            log = new.setdefault("changes", [])
            log.append({"what": key, "effective": new[eff], "seen": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "from": (old.get(val) or {}).get("cpo"), "to": (new.get(val) or {}).get("cpo")})
            new["changes"] = log[-20:]
    if new != old:
        new["checked"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        OUT.write_text(json.dumps(new, indent=1), encoding="utf-8")
    print(json.dumps(new, indent=1))


if __name__ == "__main__":
    main()
