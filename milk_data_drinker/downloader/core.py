"""Prompt-independent Timeless report download engine."""

from __future__ import annotations

import calendar
import html as htmlmod
import json
import re
import threading
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Callable, Iterable

import requests

TIMELESS_HOST = "https://northwest.prod.mbms.useast1.timelessmedical.com"
MIN_DATE = date(2000, 1, 1)
DELAY = 3.0
MAX_RETRIES = 3
RETRY_BACKOFF = (5, 15, 30)

# Number of trailing summary/total rows Timeless appends per report type.
_COMBINE_SUMMARY_ROWS = {"deposit_record": 2, "dispensation": 4}

REPORT_TYPES = {
    "donor_information": {
        "path": "/reports/donor_information_report/report.php",
        "params": {
            "donorLastName": "", "donorFirstName": "",
            "donorBarcode": "", "donorApproved": "",
            "donorBabyStatus": "", "orderBy": "screen_date",
            "date_type": "all_date", "range_option": "date_range",
            "_do_print": "y", "excel": "1",
        },
        "filters": [
            {"name": "withdrawn", "donorStatus": "0"},
            {"name": "inactive", "donorStatus": "1"},
            {"name": "active", "donorStatus": "2"},
            {"name": "retired", "donorStatus": "3"},
        ],
    },
    "deposit_record": {
        "path": "/reports/deposit_record/report.php",
        "params": {
            "donor": "", "dropofflocation": "", "milkbank_scan": "",
            "donor_search": "1", "milkbank_search": "",
            "dropofflocation_search": "", "deposit_state_type": "",
            "date_type": "date_received", "range_option": "date_range",
            "city_state_region": "", "city_state": "",
            "milkbank_donor": "", "volume_measurement": "1",
            "_do_print": "y", "excel": "1",
        },
        "filters": [{}],
    },
    "dispensation": {
        "path": "/reports/dispensation_report/report.php",
        "params": {
            "hospital": "", "outpatient": "", "milkbank": "",
            "research_facility": "", "range_option": "date_range",
            "hospital_search": "1", "internal_search": "",
            "outpatient_search": "1", "milkbank_search": "1",
            "research_facility_search": "1", "detail": "1",
            "order_number": "", "report_type": "", "milk_list": "",
            "volume_measurement": "1", "_do_print": "y", "excel": "1",
        },
        "filters": [{}],
    },
    "wastage_report": {
        "path": "/reports/wastage_report/report.php",
        "params": {
            "pool": "", "range_option": "date_range",
            "milk_reason": "", "milk": "", "display_disposed": "1",
            "display_waste": "1", "volume_measurement": "1",
            "_do_print": "y", "excel": "1",
        },
        "filters": [{}],
    },
    "batch_summary": {
        "path": "/reports/preview",
        "params": {
            "report": "batch-summary-report", "pasteurizer": "",
            "searchOption": "date_range", "milkStatus": "",
            "approveStatus": "1", "per_page": "300",
        },
        "filters": [{}],
        "date_from_key": "datefrom",
        "date_to_key": "dateto",
        "date_format": "%Y-%m-%d",
        "preview_json": True,
    },
}

REPORT_DISPLAY_NAMES = {
    "donor_information": "Donor Information",
    "deposit_record": "Deposit Record",
    "dispensation": "Dispensation",
    "wastage_report": "Wastage Report",
    "batch_summary": "Batch Summary",
}

WINDOW_CHOICES = {
    "weekly": "Weekly",
    "monthly": "Monthly",
    "quarterly": "Quarterly",
    "semiannual": "Semi-annual",
    "annual": "Annual",
}
WINDOW_MONTHS = {
    "monthly": 1,
    "quarterly": 3,
    "semiannual": 6,
    "annual": 12,
}


@dataclass(frozen=True)
class DownloadSettings:
    report_type: str
    start_date: date
    end_date: date
    window_size: str
    output_dir: Path
    combine: bool = False
    preview: bool = False
    cookie: str = field(default="", repr=False)


@dataclass
class DownloadResult:
    planned: int = 0
    completed: int = 0
    downloaded: int = 0
    existing: int = 0
    no_data: int = 0
    failed: int = 0
    cancelled: bool = False
    files: list[Path] = field(default_factory=list)
    combined_file: Path | None = None
    fatal_error: str | None = None


