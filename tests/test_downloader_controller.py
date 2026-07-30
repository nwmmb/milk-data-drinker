import threading
from datetime import date
from pathlib import Path

import pytest

from milk_data_drinker.downloader.controller import DownloadController
from milk_data_drinker.downloader.core import (
    DownloadEvent,
    DownloadResult,
    DownloadSettings,
)


def settings(tmp_path, cookie="cookie=value"):
    return DownloadSettings(
        report_type="deposit_record",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 1, 1),
        window_size="weekly",
        output_dir=Path(tmp_path),
        cookie=cookie,
    )


def test_controller_validates_before_start(tmp_path):
    controller = DownloadController()
    with pytest.raises(ValueError, match="cookie"):
        controller.start(settings(tmp_path, cookie=""))
    assert not controller.running


def test_controller_moves_worker_events_and_completion_through_queue(tmp_path):
    controller = DownloadController()

    def runner(_settings, callback, cancel_event):
        assert not cancel_event.is_set()
        callback(DownloadEvent("progress", completed=1, total=1))
        return DownloadResult(planned=1, completed=1, downloaded=1)

    controller.start(settings(tmp_path), runner=runner)
    controller.thread.join(timeout=1)
    events = controller.drain_events()
    assert isinstance(events[0], DownloadEvent)
    assert events[0].kind == "progress"
    assert events[1][0] == "worker_done"
    assert events[1][1].downloaded == 1
    assert not controller.running


def test_controller_cancellation_is_cooperative(tmp_path):
    controller = DownloadController()
    entered = threading.Event()

    def runner(_settings, callback, cancel_event):
        entered.set()
        cancel_event.wait(1)
        return DownloadResult(cancelled=cancel_event.is_set())

    controller.start(settings(tmp_path), runner=runner)
    assert entered.wait(1)
    assert controller.cancel()
    controller.thread.join(timeout=1)
    assert controller.result.cancelled
    assert not controller.cancel()


def test_controller_reports_runtime_errors(tmp_path):
    controller = DownloadController()

    def runner(*_args, **_kwargs):
        raise RuntimeError("synthetic failure")

    controller.start(settings(tmp_path), runner=runner)
    controller.thread.join(timeout=1)
    event = controller.drain_events()[0]
    assert event[0] == "worker_error"
    assert str(event[1]) == "synthetic failure"
