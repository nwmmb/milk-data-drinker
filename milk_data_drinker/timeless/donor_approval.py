import logging
import os
import pandas as pd

from ._normalizer import normalize_columns

# Timeless exports 5 metadata/title rows before the actual column header row
_HEADER_ROWS = 5


def read_file(file_path: str) -> pd.DataFrame:
    filename = os.path.basename(file_path)
    logging.info(f"Processing donor approval report: {filename}")

    df = pd.read_csv(file_path, skiprows=_HEADER_ROWS, encoding="latin1")
    df = normalize_columns(df)

    if "approved_date" in df.columns:
        df["approved_date"] = pd.to_datetime(df["approved_date"], errors="coerce")

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
