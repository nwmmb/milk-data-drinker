"""Parser tests for the Timeless wastage report."""
from pathlib import Path

import pandas as pd
import pytest

from milk_data_drinker.timeless.wastage import read_file

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "wastage_report_example.xls"
_RAW_ROWS = 64
_EXPLODED_ROWS = 104


@pytest.fixture(scope="module")
def df() -> pd.DataFrame:
    assert _FIXTURE.exists(), f"missing test fixture: {_FIXTURE}"
    return read_file(str(_FIXTURE))


def test_multi_event_rows_explode(df):
    assert len(df) == _EXPLODED_ROWS
    assert len(df) > _RAW_ROWS
    events = df[df["batch_id"] == "015326-2"]
    assert len(events) == 2
    assert events["disposal_date"].nunique() == 2


def test_merged_batch_volume_is_allocated_by_bottle_volume(df):
    """015324-4 has 1, 27, and 23 sixty-mL bottles in one merged source row."""
    events = df[df["batch_id"] == "015324-4"].sort_values("quantity_disposed")
    assert events["quantity_disposed"].tolist() == [1, 23, 27]
    assert events["bottle_size_ml"].tolist() == [60, 60, 60]
    assert events["disposed_volume_ml"].tolist() == [60.0, 1380.0, 1620.0]
    assert events["disposed_volume_ml"].sum() == 3060.0


def test_bottle_size_and_quantity_parsed(df):
    disposed = df[df["wastage_type"] == "batch"]
    assert len(disposed) > 0
    assert disposed["bottle_size_ml"].notna().all()
    assert disposed["quantity_disposed"].notna().all()
    assert set(disposed["bottle_size_ml"].unique()) <= {30, 45, 50, 60, 90, 100, 120, 240}
    assert (disposed["quantity_disposed"] >= 1).all()


def test_event_classification_preserves_all_source_shapes(df):
    deposits = df[df["wastage_type"] == "deposit"]
    batches = df[df["wastage_type"] == "batch"]
    pools = df[df["wastage_type"] == "pool"]
    assert len(deposits) > 0 and len(batches) > 0 and len(pools) > 0
    assert deposits["deposit_id"].str.startswith("DEP").all()
    assert batches["batch_id"].notna().all()
    assert pools["pool_id"].notna().all()
    assert not (df[["batch_id", "deposit_id", "pool_id"]].notna().sum(axis=1) != 1).any()


def test_pool_wastage_retains_volume_only_event(df):
    pool = df[df["pool_id"] == "015330"].iloc[0]
    assert str(pool["wastage_date"].date()) == "2026-01-06"
    assert pool["total_volume_ml"] == 16240.0
    assert pool["volume_wasted_ml"] == 1900.0
    assert pool["percent_of_volume_wasted_ml"] == 12.0


def test_canonical_columns(df):
    expected = {
        "wastage_type", "batch_id", "deposit_id", "pool_id", "disposal_date",
        "wastage_date", "disposal_reason", "disposed_volume_ml", "bottle_size_ml",
        "quantity_disposed", "total_volume_ml", "volume_wasted_ml",
        "percent_of_volume_wasted_ml",
    }
    assert expected <= set(df.columns)
    assert "barcode" not in df.columns
    assert "bottles_disposed" not in df.columns


def test_disposal_date_is_datetime(df):
    assert pd.api.types.is_datetime64_any_dtype(df["disposal_date"])
    assert df["disposal_date"].notna().all()
