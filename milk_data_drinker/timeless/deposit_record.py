import logging
import os
import pandas as pd

from ._normalizer import normalize, normalize_columns, split_id_name

# Timeless appends 2 summary/total rows at the end of every deposit record export
_SUMMARY_ROWS = 2
# Timeless formats volume fields with commas (e.g. "3,790.00")
_VOLUME_COLS = ["volume_remaining_ml", "used_volume_ml", "total_volume_ml"]
_DATE_COLS = ["date_received", "expiry_date"]


def read_file(file_path: str) -> pd.DataFrame:
    filename = os.path.basename(file_path)
    logging.info(f"Processing deposit record report: {filename}")

    df = normalize(file_path)
    df = df.iloc[:-_SUMMARY_ROWS].reset_index(drop=True)
    df = normalize_columns(df)
    df = df.rename(columns={"deposit": "deposit_id"})

    # "Donor/Milk Bank" contains "DON012345: Lastname Firstname" in real exports;
    # keep the DON##### id, drop the combined name (the donors table owns donor names)
    if "donor_milk_bank" in df.columns:
        df["donor_id"], _ = split_id_name(df["donor_milk_bank"])
        df = df.drop(columns=["donor_milk_bank"])

    for col in _VOLUME_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col].astype(str).str.replace(",", "", regex=False),
                errors="coerce",
            )

    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    front = [c for c in ["donor_id", "deposit_id"] if c in df.columns]
    df = df[front + [c for c in df.columns if c not in front]]

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
