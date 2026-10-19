"""Flydigi config-channel protocol for XInput-wrapped pads (Apex 4).

The Apex 4 disguises itself as an Xbox 360 controller (``045E:028E``,
product string "Flydigi APEX 4").  On Windows the original app talked to it
through a kernel minifilter (``Xbox360Filter64.sys``) that intercepted the
XInput *output* pipe; on Linux the same pipe is the interrupt OUT endpoint
(``0x05``) of the vendor interface, which hidapi/libusb can reach directly.

This module is a 1:1 port of the wire format recovered from the decompiled
``LibCommon`` assembly:

* ``XinputCommand.getData`` / ``CrcData`` / ``getSendData``  — 15-byte
  packets: ``[0]=0xA5, [1]=subCmd, [2..13]=payload, [14]=additive checksum``
  of bytes 0..13 (``PerPackageMaxLength = 15``).
* ``XInputDataUtils.LedFormatterWriteData`` — the LED payload is split into
  10-byte chunks (``PerPackageDataLength = 10``); each chunk is wrapped as
  ``WriteLed`` (0x29) with ``data[12]=0xA0`` and ``data[13]=packageIndex``.
* ``XInputDataUtils.FormatterStartLEDDataSpecifyId`` — optional session
  header: ``StartWriteLed`` (0x2A) carrying ``[configId, packageCount]``.
* ``GamepadConfigUtilsV2.GetNewLedByteList`` — the LED config payload:
  ``Version(2) + Type + Loop_start + Loop_end + Loop_time + Light_scale +
  Rgb_num + LedMode + 11x0xFF reserve`` followed by ``R,G,B`` for every
  unit of every non-empty ``LedGroups`` entry.

Reference: decompiled/flydigispacestation/Decompiled.cs (GetLEDConfigByteList
~L76343, LedFormatterWriteData ~L5698, GetNewLedByteList ~L4110).
"""

from __future__ import annotations

import base64

# XinputCommand constants (LibCommon).
PACKET_LEN = 15            # PerPackageMaxLength
DATA_LEN = 10              # PerPackageDataLength
MAGIC = 0xA5               # getData(): array[0] = 165
MARKER = 0xA0              # getSendData(..., packageIndex): data[12] = 160

# CommandDic.SubCmdId
CMD_GET_CUR_CONFIG_ID = 32  # "GetCurConfigId" — bare subcmd, no args
                            # (ReadGamepadConfigId L7747).  The pad answers
                            # with the same subcmd and the selected config
                            # slot at report[16] (HandleGamepadConfigId
                            # XInput path, L7387).
CMD_READ_CONFIG_ID = 33     # "ReadConfigId" — reads a slot's config *data*,
                            # not the current slot; not used for LED writes.
CMD_START_FLASH_LED = 40    # "StartFLashLEDDataKMPC" — session header the pad
                            # requires before accepting WriteLed chunks
CMD_WRITE_LED = 41          # "WriteLed"
CMD_START_WRITE_LED = 42    # "StartWriteLed"
SPECIFY_CONFIG_ID = 160     # CommandDic.SubCmdId["SpecifyConfigId"] (0xA0)

# SubCmd 80 (SubFunc_PrefixId) multiplexes config-management sub-functions
# selected by data[2] — CommandDic constants at LibCommon L17065-17077:
CMD_CONFIG_FUNC = 80
SUBFUNC_READ_RANDOM = 2     # SubFunc_ReadRandomId  — getSendData(80, 2, cfgId)
SUBFUNC_SAVE_FLASH = 3      # SubFunc_SaveFlashConfig — getSendData(80, 3, hi, lo)
SUBFUNC_READ_ALL_RANDOM = 4
SUBFUNC_SWITCH_CONFIG = 5
SUBFUNC_SWITCH_MAP_CONFIG = 6

# ACK framing: the pad multiplexes command acks into its 32-byte input
# reports — see GameControllerServiceHandler read dispatch:
#   report[14] == 0xA5 (magic) && report[15] == echoed subcmd.
ACK_REPORT_LEN = 32
ACK_MAGIC_OFFSET = 14
ACK_SUBCMD_OFFSET = 15
ACK_SLOT_OFFSET = 16        # HandleGamepadConfigId: SelCfgId = readBuffer[16]

