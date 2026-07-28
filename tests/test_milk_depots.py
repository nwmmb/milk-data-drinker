"""Parser tests for the Timeless milk depot master list.

The depot export is a raw table download whose data rows are UTF-16LE-contaminated
(a null byte after each character) under a plain-ASCII header; the parser strips the
null bytes and renames the camelCase headers to canonical snake_case.
"""
from pathlib import Path

import pytest

from milk_data_drinker.timeless.milk_depots import read_file

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "milk_depots_example.csv"


@pytest.fixture(scope="module")
def df():
    assert _FIXTURE.exists(), f"missing test fixture: {_FIXTURE}"
    return read_file(str(_FIXTURE))


def test_canonical_columns(df):
    """Every column the _ingest_milk_depots handler reads must be present."""
    expected = {
        "milk_depot_id", "milk_depot_name", "milk_depot_contact",
        "milk_depot_address_1", "milk_depot_address_2",
        "milk_depot_city", "milk_depot_state", "milk_depot_country",
        "milk_depot_postal", "milk_depot_phone", "milk_depot_email",
        "milk_depot_order", "milk_depot_active",
    }
    assert expected == set(df.columns)


def test_rows_parse_despite_utf16_contamination(df):
    """Null-byte stripping must yield clean values — no residual \\x00 anywhere."""
    assert len(df) > 0
    assert df["milk_depot_id"].is_unique
    for col in df.columns:
        assert not df[col].astype(str).str.contains("\x00").any(), col


def test_depot_id_is_int(df):
    assert df["milk_depot_id"].dtype.kind == "i"
