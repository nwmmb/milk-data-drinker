from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import timeless_downloader


ROOT = Path(__file__).resolve().parents[1]


def test_distribution_namespace_and_entry_points():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    assert project["name"] == "timeless-downloader-utility"
    assert project["scripts"] == {
        "timeless-download": "timeless_downloader:main",
        "timeless-download-cli": "timeless_downloader.cli:main",
        "mdd-download": "timeless_downloader:deprecated_main",
        "mdd-download-cli": "timeless_downloader:deprecated_cli_main",
    }
    assert not list((ROOT / "milk_data_drinker").rglob("*.py"))


def test_compatibility_aliases_warn(monkeypatch):
    calls = []
    monkeypatch.setattr(timeless_downloader, "main", lambda: calls.append("gui"))
    with pytest.warns(DeprecationWarning, match="timeless-download"):
        timeless_downloader.deprecated_main()
    assert calls == ["gui"]


def test_launcher_uses_renamed_namespace_and_requires_fresh_old_environment():
    launcher = (ROOT / "run-downloader.bat").read_text()
    assert "-m timeless_downloader" in launcher
    assert "import timeless_downloader" in launcher
    assert 'if exist ".venv\\.mdd-packaged-v2" goto :old_environment' in launcher
    assert "Delete the .venv folder" in launcher
