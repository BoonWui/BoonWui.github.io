"""Tests for scripts/update_palm_monitor.py. They use small in-memory samples, so they run offline."""
import io
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import update_palm_monitor as upm  # noqa: E402


class FakeResponse:
    def __init__(self, text="", content=b""):
        self.text, self.content = text, content


def fake_pink_sheet() -> bytes:
    """A miniature World Bank 'Monthly Prices' sheet with the same header layout."""
    header = [None, "Crude oil, Brent", "Coconut oil", "Palm oil", "Soybean oil", "Rapeseed oil", "Sunflower oil"]
    rows = [["junk"] * 7, ["junk"] * 7, ["junk"] * 7, ["Updated on November 03, 2026"] + [None] * 6, header,
            [None, "($/bbl)"] + ["($/mt)"] * 5,
            ["2009M12", 75, 900, 700, 800, 850, 860],          # before 2010: dropped
            ["2026M09", 116.8, 2079, 1180, 1615, 1442, 1393],
            ["2026M10", 125, 2029, 1120, 1546, 1405, 1413]]
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        pd.DataFrame(rows).to_excel(xw, sheet_name="Monthly Prices", header=False, index=False)
    return buf.getvalue()


def test_world_bank_parses_prices(monkeypatch):
    page = '<a href="https://thedocs.worldbank.org/x/CMO-Historical-Data-Monthly.xlsx">Monthly</a>'
    xlsx = fake_pink_sheet()
    monkeypatch.setattr(upm.requests, "get", lambda url, **kw: FakeResponse(text=page) if url == upm.WB_PAGE else FakeResponse(content=xlsx))
    rows, updated, url = upm.world_bank()
    assert updated == "November 03, 2026"
    assert url.endswith("CMO-Historical-Data-Monthly.xlsx")
    assert [r["month"] for r in rows] == ["2026-09", "2026-10"]
    assert rows[-1] == {"month": "2026-10", "palm": 1120.0, "soy": 1546.0, "sun": 1413.0, "rape": 1405.0, "coco": 2029.0, "brent": 125.0}


def test_world_bank_fails_clearly_without_link(monkeypatch):
    monkeypatch.setattr(upm.requests, "get", lambda url, **kw: FakeResponse(text="<html>no file here</html>"))
    with pytest.raises(RuntimeError, match="link not found"):
        upm.world_bank()


def test_oni_parses_seasons(monkeypatch):
    txt = "SEAS  YR   TOTAL   ANOM\nDJF 1999  25.0  -1.5\nJAS 2026  28.70   2.05\nASO 2026  29.23   2.46\n"
    monkeypatch.setattr(upm.requests, "get", lambda url, **kw: FakeResponse(text=txt))
    out = upm.oni()
    assert out == [{"season": "JAS", "year": 2026, "i": 8, "anom": 2.05}, {"season": "ASO", "year": 2026, "i": 9, "anom": 2.46}]


def test_mpob_csv_is_complete_and_ordered():
    rows = upm.mpob()
    months = [r["month"] for r in rows]
    assert months == sorted(months), "MPOB rows must be in date order"
    assert len(months) == len(set(months)), "duplicate MPOB month"
    for r in rows:
        assert r["prod"] > 0 and r["stock"] > 0 and r["exp"] > 0
        assert 500_000 < r["prod"] < 3_000_000, f"implausible production in {r['month']}"


def test_archive_keeps_one_copy_per_edition(tmp_path):
    def data(month, palm, built):
        return {"built": built, "prices": [{"month": month, "palm": palm}], "mpob": [{"month": "2026-09"}]}
    assert upm.archive(data("2026-09", 1180, "2026-10-05"), tmp_path) == "2026-09"
    upm.archive(data("2026-10", 1100, "2026-11-05"), tmp_path)
    upm.archive(data("2026-10", 1120, "2026-11-20"), tmp_path)   # same month again: replaces, does not duplicate
    idx = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert [i["edition"] for i in idx] == ["2026-10", "2026-09"]
    assert idx[0]["palm"] == 1120 and idx[0]["built"] == "2026-11-20"
    assert json.loads((tmp_path / "2026-10.json").read_text(encoding="utf-8"))["prices"][0]["palm"] == 1120


def test_published_data_json_has_expected_shape():
    data = json.loads((ROOT / "palm-oil-monitor" / "data.json").read_text(encoding="utf-8"))
    assert {"built", "sources", "prices", "oni", "mpob"} <= data.keys()
    assert data["prices"][-1]["palm"] > 0
    assert data["oni"][-1]["season"] in upm.SEASONS
