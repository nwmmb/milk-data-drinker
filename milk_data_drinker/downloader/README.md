# Timeless Report Downloader

Downloads reports from Timeless MMBMS in time-windowed batches to avoid the system hanging on large exports. Instead of one huge report that crashes Timeless, this downloads many small reports (e.g. one per week or quarter) and saves them as `.xls` files.

## Requirements

- **Python 3.10+** (check with `python --version`)
- **milk-data-drinker** with the download extra: `pip install "milk-data-drinker[download] @ git+https://github.com/nwmmb/milk-data-drinker.git@v0.1.0"`
- **Must run from your own computer** — Timeless is behind a firewall that blocks requests from other servers

## Quick start

```
mdd-download
```

Or:

```
python -m milk_data_drinker.downloader
```

The script walks you through an interactive menu:

1. **Report type** — choose which report to download
2. **Date range** — set start and end month/year
3. **Window size** — how large each download chunk should be (weekly, monthly, quarterly, etc.)
4. **Cookie** — if not already configured, you'll be prompted to paste your browser cookie
5. **Confirmation** — review the summary and confirm before downloading

### Dry run

Preview what would be downloaded without making any requests:

```
mdd-download --dry-run
```

## Setting up your cookie

The script needs your Timeless session cookie to authenticate. There are three supported ways to provide it (checked in this order):

### Option 1: cookie.txt (recommended)

Create a file called `cookie.txt` in the directory where you run `mdd-download` and paste your cookie into it. This is the simplest option for repeat use — the script reads it automatically.

```
cookie.txt   ← just the raw cookie string, nothing else
```

This file is gitignored and will not be committed.

### Option 2: Environment variable

Set `TIMELESS_COOKIE` before running the script:

```
set TIMELESS_COOKIE=your_cookie_here
mdd-download
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

## Window sizes

| Window | Notes |
|---|---|
| Weekly | Default for wastage reports. If a weekly download times out, the script automatically retries that week as individual daily downloads. |
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

## Troubleshooting

**"Session expired" or redirect to login** — Your cookie has expired. Log into Timeless again and copy a fresh cookie (update `cookie.txt` or re-paste).

**403 Forbidden** — You're running the script from a server or network that Timeless doesn't recognize. Run it from your own computer instead.

**"No data for this window"** — Normal. Some time windows have no matching data. The script skips these automatically.

**"timed out — retrying as daily downloads"** — A weekly window was too large for Timeless. The script automatically breaks it into daily downloads. No action needed.

**Server error (500)** — The script retries up to 3 times with backoff (5s, 15s, 30s). If all retries fail, it marks the file as failed and continues with the next window.

**Downloads resume** — If the script stops partway through (cookie expired, network issue), just re-run it. It skips files that already exist in the output directory.
