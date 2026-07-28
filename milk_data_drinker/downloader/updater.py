"""Check for updates via GitHub Releases and offer to install them."""

import json
import logging
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from .._version import __version__

log = logging.getLogger(__name__)

_RELEASES_URL = (
    "https://api.github.com/repos/nwmmb/milk-data-drinker/releases/latest"
)
_TIMEOUT = 5


def _fetch_latest() -> dict | None:
    try:
        req = urllib.request.Request(
            _RELEASES_URL,
            headers={"Accept": "application/vnd.github+json"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _parse_version(tag: str) -> tuple[int, ...]:
    return tuple(int(x) for x in tag.lstrip("v").split("."))


def _find_wheel_url(release: dict) -> str | None:
    for asset in release.get("assets", []):
        if asset["name"].endswith(".whl"):
            return asset["browser_download_url"]
    return None


def check_for_update() -> None:
    release = _fetch_latest()
    if release is None:
        return

    tag = release.get("tag_name", "")
    try:
        latest = _parse_version(tag)
        current = _parse_version(__version__)
    except (ValueError, AttributeError):
        return

    if latest <= current:
        return

    print(f"\n  A new version is available: {tag} (you have v{__version__})")
    body = release.get("body", "").strip()
    if body:
        for line in body.splitlines()[:3]:
            print(f"    {line}")

    try:
        answer = input("  Update now? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if answer and answer != "y":
        return

    wheel_url = _find_wheel_url(release)
    if wheel_url:
        print(f"  Downloading {Path(wheel_url).name}...")
        with tempfile.TemporaryDirectory() as tmp:
            whl_path = Path(tmp) / Path(wheel_url).name
            urllib.request.urlretrieve(wheel_url, whl_path)
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "--upgrade", str(whl_path)],
                check=True,
            )
    else:
        install_url = (
            f"git+https://github.com/nwmmb/milk-data-drinker.git@{tag}"
        )
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "--upgrade",
             f"milk-data-drinker[download] @ {install_url}"],
            check=True,
        )

    print("\n  Updated successfully. Please restart to use the new version.")
    sys.exit(0)
