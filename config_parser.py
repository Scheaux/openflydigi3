"""Parser for Flydigi ``.fdg`` configuration files.

The original Windows app stores device profiles as JSON documents inside
``*.fdg`` files (despite the extension). This module loads those documents
into lightweight Python objects so the UI can display and edit them.
"""

from __future__ import annotations

import json
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_BUNDLE_CONFIGS = Path(__file__).resolve().parent / "configs" / "device_configs"

if getattr(sys, "frozen", False):
    # Frozen build: seed an editable copy of the shipped profiles into the
    # user's config directory so ``Ctrl+S`` writes survive a restart (the
    # bundle itself is read-only or discarded when the app exits).
    from .config import user_state_dir

    CONFIGS_ROOT = user_state_dir() / "configs" / "device_configs"
    if _BUNDLE_CONFIGS.is_dir() and not CONFIGS_ROOT.exists():
        shutil.copytree(_BUNDLE_CONFIGS, CONFIGS_ROOT)
else:
    CONFIGS_ROOT = _BUNDLE_CONFIGS


@dataclass
class KeyMapping:
    """A single remappable button/key entry from ``KeyMapping``."""

    key: str = ""
    key_id: int = 0
    map_key: str = ""
    map_type: int = 0
    map_data: str = ""
    turbo: int = 0
    turbo_type: int = 1
    priority: int = 0
    is_mapped: bool = False
    is_own: bool = False
    is_func_key: bool = False
    show_res: str = ""
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "KeyMapping":
        return cls(
            key=data.get("Key") or "",
            key_id=data.get("KeyId") or 0,
            map_key=data.get("MapKey") or "",
            map_type=data.get("MapType") or 0,
            map_data=str(data.get("MapData") or ""),
            turbo=data.get("Turbo") or 0,
            turbo_type=data.get("TurboType") or 1,
            priority=data.get("Priority") or 0,
            is_mapped=bool(data.get("IsMap")),
            is_own=bool(data.get("IsOwn")),
            is_func_key=bool(data.get("IsFuncKey")),
            show_res=data.get("ShowRes") or "",
            raw=data,
        )

    @property
    def label(self) -> str:
        return self.key or self.show_res or f"Key {self.key_id}"


@dataclass
class TriggerConfig:
    """Trigger (L2/R2) configuration with curve, auto-fire and motor."""

    side: str = "left"
    trigger_type: int = 0
    motor: dict = field(default_factory=dict)
    auto: dict = field(default_factory=dict)
    curve: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, side: str, data: dict) -> "TriggerConfig":
        return cls(
            side=side,
            trigger_type=data.get("Type") or 0,
            motor=data.get("TriggerMotor") or {},
            auto=data.get("AutoTrigger") or {},
            curve=data.get("curve") or {},
            raw=data,
        )


@dataclass
class JoystickConfig:
    """Left/right stick configuration (curve + deadzone etc.)."""

    side: str = "left"
    curve: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, side: str, data: dict) -> "JoystickConfig":
        return cls(
            side=side,
            curve=data.get("Curve") or {},
            config=data.get("Config") or {},
            raw=data,
        )


@dataclass
class MotionConfig:
    """Gyro / motion mapping configuration."""

    sensitivity: float = 0.0
    sensitivity_x: float = 0.0
    sensitivity_y: float = 0.0
    deadzone: int = 0
    mode: int = 0
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "MotionConfig":
        return cls(
            sensitivity=float(data.get("Sensity") or 0),
            sensitivity_x=float(data.get("SensityX") or 0),
            sensitivity_y=float(data.get("SensityY") or 0),
            deadzone=data.get("Zero") or 0,
            mode=data.get("Mode") or 0,
            raw=data,
        )


@dataclass
class LedConfig:
    """RGB / LED ring configuration."""

    mode: int = 0
    light: int = 0
    period: int = 0
    colors: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "LedConfig":
        colors = []
        for key in ("RgbColor0", "RgbColor1"):
            val = data.get(key)
            if isinstance(val, list):
                colors.append(tuple(val[:3]) if len(val) >= 3 else tuple(val))
        return cls(
            mode=data.get("Mode") or 0,
            light=data.get("Light") or 0,
            period=data.get("Peroid") or 0,
            colors=colors,
            raw=data,
        )


@dataclass
class NewLedConfig:
    """Zone-based LED block (``Config.Basic.NewLedConfig``).

    The parsed scalar fields are a snapshot for display; ``raw`` references
    the live JSON dict — edit through :mod:`openflydigi3.led` helpers and
    the changes are what :func:`save_profile` writes back.
    """

    led_mode: int = 0
    type: int = 0
    loop_start: int = 0
    loop_end: int = 0
    loop_time: int = 0
    light_scale: int = 0
    rgb_num: int = 0
    group_count: int = 0
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: dict) -> "NewLedConfig":
        groups = data.get("LedGroups")
        return cls(
            led_mode=data.get("LedMode") or 0,
            type=data.get("Type") or 0,
            loop_start=data.get("Loop_start") or 0,
            loop_end=data.get("Loop_end") or 0,
            loop_time=data.get("Loop_time") or 0,
            light_scale=data.get("Light_scale") or 0,
            rgb_num=data.get("Rgb_num") or 0,
            group_count=len(groups) if isinstance(groups, list) else 0,
            raw=data,
        )


