"""Noninteractive discovery and installation of official release wheels."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from ._version import __version__

RELEASES_URL = (
    "https://api.github.com/repos/nwmmb/timeless-downloader-utility/releases/latest"
)
TIMEOUT = 5


class UpdateError(RuntimeError):
    """A recoverable update discovery or installation failure."""


@dataclass(frozen=True)
class UpdateInfo:
    tag: str
    version: tuple[int, ...]
    notes: str
    wheel_url: str | None


def fetch_latest_release() -> dict:
    request = urllib.request.Request(
        RELEASES_URL,
        headers={"Accept": "application/vnd.github+json"},
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
        return json.loads(response.read())


def parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(part) for part in tag.lstrip("v").split("."))


def _is_official_wheel_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and parsed.hostname == "github.com"
        and parsed.path.startswith(
            "/nwmmb/timeless-downloader-utility/releases/download/"
        )
        and Path(parsed.path).name.endswith(".whl")
    )


def find_wheel_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        name = str(asset.get("name", ""))
        url = str(asset.get("browser_download_url", ""))
        if (
            name.startswith("timeless_downloader_utility-")
            and name.endswith(".whl")
            and _is_official_wheel_url(url)
        ):
            return url
    return None


def check_for_update(
    *,
    fetcher: Callable[[], dict] = fetch_latest_release,
    current_version: str = __version__,
) -> UpdateInfo | None:
    """Return update metadata, or None when current/offline/invalid."""
    try:
        release = fetcher()
        tag = str(release.get("tag_name", ""))
        latest = parse_version(tag)
        current = parse_version(current_version)
    except Exception:
        return None
    if latest <= current:
        return None
    return UpdateInfo(
        tag=tag,
        version=latest,
        notes=str(release.get("body", "")).strip(),
        wheel_url=find_wheel_url(release),
    )


def install_update(
    update: UpdateInfo,
    *,
    executable: str = sys.executable,
    downloader: Callable[[str, str | Path], object] = urllib.request.urlretrieve,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    """Install an official wheel into the environment running the app."""
    if Path(executable).parent.parent.name != ".venv":
        raise UpdateError("Update Now requires the launcher private .venv.")
    if not update.wheel_url or not _is_official_wheel_url(update.wheel_url):
        raise UpdateError(
            f"{update.tag} has no official wheel. You can keep using this version."
        )
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            wheel_path = Path(temp_dir) / Path(
                urlparse(update.wheel_url).path
            ).name
            downloader(update.wheel_url, wheel_path)
            runner(
                [
                    executable,
                    "-m",
                    "pip",
                    "install",
                    "--upgrade",
                    "--no-deps",
                    str(wheel_path),
                ],
                check=True,
            )
    except Exception as exc:
        raise UpdateError(f"Update failed: {exc}") from exc


def restart_application(
    *,
    executable: str = sys.executable,
    execv: Callable[[str, list[str]], object] = os.execv,
) -> None:
    """Replace the current process with an isolated-mode GUI process."""
    execv(
        executable,
        [executable, "-I", "-m", "timeless_downloader"],
    )
