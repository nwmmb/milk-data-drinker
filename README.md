# milk-data-drinker

Parse Timeless MMBMS, Delta Lactoscope analyzer, and Jotform report files into normalized pandas DataFrames with canonical column names.

## Timeless downloader quick start

On Windows:

1. Download or clone this repository and extract it to a normal folder.
2. Double-click `run-downloader.bat`.

The launcher creates `.venv` inside the repository, installs the downloader and its
dependencies only inside that environment, and opens the graphical interface. It reuses
the same environment on later runs; nothing is installed into the machine-wide Python.

For a text-mode CLI instead of the GUI:

```bat
run-downloader.bat --cli
```

To preview a run without downloading reports:

```bat
run-downloader.bat --dry-run
```

### Manual virtual-environment setup

Windows:

```bat
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[download]"
.venv\Scripts\mdd-download.exe
```

macOS or Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[download]"
.venv/bin/mdd-download
```

These commands do use `pip`, because Python dependencies still need to be installed,
but the selected Python executable belongs to `.venv`; the global environment is not
changed.

## Usage

### As a library

```python
import milk_data_drinker

# Parse a single report file (auto-detects report type)
df = milk_data_drinker.read_file("path/to/report.xls")

# Parse all supported files in a directory tree
results = milk_data_drinker.read_directory("path/to/reports/")
# returns {report_type: DataFrame}
```

### Timeless report downloader

From the downloaded repository, use the launcher:

```bat
run-downloader.bat
```

The downloader provides a graphical interface (with a text-mode CLI fallback) for downloading Timeless MMBMS reports in time-windowed batches (weekly, monthly, quarterly) to avoid the system hanging on large exports. See `milk_data_drinker/downloader/README.md` for full documentation.

## Supported report types

| Report type | Source system | Parser module |
|---|---|---|
| `analyzer` | Delta Lactoscope | `analyzer/reader.py` |
| `deposit_record` | Timeless MMBMS | `timeless/deposit_record.py` |
| `dispensation` | Timeless MMBMS | `timeless/dispensation.py` |
| `donor_tracking` | Timeless MMBMS | `timeless/donor_tracking.py` |
| `donor_approval` | Timeless MMBMS | `timeless/donor_approval.py` |
| `donor_information` | Timeless MMBMS | `timeless/donor_information.py` |
| `donor_feedback` | Jotform | `jotform/feedback_survey.py` |
| `milk_depot` | Timeless MMBMS | `timeless/milk_depots.py` |
| `wastage_report` | Timeless MMBMS | `timeless/wastage.py` |
| `batch_summary` | Timeless MMBMS | `timeless/batch_summary.py` |

Report type is auto-detected by directory name, filename, or column fingerprinting. See [docs/report-types.md](docs/report-types.md) for original column schemas, ingestion transforms, and known quirks per report type.

## Development

```bash
git clone git@github.com:nwmmb/milk-data-drinker.git
cd milk-data-drinker
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,download]"
.venv/bin/python -m pytest tests/
```

### Local report fixtures

Operational report examples used by parser tests belong in `tests/fixtures/`. That
directory ignores all data files because they may contain PII/PHI or other non-public
operational information. Fixture-backed tests skip when the local examples are absent.
Do not force-add those files to git; add public synthetic fixtures separately only after
an explicit privacy review.
