"""Daily health check. Exits with an error when a feed is stale, a job keeps failing or a link is broken,
so GitHub emails the repository owner (only them). Run: python scripts/check_health.py
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.now(timezone.utc)


def load(p):
    return json.loads((ROOT / p).read_text(encoding="utf-8"))


def age_days(stamp):
    s = stamp.replace(" UTC", "+00:00").replace(" ", "T")
    if len(s) == 10:
        s += "T00:00:00+00:00"
    return (NOW - datetime.fromisoformat(s)).total_seconds() / 86400


def last_value_date(d, key):
    return max(day for day, v in zip(d["dates"], d[key]) if v is not None)


def months_back(n):
    y, m = NOW.year, NOW.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return f"{y}-{m:02d}"


def main():
    rows, problems = [], []

    def check(name, ok, detail):
        rows.append(("OK" if ok else "PROBLEM", name, detail))
        if not ok:
            problems.append(f"{name}: {detail}")

    p = load("palm-oil-monitor/data.json")
    check("Palm Oil Monitor rebuild", age_days(p["built"]) <= 25, f"built {p['built']}")
    mp = p["mpob"][-1]["month"]
    need = months_back(1) if NOW.day >= 15 else months_back(2)
    check("MPOB data (auto-fetched)", mp >= need, f"data to {mp}; expected {need} — the MPOB fetch job may have failed; check Actions or ask Claude")
    for d, name in (("bursa-monitor", "Bursa"), ("sp500-monitor", "S&P 500")):
        x = load(f"{d}/data.json")
        check(f"{name} daily history", age_days(x["built"]) <= 4, f"built {x['built']}, close of {x['dates'][-1]}")
    w = load("weather-monitor/data.json")
    check("Plantation weather", age_days(w["built"]) <= 3, f"built {w['built']}")
    e = load("energy-monitor/data.json")
    check("Energy and ringgit job", age_days(e["built"]) <= 3, f"built {e['built']}")
    check("Brent and diesel (EIA)", age_days(last_value_date(e, "brent")) <= 10, f"prices to {last_value_date(e, 'brent')}")
    check("USD/MYR (Bank Negara)", age_days(last_value_date(e, "usdmyr")) <= 6, f"rate for {last_value_date(e, 'usdmyr')}")

    # Broken links on the live site (see check_links.py: own pages strictly, other sites only when clearly gone)
    try:
        from check_links import find_broken, short
        pages, n, bad = find_broken()
        check("Links on the live site", not bad,
              f"{pages} pages, {n} links checked" + "".join(f"; BROKEN {c}: {short(u)} (on {short(on[0])})" for u, c, on in bad[:10]))
    except Exception as e:  # the crawl itself failed (network); report but don't hide the other checks
        check("Links on the live site", False, f"link check could not run: {e}")

    # Jobs whose last two runs both failed (one failure usually fixes itself on the next run)
    repo, token = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GH_TOKEN")
    if repo and token:
        r = requests.get(f"https://api.github.com/repos/{repo}/actions/runs", params={"per_page": 100},
                         headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}, timeout=60)
        runs = {}
        for run in r.json().get("workflow_runs", []):
            if run["status"] == "completed" and run["name"] != "Data health check":
                runs.setdefault(run["name"], []).append(run["conclusion"])
        for name, res in sorted(runs.items()):
            done = [c for c in res if c != "cancelled"]
            check(f"Job: {name}", not (len(done) >= 2 and done[0] == "failure" and done[1] == "failure"), "last results: " + ", ".join(done[:3]))

    lines = ["| Status | Feed | Detail |", "| --- | --- | --- |"] + [f"| {s} | {n} | {d} |" for s, n, d in rows]
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("## Data health\n\n" + "\n".join(lines) + "\n")
    print("\n".join(lines))
    if problems:
        print("\nPROBLEMS:\n- " + "\n- ".join(problems))
        sys.exit(1)
    print("\nAll feeds on time and all links working.")


if __name__ == "__main__":
    main()
