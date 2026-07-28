import logging
import os
import pandas as pd

from ._normalizer import normalize, normalize_columns, split_id_name

# Timeless appends 4 summary/total rows at the end of every dispensation export
_SUMMARY_ROWS = 4
_DATE_COLS = ["dispense_date", "date_cancelled"]

# Recipient ID prefix → type. PAT=outpatient, HOS=hospital, MBK=milk bank, RFA=research facility.
_RECIPIENT_TYPES = {
    "PAT": "outpatient",
    "HOS": "hospital",
    "MBK": "milk_bank",
    "RFA": "research_facility",
}


def _recipient_type(recipient_id) -> str | None:
    if not isinstance(recipient_id, str) or len(recipient_id) < 3:
        return None
    return _RECIPIENT_TYPES.get(recipient_id[:3].upper())


def read_file(file_path: str) -> pd.DataFrame:
    filename = os.path.basename(file_path)
    logging.info(f"Processing dispensation report: {filename}")

    df = normalize(file_path)
    df = df.iloc[:-_SUMMARY_ROWS].reset_index(drop=True)
    df = normalize_columns(df)

    # "Recipient" is "PREFIX#####:Name"; split into id + name and derive the type from the
    # prefix. The name is kept so ingest can populate the recipient reference tables
    # (facilities keep names; outpatient names are dropped) — it is not stored on the row.
    if "recipient" in df.columns:
        df["recipient_id"], df["recipient_name"] = split_id_name(df["recipient"])
        df["recipient_type"] = df["recipient_id"].map(_recipient_type)
        df = df.drop(columns=["recipient"])

    for col in _DATE_COLS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    front = [c for c in ["recipient_id", "recipient_type", "recipient_name"] if c in df.columns]
    df = df[front + [c for c in df.columns if c not in front]]

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
