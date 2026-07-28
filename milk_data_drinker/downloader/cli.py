#!/usr/bin/env python3
"""
Download Timeless MMBMS reports in time-windowed batches.

Timeless hangs on large exports, so this script downloads many small
reports — one per time window per filter — that together cover the full
date range. Output is .xls files saved to a local directory.

IMPORTANT: This must run from your local machine (same network as your
browser session). Timeless is behind CloudFront/WAF which blocks
requests from unfamiliar IPs.

See README.md for setup instructions and report type details.
"""

import calendar
import html as htmlmod
import json
import logging
import os
import re
import sys
import time
from datetime import date, timedelta

try:
    import requests
except ImportError:
    sys.exit(
        "requests is required.\n"
        "Install it with: pip install 'milk-data-drinker[download]'"
    )

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

TIMELESS_HOST = "https://northwest.prod.mbms.useast1.timelessmedical.com"

# ── Defaults ─────────────────────────────────────────────────────────

# Paste your cookie string here (from DevTools → Network → Request
# Headers → Cookie). Log into Timeless in your browser first, then
# copy the full value. Alternatively, set the TIMELESS_COOKIE env var.
COOKIE = """
"""

# Seconds to wait between requests (be gentle on Timeless)
DELAY = 3.0

# Where to save downloaded files
OUTPUT_DIR = "./downloads"

