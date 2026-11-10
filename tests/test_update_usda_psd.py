import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import update_usda_psd as U  # noqa: E402


def row(country, year, attr, value, commodity="Oil, Palm", cal=("2026", "10")):
    return {"Commodity_Description": commodity, "Country_Name": country, "Market_Year": year, "Attribute_Description": attr,
            "Value": str(value), "Calendar_Year": cal[0], "Month": cal[1]}


def test_build_keeps_countries_and_sums_world():
    rows = [row("China", "2025", "Imports", 3700), row("China", "2026", "Imports", 3800),
            row("India", "2026", "Imports", 8400), row("Kenya", "2026", "Imports", 950),
            row("China", "2026", "Ending Stocks", 409), row("China", "2026", "Imports", 99, commodity="Oil, Soybean")]
    d = U.build(rows)
    assert d["years"] == ["2025", "2026"]
    assert d["countries"]["China"]["imp"] == [3700.0, 3800.0]
    assert d["countries"]["China"]["stocks"] == [None, 409.0]
    assert "Kenya" not in d["countries"]
    assert d["world"]["imp"] == [3700.0, 3800.0 + 8400 + 950]
    assert d["as_of"] == "2026-10"
    assert d["importers"][0] == ["India", 8400.0] and ["Kenya", 950.0] in d["importers"]
