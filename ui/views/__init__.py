"""Views (pages) of the application."""

from .home import HomeView
from .gamepad import GamepadView
from .triggers import TriggerView
from .screen import ScreenView
from .firmware import FirmwareView
from .settings import SettingsView

__all__ = [
    "HomeView",
    "GamepadView",
    "TriggerView",
    "ScreenView",
    "FirmwareView",
    "SettingsView",
]
