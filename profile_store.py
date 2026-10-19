"""Loads and caches device profiles (``*.fdg``) per device folder."""

from __future__ import annotations

from pathlib import Path

from .config_parser import DeviceConfig, list_device_folders, load_profiles_for


class ProfileStore:
    """Lazily loads profiles for each device folder."""

    def __init__(self):
        self._cache: dict[str, list[DeviceConfig]] = {}

    def device_folders(self) -> list[Path]:
        return list_device_folders()

    def get(self, folder_name: str) -> list[DeviceConfig]:
        """Return profiles for a device folder (e.g. ``device_f4``)."""
        if folder_name in self._cache:
            return self._cache[folder_name]

        for folder in self.device_folders():
            if folder.name == folder_name:
                profiles = load_profiles_for(folder)
                self._cache[folder_name] = profiles
                return profiles
        self._cache[folder_name] = []
        return []

    def all_profiles(self) -> dict[str, list[DeviceConfig]]:
        out = {}
        for folder in self.device_folders():
            out[folder.name] = self.get(folder.name)
        return out
