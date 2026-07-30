"""Thread-safe controller used by the Tk interface."""

from __future__ import annotations

import queue
import threading
from typing import Callable

from .core import DownloadResult, DownloadSettings, run_download, validate_settings


class DownloadController:
    """Run the core on a worker and expose events through a queue."""

    def __init__(self) -> None:
        self.events: queue.Queue[object] = queue.Queue()
        self.cancel_event = threading.Event()
        self.running = False
        self.result: DownloadResult | None = None
        self.thread: threading.Thread | None = None

    def start(
        self,
        settings: DownloadSettings,
        *,
        runner: Callable[..., DownloadResult] = run_download,
    ) -> None:
        if self.running:
            raise RuntimeError("A download is already running.")
        validate_settings(settings)
        self.cancel_event = threading.Event()
        self.result = None
        self.running = True

        def work() -> None:
            try:
                result = runner(
                    settings,
                    callback=self.events.put,
                    cancel_event=self.cancel_event,
                )
                self.result = result
                self.events.put(("worker_done", result))
            except Exception as exc:
                self.events.put(("worker_error", exc))
            finally:
                self.running = False

        self.thread = threading.Thread(target=work, daemon=True)
        self.thread.start()

    def cancel(self) -> bool:
        if not self.running:
            return False
        self.cancel_event.set()
        return True

    def drain_events(self) -> list[object]:
        items = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except queue.Empty:
                return items
