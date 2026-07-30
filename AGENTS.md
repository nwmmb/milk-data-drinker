# AGENTS.md

This repository is the `timeless-downloader-utility` staff application. It owns
Timeless report request parameters, date-window behavior, authentication cookie
handling, local source-format recovery, strict file combination, the GUI/CLI,
launcher, updater, and tagged wheel releases.

It does not own analyzer/Jotform parsing, canonical column mappings, Azure Blob or
SQL behavior, or ingestion transformations. Those live inside
`~/repos/nwmmb-db/function_app/milk_data_drinker/`. Never import that package here
or reproduce its canonical transformations.

## Commands

Use the repository virtual environment:

```bash
.venv/bin/python -m pytest tests/
.venv/bin/python -m build --wheel
```

The distribution is `timeless-downloader-utility`; the Python namespace is
`timeless_downloader`. Primary entry points are `timeless-download` and
`timeless-download-cli`. The two `mdd-*` aliases are deprecated and exist only for
the first renamed release.

## Contracts

- Individual outputs retain original Timeless headers and ordered columns.
- Recovery may repair transport structure and remove known summary/footer rows,
  but may not apply nwmmb-db canonical renames, derived fields, or coercions.
- Combination requires one report type and identical ordered columns for every
  input; never create a union schema.
- Combined workbooks must place data first and include the hidden
  `_timeless_downloader_metadata` worksheet with `artifact_type`, `report_type`,
  and `format_version`.
- Updater downloads must be limited to official wheels from
  `nwmmb/timeless-downloader-utility` releases.

All tests and examples must be synthetic. Never read, commit, or expose report
downloads, cookies, PII, or PHI.
