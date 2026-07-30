"""Timeless source-format recovery with no nwmmb-db canonical transforms."""

from __future__ import annotations

import re
from io import StringIO
from pathlib import Path

import pandas as pd


SOURCE_PROFILES = {
    "dispensation": {"Order Number", "Bottle Size (mL)", "Dispense Date", "Recipient"},
    "deposit_record": {"Deposit", "Expiry Date", "Volume Remaining (mL)", "Donor/Milk Bank"},
    "donor_information": {"Donor Barcode", "Passed Screening"},
    "wastage_report": {"Barcode", "Bottles Disposed", "Disposal Reason"},
    "batch_summary": {"Batch", "Created On", "Created From", "Original Volume(oz)"},
}

_SUMMARY_ROWS = {"deposit_record": 2, "dispensation": 4}


def recover_table(file_path: str | Path) -> pd.DataFrame:
    """Recover HTML-as-XLS, Excel, or CSV while retaining source headers/order."""
    for strategy in (_try_html, _try_excel, _try_csv):
        frame = strategy(file_path)
        if frame is not None:
            return frame
    raise ValueError(f"Could not recover a Timeless source table from {file_path}")


def prepare_source_report(report_type: str, file_path: str | Path) -> pd.DataFrame:
    """Recover one individual report and remove only known summary/footer rows."""
    if report_type not in SOURCE_PROFILES:
        raise ValueError(f"Unsupported Timeless report type: {report_type}")
    frame = recover_table(file_path)
    tail = _SUMMARY_ROWS.get(report_type, 0)
    if tail and len(frame) >= tail:
        frame = frame.iloc[:-tail].reset_index(drop=True)
    if report_type == "batch_summary" and "Batch" in frame.columns:
        frame = frame[
            ~frame["Batch"].astype(str).str.startswith("Page")
        ].reset_index(drop=True)
    validate_source_report(report_type, frame)
    return frame


def validate_source_report(report_type: str, frame: pd.DataFrame) -> None:
    """Require a positive source-schema match for the selected report type."""
    columns = {str(column) for column in frame.columns}
    required = SOURCE_PROFILES[report_type]
    if required <= columns:
        return
    matching = [
        name for name, profile in SOURCE_PROFILES.items() if profile <= columns
    ]
    if matching:
        raise ValueError(
            f"Expected {report_type}, but source columns match {matching[0]}."
        )
    raise ValueError(
        f"{Path(str(report_type)).name} source schema is missing: "
        + ", ".join(sorted(required - columns))
    )


def _try_html(file_path: str | Path) -> pd.DataFrame | None:
    try:
        html = Path(file_path).read_text(encoding="utf-8")
        html = re.sub(r"</?br\s*/?>", " | ", html, flags=re.IGNORECASE)
        html = re.sub(r"<(t[dh])\s*/>", r"<\1>", html, flags=re.IGNORECASE)
        tables = pd.read_html(StringIO(html))
        if not tables:
            return None
        frame = max(tables, key=len)
        if all(isinstance(column, int) for column in frame.columns):
            frame.columns = frame.iloc[0]
            frame = frame.iloc[1:].reset_index(drop=True)
        return frame
    except Exception:
        return None


def _try_excel(file_path: str | Path) -> pd.DataFrame | None:
    try:
        return pd.read_excel(file_path, sheet_name=0)
    except Exception:
        return None


def _try_csv(file_path: str | Path) -> pd.DataFrame | None:
    try:
        return pd.read_csv(file_path, encoding="latin1")
    except Exception:
        return None