# Subcmd-80 replies reuse offset 16 for the echoed sub-function and put their
# payload straight after (GameControllerServiceHandler dispatch L7011):
#   SaveFlashConfigCB  — status  = report[17] == 1          (HandlerSaveFlashConfigCB)
#   ReadRandomIdCB     — random  = (report[17]<<8)|report[18], cfgId = report[19]
#                        (HandlerReadRandomIdCB, big-endian, L6738)
ACK_SUBFUNC_OFFSET = 16
ACK_STATUS_OFFSET = 17
ACK_RANDOM_OFFSET = 17

# Session pacing recovered from UsbDataManager / XInputDataManager:
#   RetrayDelayCheckTime = 100 ms per un-ACKed packet,
#   MaxRetryNum          = 5 for k2 (Apex 4) — L7344-7347.
ACK_TIMEOUT = 0.10
MAX_RETRIES = 5

# GetRevData(11) — reserved filler after the LED header.
RESERVE = b"\xff" * 11

# Header written by GetNewLedByteList before the reserve block.
_HEADER_KEYS = (
    "Type",
    "Loop_start",
    "Loop_end",
    "Loop_time",
    "Light_scale",
    "Rgb_num",
    "LedMode",
)


def checksum(packet: bytearray) -> int:
    """Port of ``XinputCommand.CrcData``: additive sum stored in the last byte."""
    return sum(packet[: PACKET_LEN - 1]) & 0xFF


def make_packet(sub_cmd: int, args: bytes = b"", package_index: int | None = None) -> bytes:
    """Build one wire packet (port of ``getSendData`` overloads)."""
    data = bytearray(PACKET_LEN)
    data[0] = MAGIC
    data[1] = sub_cmd & 0xFF
    args = args[: PACKET_LEN - 2]
    data[2 : 2 + len(args)] = args
    if package_index is not None:
        data[12] = MARKER
        data[13] = package_index & 0xFF
    data[PACKET_LEN - 1] = checksum(data)
    return bytes(data)


def _version_bytes(new_led: dict) -> bytes:
    """``NewLedConfig.Version`` is base64 in the .fdg JSON (C# serializes
    ``byte[]`` that way); the wire wants the raw bytes (normally [0, 2])."""
    version = new_led.get("Version")
    if isinstance(version, str):
        try:
            return base64.b64decode(version)
        except Exception:
            return b"\x00\x00"
    if isinstance(version, (bytes, bytearray)):
        return bytes(version)
    return b"\x00\x00"


def led_payload(new_led: dict) -> bytes:
    """Port of ``GamepadConfigUtilsV2.GetNewLedByteList``.

    Serializes the ``Config.Basic.NewLedConfig`` dict into the byte blob the
    firmware expects: a 20-byte header followed by RGB triples for every LED
    unit of every non-empty group.
    """
    out = bytearray()
    out += _version_bytes(new_led)
    for key in _HEADER_KEYS:
        out.append(int(new_led.get(key) or 0) & 0xFF)
    out += RESERVE

    for group in new_led.get("LedGroups") or []:
        if not isinstance(group, dict):
            continue
        units = group.get("Units") or []
        if not units:
            continue
        for unit in units:
            if not isinstance(unit, dict):
                continue
            out.append(int(unit.get("R") or 0) & 0xFF)
            out.append(int(unit.get("G") or 0) & 0xFF)
            out.append(int(unit.get("B") or 0) & 0xFF)
    return bytes(out)


