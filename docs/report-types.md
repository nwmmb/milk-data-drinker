# Report Type Reference

**Timeless MMBMS version:** 4.3.5 (as of 2026-07-30)

This document describes every report type that milk-data-drinker can parse, including the original column schema (as exported from the source system), the transforms the parser applies for nwmmb-db ingestion, and known quirks.

## How reports flow through the system

Reports take one of two paths:

1. **Downloader (local use)** — The `mdd-download` tool downloads reports from Timeless and saves them as `.xls` files. When combining multiple files into a single workbook, only format-recovery fixes are applied (HTML-as-XLS handling, summary row removal). Original column names and structure are preserved.

2. **nwmmb-db ingestion** — When report files are uploaded to Azure Blob Storage, the nwmmb-db Azure Function calls `milk_data_drinker.read_file()`, which applies the full parsing pipeline: format recovery, column normalization (snake_case + lowercase), report-specific renames, type coercions, and column splits/drops. The output matches the nwmmb-db SQL schema.

The **Original schema** sections below show column names as they appear in the source export. The **Ingestion transforms** sections describe what the parser changes for the database.

---

## Timeless reports

### Deposit Record

**Source:** Timeless MMBMS
**Parser:** `timeless/deposit_record.py`
**Downloadable:** Yes (quarterly default)

Records of milk deposits received from donors, including volumes, dates, and donor identification.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Deposit | text | Deposit ID (e.g., `DEP041036`) |
| Donor/Milk Bank | text | Combined `DON#####: Lastname, Firstname` |
| Date Received | date text | |
| Expiry Date | date text | |
| Volume Remaining (mL) | text | Comma-formatted (e.g., `3,790.00`) |
| Used Volume (mL) | text | Comma-formatted |
| Total Volume (mL) | text | Comma-formatted |

Additional columns may be present depending on the Timeless export configuration.

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Deposit` &rarr; `deposit_id` | Rename |
| `Donor/Milk Bank` &rarr; `donor_id` | Split on `:`, keep DON##### ID, drop name |
| Volume columns | Strip commas, convert to numeric |
| Date columns | Convert to datetime |
| Last 2 rows | Stripped (summary/totals appended by Timeless) |

#### Known quirks

- **Summary rows:** Timeless appends 2 summary/total rows at the end of every export.
- **Comma-formatted numbers:** Volume fields use commas as thousands separators (e.g., `3,790.00`).

---

### Dispensation

**Source:** Timeless MMBMS
**Parser:** `timeless/dispensation.py`
**Downloadable:** Yes (quarterly default)

Records of milk dispensed to recipients (hospitals, outpatients, milk banks, research facilities).

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Recipient | text | Combined `PREFIX#####: Name` (e.g., `PAT00123: Lastname, Firstname`) |
| Order Number | text | |
| Bottle Size (mL) | numeric | |
| Dispense Date | date text | |
| Date Cancelled | date text | May be empty |

Additional columns present depending on export configuration (detail mode).

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Recipient` &rarr; `recipient_id` + `recipient_name` + `recipient_type` | Split on `:` for ID and name; derive type from prefix (`PAT`=outpatient, `HOS`=hospital, `MBK`=milk_bank, `RFA`=research_facility) |
| Date columns | Convert to datetime |
| Last 4 rows | Stripped (summary/totals) |

#### Known quirks

- **Summary rows:** Timeless appends 4 summary/total rows at the end.

---

### Donor Information

**Source:** Timeless MMBMS
**Parser:** `timeless/donor_information.py`
**Downloadable:** Yes (quarterly default, 4 filter batches by status)

Comprehensive donor profiles including demographics, screening milestones, and approval status. Downloaded in 4 batches: withdrawn, inactive, active, retired.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Donor Barcode | text | The canonical `DON#####` identifier |
| Donor ID | integer | Timeless internal numeric ID (not the barcode) |
| Passed Screening | text | |
| 1st Microbiology Results | text | |
| 2nd Microbiology Results | text | |
| 3rd Microbiology Results | text | |
| Baby's Gestational Age at Birth | text | Note the possessive apostrophe |
| Approved Date | date text | |

