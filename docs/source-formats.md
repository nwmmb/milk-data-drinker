# Timeless source formats

This document covers only the formats the downloader requests and recovers. It
does not define nwmmb-db canonical column names or SQL ingestion mappings.

## Positive source profiles

An individual file must include the selected report's identifying headers:

| Report type | Required source headers |
|---|---|
| Donor Information | `Donor Barcode`, `Passed Screening` |
| Deposit Record | `Deposit`, `Donor/Milk Bank`, `Expiry Date`, `Volume Remaining (mL)` |
| Dispensation | `Order Number`, `Recipient`, `Bottle Size (mL)`, `Dispense Date` |
| Wastage | `Barcode`, `Bottles Disposed`, `Disposal Reason` |
| Batch Summary | `Batch`, `Created On`, `Created From`, `Original Volume(oz)` |

These fingerprints are intentionally source-header profiles. Canonicalized files
with snake_case nwmmb-db columns are not valid downloader combination inputs.

## Format recovery

Timeless commonly returns an HTML table with an `.xls` filename. Recovery tries
HTML first, then a real Excel workbook, then Latin-1 CSV. HTML recovery repairs
malformed Office-style `<td/>` and `<th/>` tags and retains `<br>`-separated cell
values with a visible delimiter.

Batch Summary uses a preview endpoint that embeds JSON in the response. The
downloader converts that JSON into an HTML source table with Timeless's displayed
headers before saving the individual file. Pagination rows whose `Batch` value
begins with `Page` are removed during combination.

Deposit Record exports include two trailing summary rows. Dispensation exports
include four. Those known rows are removed when combining; all other source rows
and columns are retained.

## Combination contract

All inputs must match one selected report type and have identical ordered columns.
A mismatch raises an error instead of silently adding, dropping, reordering, or
renaming fields. Duplicate rows are removed after concatenation. If a date-like
source column is present, rows are sorted by that column.

The output workbook puts combined data in the first worksheet and adds the hidden
`_timeless_downloader_metadata` worksheet. This marker allows downstream systems
to reject local combined artifacts reliably even if the filename changes.
