"""Application settings page."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config import APP_NAME, APP_VERSION, config


class SettingsView(QWidget):
    """Edit application preferences (persisted to settings.json)."""

    def __init__(self, parent=None):
        super().__init__(parent)

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Settings")
        title.setObjectName("PageTitle")
        header.addWidget(title)
        subtitle = QLabel(f"{APP_NAME} {APP_VERSION} — preferences are saved to settings.json.")
        subtitle.setObjectName("PageSubtitle")
        header.addWidget(subtitle)
        root.addLayout(header)

        card = QFrame()
        card.setObjectName("Card")
        card.setMaximumWidth(640)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # Appearance
        theme_row = QHBoxLayout()
        theme_row.addWidget(QLabel("Theme"))
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["dark", "light", "system"])
        self.theme_combo.setCurrentText(config.get("theme", "dark"))
        theme_row.addWidget(self.theme_combo, 1)
        lay.addLayout(theme_row)

        # Language
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Language"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["en", "zh", "de", "es", "fr", "it", "ja", "ko"])
        self.lang_combo.setCurrentText(config.get("language", "en"))
        lang_row.addWidget(self.lang_combo, 1)
        lay.addLayout(lang_row)

        # Scan interval
        scan_row = QHBoxLayout()
        scan_row.addWidget(QLabel("Device scan interval (s)"))
        self.scan_spin = QSpinBox()
        self.scan_spin.setRange(2, 120)
        self.scan_spin.setValue(int(config.get("scan_interval", 5)))
        scan_row.addWidget(self.scan_spin, 1)
        scan_row.addStretch()
        lay.addLayout(scan_row)

        # Toggles
        self.auto_connect = QCheckBox("Auto-connect to last device on startup")
        self.auto_connect.setChecked(bool(config.get("auto_connect", True)))
        lay.addWidget(self.auto_connect)

        self.demo_mode = QCheckBox("Show demo devices when no hardware attached")
        self.demo_mode.setChecked(bool(config.get("demo_mode", True)))
        lay.addWidget(self.demo_mode)

        self.start_min = QCheckBox("Start minimized to tray")
        self.start_min.setChecked(bool(config.get("start_minimized", False)))
        lay.addWidget(self.start_min)

        save = QPushButton("Save settings")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        lay.addWidget(save)

        root.addWidget(card)
        root.addStretch()

    def _save(self) -> None:
        config.set("theme", self.theme_combo.currentText())
        config.set("language", self.lang_combo.currentText())
        config.set("scan_interval", self.scan_spin.value())
        config.set("auto_connect", self.auto_connect.isChecked())
        config.set("demo_mode", self.demo_mode.isChecked())
        config.set("start_minimized", self.start_min.isChecked())