Many additional date and screening columns are present (30+ columns total). All columns with "Date" in the name are date-typed.

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Donor Barcode` &rarr; `donor_id` | Rename (this is the canonical DON##### join key) |
| Original `Donor ID` (numeric) | **Dropped** (would collide with the barcode rename) |
| `1st/2nd/3rd Microbiology Results` | Renamed to `first_/second_/third_microbiology_results` |
| `Baby's Gestational Age at Birth` | Renamed to `baby_gestational_age_at_birth` (possessive stripped) |
| All date columns | Convert to datetime |

#### Known quirks

- **Screening date ordering:** Historical/bulk-imported records have milestone dates that don't follow the nominal screening order (e.g., `blood_screening_collection_date` before `donor_application_complete_date`). Only recent records (past ~6 months) have consistent ordering. See `timeless_export_quirks.md` for details.

---

### Donor Tracking

**Source:** Timeless MMBMS
**Parser:** `timeless/donor_tracking.py`
**Downloadable:** No

Donor deposit activity summary, tracking total received volume and deposit counts per donor.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Donor/Milk Bank | text | Appears **twice**: first is `DON#####: Name`, second is the deposit count |
| Total Received Volume (mL) | text | Comma-formatted |
| Follow Up Dates | text | Not meaningful per parser documentation |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| First `Donor/Milk Bank` &rarr; `donor_id` | Split on `:`, keep DON##### ID |
| Second `Donor/Milk Bank` &rarr; `deposit_count` | pandas auto-deduplicates to `donor_milk_bank_1`, renamed |
| `Follow Up Dates` | **Dropped** (not meaningful) |
| `Total Received Volume (mL)` | Strip commas, convert to numeric |

#### Known quirks

- **Duplicate column name:** Two columns share the name "Donor/Milk Bank" — pandas auto-renames the second to `Donor/Milk Bank.1` (or `donor_milk_bank_1` after normalization).

---

### Donor Approval

**Source:** Timeless MMBMS
**Parser:** `timeless/donor_approval.py`
**Downloadable:** No

Donor approval records with addresses and approval dates.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Donor ID | integer | Timeless internal numeric ID |
| First Name | text | |
| Donor Address | text | |
| Approved Date | date text | |

File format is CSV (not HTML-as-XLS like other Timeless reports). The first 5 rows are metadata/title rows that must be skipped.

#### Ingestion transforms

| Transform | Detail |
|---|---|
| Column names | `clean_column_names()` + lowercase only (no explicit renames) |
| `Approved Date` | Convert to datetime |

#### Known quirks

- **CSV format with metadata header:** Unlike other Timeless reports, this one is actual CSV — but with 5 junk metadata/title rows before the real column header.

---

### Wastage Report

**Source:** Timeless MMBMS
**Parser:** `timeless/wastage.py`
**Downloadable:** Yes (weekly default)