@dataclass(frozen=True)
class DownloadEvent:
    kind: str
    message: str = ""
    completed: int = 0
    total: int = 0
    downloaded: int = 0
    existing: int = 0
    no_data: int = 0
    failed: int = 0


ProgressCallback = Callable[[DownloadEvent], None]


class DownloadCancelled(Exception):
    """Raised internally when cooperative cancellation is requested."""


class FatalDownloadError(Exception):
    """Authentication or network policy failure that must stop the run."""


def previous_full_month(today: date | None = None) -> tuple[date, date]:
    """Return the first and last date of the most recent complete month."""
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    return end.replace(day=1), end


def default_window(report_type: str) -> str:
    if report_type in {"wastage_report", "batch_summary"}:
        return "weekly"
    return "quarterly"


def validate_settings(
    settings: DownloadSettings, *, today: date | None = None
) -> None:
    today = today or date.today()
    if settings.report_type not in REPORT_TYPES:
        raise ValueError("Choose a valid report type.")
    if settings.window_size not in WINDOW_CHOICES:
        raise ValueError("Choose a valid window size.")
    if settings.start_date < MIN_DATE or settings.end_date > today:
        raise ValueError(
            f"Dates must be between {MIN_DATE:%B %d, %Y} and {today:%B %d, %Y}."
        )
    if settings.start_date > settings.end_date:
        raise ValueError("The start date must be on or before the end date.")
    if not str(settings.output_dir).strip():
        raise ValueError("Choose an output directory.")
    if not settings.preview and not settings.cookie.strip():
        raise ValueError("Paste a current Timeless cookie before downloading.")


def week_ranges(start_date: date, end_date: date) -> Iterable[tuple[date, date]]:
    current = start_date
    while current <= end_date:
        window_end = min(current + timedelta(days=6), end_date)
        yield current, window_end
        current = window_end + timedelta(days=1)


