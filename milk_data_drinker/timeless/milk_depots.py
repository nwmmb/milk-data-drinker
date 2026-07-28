import logging
import os
from io import StringIO

import pandas as pd

from ._normalizer import normalize_columns

# Snake_case the camelCase Timeless depot headers.
_COLUMN_RENAMES = {
    "milkdepotid": "milk_depot_id",
    "milkdepotname": "milk_depot_name",
    "milkdepotcontact": "milk_depot_contact",
    "milkdepotaddress1": "milk_depot_address_1",
    "milkdepotaddress2": "milk_depot_address_2",
    "milkdepotpostal": "milk_depot_postal",
    "milkdepotphone": "milk_depot_phone",
    "milkdepotemail": "milk_depot_email",
    "milkdepotorder": "milk_depot_order",
    "milkdepotactive": "milk_depot_active",
    "milkdepotcity": "milk_depot_city",
    "milkdepotstate": "milk_depot_state",
    "milkdepotcountry": "milk_depot_country",
}


def read_file(file_path: str) -> pd.DataFrame:
    """
    Read the Timeless milk depot master/reference list.

    Not a periodic report: a raw download of Timeless' depot table. Its header row is
    plain ASCII but every data-row field value is UTF-16LE (a null byte after each
    character), so the null bytes must be stripped before the content is valid CSV text.
    """
    filename = os.path.basename(file_path)
    logging.info(f"Processing milk depot list: {filename}")

    with open(file_path, "rb") as f:
        raw = f.read()
    cleaned = raw.replace(b"\x00", b"")

    df = pd.read_csv(StringIO(cleaned.decode("latin1")))
    df = normalize_columns(df)
    df = df.rename(columns=_COLUMN_RENAMES)

    if "milk_depot_id" in df.columns:
        df["milk_depot_id"] = df["milk_depot_id"].astype(int)

    logging.info(f"Extracted {len(df)} rows from {filename}")
    return df
