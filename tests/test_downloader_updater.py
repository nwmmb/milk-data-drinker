from pathlib import Path

import pytest

from milk_data_drinker.downloader.updater import (
    UpdateError,
    UpdateInfo,
    check_for_update,
    find_wheel_url,
    install_update,
    restart_application,
)


WHEEL_URL = (
    "https://github.com/nwmmb/milk-data-drinker/releases/download/"
    "v0.2.0/milk_data_drinker-0.2.0-py3-none-any.whl"
)


def release(tag="v0.2.0", assets=None):
    return {
        "tag_name": tag,
        "body": "A compact GUI.",
        "assets": assets
        if assets is not None
        else [
            {
                "name": "milk_data_drinker-0.2.0-py3-none-any.whl",
                "browser_download_url": WHEEL_URL,
            }
        ],
    }


def test_update_discovery_and_current_version():
    update = check_for_update(fetcher=lambda: release(), current_version="0.1.0")
    assert update.tag == "v0.2.0"
    assert update.wheel_url == WHEEL_URL
    assert check_for_update(
        fetcher=lambda: release(), current_version="0.2.0"
    ) is None
    assert check_for_update(
        fetcher=lambda: (_ for _ in ()).throw(OSError("offline")),
        current_version="0.1.0",
    ) is None


def test_wheel_selection_rejects_nonofficial_urls():
    malicious = release(
        assets=[
            {
                "name": "milk_data_drinker-9.9.9-py3-none-any.whl",
                "browser_download_url": "https://example.com/bad.whl",
            }
        ]
    )
    assert find_wheel_url(malicious) is None


def test_install_uses_only_downloaded_wheel_and_current_python(tmp_path):
    calls = []

    def downloader(url, path):
        calls.append(("download", url, Path(path).name))
        Path(path).write_bytes(b"wheel")

    def runner(command, check):
        calls.append(("run", command, check))

    update = UpdateInfo("v0.2.0", (0, 2, 0), "", WHEEL_URL)
    install_update(
        update,
        executable="C:/app/.venv/Scripts/python.exe",
        downloader=downloader,
        runner=runner,
    )
    assert calls[0][0:2] == ("download", WHEEL_URL)
    command = calls[1][1]
    assert command[0] == "C:/app/.venv/Scripts/python.exe"
    assert command[1:6] == ["-m", "pip", "install", "--upgrade", "--no-deps"]
    assert command[-1].endswith(".whl")


def test_missing_wheel_and_install_failure_are_recoverable():
    with pytest.raises(UpdateError, match="private .venv"):
        install_update(
            UpdateInfo("v0.2.0", (0, 2, 0), "", WHEEL_URL),
            executable="C:/Python/python.exe",
        )

    with pytest.raises(UpdateError, match="no official wheel"):
        install_update(UpdateInfo("v0.2.0", (0, 2, 0), "", None))

    def fail_download(_url, _path):
        raise OSError("network unavailable")

    with pytest.raises(UpdateError, match="network unavailable"):
        install_update(
            UpdateInfo("v0.2.0", (0, 2, 0), "", WHEEL_URL),
            downloader=fail_download,
        )


def test_restart_uses_isolated_mode():
    calls = []
    restart_application(executable="python.exe", execv=lambda *args: calls.append(args))
    assert calls == [
        (
            "python.exe",
            ["python.exe", "-I", "-m", "milk_data_drinker.downloader"],
        )
    ]
