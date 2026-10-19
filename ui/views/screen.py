"""Screen / LED / animation configuration page.

Contains:

* **LED effects** — controls for the Apex 4 (K2) zone-lighting block
  (``Config.Basic.NewLedConfig``): lighting mode, brightness, speed and the
  per-pick colours.  The behaviour is a 1:1 port of the original WPF
  ``NewBasicViewModel`` — see :mod:`openflydigi3.led`.
* **Animation gallery** — the bundled GIF/PNG screen animations with a live
  preview, as shipped with the original app.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QMovie, QPixmap
from PyQt6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ... import led as led_fx
from ...config import device_display_name
from ...config_parser import DeviceConfig
from ..theme import ACCENT, TEXT_DIM

IMAGES_ROOT = Path(__file__).resolve().parents[1] / "resources" / "images"


class _Thumb(QFrame):
    """Click-to-select animation thumbnail."""

    selected = pyqtSignal(str)

    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = path
        self.setObjectName("Card")
        self.setFixedSize(132, 116)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 6)
        lay.setSpacing(4)

        self.preview = QLabel()
        self.preview.setFixedSize(116, 78)
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setStyleSheet("background-color: #101215; border-radius: 6px;")

        self.movie = None
        if path.suffix.lower() == ".gif":
            self.movie = QMovie(str(path))
            self.movie.setScaledSize(self.preview.size())
            self.preview.setMovie(self.movie)
            self.movie.start()
        elif path.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            pix = QPixmap(str(path))
            if not pix.isNull():
                self.preview.setPixmap(
                    pix.scaled(
                        self.preview.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )

        lay.addWidget(self.preview, alignment=Qt.AlignmentFlag.AlignCenter)
        name = QLabel(path.stem[:16])
        name.setObjectName("Dim")
        name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name.setStyleSheet(f"color: {TEXT_DIM}; font-size: 11px;")
        lay.addWidget(name)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self.selected.emit(str(self.path))
        super().mousePressEvent(event)

    def set_selected(self, on: bool) -> None:
        border = ACCENT if on else "#3a3f45"
        self.setStyleSheet(f"#Card {{ border: 2px solid {border}; }}")


class _ValueLabel(QLabel):
    """Small right-aligned numeric readout."""

    def __init__(self, parent=None):
        super().__init__("0", parent)
        self.setObjectName("Dim")
        self.setMinimumWidth(30)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setStyleSheet(f"color: {TEXT_DIM};")


class ScreenView(QWidget):
    """Preview and choose screen animations + tune the Apex 4 lighting."""

    config_changed = pyqtSignal()
    led_apply_requested = pyqtSignal()  # user wants the LED config pushed to hardware

    def __init__(self, parent=None):
        super().__init__(parent)
        self._selected: str | None = None
        self._thumbs: list[_Thumb] = []
        self._loading = False
        self.current_config: DeviceConfig | None = None
        self._led_colors: list[tuple[int, int, int]] = []
        self._swatches: list[QPushButton] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(32, 28, 32, 28)
        root.setSpacing(18)

        # Header -------------------------------------------------------
        header = QHBoxLayout()
        box = QVBoxLayout()
        box.setSpacing(2)
        title = QLabel("Screen & Lighting")
        title.setObjectName("PageTitle")
        box.addWidget(title)
        subtitle = QLabel("Lighting effects, RGB colours and screen animations.")
        subtitle.setObjectName("PageSubtitle")
        box.addWidget(subtitle)
        header.addLayout(box)
        header.addStretch()
        root.addLayout(header)

        # Scrollable body ---------------------------------------------
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

        # ---- LED effects card (Apex 4) ------------------------------
        self.led_card = QFrame()
        self.led_card.setObjectName("Card")
        self._build_led_card(self.led_card)
        layout.addWidget(self.led_card)

        # ---- Preview + gallery --------------------------------------
        body_row = QHBoxLayout()
        body_row.setSpacing(16)

        preview_card = QFrame()
        preview_card.setObjectName("Card")
        preview_card.setMinimumWidth(340)
        pl = QVBoxLayout(preview_card)
        pl.setContentsMargins(16, 16, 16, 16)
        pl.setSpacing(12)
        preview_head = QLabel("Screen animation preview")
        preview_head.setStyleSheet("font-weight: 600;")
        pl.addWidget(preview_head)
        self.stack = QStackedWidget()
        self.stack.setFixedSize(306, 200)
        self.preview_label = QLabel("Select an animation")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFixedSize(306, 200)
        self.preview_label.setStyleSheet(
            "background-color: #101215; border-radius: 8px; color: #9aa0a6;"
        )
        self.stack.addWidget(self.preview_label)
        pl.addWidget(self.stack, alignment=Qt.AlignmentFlag.AlignCenter)
        pl.addStretch()
        body_row.addWidget(preview_card, 2)

        gallery_card = QFrame()
        gallery_card.setObjectName("Card")
        gl = QVBoxLayout(gallery_card)
        gl.setContentsMargins(16, 16, 16, 16)
        gl.setSpacing(10)
        gallery_title = QLabel("Animations")
        gallery_title.setStyleSheet("font-weight: 600;")
        gl.addWidget(gallery_title)

        gal_scroll = QScrollArea()
        gal_scroll.setWidgetResizable(True)
        gal_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        host = QWidget()
        grid = QGridLayout(host)
        grid.setContentsMargins(4, 4, 4, 4)
        grid.setSpacing(10)
        gal_scroll.setWidget(host)
        gl.addWidget(gal_scroll, 1)
        body_row.addWidget(gallery_card, 3)

        layout.addLayout(body_row, 1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        self._populate_gallery(grid, host)

        # No profile yet → hide the LED card until one is loaded.
        self.led_card.hide()

    # ------------------------------------------------------------------
    # LED card
    # ------------------------------------------------------------------
    def _build_led_card(self, card: QFrame) -> None:
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 14, 16, 16)
        lay.setSpacing(12)

        # Card header: title + apply button + device tag
        head = QHBoxLayout()
        title = QLabel("LED effects")
        title.setObjectName("CardTitle")
        head.addWidget(title)
        head.addStretch()
        self.led_apply_btn = QPushButton("Apply to controller")
        self.led_apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.led_apply_btn.setToolTip(
            "Push the current lighting config to the connected pad over the\n"
            "XInput config channel (WriteLed packets on the output pipe)."
        )
        self.led_apply_btn.clicked.connect(self.led_apply_requested.emit)
        head.addWidget(self.led_apply_btn)
        self.led_tag = QLabel("Apex 4")
        self.led_tag.setStyleSheet(
            f"color: {ACCENT}; border: 1px solid {ACCENT};"
            " border-radius: 9px; padding: 2px 10px; font-size: 11px;"
        )
        head.addWidget(self.led_tag)
        lay.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)

        # Row 0 — Lighting Mode
        grid.addWidget(QLabel("Lighting Mode"), 0, 0)
        self.mode_combo = QComboBox()
        for mode in led_fx.K2_LED_MODES:
            self.mode_combo.addItem(mode.name, mode.id)
        grid.addWidget(self.mode_combo, 0, 1, 1, 2)

        # Row 1 — Light brightness
        self.bright_label = QLabel("Light brightness")
        grid.addWidget(self.bright_label, 1, 0)
        self.bright_slider = QSlider(Qt.Orientation.Horizontal)
        self.bright_slider.setRange(led_fx.MIN_VALUE, led_fx.MAX_VALUE)
        grid.addWidget(self.bright_slider, 1, 1)
        self.bright_value = _ValueLabel()
        grid.addWidget(self.bright_value, 1, 2)

        # Row 2 — Light speed
        self.speed_label = QLabel("Light speed")
        grid.addWidget(self.speed_label, 2, 0)
        self.speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.speed_slider.setRange(led_fx.MIN_VALUE, led_fx.MAX_VALUE)
        grid.addWidget(self.speed_slider, 2, 1)
        self.speed_value = _ValueLabel()
        grid.addWidget(self.speed_value, 2, 2)

        # Row 3 — Light Color swatches
        self.color_label = QLabel("Light Color")
        grid.addWidget(self.color_label, 3, 0)
        self.color_host = QWidget()
        self.color_row = QHBoxLayout(self.color_host)
        self.color_row.setContentsMargins(0, 0, 0, 0)
        self.color_row.setSpacing(8)
        self.color_row.addStretch()
        grid.addWidget(self.color_host, 3, 1, 1, 2)

        lay.addLayout(grid)

        self.mode_combo.currentIndexChanged.connect(self._on_mode)
        self.bright_slider.valueChanged.connect(self._on_brightness)
        self.speed_slider.valueChanged.connect(self._on_speed)

    # -- profile loading ------------------------------------------------
    def set_config(self, cfg: DeviceConfig | None) -> None:
        """Load a profile; show the LED card only for supported devices."""
        self.current_config = cfg
        nled = cfg.new_led.raw if (cfg is not None and cfg.new_led is not None) else None
        folder = cfg.path.parent.name if cfg is not None else ""

        if nled is not None and led_fx.supports(folder):
            self.led_tag.setText(device_display_name(folder))
            self.led_card.show()
            self._reload_led()
        else:
            self.led_card.hide()

    @property
    def _nled(self) -> dict | None:
        cfg = self.current_config
        if cfg is None or cfg.new_led is None:
            return None
        return cfg.new_led.raw

    def _reload_led(self) -> None:
        """Refresh every control from the raw NewLedConfig dict."""
        nled = self._nled
        if nled is None:
            return
        mode = led_fx.current_mode(nled)

        self._loading = True

        # Mode combo (fall back to the first mode like the original does).
        idx = 0
        if mode is not None:
            for i, m in enumerate(led_fx.K2_LED_MODES):
                if m.id == mode.id:
                    idx = i
                    break
        self.mode_combo.setCurrentIndex(idx)

        # Brightness / speed
        bright = int(nled.get("Light_scale") or led_fx.MIN_VALUE)
        speed = int(nled.get("Loop_time") or led_fx.MIN_VALUE)
        self.bright_slider.setValue(max(led_fx.MIN_VALUE, min(led_fx.MAX_VALUE, bright)))
        self.speed_slider.setValue(max(led_fx.MIN_VALUE, min(led_fx.MAX_VALUE, speed)))
        self.bright_value.setText(str(bright))
        self.speed_value.setText(str(speed))

        # Visibility (original: IsShowAdjustTimeBox / IsShowAdjustLightBox)
        show_light = mode.show_light if mode else False
        show_time = mode.show_time if mode else False
        self.bright_label.setVisible(show_light)
        self.bright_slider.setVisible(show_light)
        self.bright_value.setVisible(show_light)
        self.speed_label.setVisible(show_time)
        self.speed_slider.setVisible(show_time)
        self.speed_value.setVisible(show_time)

        # Colours
        self._led_colors = led_fx.get_colors(nled) if mode else []
        self._rebuild_swatches()

        self._loading = False

    def _rebuild_swatches(self) -> None:
        while self.color_row.count():
            item = self.color_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._swatches.clear()

        for i, color in enumerate(self._led_colors):
            btn = QPushButton("")
            btn.setFixedSize(46, 30)
            btn.setToolTip(led_fx.rgb_hex(color).upper())
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet(self._swatch_qss(color))
            btn.clicked.connect(lambda _=False, idx=i: self._on_color(idx))
            self.color_row.addWidget(btn)
            self._swatches.append(btn)
        # Trailing stretch keeps the swatches packed to the left (otherwise
        # Qt6 spreads fixed-size items across the whole row).
        self.color_row.addStretch(1)

        has_colors = bool(self._led_colors)
        self.color_label.setVisible(has_colors)
        self.color_host.setVisible(has_colors)

    @staticmethod
    def _swatch_qss(color: tuple[int, int, int]) -> str:
        r, g, b = color
        return (
            f"background-color: rgb({r},{g},{b});"
            " border: 2px solid #3a3f45; border-radius: 6px;"
        )

    # -- change handlers (write-through like the original) --------------
    def _on_mode(self, index: int) -> None:
        if self._loading:
            return
        nled = self._nled
        if nled is None:
            return
        mode = led_fx.K2_LED_MODES[index]
        led_fx.apply_mode(nled, mode)
        self._reload_led()  # mode switch resets speed + brightness defaults
        self.config_changed.emit()

    def _on_brightness(self, value: int) -> None:
        self.bright_value.setText(str(value))
        if self._loading:
            return
        nled = self._nled
        if nled is None:
            return
        led_fx.set_brightness(nled, value)
        self.config_changed.emit()

    def _on_speed(self, value: int) -> None:
        self.speed_value.setText(str(value))
        if self._loading:
            return
        nled = self._nled
        if nled is None:
            return
        led_fx.set_speed(nled, value)
        self.config_changed.emit()

    def _on_color(self, index: int) -> None:
        nled = self._nled
        if nled is None or index >= len(self._led_colors):
            return
        current = QColor(*self._led_colors[index])
        picked = QColorDialog.getColor(
            current, self, "Light Color", QColorDialog.ColorDialogOption.DontUseNativeDialog
        )
        if not picked.isValid():
            return
        self._led_colors[index] = (picked.red(), picked.green(), picked.blue())
        led_fx.set_colors(nled, self._led_colors)
        swatch = self._swatches[index]
        swatch.setStyleSheet(self._swatch_qss(self._led_colors[index]))
        swatch.setToolTip(led_fx.rgb_hex(self._led_colors[index]).upper())
        self.config_changed.emit()

    # ------------------------------------------------------------------
    # Animation gallery
    # ------------------------------------------------------------------
    def _populate_gallery(self, grid: QGridLayout, host: QWidget) -> None:
        candidates: list[Path] = []
        screen_dir = IMAGES_ROOT / "screen"
        if screen_dir.exists():
            candidates += sorted(screen_dir.glob("*.gif"))[:8]
            gif_dir = screen_dir / "gif"
            if gif_dir.exists():
                candidates += sorted(gif_dir.glob("*.gif"))[:12]

        default_dir = IMAGES_ROOT / "default"
        if default_dir.exists():
            default_gif = default_dir / "default_ani.gif"
            if default_gif.exists():
                candidates.insert(0, default_gif)

        cols = 3
        for i, path in enumerate(candidates):
            thumb = _Thumb(path)
            thumb.selected.connect(self._select)
            self._thumbs.append(thumb)
            grid.addWidget(thumb, i // cols, i % cols)

        if not candidates:
            empty = QLabel("No animation assets found.")
            empty.setStyleSheet(f"color: {TEXT_DIM};")
            grid.addWidget(empty, 0, 0)

    def _select(self, path: str) -> None:
        self._selected = path
        for thumb in self._thumbs:
            thumb.set_selected(str(thumb.path) == path)

        # Show it in the preview stack.
        while self.stack.count() > 1:
            w = self.stack.widget(1)
            self.stack.removeWidget(w)
            w.deleteLater()

        p = Path(path)
        if p.suffix.lower() == ".gif":
            label = QLabel()
            label.setFixedSize(306, 200)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                "background-color: #101215; border-radius: 8px;"
            )
            movie = QMovie(path)
            movie.setScaledSize(label.size())
            label.setMovie(movie)
            movie.start()
            self.stack.addWidget(label)
            self.stack.setCurrentIndex(1)
        else:
            label = QLabel()
            label.setFixedSize(306, 200)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet("background-color: #101215; border-radius: 8px;")
            pix = QPixmap(path)
            if not pix.isNull():
                label.setPixmap(
                    pix.scaled(
                        label.size(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                )
            self.stack.addWidget(label)
            self.stack.setCurrentIndex(1)

        self.config_changed.emit()
