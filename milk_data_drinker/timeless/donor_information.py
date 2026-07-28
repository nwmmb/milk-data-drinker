import logging
import os
import pandas as pd

from ._normalizer import normalize, normalize_columns


def read_file(file_path: str) -> pd.DataFrame:
    filename = os.path.basename(file_path)
    logging.info(f"Processing donor information report: {filename}")

    df = normalize(file_path)
    df = normalize_columns(df)

    # donor_barcode carries the DON##### prefix and is the canonical donor_id; the report's
    # separate numeric donor_id is dropped (it would collide on the rename).
    df = df.drop(columns=["donor_id"], errors="ignore").rename(
        columns={"donor_barcode": "donor_id"}
    )
    df = df.rename(columns={
        "1st_microbiology_results": "first_microbiology_results",
        "2nd_microbiology_results": "second_microbiology_results",
        "3rd_microbiology_results": "third_microbiology_results",
        "baby_s_gestational_age_at_birth": "baby_gestational_age_at_birth",
    })

    for col in df.columns:
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