Records of milk disposal and wastage events, covering deposits (whole-deposit disposal), bottled batches, and pool wastage.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Barcode | text | `DEP#####` (deposit), batch ID, or pool ID |
| Waste Disposed Recorded Date | date text | |
| Bottles Disposed | text | Format: `60 mL: 27` (size: count) |
| Disposal Reason | text | |
| Total Volume (mL) | text | Comma-formatted |
| Volume Wasted (mL) | text | |
| Disposed Volume (mL) | text | |
| Percent of Volume Wasted (mL) | text | Contains `%` sign |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Barcode` &rarr; `deposit_id` / `batch_id` / `pool_id` | Decomposed into three mutually exclusive columns by prefix |
| `Waste Disposed Recorded Date` &rarr; `disposal_date` | Rename + datetime conversion |
| `Bottles Disposed` &rarr; `bottle_size_ml` + `quantity_disposed` | Parsed from text format |
| `wastage_type` | Derived column: `deposit`, `batch`, or `pool` |
| `wastage_date` | Set only for pool events |
| Multi-event rows | Exploded from `<br>`-joined cells into separate rows |
| Bottled-batch volume | Allocated proportionally by bottle-size x count weight |
| `Barcode`, `Bottles Disposed` | **Dropped** after decomposition |

#### Known quirks

- **HTML-as-XLS format:** Like all Timeless exports, `.xls` files are actually HTML tables.
- **Multi-event row cramming:** When a batch has events on multiple dates, Timeless packs all events into one row using `<br>` separators within cells. Date, bottles, and reason columns have parallel `<br>`-separated entries.
- **Inconsistent `<br>` variants:** The same row may use `<br />` (self-closing), `</BR>` (uppercase closing tag), and other variants. Parser uses case-insensitive regex.
- **Trailing `<br>` in single-value cells:** Even cells with one value have a trailing `<br />`.
- **Non-breaking spaces:** `&nbsp;` entities used for alignment padding in the Bottles Disposed column.
- **Date range leakage:** If any event in a batch falls within the requested date range, Timeless includes all events for that batch — even ones outside the range.

---

### Batch Summary

**Source:** Timeless MMBMS
**Parser:** `timeless/batch_summary.py`
**Downloadable:** Yes (weekly default)

Pasteurized batch metadata including creation date, bottle sizes, nutrient analysis, and approval status. Used for lot recall tracing.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Batch | text | Batch ID |
| Created On | date text | |
| Created From | text | Source milk references |
| Donor/Milk Bank | text | |
| Original Volume(oz) | numeric | **Actually milliliters** despite header |
| Original Bottles: {size} oz * | integer | One column per bottle size (e.g., 30, 45, 50, 60, 90, 100, 120, 240). Non-zero value indicates the bottle size for that batch |
| Milk Type | text | |
| Remaining Volume(oz) | numeric | |
| Remaining Bottles: {size} oz Bottles | integer | One per size |
| Fat | numeric | |
| Protein | numeric | |
| Lactose | numeric | |
| Cal/Oz | numeric | |
| g/dL | text | |
| Location | text | |
| Expiry Date | date text | |
| Milk Approved | text | e.g., `Approved`, `Not Yet Approved` |
| Milk Status | text | e.g., `Dispensed`, `Active` |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Batch` &rarr; `batch_id` | Rename |
| `Created On` &rarr; `created_date` | Rename + convert to `date` |
| `Original Volume(oz)` &rarr; `original_volume_ml` | Rename (unit correction) |
| Multiple `Original Bottles` columns &rarr; `bottle_size_ml` | Collapsed: non-zero column determines the bottle size |
| `Fat`, `Protein`, `Lactose` | Convert to numeric |
| `Expiry Date` | Convert to `date` |
| Dropped columns | `Donor/Milk Bank`, `Created From`, `Cal/Oz`, `g/dL`, `Location`, `Remaining Volume(oz)`, all `Original Bottles` and `Remaining Bottles` columns |
| Output trimmed to | `batch_id`, `created_date`, `bottle_size_ml`, `milk_type`, `original_volume_ml`, `fat`, `protein`, `lactose`, `expiry_date`, `milk_approved`, `milk_status` |
| "Page N of N" rows | Stripped (pagination footer) |

#### Known quirks

- **Pagination truncation:** The export endpoint only returns page 1 of results. The downloader uses `per_page=300` and weekly windows to stay within limits.
- **Volume unit mislabeling:** Headers say "oz" but values are in milliliters. Confirmed by bottle-size arithmetic (60 mL bottles, not 60 oz).
- **Column shift (last 5 columns):** The last 5 columns (`g/dL` through `Milk Status`) have data shifted left by one position relative to headers. The parser drops `g/dL` and `Milk Status` (the bookend columns) and the remaining columns realign. This quirk is present in the standard HTML export; the JSON preview endpoint used by the downloader maps fields correctly.
- **Downloaded via JSON preview endpoint:** Unlike other reports, the downloader fetches batch summary data from `/reports/preview` as JSON, then converts it to an HTML table (`_convert_preview_json()` in `core.py`). This avoids the column-shift and pagination issues.

---

### Milk Depot

**Source:** Timeless MMBMS
**Parser:** `timeless/milk_depots.py`
**Downloadable:** No

