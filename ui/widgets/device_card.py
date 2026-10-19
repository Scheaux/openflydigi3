"""A clickable card representing one connected device."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from ...devices import DeviceInfo, DeviceStatus
from ..theme import ACCENT, ERR, OK, TEXT_DIM, WARN

_STATUS_COLOR = {
    DeviceStatus.CONNECTED: OK,
    DeviceStatus.CONNECTING: WARN,
    DeviceStatus.CONFIGURING: WARN,
    DeviceStatus.UPDATING: WARN,
    DeviceStatus.ERROR: ERR,
    DeviceStatus.DISCONNECTED: TEXT_DIM,
}


class DeviceCard(QFrame):
    """Shows a device with connect/disconnect and configure actions."""

    connect_requested = pyqtSignal(str)
    configure_requested = pyqtSignal(str)

    def __init__(self, device: DeviceInfo, parent=None):
        super().__init__(parent)
        self.device = device
        self.setObjectName("Card")
        self.setMinimumHeight(96)

        root = QHBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(16)

        # Status dot
        self.status_dot = QLabel("\u25cf")
        dot_font = QFont()
        dot_font.setPointSize(18)
        self.status_dot.setFont(dot_font)
        root.addWidget(self.status_dot)

        # Text block
        text = QVBoxLayout()
        text.setSpacing(2)
        self.name_label = QLabel(device.display_name)
        name_font = QFont()
        name_font.setPointSize(12)
        name_font.setBold(True)
        self.name_label.setFont(name_font)
        text.addWidget(self.name_label)

        meta = []
        meta.append(device.connection_type.value.upper())
        if device.firmware_version:
            meta.append(f"FW {device.firmware_version}")
        if device.serial_number:
            meta.append(device.serial_number)
        self.meta_label = QLabel("  •  ".join(meta))
        self.meta_label.setObjectName("Dim")
        text.addWidget(self.meta_label)

        self.caps_label = QLabel("  ".join(device.capabilities))
        self.caps_label.setObjectName("Dim")
        text.addWidget(self.caps_label)
        root.addLayout(text, 1)

        # Actions
        actions = QVBoxLayout()
        actions.setSpacing(6)
        self.configure_btn = QPushButton("Configure")
        self.configure_btn.setObjectName("Primary")
        self.configure_btn.clicked.connect(
            lambda: self.configure_requested.emit(self.device.device_id)
        )
        actions.addWidget(self.configure_btn)

        self.connect_btn = QPushButton()
        self.connect_btn.clicked.connect(
            lambda: self.connect_requested.emit(self.device.device_id)
        )
        actions.addWidget(self.connect_btn)
        root.addLayout(actions)

        self.refresh()

    def refresh(self) -> None:
        dev = self.device
        color = _STATUS_COLOR.get(dev.status, TEXT_DIM)
        self.status_dot.setStyleSheet(f"color: {color};")
        if dev.is_connected:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setObjectName("Danger")
            self.configure_btn.setEnabled(True)
        elif dev.status == DeviceStatus.CONNECTING:
            self.connect_btn.setText("Connecting…")
            self.connect_btn.setEnabled(False)
            self.configure_btn.setEnabled(False)
        else:
            self.connect_btn.setText("Connect")
            self.connect_btn.setObjectName("")
            self.connect_btn.setEnabled(True)
            self.configure_btn.setEnabled(False)
        # Force style refresh after objectName change.
        self.connect_btn.style().unpolish(self.connect_btn)
        self.connect_btn.style().polish(self.connect_btn)
        self.status_dot.setToolTip(f"Status: {dev.status.value}")
