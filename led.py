"""Apex 4 (K2) LED effects — port of the original WPF view-model logic.

Faithfully ports the parts of the decompiled *Flydigi Space Station* that
drive the Apex 4 lighting page:

* ``NewLedTypeDto.GetDefaultConfigK2``   → :data:`K2_LED_MODES`
* ``NewLedTypeDto.GetK2ColorList``       → :func:`get_colors`
* ``NewLedTypeDto.GetK2LedGroupListByCustom`` (+ ``CreateLedUnits*``)
                                          → :func:`groups_by_custom`
* ``NewLedTypeDto.GetK2LedGroupList``    → :func:`preset_groups`
  (backed by the ``K2ledUnits[6,4,10,3]`` preset table extracted into
  ``data/k2_led_presets.json``)
* ``NewBasicViewModel.UpdateGamepadLedInfo`` / ``LightScale`` / ``LoopTime``
  → :func:`apply_mode` / :func:`set_brightness` / :func:`set_speed`

All functions mutate the *raw* ``Config.Basic.NewLedConfig`` dict from the
parsed ``.fdg`` profile so changes round-trip through :func:`save_profile`.

Device scope: the original uses this logic for every device whose id is in
``GamePadVersionUtils.K2Serial`` (``device_k2``, ``device_k2hsh`` — the
``K2EVA`` special case, DeviceId 86, has no profile folder here).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

DATA_FILE = Path(__file__).resolve().parent / "data" / "k2_led_presets.json"

# Rgb_num used by the original for K2: GetDefaultConfigK2(RgbNum = 4)
K2_RGB_NUM = 4

# Sliders are clamped to 1..100 (NewBasicViewModel Sub/Add commands).
MIN_VALUE = 1
MAX_VALUE = 100


@dataclass(frozen=True)
class LedMode:
    """One entry of ``NewLedTypeDto.GetDefaultConfigK2``."""

    id: int
    name: str
    map_type: int      # written to NewLedConfig.Type (1 = game feedback)
    loop_end: int      # NewLedConfig.Loop_end
    loop_time: int     # default speed  → NewLedConfig.Loop_time
    light_scale: int   # default brightness → NewLedConfig.Light_scale
    show_time: bool    # original: IsShowAdjustTimeBox
    show_light: bool   # original: IsShowAdjustLightBox
    color_count: int   # swatch count from GetK2ColorList


# Port of NewLedTypeDto.GetDefaultConfigK2(RgbNum = 4).  Display names are
# the en-US resource values shipped with the original app.
K2_LED_MODES: list[LedMode] = [
    LedMode(2, "Breathing", 0, 9, 15, 50, True, True, 5),
    LedMode(3, "Gradient", 0, 1, 15, 50, True, True, 2),
    LedMode(4, "Feedback", 1, 1, 15, 50, True, True, 1),
    LedMode(5, "Steady", 0, 0, 1, 50, False, True, 1),
    LedMode(6, "Close", 0, 0, 1, 50, False, False, 0),
]

_MODES_BY_ID = {m.id: m for m in K2_LED_MODES}


def supports(folder_name: str) -> bool:
    """True for device profile folders handled by this module (K2Serial)."""
    return folder_name.startswith("device_k2")


def mode_by_id(mode_id: int) -> LedMode | None:
    return _MODES_BY_ID.get(int(mode_id or 0))


def current_mode(new_led: dict) -> LedMode | None:
    return mode_by_id(new_led.get("LedMode"))


# --------------------------------------------------------------------------
# K2ledUnits preset table
# --------------------------------------------------------------------------
_presets_cache: list | None = None


def _presets() -> list:
    global _presets_cache
    if _presets_cache is None:
        payload = json.loads(DATA_FILE.read_text())
        _presets_cache = payload["modes"]
    return _presets_cache


def preset_groups(mode_id: int, rgb_num: int = K2_RGB_NUM) -> list:
    """Port of ``GetK2LedGroupList(modeId = id - 1, ledNum = rgb_num)``.

    Only the first ``rgb_num`` zones are emitted (the original loops 0..15
    but adds a group only while ``i < ledNum``).
    """
    table = _presets()[int(mode_id) - 1]
    return [_zone_group(zone) for zone in table[:rgb_num]]


def _unit_dict(color) -> dict:
    """Serialize one LedUnit exactly like the .fdg JSON (R/G/B keys)."""
    return {"R": int(color[0]), "G": int(color[1]), "B": int(color[2])}


def _zone_group(units) -> dict:
    """Serialize one LedGroup (``{"Units": [...]}``)."""
    return {"Units": [_unit_dict(u) for u in units]}


# --------------------------------------------------------------------------
# Color list (read side) — port of NewLedTypeDto.GetK2ColorList
# --------------------------------------------------------------------------
def get_colors(new_led: dict) -> list[tuple[int, int, int]]:
    mode_id = int(new_led.get("LedMode") or 0)
    groups = new_led.get("LedGroups") or []
    if not groups:
        return []
    units = groups[0].get("Units") or []

    def unit(i: int) -> tuple[int, int, int]:
        if i < len(units):
            u = units[i]
            return (int(u.get("R") or 0), int(u.get("G") or 0), int(u.get("B") or 0))
        return (0, 0, 0)

    if mode_id == 2:                      # Breathing: 5 colors at even steps
        return [unit(i) for i in (0, 2, 4, 6, 8)]
    if mode_id == 3:                      # Gradient: 2 colors
        return [unit(0), unit(1)]
    if mode_id in (4, 5):                 # Feedback / Steady: 1 color
        return [unit(0)]
    return []                             # Close: no colour box in the original


# --------------------------------------------------------------------------
# Group builders (write side) — port of CreateLedUnits / 2 / 3 + ByCustom
# --------------------------------------------------------------------------
def _dim(value: int) -> int:
    # C#: (byte)((double)(int)color.R * 0.8) — truncating cast.
    return int(int(value) * 0.8)


def _dim3(color: tuple[int, int, int]) -> list[int]:
    return [_dim(c) for c in color]


def _zero_group() -> dict:
    return _zone_group([(0, 0, 0)] * 10)


def _units_full(colors: list, dimmed: bool) -> dict:
    """CreateLedUnits: colors at even indices, zeros at odd indices."""
    units = []
    for i in range(10):
        if i % 2 == 0:
            c = colors[i // 2]
            units.append(_dim3(c) if dimmed else list(c))
        else:
            units.append([0, 0, 0])
    return _zone_group(units)


def _units_pair(colors: list, dimmed: bool) -> dict:
    """CreateLedUnits2: first two units hold the colors."""
    units = []
    for i in range(10):
        if i < 2:
            c = colors[i]
            units.append(_dim3(c) if dimmed else list(c))
        else:
            units.append([0, 0, 0])
    return _zone_group(units)


def _units_single(colors: list, dimmed: bool) -> dict:
    """CreateLedUnits3: only the first unit holds the color."""
    units = []
    for i in range(10):
        if i < 1:
            c = colors[0]
            units.append(_dim3(c) if dimmed else list(c))
        else:
            units.append([0, 0, 0])
    return _zone_group(units)


def groups_by_custom(mode_id: int, colors: list[tuple[int, int, int]]) -> list:
    """Port of ``NewLedTypeDto.GetK2LedGroupListByCustom`` (K2, non-EVA)."""
    mode_id = int(mode_id)
    if mode_id == 2 and len(colors) == 5:
        return [
            _units_full(colors, False),
            _units_full(colors, True),
            _units_full(colors, True),
            _units_full(colors, True),
            _zero_group(),
            _zero_group(),
        ]
    if mode_id == 3 and len(colors) == 2:
        return [_units_pair(colors, False) for _ in range(5)] + [_zero_group()]
    if mode_id == 4 and len(colors) == 1:
        return [
            _units_single(colors, False),
            _units_single(colors, True),
            _units_single(colors, False),
            _units_single(colors, True),
        ]
    if mode_id == 5 and len(colors) == 1:
        return [_units_single(colors, False) for _ in range(5)] + [_zero_group()]
    # Id == 6 (Close): the original returns an empty list.
    return []


# --------------------------------------------------------------------------
# Mutators — port of NewBasicViewModel.UpdateGamepadLedInfo / setters
# --------------------------------------------------------------------------
def _clamp(value: int) -> int:
    return max(MIN_VALUE, min(MAX_VALUE, int(value)))


def apply_mode(new_led: dict, mode: LedMode) -> None:
    """Select an LED mode (resets speed/brightness to the mode defaults)."""
    new_led["LedMode"] = mode.id
    new_led["LedGroups"] = preset_groups(mode.id, int(new_led.get("Rgb_num") or K2_RGB_NUM))
    new_led["Rgb_num"] = int(new_led.get("Rgb_num") or K2_RGB_NUM)
    new_led["Loop_end"] = mode.loop_end
    new_led["Loop_time"] = mode.loop_time
    new_led["Light_scale"] = mode.light_scale
    new_led["Type"] = mode.map_type


def set_brightness(new_led: dict, value: int) -> int:
    value = _clamp(value)
    new_led["Light_scale"] = value
    return value


def set_speed(new_led: dict, value: int) -> int:
    value = _clamp(value)
    new_led["Loop_time"] = value
    return value


def set_colors(new_led: dict, colors: list[tuple[int, int, int]]) -> bool:
    """Rewrite LedGroups from the picked colours (ByCustom path)."""
    mode = current_mode(new_led)
    if mode is None:
        return False
    if len(colors) != mode.color_count:
        return False
    new_led["LedGroups"] = groups_by_custom(mode.id, colors)
    return True


# --------------------------------------------------------------------------
# Small helpers for the UI
# --------------------------------------------------------------------------
def rgb_hex(color: tuple[int, int, int]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*color)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    if len(value) != 6:
        return (0, 0, 0)
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError:
        return (0, 0, 0)