@dataclass
class Macro:
    """A recorded macro sequence."""

    index: int = 0
    steps: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


@dataclass
class DeviceConfig:
    """A full parsed ``.fdg`` device profile."""

    path: Path
    name: str = "Unnamed"
    cfg_id: int = 0
    local_cfg_id: int = 0
    version: str = ""
    key_mappings: list[KeyMapping] = field(default_factory=list)
    left_trigger: Optional[TriggerConfig] = None
    right_trigger: Optional[TriggerConfig] = None
    left_stick: Optional[JoystickConfig] = None
    right_stick: Optional[JoystickConfig] = None
    motion: Optional[MotionConfig] = None
    led: Optional[LedConfig] = None
    new_led: Optional[NewLedConfig] = None
    macros: list[Macro] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> "DeviceConfig":
        with open(path, "r", encoding="utf-8-sig") as fh:
            data = json.load(fh)

        cfg = cls(path=path, raw=data)
        cfg.cfg_id = data.get("CfgId") or 0
        cfg.local_cfg_id = data.get("LocalCfgId") or 0
        cfg.name = (data.get("Name") or "Unnamed").strip()

        inner = data.get("Config") or {}
        cfg.version = str(inner.get("Version") or "")

        # Key mappings
        for entry in inner.get("KeyMapping") or []:
            if isinstance(entry, dict):
                cfg.key_mappings.append(KeyMapping.from_json(entry))

        # Triggers
        trig = inner.get("TriggerMapping") or {}
        if isinstance(trig, dict):
            if isinstance(trig.get("LeftTrigger"), dict):
                cfg.left_trigger = TriggerConfig.from_json("left", trig["LeftTrigger"])
            if isinstance(trig.get("RightTrigger"), dict):
                cfg.right_trigger = TriggerConfig.from_json("right", trig["RightTrigger"])

        # Joysticks
        joy = inner.get("JoyMapping") or {}
        if isinstance(joy, dict):
            if isinstance(joy.get("LeftJoystic") or joy.get("LeftJoystick"), dict):
                cfg.left_stick = JoystickConfig.from_json(
                    "left", joy.get("LeftJoystic") or joy.get("LeftJoystick")
                )
            if isinstance(joy.get("RightJoystic") or joy.get("RightJoystick"), dict):
                cfg.right_stick = JoystickConfig.from_json(
                    "right", joy.get("RightJoystic") or joy.get("RightJoystick")
                )

        # Motion / gyro
        motion = inner.get("MotionMapping")
        if isinstance(motion, dict):
            cfg.motion = MotionConfig.from_json(motion)

        # LED
        basic = inner.get("Basic") or {}
        if isinstance(basic, dict) and isinstance(basic.get("Led"), dict):
            cfg.led = LedConfig.from_json(basic["Led"])
        if isinstance(basic, dict) and isinstance(basic.get("NewLedConfig"), dict):
            cfg.new_led = NewLedConfig.from_json(basic["NewLedConfig"])

        # Macros
        macro = inner.get("Macro") or {}
        if isinstance(macro, dict):
            for i, entry in enumerate(macro.get("ListMacro") or []):
                if isinstance(entry, dict):
                    cfg.macros.append(Macro(index=i, raw=entry))

        return cfg


def list_device_folders() -> list[Path]:
    """Return the device profile folders shipped with the app."""
    if not CONFIGS_ROOT.exists():
        return []
    return sorted(p for p in CONFIGS_ROOT.iterdir() if p.is_dir())


def list_profiles(device_folder: Path) -> list[Path]:
    """Return all ``*.fdg`` profiles inside a device folder."""
    if not device_folder.exists():
        return []
    return sorted(device_folder.glob("*.fdg"))


def load_profiles_for(device_folder: Path) -> list[DeviceConfig]:
    """Load every profile in a device folder, skipping malformed files."""
    configs = []
    for path in list_profiles(device_folder):
        try:
            configs.append(DeviceConfig.load(path))
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
    return configs


def save_profile(cfg: DeviceConfig) -> None:
    """Write a profile back to its ``.fdg`` file.

    Matches the original formatting: tab-indented UTF-8 JSON with CRLF line
    endings and no trailing newline. ``cfg.raw`` (the live document the data
    classes point into) is the source of truth.
    """
    text = json.dumps(cfg.raw, ensure_ascii=False, indent="\t")
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(cfg.path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
