"""Prompt-driven troubleshooting interface for the Timeless downloader."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

from .cookies import resolve_cookie
from .core import (
    REPORT_DISPLAY_NAMES,
    REPORT_TYPES,
    WINDOW_CHOICES,
    DownloadEvent,
    DownloadSettings,
    date_ranges,
    default_window,
    planned_downloads,
    previous_full_month,
    run_download,
)


def prompt_choice(
    prompt_text: str, options: list[tuple[str, str]], default_index: int = 0
) -> str:
    print(f"\n{prompt_text}\n")
    for index, (_, label) in enumerate(options):
        marker = " *" if index == default_index else ""
        print(f"  {index + 1}. {label}{marker}")
    while True:
        raw = input(f"\nEnter number [{default_index + 1}]: ").strip()
        if not raw:
            return options[default_index][0]
        try:
            choice = int(raw)
            if 1 <= choice <= len(options):
                return options[choice - 1][0]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def prompt_date(prompt_text: str, default: date) -> date:
    while True:
        raw = input(f"{prompt_text} [{default:%Y-%m-%d}]: ").strip()
        if not raw:
            return default
        try:
            return date.fromisoformat(raw)
        except ValueError:
            print("  Enter an exact date as YYYY-MM-DD.")


def _print_event(event: DownloadEvent) -> None:
    if event.kind == "log":
        print(f"  {event.message}")
    elif event.kind in {"fatal", "cancelled"}:
        print(f"\n{event.message}")


def main() -> None:
    preview = "--dry-run" in sys.argv or "--preview" in sys.argv
    print("=" * 56)
    print("  Timeless Report Downloader — CLI fallback")
    print("=" * 56)
    if preview:
        print("  Preview mode: no requests or files will be created.")

    report_options = [(key, REPORT_DISPLAY_NAMES[key]) for key in REPORT_TYPES]
    report_type = prompt_choice(
        "Which report do you want to download?", report_options
    )
    default_start, default_end = previous_full_month()
    print("\nEnter an exact date range (YYYY-MM-DD).")
    start_date = prompt_date("Start date", default_start)
    end_date = prompt_date("End date", default_end)

    window_options = list(WINDOW_CHOICES.items())
    default_index = [key for key, _ in window_options].index(
        default_window(report_type)
    )
    window_size = prompt_choice(
        "How large should each download window be?",
        window_options,
        default_index,
    )
    default_output = Path.cwd() / "downloads"
    output_raw = input(f"\nOutput directory [{default_output}]: ").strip()
    output_dir = Path(output_raw).expanduser() if output_raw else default_output
    cookie, source = resolve_cookie()
    if not preview and not cookie:
        print("\nNo saved cookie was found.")
        cookie = input("Paste a current Timeless cookie: ").strip()
    elif not preview:
        print(f"\nUsing the {source} cookie.")

    combine = False
    if not preview:
        combine = (
            input("Combine files into one workbook? [y/N]: ").strip().lower()
            == "y"
        )
    settings = DownloadSettings(
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        window_size=window_size,
        output_dir=output_dir,
        combine=combine,
        preview=preview,
        cookie=cookie,
    )
    try:
        ranges = date_ranges(settings)
        total = planned_downloads(settings)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    print("\nSummary")
    print(f"  Report: {REPORT_DISPLAY_NAMES[report_type]}")
    print(f"  Range: {start_date:%Y-%m-%d} through {end_date:%Y-%m-%d}")
    print(f"  Window: {WINDOW_CHOICES[window_size]}")
    print(f"  Planned: {total} ({len(ranges)} windows)")
    print(f"  Output: {output_dir.resolve()}")
    if not preview:
        answer = input("\nProceed? [Y/n]: ").strip().lower()
        if answer and answer != "y":
            print("Cancelled.")
            return

    try:
        result = run_download(settings, callback=_print_event)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    print(
        "\nDone: "
        f"{result.downloaded} downloaded, {result.existing} existing, "
        f"{result.no_data} no data, {result.failed} failed."
    )


if __name__ == "__main__":
    main()
