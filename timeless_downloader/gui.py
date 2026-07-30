"""Tkinter interface for the Timeless report downloader."""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from tkcalendar import DateEntry

from .cookies import (
    forget_cookie,
    remember_cookie,
    resolve_cookie,
    saved_cookie_exists,
)
from .controller import DownloadController
from .core import (
    MIN_DATE,
    REPORT_DISPLAY_NAMES,
    WINDOW_CHOICES,
    DownloadEvent,
    DownloadResult,
    DownloadSettings,
    default_window,
    planned_downloads,
    previous_full_month,
    validate_settings,
)
from .updater import (
    UpdateError,
    UpdateInfo,
    check_for_update,
    install_update,
    restart_application,
)


class DownloaderApp:
    POLL_MS = 75

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Timeless Report Downloader")
        self.root.geometry("760x650")
        self.root.minsize(700, 600)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.controller = DownloadController()
        self.closing = False
        self.update_info: UpdateInfo | None = None
        self.updating = False
        self.update_queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self.settings_controls: list[tk.Widget] = []
        self.cookie_controls: list[tk.Widget] = []

        start, end = previous_full_month()
        self.report_var = tk.StringVar(value=REPORT_DISPLAY_NAMES["donor_information"])
        self.window_var = tk.StringVar(value=WINDOW_CHOICES["quarterly"])
        self.output_var = tk.StringVar(value=str(Path.cwd() / "downloads"))
        self.combine_var = tk.BooleanVar(value=False)
        self.preview_var = tk.BooleanVar(value=False)
        self.cookie_var = tk.StringVar()
        self.remember_var = tk.BooleanVar(value=False)
        self.status_var = tk.StringVar(value="Ready")
        self.plan_var = tk.StringVar()
        self.saved_cookie_var = tk.StringVar()
        self.count_vars = {
            "downloaded": tk.StringVar(value="Downloaded: 0"),
            "existing": tk.StringVar(value="Existing: 0"),
            "no_data": tk.StringVar(value="No data: 0"),
            "failed": tk.StringVar(value="Failed: 0"),
        }

        self._build(start, end)
        self._refresh_cookie_status()
        self._refresh_plan()
        self._apply_preview_state()
        self.root.after(self.POLL_MS, self._poll)
        threading.Thread(target=self._check_update, daemon=True).start()

    def _build(self, start: date, end: date) -> None:
        outer = ttk.Frame(self.root, padding=12)
        outer.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)
        outer.columnconfigure(1, weight=1)
        outer.rowconfigure(8, weight=1)

        title = ttk.Label(
            outer,
            text="Timeless Report Downloader",
            font=("TkDefaultFont", 14, "bold"),
        )
        title.grid(row=0, column=0, columnspan=1, sticky="w", pady=(0, 8))
        self.update_frame = ttk.Frame(outer)
        self.update_label = ttk.Label(self.update_frame)
        self.update_label.pack(side="left")
        self.update_button = ttk.Button(
            self.update_frame, text="Update Now", command=self._start_update
        )
        self.update_button.pack(side="left", padx=(8, 0))

        ttk.Label(outer, text="Report type").grid(row=1, column=0, sticky="w", pady=3)
        report = ttk.Combobox(
            outer,
            textvariable=self.report_var,
            values=list(REPORT_DISPLAY_NAMES.values()),
            state="readonly",
        )
        report.grid(row=1, column=1, columnspan=2, sticky="ew", pady=3)
        report.bind("<<ComboboxSelected>>", self._report_changed)
        self.settings_controls.append(report)

        dates = ttk.Frame(outer)
        dates.grid(row=2, column=0, columnspan=3, sticky="ew", pady=3)
        dates.columnconfigure(1, weight=1)
        dates.columnconfigure(3, weight=1)
        ttk.Label(dates, text="Start date").grid(row=0, column=0, sticky="w")
        self.start_date = DateEntry(
            dates,
            date_pattern="yyyy-mm-dd",
            mindate=MIN_DATE,
            maxdate=date.today(),
            year=start.year,
            month=start.month,
            day=start.day,
        )
        self.start_date.grid(row=0, column=1, sticky="ew", padx=(8, 16))
        ttk.Label(dates, text="End date").grid(row=0, column=2, sticky="w")
        self.end_date = DateEntry(
            dates,
            date_pattern="yyyy-mm-dd",
            mindate=MIN_DATE,
            maxdate=date.today(),
            year=end.year,
            month=end.month,
            day=end.day,
        )
        self.end_date.grid(row=0, column=3, sticky="ew", padx=(8, 0))
        self.start_date.bind("<<DateEntrySelected>>", lambda _event: self._refresh_plan())
        self.end_date.bind("<<DateEntrySelected>>", lambda _event: self._refresh_plan())
        self.settings_controls.extend([self.start_date, self.end_date])

        ttk.Label(outer, text="Window size").grid(row=3, column=0, sticky="w", pady=3)
        window = ttk.Combobox(
            outer,
            textvariable=self.window_var,
            values=list(WINDOW_CHOICES.values()),
            state="readonly",
        )
        window.grid(row=3, column=1, sticky="ew", pady=3)
        window.bind("<<ComboboxSelected>>", lambda _event: self._refresh_plan())
        ttk.Label(outer, textvariable=self.plan_var).grid(
            row=3, column=2, sticky="e", padx=(8, 0)
        )
        self.settings_controls.append(window)

        ttk.Label(outer, text="Output folder").grid(row=4, column=0, sticky="w", pady=3)
        output_entry = ttk.Entry(outer, textvariable=self.output_var)
        output_entry.grid(row=4, column=1, sticky="ew", pady=3)
        browse = ttk.Button(outer, text="Browse…", command=self._browse)
        browse.grid(row=4, column=2, sticky="e", padx=(8, 0), pady=3)
        self.settings_controls.extend([output_entry, browse])

        options = ttk.Frame(outer)
        options.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(4, 3))
        self.combine_check = ttk.Checkbutton(
            options, text="Combine into one workbook", variable=self.combine_var
        )
        self.combine_check.pack(side="left")
        preview = ttk.Checkbutton(
            options,
            text="Preview only (no requests)",
            variable=self.preview_var,
            command=self._preview_changed,
        )
        preview.pack(side="left", padx=(20, 0))
        self.settings_controls.extend([self.combine_check, preview])

        cookie_frame = ttk.LabelFrame(outer, text="Timeless cookie", padding=8)
        cookie_frame.grid(row=6, column=0, columnspan=3, sticky="ew", pady=(5, 6))
        cookie_frame.columnconfigure(1, weight=1)
        ttk.Label(cookie_frame, text="New cookie").grid(row=0, column=0, sticky="w")
        self.cookie_entry = ttk.Entry(
            cookie_frame, textvariable=self.cookie_var, show="•"
        )
        self.cookie_entry.grid(row=0, column=1, sticky="ew", padx=(8, 8))
        self.forget_button = ttk.Button(
            cookie_frame, text="Forget saved cookie", command=self._forget_cookie
        )
        self.forget_button.grid(row=0, column=2, sticky="e")
        ttk.Label(cookie_frame, textvariable=self.saved_cookie_var).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(5, 0)
        )
        self.remember_check = ttk.Checkbutton(
            cookie_frame,
            text="Remember new cookie on this computer",
            variable=self.remember_var,
        )
        self.remember_check.grid(row=1, column=2, sticky="e", pady=(5, 0))
        self.cookie_controls.extend(
            [self.cookie_entry, self.forget_button, self.remember_check]
        )
        self.settings_controls.extend(self.cookie_controls)

        runbar = ttk.Frame(outer)
        runbar.grid(row=7, column=0, columnspan=3, sticky="ew", pady=(2, 6))
        runbar.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(runbar, mode="determinate")
        self.progress.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.start_button = ttk.Button(runbar, text="Start", command=self._start)
        self.start_button.grid(row=0, column=1, padx=3)
        self.cancel_button = ttk.Button(
            runbar, text="Cancel", command=self._cancel, state="disabled"
        )
        self.cancel_button.grid(row=0, column=2, padx=3)
        self.open_button = ttk.Button(
            runbar,
            text="Open Downloads",
            command=self._open_downloads,
            state="disabled",
        )
        self.open_button.grid(row=0, column=3, padx=(3, 0))

        log_frame = ttk.LabelFrame(outer, text="Activity", padding=6)
        log_frame.grid(row=8, column=0, columnspan=3, sticky="nsew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(
            log_frame,
            height=12,
            wrap="word",
            state="disabled",
            font=("TkFixedFont", 9),
        )
        scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.grid(row=0, column=0, sticky="nsew")
        scroll.grid(row=0, column=1, sticky="ns")

        bottom = ttk.Frame(outer)
        bottom.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        for value in self.count_vars.values():
            ttk.Label(bottom, textvariable=value).pack(side="left", padx=(0, 14))
        ttk.Label(bottom, textvariable=self.status_var).pack(side="right")

    def _selected_key(self, mapping: dict[str, str], value: str) -> str:
        return next(key for key, label in mapping.items() if label == value)

    def _settings(self) -> DownloadSettings:
        report_type = self._selected_key(REPORT_DISPLAY_NAMES, self.report_var.get())
        window_size = self._selected_key(WINDOW_CHOICES, self.window_var.get())
        preview = self.preview_var.get()
        cookie, _source = resolve_cookie(self.cookie_var.get())
        return DownloadSettings(
            report_type=report_type,
            start_date=self.start_date.get_date(),
            end_date=self.end_date.get_date(),
            window_size=window_size,
            output_dir=Path(self.output_var.get()).expanduser(),
            combine=self.combine_var.get() and not preview,
            preview=preview,
            cookie="" if preview else cookie,
        )

    def _report_changed(self, _event: object = None) -> None:
        report_type = self._selected_key(REPORT_DISPLAY_NAMES, self.report_var.get())
        self.window_var.set(WINDOW_CHOICES[default_window(report_type)])
        self._refresh_plan()

    def _refresh_plan(self) -> None:
        try:
            total = planned_downloads(self._settings())
            self.plan_var.set(f"{total} planned")
        except (ValueError, StopIteration):
            self.plan_var.set("Check dates")

    def _preview_changed(self) -> None:
        self._apply_preview_state()
        self._refresh_plan()

    def _apply_preview_state(self) -> None:
        disabled = self.preview_var.get() or self.controller.running
        state = "disabled" if disabled else "normal"
        self.combine_check.configure(state=state)
        for widget in self.cookie_controls:
            widget.configure(state=state)

    def _refresh_cookie_status(self) -> None:
        self.saved_cookie_var.set(
            "Saved cookie: available"
            if saved_cookie_exists()
            else "Saved cookie: none"
        )

    def _forget_cookie(self) -> None:
        if not saved_cookie_exists():
            self._refresh_cookie_status()
            return
        if messagebox.askyesno(
            "Forget saved cookie?",
            "Remove the saved Timeless cookie from this computer?",
            parent=self.root,
        ):
            forget_cookie()
            self._refresh_cookie_status()
            self._append_log("Saved cookie removed.")

    def _browse(self) -> None:
        selected = filedialog.askdirectory(
            parent=self.root,
            initialdir=self.output_var.get() or str(Path.cwd()),
        )
        if selected:
            self.output_var.set(selected)

    def _start(self) -> None:
        if self.updating:
            return
        try:
            settings = self._settings()
            validate_settings(settings)
            if self.remember_var.get() and self.cookie_var.get().strip() and not settings.preview:
                remember_cookie(self.cookie_var.get())
                self._refresh_cookie_status()
            total = planned_downloads(settings)
            self.controller.start(settings)
        except (ValueError, OSError, RuntimeError) as exc:
            messagebox.showerror("Cannot start", str(exc), parent=self.root)
            return

        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")
        self.progress.configure(maximum=max(total, 1), value=0)
        for key, variable in self.count_vars.items():
            label = "No data" if key == "no_data" else key.title()
            variable.set(f"{label}: 0")
        self.status_var.set("Previewing…" if settings.preview else "Downloading…")
        self.open_button.configure(state="disabled")
        self._set_running(True)

    def _set_running(self, running: bool) -> None:
        for widget in self.settings_controls:
            widget.configure(state="disabled" if running else "normal")
        if not running:
            for widget in self.settings_controls:
                if isinstance(widget, ttk.Combobox):
                    widget.configure(state="readonly")
            self._apply_preview_state()
        self.start_button.configure(state="disabled" if running else "normal")
        self.cancel_button.configure(state="normal" if running else "disabled")
        if self.update_info:
            disabled = running or self.updating
            self.update_button.configure(state="disabled" if disabled else "normal")

    def _cancel(self) -> None:
        if self.controller.cancel():
            self.status_var.set("Cancelling after current request…")
            self.cancel_button.configure(state="disabled")
            self._append_log("Cancellation requested; the current request will finish.")

    def _append_log(self, message: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _handle_download_event(self, event: DownloadEvent) -> None:
        if event.message:
            self._append_log(event.message)
        if event.kind in {"progress", "counts", "started"}:
            self.progress.configure(maximum=max(event.total, 1), value=event.completed)
            self.count_vars["downloaded"].set(f"Downloaded: {event.downloaded}")
            self.count_vars["existing"].set(f"Existing: {event.existing}")
            self.count_vars["no_data"].set(f"No data: {event.no_data}")
            self.count_vars["failed"].set(f"Failed: {event.failed}")

    def _finish(self, result: DownloadResult) -> None:
        self._set_running(False)
        summary = (
            f"{result.downloaded} downloaded, {result.existing} existing, "
            f"{result.no_data} no data, {result.failed} failed"
        )
        if result.cancelled:
            self.status_var.set("Cancelled — " + summary)
        elif result.fatal_error:
            self.status_var.set("Stopped — " + summary)
            messagebox.showerror(
                "Download stopped", result.fatal_error, parent=self.root
            )
        else:
            self.status_var.set("Complete — " + summary)
        output = Path(self.output_var.get()).expanduser()
        if output.is_dir():
            self.open_button.configure(state="normal")

    def _poll(self) -> None:
        for item in self.controller.drain_events():
            if isinstance(item, DownloadEvent):
                self._handle_download_event(item)
            elif isinstance(item, tuple) and item[0] == "worker_done":
                self._finish(item[1])
            elif isinstance(item, tuple) and item[0] == "worker_error":
                self._set_running(False)
                self.status_var.set("Error")
                messagebox.showerror("Runtime error", str(item[1]), parent=self.root)

        if self.closing and not self.controller.running:
            self.root.destroy()
            return

        while True:
            try:
                kind, value = self.update_queue.get_nowait()
            except queue.Empty:
                break
            if kind == "available":
                self.update_info = value  # type: ignore[assignment]
                self.update_label.configure(text=f"Version {value.tag} is available.")
                self.update_frame.grid(
                    row=0, column=1, columnspan=2, sticky="e", pady=(0, 8)
                )
                self.update_button.configure(
                    state="disabled" if self.controller.running else "normal"
                )
            elif kind == "installed":
                restart_application()
            elif kind == "update_error":
                self.updating = False
                self._set_running(False)
                messagebox.showerror("Update failed", str(value), parent=self.root)

        if self.root.winfo_exists():
            self.root.after(self.POLL_MS, self._poll)

    def _check_update(self) -> None:
        update = check_for_update()
        if update:
            self.update_queue.put(("available", update))

    def _start_update(self) -> None:
        if self.controller.running or not self.update_info:
            return
        update = self.update_info
        self.updating = True
        self._set_running(True)
        self.cancel_button.configure(state="disabled")
        self.update_button.configure(state="disabled")
        self.update_label.configure(text=f"Installing {self.update_info.tag}…")

        def work() -> None:
            try:
                install_update(update)
                self.update_queue.put(("installed", update))
            except UpdateError as exc:
                self.update_queue.put(("update_error", exc))

        threading.Thread(target=work, daemon=True).start()

    def _open_downloads(self) -> None:
        output = Path(self.output_var.get()).expanduser()
        if not output.is_dir():
            messagebox.showerror(
                "Folder unavailable", "The output folder does not exist yet.", parent=self.root
            )
            return
        try:
            if sys.platform == "win32":
                os.startfile(output)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(output)])
            else:
                subprocess.Popen(["xdg-open", str(output)])
        except OSError as exc:
            messagebox.showerror("Could not open folder", str(exc), parent=self.root)

    def _on_close(self) -> None:
        if self.updating:
            messagebox.showinfo(
                "Update in progress",
                "Please wait for the update to finish and restart.",
                parent=self.root,
            )
            return
        if not self.controller.running:
            self.root.destroy()
            return
        if messagebox.askyesno(
            "Cancel download?",
            "A run is still active. Cancel it and close after the current request?",
            parent=self.root,
        ):
            self.closing = True
            self._cancel()


def main() -> None:
    root = tk.Tk()
    DownloaderApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
