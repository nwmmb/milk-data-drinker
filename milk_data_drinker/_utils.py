import pandas as pd


def clean_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize column names to snake_case, removing special characters."""
    clean = {}
    for col in df.columns:
        c = str(col)
        for ch in (' ', ',', ';', ':', '!', '(', ')', '\n', '\t', '=', '{', '}', '/', '-', '.', "'", '?'):
            c = c.replace(ch, '_')
        while '__' in c:
            c = c.replace('__', '_')
        clean[col] = c.strip('_')
    return df.rename(columns=clean)
