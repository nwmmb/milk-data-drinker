import re
from io import StringIO

import pandas as pd

from .._utils import clean_column_names


def normalize(file_path: str) -> pd.DataFrame:
    """
    Convert any supported Timeless file format to a raw DataFrame.
    Tries HTML (for Timeless .xls exports that are actually HTML), then Excel, then CSV.
    Returns the DataFrame with original column names — call normalize_columns() to clean them.
    """
    for strategy in (_try_html, _try_excel, _try_csv):
        df = strategy(file_path)
        if df is not None:
            return df
    raise ValueError(f"Could not parse file with any available format: {file_path}")


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Replace special characters with underscores and lowercase all column names."""
    df = clean_column_names(df)
    df.columns = df.columns.str.lower()
    return df


def split_id_name(series: pd.Series) -> tuple[pd.Series, pd.Series]:
    """
    Split a Timeless 'ID: Name' column into separate ID and name Series.
    Handles 'DON012345: Lastname, Firstname', 'DON012345 : Name', and bare 'DON012345'
    (no colon, name absent) — the last case yields None for the name.
    """
    parts = series.astype(str).str.split(":", n=1, expand=True)
    ids = parts[0].str.strip()
    names = parts[1].str.strip() if parts.shape[1] > 1 else pd.Series([None] * len(series), index=series.index)
    names = names.replace("", None)
    return ids, names


def _try_html(file_path: str) -> pd.DataFrame | None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            html = f.read()
        # Timeless packs multi-value cells with <br> tags (e.g. multiple follow-up
        # dates). Substitute before pd.read_html so the values aren't collapsed.
        html = re.sub(r"</?br\s*/?>", " | ", html, flags=re.IGNORECASE)
        # Office-HTML exports from Timeless use malformed self-closing <td/> and
        # <th/> tags that pandas cannot parse; normalise to proper opening tags.
        html = re.sub(r"<(t[dh])\s*/>", r"<\1>", html, flags=re.IGNORECASE)
        tables = pd.read_html(StringIO(html))
        if not tables:
            return None
        df = max(tables, key=lambda t: len(t))
        # Timeless HTML exports sometimes omit <th> tags; pandas assigns integer indices
        if all(isinstance(c, int) for c in df.columns):
            df.columns = df.iloc[0]
            df = df.iloc[1:].reset_index(drop=True)
        return df
    except Exception:
        return None


def _try_excel(file_path: str) -> pd.DataFrame | None:
    try:
        return pd.read_excel(file_path, sheet_name=0)
    except Exception:
        return None


def _try_csv(file_path: str) -> pd.DataFrame | None:
    try:
        return pd.read_csv(file_path, encoding="latin1")
    except Exception:
        return None
