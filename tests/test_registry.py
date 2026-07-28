from pathlib import Path

import pytest

from milk_data_drinker._registry import detect_type

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "wastage_report_example.xls"


@pytest.mark.skipif(
    not _FIXTURE.exists(),
    reason="optional local report fixture is not available",
)
def test_content_detection_uses_local_file_when_blob_path_has_no_hint():
    assert detect_type("uploads/unnamed-export.xls", str(_FIXTURE)) == "wastage_report"
