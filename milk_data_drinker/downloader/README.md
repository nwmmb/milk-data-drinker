# Timeless Report Downloader

Downloads reports from Timeless MMBMS in time-windowed batches to avoid the system hanging on large exports. Instead of one huge report that crashes Timeless, this downloads many small reports (e.g. one per week or quarter) and saves them as `.xls` files.

## Requirements

- **Python 3.10+** installed on the local computer
- A downloaded or cloned copy of the `milk-data-drinker` repository
- **Must run from your own computer** — Timeless is behind a firewall that blocks requests from other servers

## Quick start on Windows

1. Extract the downloaded repository to a normal folder.
2. Double-click `run-downloader.bat` in the repository root.

On its first run, the launcher creates a private `.venv` folder and installs all
dependencies inside it. Later runs reuse that environment. It does not install the
package or dependencies into the machine-wide Python environment.

From Command Prompt, the equivalent command is:

```bat
run-downloader.bat
```

This launches the graphical interface (Tkinter). If you prefer a text-mode CLI:

```bat
run-downloader.bat --cli
```

Or use the dedicated CLI entry point:

```bat
.venv\Scripts\mdd-download-cli.exe
```

### Dry run

Preview what would be downloaded without making any requests:

```bat
run-downloader.bat --dry-run
```

### Manual virtual-environment setup

If you do not want to use the launcher:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[download]"
.venv\Scripts\python.exe -m milk_data_drinker.downloader
```

The `pip` command above runs through `.venv\Scripts\python.exe`, so it installs
only inside the repository virtual environment.

## Interfaces

### GUI (default)

The graphical interface (`mdd-download` or `run-downloader.bat`) provides:

- Report type selection
- Date range picker (calendar widget)
- Window size selection
- Cookie management (save/forget)
- Combine-into-one-workbook checkbox
- Real-time download progress log
- Preview mode (dry run)

### CLI (fallback)

The text-mode interface (`mdd-download-cli` or `run-downloader.bat --cli`) walks you through the same options via interactive prompts:

1. **Report type** — choose which report to download
2. **Date range** — set start and end month/year
3. **Window size** — how large each download chunk should be (weekly, monthly, quarterly, etc.)
4. **Cookie** — if not already configured, you'll be prompted to paste your browser cookie
5. **Confirmation** — review the summary and confirm before downloading

## Setting up your cookie

The downloader needs your Timeless session cookie to authenticate. There are three supported ways to provide it (checked in this order):

### Option 1: cookie.txt (recommended)

Create a file called `cookie.txt` in the repository root beside `run-downloader.bat`, and paste your cookie into it. This is the simplest option for repeat use — the downloader reads it automatically.

```
cookie.txt   <- just the raw cookie string, nothing else
```

This file is gitignored and will not be committed.

### Option 2: Environment variable

Set `TIMELESS_COOKIE` before running the downloader:

```
set TIMELESS_COOKIE=your_cookie_here
run-downloader.bat
```

### Option 3: Interactive prompt

If no cookie is found via any of the above methods, you'll be prompted to paste one with instructions on where to find it.

### Getting your cookie

1. Log into Timeless in Chrome.
2. Press **F12** to open Developer Tools.
3. Click the **Network** tab.
4. Reload the page (F5).
5. Click the first request in the list.
6. Scroll down to **Request Headers**.
7. Find the line that says **Cookie:** — copy everything after `Cookie: `.

Your cookie expires when you log out or after a period of inactivity. If downloads start failing, log back in and grab a fresh cookie.

## Available reports

| Report | Default window | Description |
|---|---|---|
| Donor Information | Quarterly | Full donor profile — demographics, screening, approval. Downloaded in 4 batches by status (withdrawn, inactive, active, retired). |
| Deposit Record | Quarterly | All deposits in the date range (filtered by date received). |
| Dispensation | Quarterly | Milk dispensed to recipients. |
| Wastage Report | Weekly | Batch and deposit wastage/disposal records. |
| Batch Summary | Weekly | Pasteurized batch metadata — creation date, bottle size, nutrients, status. Used for lot recall tracing. |

See [docs/report-types.md](../../docs/report-types.md) for original column schemas, ingestion transforms, and known quirks per report type.

## Combining files

When the "Combine into one workbook" option is selected, the downloader merges all downloaded files into a single `.xlsx` file. The combined output preserves original Timeless column names and structure — only format-recovery fixes are applied (HTML-as-XLS handling, summary row removal). No schema normalization is performed; that happens separately when files are ingested into nwmmb-db.

## Window sizes

| Window | Notes |
|---|---|
| Weekly | Default for wastage reports. If a weekly download times out, the downloader automatically retries that week as individual daily downloads. |
| Monthly | Good for most reports. |
| Quarterly | Default for all reports except wastage. |
| Semi-annual | For light-traffic reports. |
| Annual | For very small reports. |

## Output

Files are saved to `./downloads/`, named:
```
{report_type}_{filter}_{start}_to_{end}.xls
```

Examples:
- `donor_information_active_2024-01-01_to_2024-03-31.xls`
- `deposit_record_2024-01-01_to_2024-01-31.xls`
- `wastage_report_2026-01-01_to_2026-01-07.xls`
- `batch_summary_2025-02-19_to_2025-02-25.xls`
- `wastage_report_2026-01-08_to_2026-01-08.xls` (daily fallback after timeout)

## Architecture

The downloader is split into focused modules:

| Module | Responsibility |
|---|---|
| `core.py` | Download engine — report types, date windowing, HTTP requests, file combination. No UI dependency. |
| `gui.py` | Tkinter graphical interface. |
| `cli.py` | Text-mode interactive CLI (fallback). |
| `controller.py` | Thread-safe wrapper for running downloads from the GUI without blocking the event loop. |
| `cookies.py` | Cookie resolution (file, env var, saved) and persistence. |
| `updater.py` | Self-update mechanism — checks GitHub releases for newer versions. |

## Troubleshooting

**"Session expired" or redirect to login** — Your cookie has expired. Log into Timeless again and copy a fresh cookie (update `cookie.txt` or re-paste).

**403 Forbidden** — You're running the downloader from a server or network that Timeless doesn't recognize. Run it from your own computer instead.

**"No data for this window"** — Normal. Some time windows have no matching data. The downloader skips these automatically.

**"timed out — retrying as daily downloads"** — A weekly window was too large for Timeless. The downloader automatically breaks it into daily downloads. No action needed.

**Server error (500)** — The downloader retries up to 3 times with backoff (5s, 15s, 30s). If all retries fail, it marks the file as failed and continues with the next window.

**Downloads resume** — If the downloader stops partway through (cookie expired, network issue), just re-run it. It skips files that already exist in the output directory.
