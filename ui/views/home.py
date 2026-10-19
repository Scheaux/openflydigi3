"""Home / device management page."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from ...devices import DeviceInfo
from ..theme import TEXT_DIM
from ..widgets.device_card import DeviceCard


class HomeView(QWidget):
    """Lists detected devices, allows scanning and connecting."""

    device_selected = pyqtSignal(str)

    def __init__(self, device_manager, parent=None):
        super().__init__(parent)
        self.device_manager = device_manager
        self._cards: dict[str, DeviceCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # Header
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Devices")
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        subtitle = QLabel("Detect, connect and configure your Flydigi controllers.")
        subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch()

        scan_btn = QPushButton("Scan for devices")
        scan_btn.setObjectName("Primary")
        scan_btn.clicked.connect(self.device_manager.scan)
        header.addWidget(scan_btn)
        root.addLayout(header)

        # Card list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        self.card_host = QWidget()
        self.card_host.setObjectName("CardHost")
        self.card_host.setStyleSheet("#CardHost { background: transparent; }")
        self.cards_layout = QVBoxLayout(self.card_host)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(12)
        scroll.setWidget(self.card_host)
        root.addWidget(scroll, 1)

        self.empty_label = QLabel("No devices found. Connect a controller and press Scan.")
        self.empty_label.setStyleSheet(f"color: {TEXT_DIM};")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cards_layout.addWidget(self.empty_label)
        # Keep the cards at their natural height; extra space goes to the end.
        self.cards_layout.addStretch(1)

        self.device_manager.add_listener(self.refresh)

    # ------------------------------------------------------------------
    def refresh(self, devices: list[DeviceInfo]) -> None:
        """Rebuild the card list from the current device snapshot."""
        # Drop cards whose device disappeared.
        for dev_id in list(self._cards):
            if dev_id not in {d.device_id for d in devices}:
                card = self._cards.pop(dev_id)
                self.cards_layout.removeWidget(card)
                card.deleteLater()

        self.empty_label.setVisible(not devices)

        for dev in devices:
            card = self._cards.get(dev.device_id)
            if card is None:
                card = DeviceCard(dev)
                card.connect_requested.connect(self._on_connect)
                card.configure_requested.connect(self.device_selected.emit)
                self._cards[dev.device_id] = card
                # Insert before the trailing stretch so cards stay compact.
                self.cards_layout.insertWidget(self.cards_layout.count() - 1, card)
            card.device = dev
            card.refresh()

    def _on_connect(self, device_id: str) -> None:
        dev = self.device_manager.get(device_id)
        if dev is None:
            return
        if dev.is_connected:
            self.device_manager.disconnect(device_id)
        else:
            self.device_manager.connect(device_id)
