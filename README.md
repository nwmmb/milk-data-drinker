# Timeless Downloader Utility

Downloads Timeless MMBMS reports in bounded date windows so large exports do not
hang the Timeless reporting interface. This repository is a local staff utility; it
does not connect to Azure, upload files, or transform reports into nwmmb-db's
canonical schema.

The repository is published at
[`nwmmb/timeless-downloader-utility`](https://github.com/nwmmb/timeless-downloader-utility).
Release `v0.2.0` is the first downloader-only release under this name. GitHub retains
the history and redirects from the former `nwmmb/milk-data-drinker` URL.

## Windows quick start

1. Download and extract a fresh copy of the repository.
2. Double-click `run-downloader.bat`.

The launcher creates a private `.venv`, installs the utility and its dependencies,
then opens the graphical interface. Nothing is installed into the machine-wide
Python environment.

This release changes both the distribution and Python namespace. If an older copy
already has a `.venv`, delete that `.venv` or start from a fresh download. There is
no bridge release from `milk-data-drinker`.

For the text interface:

```bat
run-downloader.bat --cli
```

For a preview with no requests or output files:

```bat
run-downloader.bat --dry-run
```

## Commands

The primary commands are:

- `timeless-download` — graphical interface
- `timeless-download-cli` — interactive text interface

For `v0.2.0` only, `mdd-download` and `mdd-download-cli` remain as deprecated
aliases. New shortcuts and documentation should use the `timeless-*` names.

Manual virtual-environment setup:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[download]"
.venv/bin/timeless-download
```

## What it downloads

The utility supports Donor Information, Deposit Record, Dispensation, Wastage,
and Batch Summary reports. It downloads each report in weekly, monthly,
quarterly, semi-annual, or annual windows and automatically retries a timed-out
window one day at a time.

Individual `.xls` files remain source-faithful: original Timeless headers and
ordered columns are retained. Only download-format recovery occurs, such as
reading HTML files saved with an `.xls` extension and converting Batch Summary
preview JSON into an equivalent source table. See
[Source formats](docs/source-formats.md) for the exact profiles and quirks.

Canonical mappings and ingestion behavior belong to
[`nwmmb-db`](https://github.com/nwmmb/nwmmb-db), not this utility.

## Combined workbooks

Combination is deliberately strict. Every input must:

- match the selected report type's positive source-schema profile; and
- have exactly the same columns in exactly the same order.

The utility fails the combination if either condition is false. It never builds a
union schema.

The combined rows are written to the first worksheet. A hidden worksheet named
`_timeless_downloader_metadata` records:

- `artifact_type=combined`
- `report_type=<selected type>`
- `format_version=1`

Combined workbooks are local-use artifacts. Do not upload them for nwmmb-db
ingestion; nwmmb-db rejects both the `_combined_` filename marker and the hidden
metadata marker.

## Authentication and privacy

The utility must run from the normal local network because Timeless blocks server
traffic. It reads a Timeless session cookie from `cookie.txt`, the
`TIMELESS_COOKIE` environment variable, or the saved GUI value. `cookie.txt`,
`.venv`, `downloads`, and build output are gitignored.

Report files may contain PII/PHI. Never commit downloads or copy their contents
into issues, logs, tests, or third-party tools. Tests use synthetic records only.

## Updating

The GUI checks the latest release at
`nwmmb/timeless-downloader-utility` and accepts only a wheel hosted on that
repository's GitHub Releases page. `Update Now` installs the wheel into the
launcher's private `.venv` and restarts `timeless_downloader` in isolated mode.

## Development

```bash
git clone git@github.com:nwmmb/timeless-downloader-utility.git
cd timeless-downloader-utility
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,download]"
.venv/bin/python -m pytest tests/
```

Tagged releases run the tests, build the
`timeless_downloader_utility-<version>-py3-none-any.whl` wheel, and attach it to a
GitHub Release.
