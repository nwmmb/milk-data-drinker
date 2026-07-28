import csv
import logging
import os
import re
import pandas as pd
from io import StringIO

from .sample_reader import SampleReader
from .._utils import clean_column_names

# Maps raw column names (after clean_column_names) to canonical output names.
# Nutr_Pro comes from "Nutr Pro" after clean_column_names normalizes spaces.
_COLUMN_RENAMES = {
    'Name': 'deposit_id',
    'Date': 'date',
    'Replicate': 'replicate',
    'Fat': 'fat',
    'Protein': 'protein',
    'Lactose': 'lactose',
    'Nutr_Pro': 'nutr_pro',
    'Solids': 'solids',
    'Cal': 'cal',
}

_NUMERIC_COLS = ['fat', 'protein', 'lactose', 'nutr_pro', 'solids', 'cal']
_ID_COLS = ['deposit_id', 'date', 'source_file']


def read_file(file_path: str) -> pd.DataFrame:
    """Read a lactoscope analyzer .xls, .xlsx, or .csv file. Returns a DataFrame."""
    filename = os.path.basename(file_path)
    logging.info(f"Processing: {filename}")

    if file_path.endswith('.xls') or file_path.endswith('.xlsx'):
        csv_content = _xls_to_csv_string(file_path)
    else:
        with open(file_path, 'r') as f:
            csv_content = f.read()

    return _parse_csv_content(csv_content, filename)


def _xls_to_csv_string(path: str) -> str:
    df_raw = pd.read_excel(path, header=None)
    first_data_row = 0
    for i in range(min(10, len(df_raw))):
        if df_raw.iloc[i].notna().any():
            first_data_row = i
            break
    if first_data_row > 0:
        df_raw = df_raw.iloc[first_data_row:].reset_index(drop=True)
    buf = StringIO()
    df_raw.to_csv(buf, index=False, header=False)
    return buf.getvalue()


def _extract_deposit_id(name) -> str | None:
    if pd.isna(name):
        return None
    match = re.search(r'DEP\s*\d+', str(name), re.IGNORECASE)
    return match.group(0) if match else None


def _parse_csv_content(csv_content: str, filename: str) -> pd.DataFrame:
    lines = csv_content.split('\n')
    first_data_line = next((i for i, line in enumerate(lines) if line.strip()), 0)
    if first_data_line > 0:
        logging.debug(f"Skipped {first_data_line} blank row(s) at start of {filename}")
        csv_content = '\n'.join(lines[first_data_line:])

    reader = SampleReader(csv.reader(StringIO(csv_content)))
    frames = []

    while not reader.end_of_file:
        df = reader.read_sample()
        if not df.empty:
            df['source_file'] = filename
            frames.append(df)

    if not frames:
        logging.warning(f"No data extracted from {filename}")
        return pd.DataFrame()

    result = pd.concat(frames, ignore_index=True)
    result = clean_column_names(result)
    result = result.rename(columns=_COLUMN_RENAMES)
    result = result.drop(columns=['Type'], errors='ignore')

    if 'date' in result.columns:
        result['date'] = pd.to_datetime(result['date'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')

    result['deposit_id'] = result['deposit_id'].apply(_extract_deposit_id)

    before = len(result)
    result = result[result['deposit_id'].notna()].reset_index(drop=True)
    dropped = before - len(result)
    if dropped:
        logging.info(f"Dropped {dropped} record(s) with no usable deposit ID from {filename}")

    result = _pivot_to_one_row(result)

    logging.info(f"Extracted {len(result)} records from {filename}")
    return result


def _pivot_to_one_row(df: pd.DataFrame) -> pd.DataFrame:
    mean_df = df[df['replicate'] == 'Mean'].drop(columns='replicate').reset_index(drop=True)
    stddev_df = df[df['replicate'] == 'StdDev'].drop(columns='replicate')

    numeric_cols = [c for c in _NUMERIC_COLS if c in stddev_df.columns]
    id_cols = [c for c in _ID_COLS if c in mean_df.columns]

    stddev_cols = stddev_df[id_cols + numeric_cols].rename(columns={c: f'{c}_stddev' for c in numeric_cols})

    return mean_df.merge(stddev_cols, on=id_cols, how='left')
