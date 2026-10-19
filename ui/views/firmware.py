"""Firmware upgrade page."""

from __future__ import annotations

import random
import subprocess
import time
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from ...devices import DeviceInfo
from ..theme import ERR, OK, WARN

ESPTOOL_PATH = Path(__file__).resolve().parents[3] / "esptool" / "esptool.py"


class FlashWorker(QThread):
    """Simulated (or real) firmware flash process.

    Real flashing would shell out to ``esptool.py``; without hardware we run a
    deterministic simulated progress sequence so the UI is fully exercisable.
    """

    progress = pyqtSignal(int, str)
    finished_ok = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, firmware_path: str, device: DeviceInfo | None, parent=None):
        super().__init__(parent)
        self.firmware_path = firmware_path
        self.device = device
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        if not self.firmware_path or not Path(self.firmware_path).exists():
            self.failed.emit("Firmware file not found.")
            return

        stages = [
            (5, "Initializing…"),
            (12, "Erasing flash…"),
            (35, "Writing firmware image…"),
            (70, "Writing firmware image…"),
            (92, "Verifying image…"),
            (100, "Finalizing…"),
        ]
        for pct, msg in stages:
            if self._cancelled:
                self.failed.emit("Flash cancelled.")
                return
            self.progress.emit(pct, msg)
            time.sleep(0.6)

        self.progress.emit(100, "Done.")
        self.finished_ok.emit()


class FirmwareView(QWidget):
    """Select a firmware image, flash it, and watch progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_device: DeviceInfo | None = None
        self.worker: FlashWorker | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Firmware Upgrade")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        self.device_lbl = QLabel("No device selected.")
        self.device_lbl.setObjectName("PageSubtitle")
        header.addWidget(self.device_lbl)
        root.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 16, 16, 16)
        cl.setSpacing(12)

        # Firmware file picker
        file_row = QHBoxLayout()
        cl.addWidget(self._label("Firmware image (.bin)"))
        self.file_edit = QLineEdit()
        self.file_edit.setPlaceholderText("Select a firmware image…")
        file_row.addWidget(self.file_edit, 1)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse)
        file_row.addWidget(browse)
        cl.addLayout(file_row)

        # Progress
        cl.addWidget(self._label("Progress"))
        self.bar = QProgressBar()
        cl.addWidget(self.bar)
        self.status_lbl = QLabel("Idle")
        self.status_lbl.setObjectName("Dim")
        cl.addWidget(self.status_lbl)

        # Actions
        actions = QHBoxLayout()
        self.flash_btn = QPushButton("Start upgrade")
        self.flash_btn.setObjectName("Primary")
        self.flash_btn.clicked.connect(self._start)
        actions.addWidget(self.flash_btn)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.setObjectName("Danger")
        self.cancel_btn.clicked.connect(self._cancel)
        actions.addWidget(self.cancel_btn)
        actions.addStretch()
        cl.addLayout(actions)
        root.addWidget(card)

        # Log
        cl.addWidget(self._label("Log"))
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMinimumHeight(140)
        cl.addWidget(self.log, 1)
        root.addWidget(card, 1)

    # ------------------------------------------------------------------
    @staticmethod
    def _label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("CardTitle")
        return lbl

    def set_device(self, device: DeviceInfo | None) -> None:
        self.current_device = device
        if device is None:
            self.device_lbl.setText("No device selected.")
        else:
            self.device_lbl.setText(
                f"{device.display_name}  •  firmware {device.firmware_version or 'unknown'}"
            )

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select firmware image", "", "Firmware (*.bin);;All files (*)"
        )
        if path:
            self.file_edit.setText(path)

    def _start(self) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        self.bar.setValue(0)
        self.log.clear()
        self.flash_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        self._append("Starting firmware upgrade…", WARN)

        self.worker = FlashWorker(self.file_edit.text().strip(), self.current_device)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished_ok.connect(self._on_done)
        self.worker.failed.connect(self._on_failed)
        self.worker.start()

    def _cancel(self) -> None:
        if self.worker is not None:
            self.worker.cancel()

    def _on_progress(self, pct: int, msg: str) -> None:
        self.bar.setValue(pct)
        self.status_lbl.setText(msg)
        self._append(f"[{pct:3d}%] {msg}")

    def _on_done(self) -> None:
        self.status_lbl.setText("Upgrade complete ✔")
        self._append("Firmware upgraded successfully.", OK)
        self._reset_buttons()

    def _on_failed(self, reason: str) -> None:
        self.status_lbl.setText(f"Failed: {reason}")
        self._append(f"ERROR: {reason}", ERR)
        self._reset_buttons()

    def _reset_buttons(self) -> None:
        self.flash_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)

    def _append(self, text: str, color: str | None = None) -> None:
        if color:
            self.log.append(f'<span style="color:{color}">{text}</span>')
        else:
            self.log.append(text)
