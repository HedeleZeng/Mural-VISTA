"""GUI-side subprocess lifecycle control and durable progress messages.

VTK owns the main thread of a child process. The main panel only reads small
messages and never accesses an analysis render window or blocks on its loop.
The core analysis entry point remains in muralvista_gui.run_analysis_process;
this module launches that entry point and relays its events to the main panel.
"""

import json
import os
import sys
import uuid
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal


def write_message(path, payload):
    """Publish a complete control message, including on Windows."""
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)


def read_message(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


class AnalysisProcessController(QObject):
    worker_mode = "--analysis-worker"
    dataset_started = Signal(int, int, str)
    raw_stack_requested = Signal(str, str)
    dataset_finished = Signal(str, str)
    dataset_removed = Signal(str)
    log_message = Signal(str)
    batch_finished = Signal(int, int, int)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.process = None
        self.run_dir = None
        self.active_name = None
        self._positions = {}
        self._buffers = {}
        self._result = None
        self._finalized = False
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)

    def start(self, job, gui_path):
        output = Path(job["output_dir"]).resolve()
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.run_dir = output / "Mural-VISTA_logs" / f"{stamp}-{uuid.uuid4().hex[:8]}"
        self.run_dir.mkdir(parents=True)
        job_path = self.run_dir / "job.json"
        write_message(job_path, job)
        self.process = QProcess(self)
        self.process.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        self.process.readyReadStandardOutput.connect(self._read_native_output)
        self.process.finished.connect(self._process_finished)
        self.process.errorOccurred.connect(self._process_error)
        arguments = [self.worker_mode, str(job_path)]
        if not getattr(sys, "frozen", False):
            arguments.insert(0, str(Path(gui_path).resolve()))
        self.process.setProgram(sys.executable)
        self.process.setArguments(arguments)
        self.process.start()
        self.timer.start()
        self.log_message.emit(f"Analysis runs in a separate process. Diagnostic logs: {self.run_dir}")

    def _read_native_output(self):
        if self.process is not None:
            output = bytes(self.process.readAllStandardOutput()).decode("utf-8", errors="replace")
            if output.strip():
                self.log_message.emit(output.rstrip())

    def _poll(self):
        if self.run_dir is None:
            return
        for name in ("events.jsonl", "worker.log"):
            path = self.run_dir / name
            try:
                with path.open("rb") as stream:
                    stream.seek(self._positions.get(name, 0))
                    chunk = stream.read(65536)
                    self._positions[name] = stream.tell()
            except OSError:
                continue
            data = self._buffers.get(name, b"") + chunk
            lines = data.split(b"\n")
            self._buffers[name] = lines.pop()
            if name == "worker.log":
                if lines:
                    self.log_message.emit(b"\n".join(lines).decode("utf-8", errors="replace"))
                continue
            for line in lines:
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                    self._handle_event(payload["event"], payload["args"])
                except (ValueError, KeyError, TypeError) as exc:
                    self.log_message.emit(f"Invalid worker message: {exc}")

    def _handle_event(self, name, args):
        if name == "dataset_started":
            self.active_name = args[2]
        elif name == "dataset_finished":
            self.active_name = None
        if name in ("batch_finished", "failed"):
            self._result = (name, args)
        elif name in ("dataset_started", "dataset_finished", "dataset_removed",
                      "raw_stack_requested", "log_message"):
            getattr(self, name).emit(*args)

    def acknowledge_stack(self, dataset_name, success):
        if self.run_dir is not None:
            write_message(self.run_dir / "viewer_ack.json", {
                "dataset": dataset_name, "success": bool(success),
            })

    def request_skip(self, remove=False):
        if self.active_name is None or self.run_dir is None:
            return None
        write_message(self.run_dir / "control.json", {
            "dataset": self.active_name, "remove": bool(remove),
        })
        return self.active_name

    def _process_error(self, error):
        if error == QProcess.ProcessError.FailedToStart:
            self._result = ("failed", [f"Could not start analysis: {self.process.errorString()}"])
            self._process_finished(-1, QProcess.ExitStatus.CrashExit)

    def _process_finished(self, exit_code, exit_status):
        if self._finalized:
            return
        self._finalized = True
        self.timer.stop()
        self._read_native_output()
        self._poll()
        self.active_name = None
        if exit_code != 0 or exit_status == QProcess.ExitStatus.CrashExit:
            if self._result is None or self._result[0] != "failed":
                self._result = ("failed", [
                    f"Analysis process stopped (exit code {exit_code}). "
                    f"The main panel is still available. Diagnostic logs: {self.run_dir}"
                ])
        if self._result is None:
            self._result = ("failed", [f"Analysis ended without a completion message. Logs: {self.run_dir}"])
        name, args = self._result
        getattr(self, name).emit(*args)
        self.finished.emit()
