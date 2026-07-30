"""Timeless downloader interfaces."""


def main() -> None:
    from .gui import main as gui_main

    gui_main()


__all__ = ["main"]
