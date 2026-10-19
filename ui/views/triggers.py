"""Trigger (L2/R2) configuration page."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ...config_parser import DeviceConfig
from ..widgets.macro_editor import MacroEditor

TRIGGER_MODES = [
    "Normal (digital)",
    "Linear (analog)",
    "Hair-trigger",
    "Stage (progressive)",
    "Rumble feedback",
]


class TriggerView(QWidget):
    """Edit trigger mode, curve, auto-trigger and vibration per side."""

    config_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_config: DeviceConfig | None = None
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        header = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title = QLabel("Triggers")
        title.setObjectName("PageTitle")
        title_box.addWidget(title)
        self.subtitle = QLabel("Configure the L2 / R2 response, hair-trigger and vibration.")
        self.subtitle.setObjectName("PageSubtitle")
        title_box.addWidget(self.subtitle)
        header.addLayout(title_box)
        header.addStretch()
        root.addLayout(header)

        # L2 / R2 cards ------------------------------------------------
        grid = QHBoxLayout()
        grid.setSpacing(16)
        self.left_card = self._build_side_card("Left trigger (L2)")
        self.right_card = self._build_side_card("Right trigger (R2)")
        grid.addWidget(self.left_card)
        grid.addWidget(self.right_card)
        root.addLayout(grid)

        # Macro editor --------------------------------------------------
        root.addWidget(self._section_label("Macros"))
        self.macro_editor = MacroEditor()
        root.addWidget(self.macro_editor, 1)

        save = QPushButton("Apply trigger & macro settings")
        save.setObjectName("Primary")
        save.clicked.connect(self._save)
        root.addWidget(save, alignment=Qt.AlignmentFlag.AlignRight)

    # ------------------------------------------------------------------
    @staticmethod
    def _section_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setObjectName("CardTitle")
        return lbl

    def _build_side_card(self, title_text: str) -> QFrame:
        card = QFrame()
        card.setObjectName("Card")
        card.setMinimumHeight(240)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(12)

        title = QLabel(title_text)
        title.setObjectName("CardTitle")
        lay.addWidget(title)

        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode"))
        mode = QComboBox()
        mode.addItems(TRIGGER_MODES)
        mode_row.addWidget(mode, 1)
        lay.addLayout(mode_row)

        sensitivity = QSlider(Qt.Orientation.Horizontal)
        sensitivity.setRange(0, 100)
        sensitivity.setValue(50)
        lay.addWidget(QLabel("Sensitivity"))
        lay.addWidget(sensitivity)

        deadzone = QSlider(Qt.Orientation.Horizontal)
        deadzone.setRange(0, 100)
        deadzone.setValue(10)
        lay.addWidget(QLabel("Deadzone"))
        lay.addWidget(deadzone)

        motor_row = QHBoxLayout()
        motor = QSpinBox()
        motor.setRange(0, 100)
        motor.setValue(60)
        motor.setSuffix("%")
        motor_row.addWidget(QLabel("Vibration"))
        motor_row.addWidget(motor)
        motor_row.addStretch()
        lay.addLayout(motor_row)

        auto = QCheckBox("Auto-trigger (rapid fire)")
        lay.addWidget(auto)

        lay.addStretch()

        # Keep references for read/write.
        card._mode = mode          # type: ignore[attr-defined]
        card._sensitivity = sensitivity  # type: ignore[attr-defined]
        card._deadzone = deadzone  # type: ignore[attr-defined]
        card._motor = motor        # type: ignore[attr-defined]
        card._auto = auto          # type: ignore[attr-defined]

        sensitivity.valueChanged.connect(self._mark_dirty)
        deadzone.valueChanged.connect(self._mark_dirty)
        mode.currentIndexChanged.connect(self._mark_dirty)
        motor.valueChanged.connect(self._mark_dirty)
        auto.toggled.connect(self._mark_dirty)
        return card

    # ------------------------------------------------------------------
    def set_config(self, cfg: DeviceConfig | None) -> None:
        self.current_config = cfg
        if cfg is None:
            self.subtitle.setText("No profile loaded.")
            return
        self.subtitle.setText(f"{cfg.name}  •  trigger & macro settings")
        self._loading = True

        self._apply_trigger(cfg.left_trigger, self.left_card)
        self._apply_trigger(cfg.right_trigger, self.right_card)

        steps = []
        if cfg.macros and cfg.macros[0].raw:
            raw = cfg.macros[0].raw
            steps = [
                {
                    "button": raw.get("Key") or raw.get("Button") or "",
                    "hold_ms": raw.get("HoldTime") or 50,
                    "delay_ms": raw.get("Delay") or 30,
                }
            ]
        self.macro_editor.set_steps(steps)
        self._loading = False

    @staticmethod
    def _apply_trigger(trigger, card) -> None:
        if trigger is None:
            return
        mode_idx = trigger.trigger_type or 0
        if 0 <= mode_idx < len(TRIGGER_MODES):
            card._mode.setCurrentIndex(mode_idx)  # type: ignore[attr-defined]
        motor = trigger.motor or {}
        strength = motor.get("Strength") or motor.get("Level")
        if strength is not None:
            card._motor.setValue(int(strength))  # type: ignore[attr-defined]
        auto = trigger.auto or {}
        card._auto.setChecked(bool(auto.get("Open")))  # type: ignore[attr-defined]

    def _save(self) -> None:
        cfg = self.current_config
        if cfg is not None:
            self._write_trigger(cfg.left_trigger, self.left_card)
            self._write_trigger(cfg.right_trigger, self.right_card)
        self.config_changed.emit()

    @staticmethod
    def _write_trigger(trigger, card) -> None:
        if trigger is None:
            return
        trigger.trigger_type = card._mode.currentIndex()  # type: ignore[attr-defined]
        trigger.raw["Type"] = trigger.trigger_type
        trigger.raw.setdefault("TriggerMotor", {})["Strength"] = card._motor.value()  # type: ignore[attr-defined]
        trigger.raw.setdefault("AutoTrigger", {})["Open"] = card._auto.isChecked()  # type: ignore[attr-defined]

    def _mark_dirty(self, *_args) -> None:
        if not self._loading:
            self.config_changed.emit()
