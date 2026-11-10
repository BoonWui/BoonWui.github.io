import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import add_mpob as A  # noqa: E402

ROWS = [
    {"month": "2026-07", "production_t": 1_800_000, "imports_t": 50_000, "exports_t": 1_400_000, "domestic_t": 350_000, "end_stocks_t": 2_600_000},
    {"month": "2026-08", "production_t": 1_800_000, "imports_t": 50_000, "exports_t": 1_300_000, "domestic_t": 400_000, "end_stocks_t": 2_750_000},
]


def test_next_month():
    assert A.next_month("2026-09") == "2026-10"
    assert A.next_month("2026-12") == "2027-01"


def test_num_accepts_commas():
    assert A.num("1,950,000") == 1_950_000


def test_new_month_domestic_is_residual():
    new, row, warn = A.build_row(ROWS, "2026-09", 1_900_000, 60_000, 1_350_000, 2_950_000)
    assert len(new) == 3 and row["domestic_t"] == 2_750_000 + 1_900_000 + 60_000 - 1_350_000 - 2_950_000
    assert warn == []


def test_typo_is_flagged():
    _, _, warn = A.build_row(ROWS, "2026-09", 190_000, 60_000, 1_350_000, 1_200_000)
    assert any("production_t" in w for w in warn)


def test_negative_domestic_is_an_error():
    with pytest.raises(ValueError):
        A.build_row(ROWS, "2026-09", 1_900_000, 60_000, 1_350_000, 3_500_000)


def test_skipping_a_month_is_an_error():
    with pytest.raises(ValueError):
        A.build_row(ROWS, "2026-10", 1_900_000, 60_000, 1_350_000, 2_950_000)


def test_correction_rebalances_next_month():
    rows, _, _ = A.build_row(ROWS, "2026-09", 1_900_000, 60_000, 1_350_000, 2_950_000)
    new, _, warn = A.build_row(rows, "2026-08", 1_800_000, 50_000, 1_300_000, 2_700_000)
    assert new[1]["domestic_t"] == 2_600_000 + 1_800_000 + 50_000 - 1_300_000 - 2_700_000
    assert new[2]["domestic_t"] == 2_700_000 + 1_900_000 + 60_000 - 1_350_000 - 2_950_000
    assert any("updated" in w for w in warn)


def test_first_row_cannot_be_rebuilt():
    with pytest.raises(ValueError):
        A.build_row(ROWS, "2026-07", 1_800_000, 50_000, 1_400_000, 2_650_000)


def test_dom_cross_check():
    _, _, warn = A.build_row(ROWS, "2026-09", 1_900_000, 60_000, 1_350_000, 2_950_000, dom=500_000)
    assert any("MPOB domestic" in w for w in warn)
