# Local-only report fixtures

This directory holds optional report examples used by the parser test suite. The
operational examples may contain PII/PHI or other non-public information, so every
data file here is ignored by git and must never be committed to this public repo.

The fixture-backed tests skip when their corresponding local file is absent. Local
development currently recognizes these filenames:

- `batch_summary_example.xls`
- `donor_feedback_example.csv`
- `donor_information_report_example_sanitized.csv`
- `milk_depots_example.csv`
- `wastage_report_example.xls`

Public, synthetic fixtures can be added later only after they have been explicitly
reviewed as safe to publish.