def led_packets(new_led: dict, config_id: int | None = None) -> list[bytes]:
    """Full packet list to push an LED config to the pad.

    Mirrors the *service* side path (GameControllerServiceHandler
    ``ApplyFlashLEDConfigInfo`` → ``XInputDataUtils.FormatterWriteFlashLEDFullData``):
    a ``StartFLashLEDDataKMPC`` (0x28) session header carrying
    ``[startIndex, packageCount, SpecifyConfigId(0xA0), configId]`` followed
    by the ``WriteLed`` chunks.  The pad only accepts ``WriteLed`` chunks
    after this header has been acked.

    ``config_id=None`` uses the pad's config slot 0 for the header.
    """
    payload = led_payload(new_led)
    package_count = (len(payload) + DATA_LEN - 1) // DATA_LEN

    packets: list[bytes] = [
        make_packet(
            CMD_START_FLASH_LED,
            bytes(
                [
                    0,  # startPkgIndex
                    package_count & 0xFF,
                    SPECIFY_CONFIG_ID,
                    (config_id or 0) & 0xFF,
                ]
            ),
        )
    ]
    for index in range(package_count):
        chunk = payload[index * DATA_LEN : (index + 1) * DATA_LEN]
        packets.append(make_packet(CMD_WRITE_LED, chunk, package_index=index))
    return packets


def config_id_packet() -> bytes:
    """Port of ``XInputDataManager.ReadGamepadConfigId`` (L7747).

    ``GetCurConfigId`` (32) is sent bare — ``getSendData(subCmd)`` with no
    args.  The pad answers with ``report[14]==0xA5, report[15]==32`` and the
    active config slot at ``report[16]`` (``HandleGamepadConfigId``, XInput
    path L7387; the DInput handler reads it at report[5] instead).
    """
    return make_packet(CMD_GET_CUR_CONFIG_ID)


def read_random_packet(config_id: int) -> bytes:
    """Port of ``FlashGamepadConfigService.ReadRandomInfo`` (L835).

    ``getSendData(80, 2, cfgId)`` asks the pad for the 16-bit change counter
    it stores alongside a config slot.  The answer carries it big-endian at
    ``report[17..18]`` with the echoed slot at ``report[19]``.
    """
    return make_packet(CMD_CONFIG_FUNC, bytes([SUBFUNC_READ_RANDOM, config_id & 0xFF]))


def save_flash_packet(random_id: int) -> bytes:
    """Port of ``FlashGamepadConfigService.SendSaveFlashConfigCmd`` (L819).

    ``getSendData(80, 3, [hi, lo])`` — the commit-to-flash step.  The pad
    persists whatever config it is currently running (the LED/keymap bytes
    already accepted via the subcmd 40/41 session) together with this change
    counter, which is why it must be bumped: ``SaveFlashConfig`` sends
    ``ConfigRandomBean.Random + 1`` (app L76475).

    Without this packet the write lands only in the pad's active RAM copy —
    it renders immediately but vanishes on power-off.  The original app calls
    it on window deactivate/close/tab-change and logs ``永久保存成功``
    ("permanent save success") when the pad acks (app L75742).

    ``random_id`` is a 16-bit counter, truncated on wrap the same way the
    service's ``(short)randomId`` cast does (L813).
    """
    value = random_id & 0xFFFF
    return make_packet(
        CMD_CONFIG_FUNC, bytes([SUBFUNC_SAVE_FLASH, value >> 8, value & 0xFF])
    )


def ack_matches(report: bytes | None, sub_cmd: int, sub_func: int | None = None) -> bool:
    """True when ``report`` is an ack for ``sub_cmd`` (and optionally ``sub_func``)."""
    if report is None or len(report) < ACK_SUBFUNC_OFFSET + 1:
        return False
    if report[ACK_MAGIC_OFFSET] != MAGIC:
        return False
    if report[ACK_SUBCMD_OFFSET] != sub_cmd:
        return False
    if sub_func is not None and report[ACK_SUBFUNC_OFFSET] != sub_func:
        return False
    return True


def parse_ack(report: bytes) -> tuple[int, int] | None:
    """Extract ``(subcmd, packageIndex)`` from a pad ack report, else None.

    The pad multiplexes acks into its regular 32-byte input reports:
    ``report[14] == 0xA5`` (magic) and ``report[15]`` is the echoed subcmd;
    the acked package index follows at ``report[16]``
    (see GameControllerServiceHandler.HandleWriteLEDConfigCBK).
    """
    if len(report) < 17:
        return None
    if report[ACK_MAGIC_OFFSET] != MAGIC:
        return None
    return report[ACK_SUBCMD_OFFSET], report[ACK_SUBCMD_OFFSET + 1]

