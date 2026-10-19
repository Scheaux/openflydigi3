"""Main application window with sidebar navigation."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from ..config import APP_NAME, APP_VERSION, config
from ..config_parser import save_profile
from ..hardware import DeviceManager
from .views import (
    FirmwareView,
    GamepadView,
    HomeView,
    ScreenView,
    SettingsView,
    TriggerView,
)
from .theme import ACCENT

# (display name, icon-glyph)
# Geometric BMP symbols are used instead of emoji so glyphs render on every
# platform/font stack (verified to rasterise even without an emoji font).
_NAV_ITEMS = [
    ("Devices", "\u21c4"),      # ⇄  connection / transfer
    ("Gamepad", "\u24b6"),      # Ⓐ  face button A
    ("Triggers", "\u25ce"),     # ◎  target / sensor
    ("Screen", "\u2600"),       # ☀  light / LED
    ("Firmware", "\u21e7"),     # ⇧  upload / flash
    ("Settings", "\u2699"),     # ⚙  gear
]


class MainWindow(QMainWindow):
    """Top-level shell: sidebar navigation + stacked pages."""

    def __init__(self, device_manager: DeviceManager, profile_store):
        super().__init__()
        self.device_manager = device_manager
        self.profile_store = profile_store
        self.setWindowTitle(f"{APP_NAME} {APP_VERSION}")
        self.resize(1180, 760)
        self.setMinimumSize(940, 620)

        central = QWidget()
        self.setCentralWidget(central)
        outer = QHBoxLayout(central)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # ---- Sidebar ----
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(220)
        sl = QVBoxLayout(sidebar)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(0)

        logo = QLabel("FLYDIGI")
        logo.setObjectName("Logo")
        sl.addWidget(logo)
        sub = QLabel("Station  •  Linux")
        sub.setObjectName("LogoSub")
        sl.addWidget(sub)

        self.nav = QListWidget()
        self.nav.setObjectName("NavList")
        self.nav.setFixedWidth(220)
        for name, glyph in _NAV_ITEMS:
            item = QListWidgetItem(f"{glyph}   {name}")
            item.setData(Qt.ItemDataRole.UserRole, name)
            self.nav.addItem(item)
        self.nav.currentRowChanged.connect(self._on_nav)
        sl.addWidget(self.nav, 1)

        # Device status strip in the sidebar footer.
        self.footer = QLabel("No device selected")
        self.footer.setObjectName("LogoSub")
        self.footer.setWordWrap(True)
        sl.addWidget(self.footer)
        outer.addWidget(sidebar)

        # ---- Pages ----
        self.stack = QStackedWidget()
        outer.addWidget(self.stack, 1)

        self.home_view = HomeView(device_manager)
        self.gamepad_view = GamepadView()
        self.trigger_view = TriggerView()
        self.screen_view = ScreenView()
        self.firmware_view = FirmwareView()
        self.settings_view = SettingsView()

        for view in (
            self.home_view,
            self.gamepad_view,
            self.trigger_view,
            self.screen_view,
            self.firmware_view,
            self.settings_view,
        ):
            self.stack.addWidget(view)

        self.home_view.device_selected.connect(self._on_device_selected)
        self.gamepad_view.config_changed.connect(self._on_config_changed)
        self.gamepad_view.profile_changed.connect(self._on_profile_changed)
        self.trigger_view.config_changed.connect(self._on_config_changed)
        self.screen_view.config_changed.connect(self._on_config_changed)
        self.screen_view.led_apply_requested.connect(self._apply_led)

        # ---- Status bar ----
        status = QStatusBar()
        self.setStatusBar(status)
        self.status_left = QLabel("Ready")
        status.addWidget(self.status_left)
        self.status_right = QLabel("")
        status.addPermanentWidget(self.status_right)

        # ---- Shortcuts ----
        self._add_shortcut("Ctrl+R", self.device_manager.scan, "Scan for devices")
        self._add_shortcut("Ctrl+S", self._save_current, "Save current profile")

        # Initial state
        self.nav.setCurrentRow(0)
        self.device_manager.scan()

        # Periodic scan
        self.scan_timer = QTimer(self)
        self.scan_timer.timeout.connect(self.device_manager.scan)
        self.scan_timer.start(int(config.get("scan_interval", 5)) * 1000)

        self.current_device_id: str | None = None

    # ------------------------------------------------------------------
    def _add_shortcut(self, key: str, slot, desc: str) -> None:
        action = QAction(self)
        action.setShortcut(QKeySequence(key))
        action.setToolTip(desc)
        action.triggered.connect(slot)
        self.addAction(action)

    def _on_nav(self, row: int) -> None:
        if row < 0:
            return
        self.stack.setCurrentIndex(row)
        name = _NAV_ITEMS[row][0]
        self.status_left.setText(name)

    def _on_device_selected(self, device_id: str) -> None:
        """Handle 'Configure' pressed on a device card."""
        dev = self.device_manager.get(device_id)
        if dev is None:
            return
        self.current_device_id = device_id
        self.footer.setText(f"Selected:\n{dev.display_name}")
        self.status_right.setText(dev.display_name)
        self.firmware_view.set_device(dev)

        # Load matching profile folder if we have one.  set_profiles() emits
        # profile_changed, which feeds the Triggers and Screen & Lighting
        # pages too (see _on_profile_changed).
        profiles = self.profile_store.get(dev.config_path) if dev.config_path else []
        self.gamepad_view.set_profiles(profiles)

        # Jump to the gamepad page.
        self.nav.setCurrentRow(1)

    def _on_profile_changed(self, cfg) -> None:
        """Keep every profile-driven page on the same selected profile."""
        self.trigger_view.set_config(cfg)
        self.screen_view.set_config(cfg)

    def _on_config_changed(self) -> None:
        self.status_left.setText("Unsaved changes")
        self.status_right.setText("Press Ctrl+S to save")

    def _apply_led(self) -> None:
        """Push the LED config to the selected pad (Apply to controller)."""
        cfg = self.screen_view.current_config
        if cfg is None or cfg.new_led is None:
            self.status_left.setText("No LED-capable profile loaded")
            return
        dev = (
            self.device_manager.get(self.current_device_id)
            if self.current_device_id
            else None
        )
        if dev is None or not dev.path:
            self.status_left.setText("No wired controller selected")
            self.status_right.setText("Connect the pad via USB and press Ctrl+R")
            return
        ok = self.device_manager.send_led_config(dev.device_id, cfg.new_led.raw)
        if ok:
            self.status_left.setText(f"LED config saved to {dev.display_name}")
            self.status_right.setText("Committed to controller flash — survives power-off")
        else:
            self.status_left.setText("LED write failed")
            self.status_right.setText("Check USB permissions (see README udev rule)")

    def _save_current(self) -> None:
        cfg = self.gamepad_view.current_config
        if cfg is None:
            self.status_left.setText("No profile loaded")
            self.status_right.setText("")
            return
        try:
            save_profile(cfg)
        except OSError as exc:
            self.status_left.setText(f"Save failed: {exc}")
            return
        self.status_left.setText(f"Saved profile: {cfg.name}")
        self.status_right.setText("")
