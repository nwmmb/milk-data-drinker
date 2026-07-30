import sys

from timeless_downloader import cli
from timeless_downloader.core import DownloadResult


def test_cli_preview_uses_shared_core_without_cookie(monkeypatch, capsys):
    answers = iter(["", "", "", "", ""])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(answers))
    monkeypatch.setattr(sys, "argv", ["timeless-download-cli", "--dry-run"])
    seen = []

    def fake_run(settings, callback):
        seen.append(settings)
        return DownloadResult(planned=1, completed=1)

    monkeypatch.setattr(cli, "run_download", fake_run)
    cli.main()
    assert seen[0].preview
    assert seen[0].cookie == ""
    assert "CLI fallback" in capsys.readouterr().out
