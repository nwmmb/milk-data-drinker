from pathlib import Path

from milk_data_drinker._registry import detect_type


def test_content_detection_uses_local_file_when_blob_path_has_no_hint():
    fixture = Path(__file__).resolve().parent / "fixtures" / "wastage_report_example.xls"
    assert detect_type("uploads/unnamed-export.xls", str(fixture)) == "wastage_report"
