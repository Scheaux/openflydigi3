#!/usr/bin/env python3
"""openflydigi3 — a cross-platform (Linux-first) GUI for Flydigi controllers.

Rebuilt from the decompiled C# of the original *Flydigi Space Station*
Windows app using Python + PyQt6. Talks to hardware over HID/USB/BLE
instead of the original Windows kernel drivers.

Usage:
    python -m openflydigi3.main        # from the repository root
    python main.py                       # from inside the package folder
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow running as a plain script (`python main.py`) as well as a module.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from openflydigi3.config import APP_NAME, APP_ORG, APP_VERSION, config
    from openflydigi3.hardware import DeviceManager
    from openflydigi3.profile_store import ProfileStore
    from openflydigi3.ui.main_window import MainWindow
    from openflydigi3.ui.theme import STYLESHEET
else:
    from .config import APP_NAME, APP_ORG, APP_VERSION, config
    from .hardware import DeviceManager
    from .profile_store import ProfileStore
    from .ui.main_window import MainWindow
    from .ui.theme import STYLESHEET

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QSplashScreen
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor


def _make_splash() -> QSplashScreen | None:
    """A simple branded splash shown while the window is prepared."""
    pix = QPixmap(420, 240)
    pix.fill(QColor("#1b1d21"))
    painter = QPainter(pix)
    try:
        painter.setPen(QColor("#ff5722"))
        font = QFont()
        font.setPointSize(30)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(pix.rect(), Qt.AlignmentFlag.AlignCenter, "FLYDIGI")
        painter.setPen(QColor("#9aa0a6"))
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(
            pix.rect().adjusted(0, 44, 0, 0),
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
            "openflydigi3  •  Linux edition",
        )
    finally:
        painter.end()
    return QSplashScreen(pix)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("openflydigi3")

    # High-DPI scaling is automatic in Qt6, but keep touch/tablet friendly.
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setOrganizationName(APP_ORG)
    app.setStyle("Fusion")
    app.setStyleSheet(STYLESHEET)

    splash = None
    if config.get("show_splash", True):
        splash = _make_splash()
        if splash is not None:
            splash.show()
            app.processEvents()

    allow_demo = bool(config.get("demo_mode", True))
    device_manager = DeviceManager(allow_demo=allow_demo)
    profile_store = ProfileStore()

    window = MainWindow(device_manager, profile_store)

    if splash is not None:
        splash.finish(window)
    window.show()

    log.info("Started %s %s", APP_NAME, APP_VERSION)

    try:
        code = app.exec()
    finally:
        device_manager.shutdown()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
