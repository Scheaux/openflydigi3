"""Gamepad configuration page: key/button remapping and sticks."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...config_parser import DeviceConfig
from ..theme import TEXT_DIM

# Common actions a button can be remapped to (mirrors the original app's action list).
ACTIONS = [
    "None / Default",
    "Up", "Down", "Left", "Right",
    "A", "B", "X", "Y",
    "L1", "R1", "L2", "R2",
    "L3", "R3",
    "Start", "Select",
    "Home", "Back",
    "Turbo",
    "Macro 1", "Macro 2", "Macro 3", "Macro 4",
    "Menu Function",
]


class GamepadView(QWidget):
    """Displays and edits the key mapping + joystick curve of a profile."""

    config_changed = pyqtSignal()
    # Emitted whenever the user (or device selection) switches profiles so
    # sibling pages (Triggers, Screen & Lighting) can follow along.
    profile_changed = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: DeviceConfig | None = None
        self._profiles: list[DeviceConfig] = []
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # Header ------------------------------------------------------
        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Gamepad")
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        self.subtitle = QLabel("Select a profile, then remap buttons and tune the sticks.")
        self.subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box)
        header.addStretch()

        self.profile_combo = QComboBox()
        self.profile_combo.setMinimumWidth(260)
        header.addWidget(self.profile_combo)
        root.addLayout(header)

        # Scrollable body --------------------------------------------
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        body = QWidget()
        body.setObjectName("PageBody")
        body.setStyleSheet("#PageBody { background: transparent; }")
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Key mapping table ------------------------------------------
        layout.addWidget(self._section_label("Button mapping"))
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Button", "Mapped to", "Turbo", "Priority"])
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(False)
        self.table.setMinimumHeight(320)
        layout.addWidget(self.table, 1)

        row_btns = QHBoxLayout()
        save_btn = QPushButton("Apply mapping")
        save_btn.setObjectName("Primary")
        save_btn.clicked.connect(self._save_table)
        row_btns.addWidget(save_btn)
        reset_btn = QPushButton("Reset defaults")
        reset_btn.clicked.connect(self._load_table)
        row_btns.addWidget(reset_btn)
        row_btns.addStretch()
        layout.addLayout(row_btns)

        # Joystick curve card ----------------------------------------
        layout.addWidget(self._section_label("Joystick sensitivity"))
        stick_card = QFrame()
        stick_card.setObjectName("Card")
        grid = QGridLayout(stick_card)
        grid.setContentsMargins(16, 14, 16, 14)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(12)

        self.stick_sliders: dict[str, QSlider] = {}
        self.stick_values: dict[str, QLabel] = {}

        rows = [
            ("left_deadzone", "Left deadzone"),
            ("left_resp", "Left response curve"),
            ("right_deadzone", "Right deadzone"),
            ("right_resp", "Right response curve"),
        ]
        for i, (key, label) in enumerate(rows):
            grid.addWidget(QLabel(label), i, 0)
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(20)
            slider.valueChanged.connect(lambda v, k=key: self._on_stick(k, v))
            grid.addWidget(slider, i, 1)
            value_lbl = QLabel("20")
            value_lbl.setObjectName("Dim")
            value_lbl.setMinimumWidth(32)
            grid.addWidget(value_lbl, i, 2)
            self.stick_sliders[key] = slider
            self.stick_values[key] = value_lbl
        layout.addWidget(stick_card)

        layout.addStretch()
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        # Connect profile selector ----------------------------------
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)

        # Sensitivity sliders only emit when the user changes them.
        self._loading = False

    # ------------------------------------------------------------------
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("CardTitle")
        return lbl

    # ------------------------------------------------------------------
    def set_profiles(self, profiles: list[DeviceConfig]) -> None:
        """Populate the profile selector."""
        self._loading = True
        self.profile_combo.clear()
        self._profiles = profiles
        for cfg in profiles:
            self.profile_combo.addItem(cfg.name, str(cfg.path))
        self._loading = False
        if profiles:
            self.set_config(profiles[0])
            self.profile_changed.emit(profiles[0])
        else:
            self.current_config = None
            self.profile_changed.emit(None)

    def set_config(self, cfg: DeviceConfig) -> None:
        """Load a config into the editor widgets."""
        self.current_config = cfg
        idx = -1
        for i in range(self.profile_combo.count()):
            if self.profile_combo.itemData(i) == str(cfg.path):
                idx = i
                break
        if idx >= 0:
            self._loading = True
            self.profile_combo.setCurrentIndex(idx)
            self._loading = False

        self.subtitle.setText(
            f"{cfg.name}   •   config version {cfg.version or '?'}   •   "
            f"{len(cfg.key_mappings)} buttons"
        )
        self._load_table()
        self._load_sticks()

    def _on_profile_changed(self, index: int) -> None:
        """Switch the editor to the newly selected profile."""
        if self._loading:
            return
        path = self.profile_combo.itemData(index)
        if not path:
            return
        for cfg in getattr(self, "_profiles", []):
            if str(cfg.path) == str(path):
                self._loading = True
                self.current_config = cfg
                self._loading = False
                self.subtitle.setText(
                    f"{cfg.name}   •   config version {cfg.version or '?'}   •   "
                    f"{len(cfg.key_mappings)} buttons"
                )
                self._load_table()
                self._load_sticks()
                self.profile_changed.emit(cfg)
                return

    # -- table --------------------------------------------------------
    def _load_table(self) -> None:
        if self.current_config is None:
            return
        cfg = self.current_config
        mappings = cfg.key_mappings
        self._loading = True
        self.table.setRowCount(0)
        for km in mappings:
            r = self.table.rowCount()
            self.table.insertRow(r)

            name_item = QTableWidgetItem(km.label)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 0, name_item)

            combo = QComboBox()
            combo.addItems(ACTIONS)
            target = km.map_key or "None / Default"
            idx = combo.findText(target)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.currentIndexChanged.connect(self._mark_dirty)
            self.table.setCellWidget(r, 1, combo)

            turbo = QComboBox()
            turbo.addItems(["Off", "Rapid 1", "Rapid 2", "Rapid 3"])
            turbo.setCurrentIndex(km.turbo if 0 <= km.turbo < 4 else 0)
            turbo.currentIndexChanged.connect(self._mark_dirty)
            self.table.setCellWidget(r, 2, turbo)

            prio = QTableWidgetItem(str(km.priority))
            self.table.setItem(r, 3, prio)
        self._loading = False

    def _save_table(self) -> None:
        if self.current_config is None:
            return
        for r, km in enumerate(self.current_config.key_mappings):
            combo = self.table.cellWidget(r, 1)
            turbo = self.table.cellWidget(r, 2)
            prio = self.table.item(r, 3)
            if isinstance(combo, QComboBox):
                km.map_key = combo.currentText()
                km.is_mapped = combo.currentIndex() > 0
            if isinstance(turbo, QComboBox):
                km.turbo = turbo.currentIndex()
            if prio is not None:
                try:
                    km.priority = int(prio.text())
                except ValueError:
                    pass
        self.config_changed.emit()

    def _mark_dirty(self, *_args) -> None:
        if not self._loading:
            self.config_changed.emit()

    # -- sticks -------------------------------------------------------
    def _load_sticks(self) -> None:
        self._loading = True
        for key, slider in self.stick_sliders.items():
            slider.setValue(20)
            self.stick_values[key].setText("20")
        self._loading = False

    def _on_stick(self, key: str, value: int) -> None:
        self.stick_values[key].setText(str(value))
        if not self._loading:
            self.config_changed.emit()
