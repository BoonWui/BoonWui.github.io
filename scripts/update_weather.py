"""Build weather-monitor/data.json: rainfall in the main palm oil regions of Malaysia and Indonesia.

Source: Open-Meteo (https://open-meteo.com), ERA5 reanalysis archive plus the 16-day forecast. Data licence CC BY 4.0.
Monthly totals since 2001, a 2001-2020 normal for each calendar month, recent daily rain and the forecast.
Run: python scripts/update_weather.py   (needs requests)
"""
import json
import time
from calendar import monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "weather-monitor" / "data.json"
UA = {"User-Agent": "palm-weather-monitor (github.com/BoonWui/BoonWui.github.io)"}
ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
FORECAST = "https://api.open-meteo.com/v1/forecast"
START = "2001-01-01"
NORMAL_YEARS = range(2001, 2021)
REGIONS = [  # key, name, country, lat, lon (a representative point in each oil palm belt)
    ("sabah", "Sabah (east coast)", "Malaysia", 5.03, 118.33),
    ("sarawak", "Sarawak (Bintulu–Miri)", "Malaysia", 3.17, 113.04),
    ("johor", "Johor", "Malaysia", 2.03, 103.32),
    ("pahang", "Pahang", "Malaysia", 3.81, 103.10),
    ("perak", "Perak (Lower Perak)", "Malaysia", 4.02, 101.02),
    ("riau", "Riau", "Indonesia", 0.51, 101.45),
    ("nsumatra", "North Sumatra", "Indonesia", 2.90, 99.10),
    ("ckalimantan", "Central Kalimantan", "Indonesia", -2.54, 112.95),
]


def get(url, params):
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=UA, timeout=90)
            r.raise_for_status()
            return r.json()
        except Exception as exc:  # network hiccup or rate limit: wait and retry
            print("retry", url, exc)
            time.sleep(20 * (attempt + 1))
    raise RuntimeError(f"Open-Meteo request failed: {url}")


def region_data(key, name, country, lat, lon, end, old=None):
    """Full history on the first run; afterwards only the last ~70 days (Open-Meteo weighs long ranges as many calls)."""
    if old and old.get("monthly") and old.get("recent"):
        start = (end - timedelta(days=70)).replace(day=1)
        monthly = {m: v for m, v in old["monthly"].items() if m < start.strftime("%Y-%m")}
        counts = {m: monthrange(int(m[:4]), int(m[5:]))[1] for m in monthly}
        keep = [r for r in old["recent"] if r[0] < start.isoformat()]
        normal = old["normal"]
    else:
        start, monthly, counts, keep, normal = date.fromisoformat(START), {}, {}, [], None
    a = get(ARCHIVE, {"latitude": lat, "longitude": lon, "start_date": start.isoformat(), "end_date": end.isoformat(),
                      "daily": "precipitation_sum", "timezone": "Asia/Kuala_Lumpur"})
    new = [(d, v) for d, v in zip(a["daily"]["time"], a["daily"]["precipitation_sum"]) if v is not None]
    for d, v in new:
        m = d[:7]
        monthly[m] = monthly.get(m, 0.0) + v
        counts[m] = counts.get(m, 0) + 1
    days = [tuple(r) for r in keep] + new
    last_day = days[-1][0]
    if normal is None:
        normal = []
        for mo in range(1, 13):
            vals = [monthly[f"{y}-{mo:02d}"] for y in NORMAL_YEARS if f"{y}-{mo:02d}" in monthly]
            normal.append(round(sum(vals) / len(vals), 1))
    f = get(FORECAST, {"latitude": lat, "longitude": lon, "daily": "precipitation_sum", "forecast_days": 16, "timezone": "Asia/Kuala_Lumpur"})
    fc = [[d, round(v, 1)] for d, v in zip(f["daily"]["time"], f["daily"]["precipitation_sum"]) if v is not None and d > last_day]
    return {
        "key": key, "name": name, "country": country, "lat": lat, "lon": lon,
        "monthly": {m: round(v, 1) for m, v in monthly.items()},
        "days_in": {m: c for m, c in counts.items() if c < monthrange(int(m[:4]), int(m[5:]))[1]},  # partial months only
        "normal": normal,
        "recent": [[d, round(v, 1)] for d, v in days[-120:]],
        "forecast": fc,
    }


def main():
    end = date.today() - timedelta(days=2)
    old = {}
    if OUT.exists():
        old = {r["key"]: r for r in json.loads(OUT.read_text(encoding="utf-8"))["regions"]}
    regions = []
    for r in REGIONS:
        regions.append(region_data(*r, end, old.get(r[0])))
        time.sleep(3)  # be gentle with the free API
    data = {"built": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "normal_years": "2001–2020",
            "source": "Open-Meteo (ERA5 reanalysis and forecast), CC BY 4.0", "regions": regions}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
    print(f"{len(regions)} regions to {regions[0]['recent'][-1][0]}, forecast to {regions[0]['forecast'][-1][0] if regions[0]['forecast'] else '-'} -> {OUT}")


if __name__ == "__main__":
    main()
