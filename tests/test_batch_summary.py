"""Tests for the Batch Summary report parser."""
import datetime
from pathlib import Path

import pytest

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "batch_summary_example.xls"


@pytest.fixture
def batch_df():
    from milk_data_drinker.timeless.batch_summary import read_file
    return read_file(str(FIXTURE))


def test_fixture_exists():
    assert FIXTURE.exists()


def test_row_count(batch_df):
    assert len(batch_df) == 15


def test_columns(batch_df):
    expected = [
        "batch_id", "created_date", "bottle_size_ml", "milk_type",
        "original_volume_ml", "fat", "protein", "lactose",
        "expiry_date", "milk_approved", "milk_status",
    ]
    assert list(batch_df.columns) == expected


def test_footer_stripped(batch_df):
    assert not batch_df["batch_id"].str.contains("Page").any()


def test_data_integrity(batch_df):
    """Verify columns contain correct data types and values."""
    assert batch_df["milk_status"].isin(
        ["Dispensed", "Active", "Disposed"]
    ).all()
    assert batch_df["milk_approved"].isin(
        ["Approved", "Not Approved"]
    ).all()
    for val in batch_df["expiry_date"]:
        assert val is None or isinstance(val, datetime.date)


def test_created_date_is_date_not_datetime(batch_df):
    for val in batch_df["created_date"]:
        if val is not None:
            assert type(val) is datetime.date


def test_bottle_size_extracted(batch_df):
    assert batch_df["bottle_size_ml"].notna().sum() >= 14
    valid_sizes = {30, 45, 50, 60, 90, 100, 120, 240}
    assert set(batch_df["bottle_size_ml"].dropna().unique()).issubset(valid_sizes)


def test_volume_is_numeric(batch_df):
    assert batch_df["original_volume_ml"].dtype == "float64"
    assert (batch_df["original_volume_ml"] > 0).all()


def test_batch_id_format(batch_df):
    for bid in batch_df["batch_id"]:
        assert "-" in bid, f"batch_id should be in NNNNNN-N format, got {bid}"


def test_first_row_values(batch_df):
    row = batch_df.iloc[0]
    assert row["batch_id"] == "015847-4"
    assert row["created_date"] == datetime.date(2025, 2, 24)
    assert row["bottle_size_ml"] == 60
    assert row["original_volume_ml"] == 3720.0
    assert row["fat"] == 3.92
    assert row["milk_status"] == "Dispensed"
    assert row["milk_approved"] == "Approved"
    assert row["expiry_date"] == datetime.date(2025, 11, 1)