# ── Report types ──────────────────────────────────────────────────────
# Each entry defines the URL path and parameters for one Timeless report.
#
# "path"       - the report.php URL path on the Timeless server
# "params"     - fixed query parameters (always sent)
# "filters"    - list of parameter variations to download separately;
#                each filter produces its own set of time-windowed files.
#                A filter's keys are merged into params for each request.
#                Use a single empty-dict filter [{}] if the report has
#                no meaningful sub-filters.
#
# Donor status codes: 0=Withdrawn, 1=Inactive, 2=Active, 3=Retired

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
            {"name": "withdrawn",    "donorStatus": "0"},
            {"name": "inactive",    "donorStatus": "1"},
            {"name": "active",    "donorStatus": "2"},
            {"name": "retired",   "donorStatus": "3"},
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
            "research_facility": "",
            "range_option": "date_range",
            "hospital_search": "1", "internal_search": "",
            "outpatient_search": "1", "milkbank_search": "1",
            "research_facility_search": "1",
            "detail": "1", "order_number": "", "report_type": "",
            "milk_list": "", "volume_measurement": "1",
            "_do_print": "y", "excel": "1",
        },
        "filters": [{}],
    },
    "wastage_report": {
        "path": "/reports/wastage_report/report.php",
        "params": {
            "pool": "", "range_option": "date_range",
            "milk_reason": "", "milk": "",
            "display_disposed": "1", "display_waste": "1",
            "volume_measurement": "1",
            "_do_print": "y", "excel": "1",
        },
        "filters": [{}],
    },
    "batch_summary": {
        "path": "/reports/preview",
        "params": {
            "report": "batch-summary-report",
            "pasteurizer": "",
            "searchOption": "date_range",
            "milkStatus": "",
            "approveStatus": "1",
            "per_page": "300",
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

INTERVAL_CHOICES = [
    ("weekly", "Weekly"),
    (1, "Monthly"),
    (3, "Quarterly"),
    (6, "Semi-annual"),
    (12, "Annual"),
]


# ── Internals ─────────────────────────────────────────────────────────

def month_ranges(start_year: int, start_month: int, interval_months: int,
                 end_year: int | None = None, end_month: int | None = None):
    today = date.today()
    if end_year and end_month:
        last_day = calendar.monthrange(end_year, end_month)[1]
        cutoff = date(end_year, end_month, last_day)
    else:
        cutoff = today
    year, month = start_year, start_month
    while date(year, month, 1) <= cutoff:
        from_date = date(year, month, 1)
        em = month + interval_months - 1
        ey = year + (em - 1) // 12
        em = (em - 1) % 12 + 1
        last_day = calendar.monthrange(ey, em)[1]
        to_date = min(date(ey, em, last_day), cutoff)
        yield from_date, to_date
        month += interval_months
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1


def week_ranges(start_date: date, end_date: date):
    current = start_date
    week = timedelta(days=7)
    while current <= end_date:
        window_end = min(current + week - timedelta(days=1), end_date)
        yield current, window_end
        current += week


def build_params(report_cfg: dict, filt: dict,
                 from_date: date, to_date: date) -> dict:
    params = dict(report_cfg["params"])
    for k, v in filt.items():
        if k != "name":
            params[k] = v
    date_from_key = report_cfg.get("date_from_key", "fromdate")
    date_to_key = report_cfg.get("date_to_key", "todate")
    date_format = report_cfg.get("date_format", "%m/%d/%Y")
    params[date_from_key] = from_date.strftime(date_format)
    params[date_to_key] = to_date.strftime(date_format)
    return params


def output_filename(report_name: str, filt: dict,
                    from_date: date, to_date: date) -> str:
    parts = [report_name]
    if filt.get("name"):
        parts.append(filt["name"])
    parts.append(f"{from_date.strftime('%Y-%m-%d')}_to_{to_date.strftime('%Y-%m-%d')}")
    return "_".join(parts) + ".xls"


def _convert_preview_json(filepath: str) -> None:
    """Extract JSON data from a Timeless /reports/preview HTML page and
    rewrite the file as an HTML table (.xls) that normalize() can parse.

    The preview endpoint embeds all report data as JSON inside a Vue
    component attribute (:report-data="...") rather than rendering a
    server-side HTML table.  The browser's "Download to Excel" button
    uses table2excel.js to convert the client-rendered table — we
    replicate that by building the table from the JSON directly.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    m = re.search(r':report-data="([^"]+)"', content)
    if not m:
        log.warning("  Could not find :report-data in %s — leaving as-is",
                    filepath)
        return

    data = json.loads(htmlmod.unescape(m.group(1)))
    records = data.get("data", {}).get("data", [])
    if not records:
        log.warning("  No records in preview JSON — leaving as-is")
        return

    bottle_sizes = [
        d["milkbottlesVolume"]
        for d in data.get("milkBottleVolumes", [])
    ]

    headers = [
        "Batch", "Created On", "Created From", "Donor/Milk Bank",
        "Original Volume(oz)",
    ]
    for s in bottle_sizes:
        headers.append(f"Original Bottles: {s} oz *")
    headers += ["Milk Type", "Remaining Volume(oz)"]
    for s in bottle_sizes:
        headers.append(f"Remaining Bottles: {s} oz Bottles")
    headers += [
        "Fat", "Protein", "Lactose", "Cal/Oz", "g/dL",
        "Location", "Expiry Date", "Milk Approved", "Milk Status",
    ]

    lines = ['<table class="alternatingrows">', "<thead><tr>"]
    for h in headers:
        lines.append(f"<th>{h}</th>")
    lines.append("</tr></thead><tbody>")

    for rec in records:
        ob = rec.get("originalBottles") or {}
        rb = rec.get("remainingBottles") or {}
        cells = [
            rec.get("milkBarcode", ""),
            rec.get("milkDateTimeReceived", ""),
            rec.get("sourceMilk", ""),
            rec.get("donorSource", ""),
            rec.get("milkReceivedVolume", ""),
        ]
        for s in bottle_sizes:
            vals = ob.get(s, [0])
            cells.append(vals[0] if vals else 0)
        cells += [
            rec.get("milkType", ""),
            rec.get("remainingVolume", ""),
        ]
        for s in bottle_sizes:
            vals = rb.get(s, [0])
            cells.append(vals[0] if vals else 0)
        cells += [
            rec.get("fat", ""),
            rec.get("protein", ""),
            rec.get("lactose", ""),
            rec.get("milkTotalCalories", ""),
            rec.get("milkCaloriesGDL", ""),
            rec.get("location", ""),
            rec.get("milkExpiryDateTime", ""),
            rec.get("approved", ""),
            rec.get("milkStatus", ""),
        ]
        lines.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

    lines.append("</tbody></table>")

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("         converted preview JSON → HTML table (%d rows)",
             len(records))


MAX_RETRIES = 3
RETRY_BACKOFF = [5, 15, 30]


def download_one(session: requests.Session, url: str, params: dict,
                 filepath: str) -> str | None:
    for attempt in range(MAX_RETRIES):
        resp = session.get(url, params=params, timeout=120)

        if resp.status_code == 302 or "login" in resp.url.lower():
            log.error("Session expired — got redirected to login. Re-copy your cookie.")
            return None

        if resp.status_code >= 500:
            wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
            if attempt < MAX_RETRIES - 1:
                log.warning("         server error %d — retrying in %ds (%d/%d)",
                            resp.status_code, wait, attempt + 1, MAX_RETRIES)
                time.sleep(wait)
                continue
            log.error("         server error %d — giving up after %d attempts",
                      resp.status_code, MAX_RETRIES)
            return None

        resp.raise_for_status()

        if b"No data found matching report criteria" in resp.content:
            log.info("         no data for this window — skipping")
            return None

        with open(filepath, "wb") as f:
            f.write(resp.content)
        return filepath
    return None


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
        part = part.strip()
        if "=" not in part:
            continue
        name, value = part.split("=", 1)
        session.cookies.set(
            name.strip(), value.strip(),
            domain="northwest.prod.mbms.useast1.timelessmedical.com",
        )
    return session


# ── Interactive prompts ──────────────────────────────────────────────

def prompt_choice(prompt_text: str, options: list[tuple], default_index: int = 0):
    """Show a numbered menu and return the value of the selected option.

    options: list of (value, display_label) tuples.
    default_index: 0-based index of the default choice.
    """
    print(f"\n{prompt_text}\n")
    for i, (_, label) in enumerate(options):
        marker = " *" if i == default_index else ""
        print(f"  {i + 1}. {label}{marker}")
    print()

    while True:
        raw = input(f"Enter number [{ default_index + 1}]: ").strip()
        if not raw:
            return options[default_index][0]
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def prompt_int(prompt_text: str, default: int | None = None,
               min_val: int | None = None, max_val: int | None = None) -> int | None:
    """Prompt for an integer with optional range validation."""
    default_str = str(default) if default is not None else ""
    while True:
        raw = input(f"{prompt_text} [{default_str}]: ").strip()
        if not raw:
            return default
        try:
            val = int(raw)
            if min_val is not None and val < min_val:
                print(f"  Must be at least {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"  Must be at most {max_val}.")
                continue
            return val
        except ValueError:
            print("  Please enter a number.")


COOKIE_FILE = "cookie.txt"


def get_cookie(dry_run: bool) -> str:
    """Resolve cookie: cookie.txt → script variable → env var → interactive prompt."""
    if os.path.exists(COOKIE_FILE):
        cookie = open(COOKIE_FILE).read().strip()
        if cookie:
            log.info("Using cookie from %s", COOKIE_FILE)
            return cookie

    cookie = COOKIE.strip()
    if cookie:
        return cookie

    cookie = os.environ.get("TIMELESS_COOKIE", "").strip()
    if cookie:
        return cookie

    if dry_run:
        return ""

    print("\n── Cookie ──────────────────────────────────────────────")
    print("No cookie found. To get your cookie:")
    print("  1. Log into Timeless in Chrome")
    print("  2. Press F12 → Network tab → reload page")
    print("  3. Click any request → find \"Cookie:\" in Request Headers")
    print("  4. Copy everything after \"Cookie: \"")
    print(f"\nSave it to {COOKIE_FILE} to skip this prompt next time.\n")
    cookie = input("Paste cookie: ").strip()
    if not cookie:
        sys.exit("No cookie provided. Cannot download without a valid cookie.")
    return cookie


# ── Download logic ───────────────────────────────────────────────────

def _is_timeout(exc: requests.RequestException) -> bool:
    if isinstance(exc, requests.Timeout):
        return True
    if isinstance(exc, requests.HTTPError) and exc.response is not None:
        return exc.response.status_code == 504
    return False


def _download_window(session, url, report_cfg, report_name, filt,
                     from_date, to_date):
    """Download a single time window. On timeout, retry as daily downloads.

    Returns (downloaded, skipped, failed, files) where files is a list of
    paths that now exist on disk (downloaded or already present).
    """
    downloaded, skipped, failed = 0, 0, 0
    files = []

    fname = output_filename(report_name, filt, from_date, to_date)
    filepath = os.path.join(OUTPUT_DIR, fname)

    if os.path.exists(filepath):
        log.info("  [skip] %s (already exists)", fname)
        return 0, 1, 0, [filepath]

    log.info("  [get]  %s", fname)
    params = build_params(report_cfg, filt, from_date, to_date)
    try:
        result = download_one(session, url, params, filepath)
        if result is None:
            failed += 1
        else:
            if report_cfg.get("preview_json"):
                _convert_preview_json(result)
            downloaded += 1
            files.append(result)
            log.info("         saved (%d bytes)", os.path.getsize(result))
    except requests.RequestException as e:
        if _is_timeout(e) and from_date != to_date:
            log.warning("         timed out — retrying as daily downloads")
            current = from_date
            while current <= to_date:
                d, s, f, daily_files = _download_window(
                    session, url, report_cfg, report_name, filt,
                    current, current,
                )
                downloaded += d
                skipped += s
                failed += f
                files.extend(daily_files)
                current += timedelta(days=1)
        else:
            log.error("         FAILED: %s", e)
            failed += 1

    time.sleep(DELAY)
    return downloaded, skipped, failed, files


# ── Combine ─────────────────────────────────────────────────────────

def combine_files(report_name: str, file_paths: list[str],
                  range_start: date, range_end: date):
    """Parse downloaded files with milk_data_drinker and write a combined .xlsx."""
    import milk_data_drinker
    import pandas as pd

    log.info("Parsing %d files...", len(file_paths))
    dfs = []
    for path in file_paths:
        try:
            df = milk_data_drinker.read_file(path)
            dfs.append(df)
        except Exception as e:
            log.warning("  Could not parse %s: %s", os.path.basename(path), e)

    if not dfs:
        log.warning("No files could be parsed — cannot combine.")
        return

    combined = pd.concat(dfs, ignore_index=True)
    combined = combined.drop_duplicates()

    date_cols = [c for c in combined.columns if "date" in c and combined[c].dtype == "datetime64[ns]"]
    if date_cols:
        combined = combined.sort_values(date_cols[0], na_position="last")

    output_name = (
        f"{report_name}_combined_"
        f"{range_start.strftime('%Y-%m-%d')}_to_{range_end.strftime('%Y-%m-%d')}.xlsx"
    )
    output_path = os.path.join(OUTPUT_DIR, output_name)
    combined.to_excel(output_path, index=False)
    log.info("Combined %d files (%d rows) → %s", len(dfs), len(combined), output_name)


# ── Main ─────────────────────────────────────────────────────────────

def main():
    dry_run = "--dry-run" in sys.argv

    from .updater import check_for_update
    check_for_update()

    try:
        print("=" * 56)
        print("  Timeless Report Downloader")
        print("=" * 56)

        if dry_run:
            print("  (dry-run mode — no downloads will be made)")

        # 1. Report type
        report_options = [
            (key, REPORT_DISPLAY_NAMES[key])
            for key in REPORT_TYPES
        ]
        report_name = prompt_choice("Which report do you want to download?",
                                    report_options, default_index=0)
        report_cfg = REPORT_TYPES[report_name]
        filters = report_cfg["filters"]

        # 2. Date range
        print("\n── Date range ──────────────────────────────────────────")
        today = date.today()
        start_month = prompt_int("Start month (1-12)", default=1,
                                 min_val=1, max_val=12)
        start_year = prompt_int("Start year", default=2020,
                                min_val=2000, max_val=today.year)
        end_month = prompt_int("End month (1-12, Enter for current)",
                               default=today.month, min_val=1, max_val=12)
        end_year = prompt_int("End year (Enter for current)",
                              default=today.year, min_val=2000, max_val=today.year + 1)

        # 3. Window size (default to weekly for wastage, quarterly for others)
        default_interval = 0 if report_name in ("wastage_report", "batch_summary") else 2
        interval = prompt_choice(
            "How large should each download window be?",
            [(val, label) for val, label in INTERVAL_CHOICES],
            default_index=default_interval,
        )

        # 4. Cookie
        cookie = get_cookie(dry_run)

        # 5. Summary & confirmation
        url = TIMELESS_HOST + report_cfg["path"]
        if interval == "weekly":
            start_date = date(start_year, start_month, 1)
            end_date = date(end_year, end_month,
                            calendar.monthrange(end_year, end_month)[1])
            ranges = list(week_ranges(start_date, end_date))
        else:
            ranges = list(month_ranges(start_year, start_month, interval,
                                       end_year, end_month))
        total = len(filters) * len(ranges)
        filter_desc = ", ".join(f.get("name", "all") for f in filters)
        interval_label = next(label for val, label in INTERVAL_CHOICES
                              if val == interval)

        print("\n── Summary ─────────────────────────────────────────────")
        print(f"  Report:    {REPORT_DISPLAY_NAMES[report_name]}")
        print(f"  Range:     {start_month:02d}/{start_year} – {end_month:02d}/{end_year}")
        print(f"  Window:    {interval_label}")
        print(f"  Filters:   {filter_desc}")
        print(f"  Downloads: {len(filters)} filter(s) × {len(ranges)} windows = {total} files")
        print(f"  Output:    {os.path.abspath(OUTPUT_DIR)}/")
        print()

        if dry_run:
            for filt in filters:
                label = filt.get("name", "(no filter)")
                log.info("── %s ──", label)
                for from_date, to_date in ranges:
                    fname = output_filename(report_name, filt, from_date, to_date)
                    log.info("  %s", fname)
            log.info("Dry run complete. %d files would be downloaded.", total)
            return

        confirm = input("Proceed? [Y/n]: ").strip().lower()
        if confirm and confirm != "y":
            print("Cancelled.")
            return

        # 6. Download
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        session = make_session(cookie)

        downloaded = 0
        skipped = 0
        failed = 0
        all_files = []

        for filt in filters:
            label = filt.get("name", "(no filter)")
            log.info("── %s ──", label)
            for from_date, to_date in ranges:
                d, s, f, window_files = _download_window(
                    session, url, report_cfg, report_name, filt,
                    from_date, to_date,
                )
                downloaded += d
                skipped += s
                failed += f
                all_files.extend(window_files)

        log.info("Done. %d downloaded, %d skipped, %d failed.",
                 downloaded, skipped, failed)

        # 7. Optional: combine into one Excel workbook
        if all_files:
            combine = input(
                "\nCombine all files into one Excel workbook? [y/N]: "
            ).strip().lower()
            if combine == "y":
                range_start = ranges[0][0]
                range_end = ranges[-1][1]
                combine_files(report_name, all_files, range_start, range_end)

    except KeyboardInterrupt:
        print("\nCancelled.")
        sys.exit(0)


if __name__ == "__main__":
    main()
