import logging
import re
import os

import pandas as pd

from ._normalizer import normalize, normalize_columns

_BOTTLE_COL_RE = re.compile(r"^original_bottles_(\d+)_\d+_oz_\*$")


def read_file(file_path: str) -> pd.DataFrame:
    filename = os.path.basename(file_path)
    logging.info(f"Processing batch summary report: {filename}")

    _KEEP = [
        "batch_id", "created_date", "bottle_size_ml", "milk_type",
        "original_volume_ml", "fat", "protein", "lactose",
        "expiry_date", "milk_approved", "milk_status",
    ]

    df = normalize(file_path)

    if "Batch" not in df.columns or len(df) == 0:
        logging.warning(f"No batch data in {filename} — returning empty DataFrame")
        return pd.DataFrame(columns=_KEEP)

    df = normalize_columns(df)

    # Strip pagination footer ("Page 1 of 1" in the Batch column)
    footer_mask = df["batch"].astype(str).str.startswith("Page")
    df = df[~footer_mask].reset_index(drop=True)

    # Extract bottle size from Original Bottles columns (one non-zero per row)
    bottle_cols = {}
    for col in df.columns:
        m = _BOTTLE_COL_RE.match(col)
        if m:
            bottle_cols[col] = int(m.group(1))

    df["bottle_size_ml"] = pd.array([pd.NA] * len(df), dtype=pd.Int64Dtype())
    for col, size in bottle_cols.items():
        df[col] = pd.to_numeric(df[col], errors="coerce")
        mask = df[col].fillna(0) > 0
        df.loc[mask, "bottle_size_ml"] = size

    # Rename to canonical names
    df = df.rename(columns={
        "batch": "batch_id",
        "original_volume_oz": "original_volume_ml",
        "created_on": "created_date",
    })

    # Convert types
    df["created_date"] = pd.to_datetime(df["created_date"], errors="coerce").dt.date
    df["original_volume_ml"] = pd.to_numeric(
        df["original_volume_ml"], errors="coerce"
    )
    df["expiry_date"] = pd.to_datetime(df["expiry_date"], errors="coerce").dt.date
    for col in ("fat", "protein", "lactose"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop columns we don't need
    drop_cols = (
        ["donor_milk_bank", "created_from", "cal_oz", "g_dl",
         "location", "remaining_volume_oz"]
        + list(bottle_cols.keys())
        + [c for c in df.columns if c.startswith("remaining_bottles_")]
    )
    df = df.drop(columns=[c for c in drop_cols if c in df.columns])

    df = df[[c for c in _KEEP if c in df.columns]]

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
