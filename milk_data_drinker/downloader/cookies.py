"""Cookie storage and resolution without ever exposing cookie contents."""

from __future__ import annotations

import os
from pathlib import Path

COOKIE_FILENAME = "cookie.txt"


def cookie_path(base_dir: Path | str | None = None) -> Path:
    return Path(base_dir or Path.cwd()) / COOKIE_FILENAME


def saved_cookie_exists(base_dir: Path | str | None = None) -> bool:
    path = cookie_path(base_dir)
    try:
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def resolve_cookie(
    new_cookie: str = "",
    *,
    base_dir: Path | str | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str, str]:
    """Resolve new value, ignored cookie.txt, then TIMELESS_COOKIE."""
    if new_cookie.strip():
        return new_cookie.strip(), "new"
    path = cookie_path(base_dir)
    try:
        saved = path.read_text(encoding="utf-8").strip()
    except OSError:
        saved = ""
    if saved:
        return saved, "saved"
    value = (environ or os.environ).get("TIMELESS_COOKIE", "").strip()
    if value:
        return value, "environment"
    return "", "missing"


def remember_cookie(cookie: str, base_dir: Path | str | None = None) -> Path:
    value = cookie.strip()
    if not value:
        raise ValueError("There is no new cookie to remember.")
    path = cookie_path(base_dir)
    path.write_text(value, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return path


def forget_cookie(base_dir: Path | str | None = None) -> bool:
    path = cookie_path(base_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
