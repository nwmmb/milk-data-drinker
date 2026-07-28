# milk-data-drinker

Parse Timeless MMBMS, Delta Lactoscope analyzer, and Jotform report files into normalized pandas DataFrames with canonical column names.

## Installation

```bash
pip install "milk-data-drinker @ git+https://github.com/nwmmb/milk-data-drinker.git@v0.1.0"
```

To include the Timeless report downloader:

```bash
pip install "milk-data-drinker[download] @ git+https://github.com/nwmmb/milk-data-drinker.git@v0.1.0"
```

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

After installing with the `[download]` extra:

```bash
mdd-download
```

Or:

```bash
python -m milk_data_drinker.downloader
```

The downloader walks you through an interactive menu to download Timeless MMBMS reports in time-windowed batches (weekly, monthly, quarterly) to avoid the system hanging on large exports. See `milk_data_drinker/downloader/README.md` for full documentation.

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

Report type is auto-detected by directory name, filename, or column fingerprinting.

## Development

```bash
git clone git@github.com:nwmmb/milk-data-drinker.git
cd milk-data-drinker
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,download]"
pytest tests/
```

### Local report fixtures

Operational report examples used by parser tests belong in `tests/fixtures/`. That
directory ignores all data files because they may contain PII/PHI or other non-public
operational information. Fixture-backed tests skip when the local examples are absent.
Do not force-add those files to git; add public synthetic fixtures separately only after
an explicit privacy review.