Reference/master list of milk depot locations. Not a periodic report — a raw download of the depot table.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| milkdepotID | integer | camelCase (no spaces) |
| milkdepotName | text | |
| milkdepotContact | text | |
| milkdepotAddress1 | text | |
| milkdepotAddress2 | text | |
| milkdepotPostal | text | |
| milkdepotPhone | text | |
| milkdepotEmail | text | |
| milkdepotOrder | integer | |
| milkdepotActive | text | |
| milkdepotCity | text | |
| milkdepotState | text | |
| milkdepotCountry | text | |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| All columns | camelCase &rarr; `snake_case` (e.g., `milkdepotID` &rarr; `milk_depot_id`) |
| `milk_depot_id` | Cast to integer |

#### Known quirks

- **UTF-16LE null bytes:** Every data field value is UTF-16LE encoded (a null byte after each character), while the header row is plain ASCII. The parser strips null bytes before parsing as CSV.
- **Not HTML-as-XLS:** Unlike other Timeless exports, this is actually a text file (CSV-like) with the encoding issue above.

---

## Non-Timeless reports

### Analyzer (Delta Lactoscope)

**Source:** Delta Lactoscope instrument software
**Parser:** `analyzer/reader.py`
**Downloadable:** No

Milk composition analysis results from the Lactoscope instrument. Each sample has Mean and StdDev replicates that are pivoted into a single row.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Name | text | Free-form text containing `DEP #####` somewhere |
| Date | date text | Format: `MM/DD/YYYY HH:MM:SS AM/PM` |
| Replicate | text | `Mean` or `StdDev` |
| Fat | numeric | |
| Protein | numeric | |
| Lactose | numeric | |
| Solids | numeric | |
| Cal | numeric | |
| Nutr Pro | numeric | Space in name |
| Type | text | |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| `Name` &rarr; `deposit_id` | Regex extraction of `DEP\s*\d+`; rows without a valid ID are dropped |
| `Date` &rarr; `date` | Parsed from `%m/%d/%Y %I:%M:%S %p` format |
| Mean/StdDev pivot | StdDev row's numeric columns become `fat_stddev`, `protein_stddev`, etc., merged alongside the Mean row |
| `source_file` | Added column with the source filename |
| `Type` | **Dropped** |

#### Known quirks

- **Free-form deposit ID:** The `Name` field is free text entered by the operator — the parser uses regex to extract the DEP ID. Rows without a valid deposit ID are silently dropped.

---

### Donor Feedback Survey

**Source:** Jotform
**Parser:** `jotform/feedback_survey.py`
**Downloadable:** No

Donor experience survey responses exported from Jotform. Column headers are full question sentences.

#### Original schema

| Column | Type | Notes |
|---|---|---|
| Submission Date | date text | Format: `DD-Mon-YY` (e.g., `15-Jul-26`) |
| (question sentence headers) | text | 14+ columns with full question text as headers |
| Rating columns (positions 13-15) | text | Three satisfaction rating columns; positions 14-15 may have blank headers in the export |
| Milk drop columns (positions 8-10) | text | Three mutually exclusive columns (one populated per row, determined by the channel question at position 7) |

#### Ingestion transforms

| Transform | Detail |
|---|---|
| Rating columns (13, 14, 15) | Renamed by position to `friendliness_of_staff`, `gratitude_for_donation`, `ease_of_arrangements` |
| Three milk drop columns (8, 9, 10) | Coalesced into single `milk_drop` column; originals dropped |
| Question-sentence headers | 14 long column names aliased to short canonical names (e.g., `how_long_did_it_take_you_to_complete_...` &rarr; `approval_process_duration`) |
| Multi-select values | Newline-joined within cells; re-joined with `"; "` |
| Self-identification column | **Dropped** (staff handle contact requests in Jotform) |
| `Submission Date` | Parsed as datetime |

#### Known quirks

- **UTF-8 BOM encoding:** The CSV export uses `utf-8-sig` encoding (with byte-order mark). This defeats the content fingerprinter's `latin1` fallback, so detection relies on path/filename hints.
- **Blank column headers:** Jotform exports sometimes have blank headers for positions 14 and 15 — pandas deduplicates them. The parser renames by position index rather than header text.
- **Column positions may shift:** Since some renames are by position index, adding or removing questions in Jotform would require updating the position constants in the parser.