def calendar_ranges(
    start_date: date, end_date: date, interval_months: int
) -> Iterable[tuple[date, date]]:
    """Yield calendar-aligned month groups, clipping first and last windows."""
    if interval_months not in {1, 3, 6, 12}:
        raise ValueError("Calendar interval must be 1, 3, 6, or 12 months.")

    period_start_month = ((start_date.month - 1) // interval_months) * interval_months + 1
    period_start = date(start_date.year, period_start_month, 1)
    while period_start <= end_date:
        end_month_index = period_start.month - 1 + interval_months - 1
        end_year = period_start.year + end_month_index // 12
        end_month = end_month_index % 12 + 1
        period_end = date(
            end_year, end_month, calendar.monthrange(end_year, end_month)[1]
        )
        yield max(start_date, period_start), min(end_date, period_end)
        next_month_index = period_start.month - 1 + interval_months
        period_start = date(
            period_start.year + next_month_index // 12,
            next_month_index % 12 + 1,
            1,
        )


def date_ranges(settings: DownloadSettings) -> list[tuple[date, date]]:
    if settings.window_size == "weekly":
        return list(week_ranges(settings.start_date, settings.end_date))
    return list(
        calendar_ranges(
            settings.start_date,
            settings.end_date,
            WINDOW_MONTHS[settings.window_size],
        )
    )


def planned_downloads(settings: DownloadSettings) -> int:
    return len(REPORT_TYPES[settings.report_type]["filters"]) * len(
        date_ranges(settings)
    )


def build_params(
    report_cfg: dict, filt: dict, from_date: date, to_date: date
) -> dict:
    params = dict(report_cfg["params"])
    params.update({key: value for key, value in filt.items() if key != "name"})
    date_from_key = report_cfg.get("date_from_key", "fromdate")
    date_to_key = report_cfg.get("date_to_key", "todate")
    date_format = report_cfg.get("date_format", "%m/%d/%Y")
    params[date_from_key] = from_date.strftime(date_format)
    params[date_to_key] = to_date.strftime(date_format)
    return params


def output_filename(
    report_name: str, filt: dict, from_date: date, to_date: date
) -> str:
    parts = [report_name]
    if filt.get("name"):
        parts.append(filt["name"])
    parts.append(f"{from_date:%Y-%m-%d}_to_{to_date:%Y-%m-%d}")
    return "_".join(parts) + ".xls"


def make_session(cookie: str) -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36"
    )
    session.headers["Referer"] = TIMELESS_HOST + "/"
    session.headers["Accept"] = (
        "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    )
    for part in cookie.split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        session.cookies.set(
            name.strip(),
            value.strip(),
            domain="northwest.prod.mbms.useast1.timelessmedical.com",
        )
    return session


def _emit(
    callback: ProgressCallback | None,
    kind: str,
    result: DownloadResult,
    message: str = "",
) -> None:
    if callback:
        callback(
            DownloadEvent(
                kind=kind,
                message=message,
                completed=result.completed,
                total=result.planned,
                downloaded=result.downloaded,
                existing=result.existing,
                no_data=result.no_data,
                failed=result.failed,
            )
        )


def _wait(delay: float, cancel_event: threading.Event) -> None:
    if delay > 0 and cancel_event.wait(delay):
        raise DownloadCancelled
    if cancel_event.is_set():
        raise DownloadCancelled


def _is_login_response(response: requests.Response) -> bool:
    if "login" in response.url.lower():
        return True
    if (
        response.status_code in {301, 302, 303, 307, 308}
        and "login" in response.headers.get("Location", "").lower()
    ):
        return True
    return any(
        item.status_code in {301, 302, 303, 307, 308}
        and "login" in item.headers.get("Location", "").lower()
        for item in response.history
    )


def _request(
    session: requests.Session,
    url: str,
    params: dict,
    cancel_event: threading.Event,
    callback: ProgressCallback | None,
    result: DownloadResult,
    retry_backoff: tuple[float, ...],
) -> requests.Response:
    for attempt in range(MAX_RETRIES):
        if cancel_event.is_set():
            raise DownloadCancelled
        try:
            response = session.get(url, params=params, timeout=120)
        except requests.Timeout:
            raise
        except requests.RequestException:
            raise

        if _is_login_response(response):
            raise FatalDownloadError(
                "Timeless redirected to login. The saved cookie may have expired."
            )
        if response.status_code == 403:
            raise FatalDownloadError(
                "Timeless returned 403 Forbidden. Check the cookie and run from "
                "the usual local network."
            )
        if response.status_code == 504:
            raise requests.Timeout("Timeless timed out (504).")
        if response.status_code >= 500:
            if attempt < MAX_RETRIES - 1:
                wait = retry_backoff[min(attempt, len(retry_backoff) - 1)]
                _emit(
                    callback,
                    "log",
                    result,
                    f"Server error {response.status_code}; retrying in {wait:g}s "
                    f"({attempt + 1}/{MAX_RETRIES}).",
                )
                _wait(wait, cancel_event)
                continue
        response.raise_for_status()
        return response
    raise requests.HTTPError(f"Server error after {MAX_RETRIES} attempts.")


def _convert_preview_json(
    filepath: Path,
    callback: ProgressCallback | None = None,
    result: DownloadResult | None = None,
) -> bool:
    content = filepath.read_text(encoding="utf-8")
    match = re.search(r':report-data="([^"]+)"', content)
    if not match:
        if result:
            _emit(callback, "log", result, "Preview data was not found; file left as-is.")
        return True

    data = json.loads(htmlmod.unescape(match.group(1)))
    records = data.get("data", {}).get("data", [])
    if not records:
        if result:
            _emit(callback, "log", result, "Preview contained no records.")
        return False

    bottle_sizes = [
        item["milkbottlesVolume"] for item in data.get("milkBottleVolumes", [])
    ]
    headers = [
        "Batch", "Created On", "Created From", "Donor/Milk Bank",
        "Original Volume(oz)",
    ]
    headers.extend(f"Original Bottles: {size} oz *" for size in bottle_sizes)
    headers.extend(["Milk Type", "Remaining Volume(oz)"])
    headers.extend(
        f"Remaining Bottles: {size} oz Bottles" for size in bottle_sizes
    )
    headers.extend(
        [
            "Fat", "Protein", "Lactose", "Cal/Oz", "g/dL", "Location",
            "Expiry Date", "Milk Approved", "Milk Status",
        ]
    )

    lines = ['<table class="alternatingrows">', "<thead><tr>"]
    lines.extend(f"<th>{htmlmod.escape(str(header))}</th>" for header in headers)
    lines.append("</tr></thead><tbody>")
    for record in records:
        original = record.get("originalBottles") or {}
        remaining = record.get("remainingBottles") or {}
        cells = [
            record.get("milkBarcode", ""),
            record.get("milkDateTimeReceived", ""),
            record.get("sourceMilk", ""),
            record.get("donorSource", ""),
            record.get("milkReceivedVolume", ""),
        ]
        cells.extend((original.get(size, [0]) or [0])[0] for size in bottle_sizes)
        cells.extend([record.get("milkType", ""), record.get("remainingVolume", "")])
        cells.extend((remaining.get(size, [0]) or [0])[0] for size in bottle_sizes)
        cells.extend(
            [
                record.get("fat", ""),
                record.get("protein", ""),
                record.get("lactose", ""),
                record.get("milkTotalCalories", ""),
                record.get("milkCaloriesGDL", ""),
                record.get("location", ""),
                record.get("milkExpiryDateTime", ""),
                record.get("approved", ""),
                record.get("milkStatus", ""),
            ]
        )
        lines.append(
            "<tr>"
            + "".join(f"<td>{htmlmod.escape(str(cell))}</td>" for cell in cells)
            + "</tr>"
        )
    lines.append("</tbody></table>")
    filepath.write_text("\n".join(lines), encoding="utf-8")
    if result:
        _emit(
            callback, "log", result, f"Converted preview data ({len(records)} rows)."
        )
    return True


def _record_status(
    status: str,
    path: Path | None,
    result: DownloadResult,
    callback: ProgressCallback | None,
) -> None:
    if status == "downloaded":
        result.downloaded += 1
    elif status == "existing":
        result.existing += 1
    elif status == "no_data":
        result.no_data += 1
    elif status == "failed":
        result.failed += 1
    if path is not None and path not in result.files:
        result.files.append(path)
    _emit(callback, "counts", result)


def _download_request(
    session: requests.Session,
    url: str,
    report_cfg: dict,
    report_name: str,
    filt: dict,
    from_date: date,
    to_date: date,
    output_dir: Path,
    cancel_event: threading.Event,
    callback: ProgressCallback | None,
    result: DownloadResult,
    retry_backoff: tuple[float, ...],
) -> str:
    filename = output_filename(report_name, filt, from_date, to_date)
    filepath = output_dir / filename
    if filepath.exists():
        _emit(callback, "log", result, f"Existing: {filename}")
        _record_status("existing", filepath, result, callback)
        return "existing"

    _emit(callback, "log", result, f"Downloading: {filename}")
    params = build_params(report_cfg, filt, from_date, to_date)
    response = _request(
        session, url, params, cancel_event, callback, result, retry_backoff
    )
    if b"No data found matching report criteria" in response.content:
        _emit(callback, "log", result, f"No data: {filename}")
        _record_status("no_data", None, result, callback)
        return "no_data"

    filepath.write_bytes(response.content)
    if report_cfg.get("preview_json"):
        if not _convert_preview_json(filepath, callback, result):
            filepath.unlink(missing_ok=True)
            _emit(callback, "log", result, f"No data: {filename}")
            _record_status("no_data", None, result, callback)
            return "no_data"
    _emit(callback, "log", result, f"Saved: {filename} ({filepath.stat().st_size} bytes)")
    _record_status("downloaded", filepath, result, callback)
    return "downloaded"


def _download_window(
    session: requests.Session,
    url: str,
    report_cfg: dict,
    settings: DownloadSettings,
    filt: dict,
    from_date: date,
    to_date: date,
    cancel_event: threading.Event,
    callback: ProgressCallback | None,
    result: DownloadResult,
    delay: float,
    retry_backoff: tuple[float, ...],
) -> None:
    try:
        _download_request(
            session,
            url,
            report_cfg,
            settings.report_type,
            filt,
            from_date,
            to_date,
            settings.output_dir,
            cancel_event,
            callback,
            result,
            retry_backoff,
        )
        cancel_event.wait(delay)
    except requests.Timeout as exc:
        if from_date == to_date:
            _emit(callback, "log", result, f"Failed: {exc}")
            _record_status("failed", None, result, callback)
            return
        _emit(
            callback,
            "log",
            result,
            "Window timed out; retrying its dates as daily downloads.",
        )
        current = from_date
        while current <= to_date:
            _download_window(
                session,
                url,
                report_cfg,
                settings,
                filt,
                current,
                current,
                cancel_event,
                callback,
                result,
                delay,
                retry_backoff,
            )
            current += timedelta(days=1)
    except requests.RequestException as exc:
        _emit(callback, "log", result, f"Failed: {exc}")
        _record_status("failed", None, result, callback)


def _read_raw(report_type: str, file_path: Path) -> "pd.DataFrame":
    """Read a Timeless report with format recovery only, preserving original column names."""
    from milk_data_drinker.timeless._normalizer import normalize

    import pandas as pd

    df = normalize(str(file_path))

    tail = _COMBINE_SUMMARY_ROWS.get(report_type, 0)
    if tail and len(df) > tail:
        df = df.iloc[:-tail].reset_index(drop=True)

    if report_type == "batch_summary" and "Batch" in df.columns:
        df = df[~df["Batch"].astype(str).str.startswith("Page")].reset_index(
            drop=True
        )

    return df


def combine_files(
    report_name: str,
    file_paths: list[Path],
    range_start: date,
    range_end: date,
    output_dir: Path,
    callback: ProgressCallback | None = None,
    result: DownloadResult | None = None,
) -> Path | None:
    """Read downloaded files with format recovery only and write one deduplicated workbook.

    Original Timeless column names are preserved — no schema normalization is applied.
    """
    import pandas as pd

    frames = []
    for path in file_paths:
        try:
            frames.append(_read_raw(report_name, path))
        except Exception as exc:
            if result:
                _emit(callback, "log", result, f"Could not combine {path.name}: {exc}")
    if not frames:
        if result:
            _emit(callback, "log", result, "No files could be parsed for combination.")
        return None

    combined = pd.concat(frames, ignore_index=True).drop_duplicates()
    date_col = next(
        (c for c in combined.columns if "date" in c.lower()), None
    )
    if date_col is not None:
        combined = combined.sort_values(
            date_col,
            key=lambda s: pd.to_datetime(s, errors="coerce"),
            na_position="last",
        )
    output_path = output_dir / (
        f"{report_name}_combined_{range_start:%Y-%m-%d}_to_{range_end:%Y-%m-%d}.xlsx"
    )
    combined.to_excel(output_path, index=False)
    if result:
        _emit(
            callback,
            "log",
            result,
            f"Combined {len(frames)} files ({len(combined)} rows): {output_path.name}",
        )
    return output_path


def run_download(
    settings: DownloadSettings,
    *,
    callback: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
    session_factory: Callable[[str], requests.Session] = make_session,
    delay: float = DELAY,
    retry_backoff: tuple[float, ...] = RETRY_BACKOFF,
) -> DownloadResult:
    """Execute or preview a sequential report run."""
    validate_settings(settings)
    cancel_event = cancel_event or threading.Event()
    ranges = date_ranges(settings)
    report_cfg = REPORT_TYPES[settings.report_type]
    filters = report_cfg["filters"]
    result = DownloadResult(planned=len(filters) * len(ranges))
    _emit(callback, "started", result)

    if settings.preview:
        for filt in filters:
            for from_date, to_date in ranges:
                if cancel_event.is_set():
                    result.cancelled = True
                    _emit(callback, "cancelled", result, "Preview cancelled.")
                    return result
                filename = output_filename(
                    settings.report_type, filt, from_date, to_date
                )
                _emit(callback, "log", result, f"Would download: {filename}")
                result.completed += 1
                _emit(callback, "progress", result)
        _emit(callback, "complete", result, "Preview complete.")
        return result

    settings.output_dir.mkdir(parents=True, exist_ok=True)
    session = session_factory(settings.cookie)
    url = TIMELESS_HOST + report_cfg["path"]
    try:
        for filt in filters:
            label = filt.get("name")
            if label:
                _emit(callback, "log", result, f"Filter: {label}")
            for from_date, to_date in ranges:
                if cancel_event.is_set():
                    raise DownloadCancelled
                _download_window(
                    session,
                    url,
                    report_cfg,
                    settings,
                    filt,
                    from_date,
                    to_date,
                    cancel_event,
                    callback,
                    result,
                    delay,
                    retry_backoff,
                )
                result.completed += 1
                _emit(callback, "progress", result)
    except DownloadCancelled:
        result.cancelled = True
        _emit(callback, "cancelled", result, "Cancelled; completed files were kept.")
        return result
    except FatalDownloadError as exc:
        result.fatal_error = str(exc)
        _emit(callback, "fatal", result, result.fatal_error)
        return result
    finally:
        session.close()

    if settings.combine and result.files:
        result.combined_file = combine_files(
            settings.report_type,
            result.files,
            settings.start_date,
            settings.end_date,
            settings.output_dir,
            callback,
            result,
        )
    _emit(callback, "complete", result, "Download run complete.")
    return result
