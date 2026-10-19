"""Application configuration and constants."""

import json
import os
import sys
from pathlib import Path

# Base directories (project root when running from source)
BASE_DIR = Path(__file__).resolve().parent.parent

# Application info
APP_NAME = "openflydigi3"
APP_VERSION = "1.0.0"
APP_ORG = "openflydigi3"

# Running as a PyInstaller build?  The bundle is read-only (or a per-run temp
# dir), so read-only assets come from ``sys._MEIPASS`` while writable state
# lives in the user's per-app config directory.
FROZEN = bool(getattr(sys, "frozen", False))


def user_state_dir() -> Path:
    """Writable per-user state directory (settings, editable profiles)."""
    if os.name == "nt":
        base = Path(
            os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming"
        )
        path = base / APP_ORG
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / APP_ORG
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
        path = base / APP_ORG.lower()
    path.mkdir(parents=True, exist_ok=True)
    return path


if FROZEN:
    _BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", str(BASE_DIR))) / "openflydigi3"
    ASSETS_DIR = _BUNDLE_DIR / "ui" / "resources" / "images"
    CONFIGS_DIR = _BUNDLE_DIR / "configs" / "device_configs"
    SETTINGS_FILE = user_state_dir() / "settings.json"
else:
    ASSETS_DIR = BASE_DIR / "ui" / "resources" / "images"
    CONFIGS_DIR = BASE_DIR / "configs" / "device_configs"
    SETTINGS_FILE = BASE_DIR / "settings.json"

# Supported device types (from extracted installer).  Display names are the
# official marketing names recovered from NpsDeviceInfoDict in the decompiled
# assembly (k1 = 八爪鱼3 "Apex 3", k2 = 八爪鱼4 "Apex 4", ...).
DEVICE_TYPES = {
    "f3": {"name": "Vader 3", "folder": "device_f3"},
    "f4": {"name": "Vader 4 Pro", "folder": "device_f4"},
    "f4_jl": {"name": "Vader 4 Pro JL", "folder": "device_f4_jl"},
    "fp2": {"name": "DireWolf", "folder": "device_fp2"},
    "fp3": {"name": "DireWolf 3", "folder": "device_fp3"},
    "fp4": {"name": "DireWolf 3 FP", "folder": "device_fp4"},
    "k1": {"name": "Apex 3", "folder": "device_k1"},
    "k2": {"name": "Apex 4", "folder": "device_k2"},
    "k2hsh": {"name": "Apex 4 HSH", "folder": "device_k2hsh"},
    "m1": {"name": "Dune Fox", "folder": "device_m1"},
}


def device_display_name(folder_name: str) -> str:
    """Human name for a profile folder (``device_k2`` → ``Apex 4``)."""
    key = folder_name.removeprefix("device_")
    entry = DEVICE_TYPES.get(key)
    return entry["name"] if entry else folder_name

# Real Flydigi USB identifiers.  Two modes exist:
#  * Dongle / BLE HID mode — Flydigi's own vendor id (0x31EB).
#  * Wired XInput mode — Microsoft-licensed Xbox 360 ids (045E:028E …)
#    where the pad is identified by its USB product string
#    (see openflydigi3.hardware.identify_model).
FLYDIGI_VID = 0x31EB
FLYDIGI_PIDS = {
    0x0075: "Apex 3",
    0x0076: "Apex 4",
    0x0077: "Vader 4 Pro",
    0x0078: "DireWolf 3 FP",
    0x0079: "Dune Fox",
}


class AppConfig:
    """Application settings manager."""

    def __init__(self):
        self._settings = self._load()

    def _load(self):
        if SETTINGS_FILE.exists():
            try:
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {
            "theme": "dark",
            "language": "en",
            "auto_connect": True,
            "show_splash": True,
            "last_device": None,
        }

    def save(self):
        with open(SETTINGS_FILE, "w") as f:
            json.dump(self._settings, f, indent=2)

    def get(self, key, default=None):
        return self._settings.get(key, default)

    def set(self, key, value):
        self._settings[key] = value
        self.save()


config = AppConfig()