"""Timeless downloader interfaces."""

import warnings


def main() -> None:
    from .gui import main as gui_main

    gui_main()


def deprecated_main() -> None:
    warnings.warn(
        "mdd-download is deprecated; use timeless-download.",
        DeprecationWarning,
        stacklevel=2,
    )
    main()


def deprecated_cli_main() -> None:
    warnings.warn(
        "mdd-download-cli is deprecated; use timeless-download-cli.",
        DeprecationWarning,
        stacklevel=2,
    )
    from .cli import main as cli_main

    cli_main()


__all__ = ["main", "deprecated_main", "deprecated_cli_main"]
