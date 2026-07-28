import logging
import os
import re
from io import StringIO

import pandas as pd

from ._normalizer import normalize_columns

_BR_DELIM = "|||"
_BOTTLE_PATTERN = re.compile(r"([\d.]+)\s*mL:\s*(\d+)")


def read_file(file_path: str) -> pd.DataFrame:
    """Read Timeless wastage as deposit, bottled-batch, or pool events."""
    filename = os.path.basename(file_path)
    logging.info("Processing wastage report: %s", filename)

    df = normalize_columns(_parse_html(file_path))
    df["_source_row"] = range(len(df))
    df = _explode_multi_events(df)
    df = _normalize_values(df)
    df = _parse_bottles(df)
    df = _classify_events(df)
    df = _allocate_bottled_volume(df)
    _validate_events(df)

    df = df.drop(columns=["barcode", "bottles_disposed", "_source_row"], errors="ignore")
    front = [
        "wastage_type", "batch_id", "deposit_id", "pool_id", "disposal_date",
        "wastage_date", "disposal_reason",
    ]
    front = [column for column in front if column in df.columns]
    df = df[front + [column for column in df.columns if column not in front]]
    logging.info("Extracted %d wastage events from %s", len(df), filename)
    return df


def _parse_html(file_path: str) -> pd.DataFrame:
    """Parse HTML while preserving ``<br>`` boundaries inside report cells."""
    with open(file_path, "r", encoding="utf-8") as f:
        html = f.read()
    html = re.sub(r"</?br\s*/?>", _BR_DELIM, html, flags=re.IGNORECASE)
    tables = pd.read_html(StringIO(html))
    if not tables:
        raise ValueError(f"No tables found in {file_path}")
    df = max(tables, key=lambda table: len(table))
    if all(isinstance(column, int) for column in df.columns):
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
    return df


def _explode_multi_events(df: pd.DataFrame) -> pd.DataFrame:
    """Explode aligned ``<br>``-separated event cells into separate rows."""
    splittable = [
        column for column in df.columns
        if df[column].astype(str).str.contains(re.escape(_BR_DELIM), na=False).any()
    ]
    if not splittable:
        return df

    rows = []
    for _, row in df.iterrows():
        splits, count = {}, 1
        for column in splittable:
            value = str(row[column]) if pd.notna(row[column]) else ""
            parts = [part.strip() for part in value.split(_BR_DELIM) if part.strip()]
            splits[column] = parts
            count = max(count, len(parts))
        for index in range(count):
            event = row.copy()
            for column, parts in splits.items():
                # A single value in an otherwise merged row applies to every event.
                event[column] = parts[index] if index < len(parts) else parts[-1] if parts else None
            rows.append(event)
    return pd.DataFrame(rows).reset_index(drop=True)


def _numeric(series: pd.Series, *, percent: bool = False) -> pd.Series:
    values = series.astype(str).str.replace(",", "", regex=False)
    if percent:
        values = values.str.replace("%", "", regex=False)
    return pd.to_numeric(values, errors="coerce")


def _normalize_values(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"waste_disposed_recorded_date": "disposal_date"})
    df["disposal_date"] = pd.to_datetime(df["disposal_date"], errors="coerce")
    for column in ("total_volume_ml", "volume_wasted_ml", "disposed_volume_ml"):
        if column in df.columns:
            df[column] = _numeric(df[column])
    if "percent_of_volume_wasted_ml" in df.columns:
        df["percent_of_volume_wasted_ml"] = _numeric(
            df["percent_of_volume_wasted_ml"], percent=True
        )
    return df


def _parse_bottles(df: pd.DataFrame) -> pd.DataFrame:
    """Split ``bottles_disposed`` into integer size and quantity columns."""
    values = df.get("bottles_disposed", pd.Series([pd.NA] * len(df), index=df.index))
    sizes, quantities = [], []
    for value in values:
        match = _BOTTLE_PATTERN.search(str(value)) if pd.notna(value) else None
        sizes.append(int(float(match.group(1))) if match else pd.NA)
        quantities.append(int(match.group(2)) if match else pd.NA)
    df["bottle_size_ml"] = pd.array(sizes, dtype=pd.Int64Dtype())
    df["quantity_disposed"] = pd.array(quantities, dtype=pd.Int64Dtype())
    return df


def _classify_events(df: pd.DataFrame) -> pd.DataFrame:
    """Classify whole-deposit disposal, bottled-batch disposal, and pool wastage."""
    barcode = df["barcode"].astype(str).str.strip()
    is_deposit = barcode.str.startswith("DEP")
    has_bottles = df["bottle_size_ml"].notna() & df["quantity_disposed"].notna()
    volume_wasted = df.get("volume_wasted_ml", pd.Series(0, index=df.index)).fillna(0)
    is_batch = ~is_deposit & has_bottles
    is_pool = ~is_deposit & ~has_bottles & (volume_wasted > 0)

    df["wastage_type"] = pd.NA
    df.loc[is_deposit, "wastage_type"] = "deposit"
    df.loc[is_batch, "wastage_type"] = "batch"
    df.loc[is_pool, "wastage_type"] = "pool"
    df["deposit_id"] = barcode.where(is_deposit)
    df["batch_id"] = barcode.where(is_batch)
    df["pool_id"] = barcode.where(is_pool)
    df["wastage_date"] = df["disposal_date"].where(is_pool)
    return df


def _allocate_bottled_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Allocate each merged source total by its bottle-size × count weight."""
    for _, indexes in df[df["wastage_type"].eq("batch")].groupby("_source_row").groups.items():
        indexes = list(indexes)
        total = df.loc[indexes[0], "disposed_volume_ml"]
        weights = (
            df.loc[indexes, "bottle_size_ml"].astype(float)
            * df.loc[indexes, "quantity_disposed"].astype(float)
        )
        if pd.isna(total) or total < 0 or weights.sum() <= 0:
            raise ValueError("Bottled batch row has no usable disposed volume or bottle weights")
        allocated = total * weights / weights.sum()
        # Preserve the source total exactly despite floating-point division.
        allocated.iloc[-1] = total - allocated.iloc[:-1].sum()
        df.loc[indexes, "disposed_volume_ml"] = allocated.to_numpy()
    return df


def _validate_events(df: pd.DataFrame) -> None:
    """Reject source rows that cannot be retained in a fact table."""
    invalid = df["wastage_type"].isna() | df["disposal_date"].isna()
    invalid |= df["wastage_type"].eq("deposit") & (
        df["deposit_id"].isna() | df["disposal_reason"].isna() | df["disposed_volume_ml"].isna()
    )
    invalid |= df["wastage_type"].eq("batch") & (
        df["batch_id"].isna() | df["disposal_reason"].isna()
        | df["bottle_size_ml"].isna() | df["quantity_disposed"].isna()
        | df["disposed_volume_ml"].isna()
    )
    invalid |= df["wastage_type"].eq("pool") & (
        df["pool_id"].isna() | df["total_volume_ml"].isna() | df["volume_wasted_ml"].isna()
    )
    if invalid.any():
        raise ValueError(f"Unclassifiable wastage rows: {df.loc[invalid, 'barcode'].astype(str).tolist()}")
