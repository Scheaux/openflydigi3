"""Hardware communication layer.

On Linux the Flydigi devices expose themselves through several transports:

* **HID** (``/dev/hidraw*``) via ``hidapi`` for the receiver/dongle.
* **Bluetooth LE** via ``bleak`` for the newer BLE-capable controllers.
* **USB CDC / serial** (``/dev/ttyACM*``) for firmware flashing.

The Windows app talked to a kernel driver (``FeizVKB64.sys``, ``flydigigamemap.sys``);
on Linux we bypass the driver entirely and speak to the raw HID/BLE endpoints.

Everything here degrades gracefully: if no hardware is present the manager
yields a set of *demo* devices so the UI can be exercised.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Optional

from .devices import ConnectionType, DeviceInfo, DeviceStatus
from . import xinput_proto

log = logging.getLogger(__name__)

# Flydigi's own USB vendor id (used by the 2.4G dongle / BLE HID mode).
FLYDIGI_VID = 0x31EB
KNOWN_PIDS = {
    0x0075: "K1",
    0x0076: "K2",
    0x0077: "F4",
    0x0078: "FP4",
    0x007A: "F3",
    0x007B: "FP3",
    0x007C: "M1",
    0x007D: "FP2",
}

# Wired/XInput disguise: in this mode the pad enumerates with Microsoft's
# licensed Xbox 360 ids and identifies itself only by the USB product
# string ("Flydigi APEX 4").  We therefore match these VID/PID pairs only
# when the product/serial string says Flydigi, so real Xbox pads are never
# claimed.  (The original Windows app used the same product-name approach —
# see LibCommon FDGDeviceInfo.UpdateDeviceIdByDeviceInfo.)
XINPUT_STEALTH_IDS = {
    (0x045E, 0x028E),  # Xbox 360 wired — Apex 4 in XInput mode
    (0x045E, 0x0291),
    (0x045E, 0x02A9),
}

_XINPUT_CAPABILITIES = ["keys", "sticks", "triggers", "gyro", "led", "macro", "screen"]


def identify_model(text: str) -> Optional[str]:
    """Map a USB product string to a device key (``k2``, ``f4``, ...).

    Port of ``FDGDeviceInfo.UpdateDeviceIdByDeviceInfo``: the pad family is
    recognised from the product name because the wired/XInput ids are
    Microsoft-licensed and shared across generations.
    """
    name = (text or "").lower()
    if "apex" in name:
        if "4" in name:
            return "k2"
        if "3" in name:
            return "k1"
    elif "vader" in name:
        if "4" in name:
            return "f4"
        if "3" in name:
            return "f3"
    elif "direwolf" in name:
        if "3" in name:
            return "fp3"
        if "2" in name:
            return "fp2"
        return "fp2"
    elif "dune" in name or "fox" in name:
        return "m1"
    return None

try:  # pragma: no cover - import guard
    import hid  # type: ignore

    _HAS_HID = True
except Exception:  # pragma: no cover
    hid = None
    _HAS_HID = False

try:  # pragma: no cover - import guard
    import serial.tools.list_ports  # type: ignore

    _HAS_SERIAL = True
except Exception:  # pragma: no cover
    _HAS_SERIAL = False


class HidTransport:
    """Thin wrapper around a ``hidapi`` device handle."""

    def __init__(self, path: bytes, vendor_id: int, product_id: int):
        self.path = path
        self.vendor_id = vendor_id
        self.product_id = product_id
        self._dev = None

    def open(self) -> bool:
        if not _HAS_HID:
            return False
        try:
            self._dev = hid.device()
            self._dev.open_path(self.path)
            self._dev.set_nonblocking(1)
            return True
        except Exception as exc:  # pragma: no cover - hardware dependent
            log.warning("Failed to open HID device %s: %s", self.path, exc)
            self._dev = None
            return False

    def write(self, report: bytes) -> bool:
        if self._dev is None:
            return False
        try:
            self._dev.write(report)
            return True
        except Exception as exc:  # pragma: no cover
            log.warning("HID write failed: %s", exc)
            return False

    def read(self, size: int = 64, timeout_ms: int = 100) -> Optional[bytes]:
        if self._dev is None:
            return None
        try:
            data = self._dev.read(size, timeout_ms)
            return bytes(data) if data else None
        except Exception:  # pragma: no cover
            return None

    def close(self) -> None:
        if self._dev is not None:
            try:
                self._dev.close()
            except Exception:  # pragma: no cover
                pass
            self._dev = None


class SerialTransport:
    """Serial/USB-CDC transport used for firmware flashing."""

    def __init__(self, port: str, baudrate: int = 115200):
        self.port = port
        self.baudrate = baudrate
        self._ser = None

    def open(self) -> bool:
        if not _HAS_SERIAL:
            return False
        try:
            import serial  # type: ignore

            self._ser = serial.Serial(self.port, self.baudrate, timeout=1)
            return True
        except Exception as exc:  # pragma: no cover
            log.warning("Failed to open serial %s: %s", self.port, exc)
            return False

    def write(self, data: bytes) -> bool:
        if self._ser is None:
            return False
        self._ser.write(data)
        return True

    def close(self) -> None:
        if self._ser is not None:
            self._ser.close()
            self._ser = None


def scan_hid_devices() -> list[DeviceInfo]:
    """Enumerate HID/USB interfaces that look like Flydigi hardware.

    Matching follows the original app's approach (product-name based), plus
    the known Flydigi VID for dongle/BLE mode.  Detected devices get their
    ``config_path`` set from the model key so profiles (and the LED page)
    load for real hardware, not just for the demo set.
    """
    found: list[DeviceInfo] = []
    seen: set[str] = set()
    if not _HAS_HID:
        return found
    try:
        for entry in hid.enumerate():
            vid = entry.get("vendor_id") or 0
            pid = entry.get("product_id") or 0
            product = entry.get("product_string") or ""
            serial = entry.get("serial_number") or ""
            label = f"{product} {serial}"

            if vid == FLYDIGI_VID and pid in KNOWN_PIDS:
                model_key = None
                name = f"Flydigi {KNOWN_PIDS[pid]}"
            elif (vid, pid) in XINPUT_STEALTH_IDS and "flydigi" in label.lower():
                model_key = identify_model(label)
                name = product or f"Flydigi {model_key or 'Controller'}"
            elif "flydigi" in label.lower():
                model_key = identify_model(label)
                name = product or "Flydigi Controller"
            else:
                continue

            from .config import DEVICE_TYPES  # local import: avoid cycle

            config_path = None
            model = name
            if model_key and model_key in DEVICE_TYPES:
                config_path = DEVICE_TYPES[model_key]["folder"]
                model = DEVICE_TYPES[model_key]["name"]

            key = f"{vid:04x}:{pid:04x}:{serial or product}"
            if key in seen:
                continue
            seen.add(key)

            found.append(
                DeviceInfo(
                    device_id=f"hid:{key}",
                    name=name,
                    model=model,
                    connection_type=ConnectionType.HID,
                    vendor_id=vid,
                    product_id=pid,
                    serial_number=serial or None,
                    path=entry.get("path"),
                    status=DeviceStatus.CONNECTED,
                    capabilities=list(_XINPUT_CAPABILITIES),
                    config_path=config_path,
                )
            )
    except Exception as exc:  # pragma: no cover
        log.warning("HID enumeration failed: %s", exc)
    return found


def scan_serial_devices() -> list[DeviceInfo]:
    """Enumerate serial ports that may host a controller in flash mode."""
    found: list[DeviceInfo] = []
    if not _HAS_SERIAL:
        return found
    try:
        import serial.tools.list_ports  # type: ignore

        for port in serial.tools.list_ports.comports():
            desc = (port.description or "").lower()
            if "flydigi" not in desc and not any(
                tag in (port.device or "") for tag in ("ttyACM", "ttyUSB")
            ):
                continue
            found.append(
                DeviceInfo(
                    device_id=f"serial:{port.device}",
                    name=port.description or port.device,
                    model="Flash Mode",
                    connection_type=ConnectionType.USB_CDC,
                    port=port.device,
                )
            )
    except Exception as exc:  # pragma: no cover
        log.warning("Serial enumeration failed: %s", exc)
    return found


def demo_devices() -> list[DeviceInfo]:
    """A representative device set shown when no hardware is attached."""
    return [
        DeviceInfo(
            device_id="demo:f4",
            name="Flydigi F4",
            model="F4",
            connection_type=ConnectionType.HID,
            vendor_id=FLYDIGI_VID,
            product_id=0x0077,
            serial_number="F4-DEMO-0001",
            firmware_version="1.0.9",
            status=DeviceStatus.CONNECTED,
            capabilities=["keys", "sticks", "triggers", "gyro", "led", "macro", "screen"],
            config_path="device_f4",
        ),
        DeviceInfo(
            device_id="demo:k2",
            name="Flydigi Apex 4",
            model="Apex 4",
            connection_type=ConnectionType.BLUETOOTH,
            vendor_id=FLYDIGI_VID,
            product_id=0x0076,
            address="AA:BB:CC:DD:EE:FF",
            firmware_version="1.2.1",
            status=DeviceStatus.DISCONNECTED,
            capabilities=["keys", "sticks", "triggers", "gyro", "led", "macro", "screen"],
            config_path="device_k2",
        ),
        DeviceInfo(
            device_id="demo:fp4",
            name="Flydigi FP4",
            model="FP4",
            connection_type=ConnectionType.SERIAL,
            port="/dev/ttyACM0",
            firmware_version="0.9.4",
            status=DeviceStatus.DISCONNECTED,
            capabilities=["keys", "triggers", "led", "macro"],
            config_path="device_fp4",
        ),
    ]


class DeviceManager:
    """Discovers and tracks Flydigi devices.

    Emits callbacks when the device list changes. Falls back to demo devices
    when nothing is physically attached so the app remains usable.
    """

    def __init__(self, allow_demo: bool = True, force_demo: bool = False):
        self.allow_demo = allow_demo
        # Force the demo set even when hardware is attached — used by the
        # headless smoke test so it stays deterministic on a dev box with a
        # real pad plugged in.
        self.force_demo = force_demo
        self._devices: dict[str, DeviceInfo] = {}
        self._listeners: list[Callable[[list[DeviceInfo]], None]] = []
        self._lock = threading.Lock()
        self._transports: dict[str, object] = {}

    # -- listeners -------------------------------------------------------
    def add_listener(self, callback: Callable[[list[DeviceInfo]], None]) -> None:
        self._listeners.append(callback)

    def _notify(self) -> None:
        snapshot = self.devices
        for cb in self._listeners:
            try:
                cb(snapshot)
            except Exception:  # pragma: no cover
                log.exception("Device listener failed")

    # -- accessors -------------------------------------------------------
    @property
    def devices(self) -> list[DeviceInfo]:
        with self._lock:
            return list(self._devices.values())

    def get(self, device_id: str) -> Optional[DeviceInfo]:
        return self._devices.get(device_id)

    # -- scanning --------------------------------------------------------
    def scan(self) -> list[DeviceInfo]:
        """Scan all transports and merge the results."""
        results: list[DeviceInfo] = []
        if self.force_demo:
            results = demo_devices() if self.allow_demo else []
        else:
            results.extend(scan_hid_devices())
            results.extend(scan_serial_devices())

            if not results and self.allow_demo:
                results = demo_devices()

        with self._lock:
            for dev in results:
                existing = self._devices.get(dev.device_id)
                if existing is not None:
                    dev.status = existing.status
                self._devices[dev.device_id] = dev

        self._notify()
        return self.devices

    def connect(self, device_id: str) -> bool:
        dev = self._devices.get(device_id)
        if dev is None:
            return False
        dev.status = DeviceStatus.CONNECTING
        self._notify()

        # Demo devices are always "connectable".
        if device_id.startswith("demo:"):
            dev.status = DeviceStatus.CONNECTED
            self._notify()
            return True

        # XInput-stealth pads are driven by the kernel xpad driver; grabbing
        # a persistent hidapi handle would unbind it and freeze game input.
        # Enumeration already proves presence, and config writes (LED) open
        # the device ephemerally in send_led_config().
        if dev.vendor_id == 0x045E:
            dev.status = DeviceStatus.CONNECTED
            self._notify()
            return True

        transport = None
        if dev.connection_type == ConnectionType.HID and dev.path:
            transport = HidTransport(dev.path, dev.vendor_id or 0, dev.product_id or 0)
        elif dev.connection_type == ConnectionType.USB_CDC and dev.port:
            transport = SerialTransport(dev.port)

        if transport and transport.open():
            self._transports[device_id] = transport
            dev.status = DeviceStatus.CONNECTED
        else:
            dev.status = DeviceStatus.ERROR
        self._notify()
        return dev.status == DeviceStatus.CONNECTED

    def disconnect(self, device_id: str) -> None:
        transport = self._transports.pop(device_id, None)
        if transport is not None:
            try:
                transport.close()
            except Exception:  # pragma: no cover
                pass
        dev = self._devices.get(device_id)
        if dev is not None:
            dev.status = DeviceStatus.DISCONNECTED
        self._notify()

    def send_report(self, device_id: str, report: bytes) -> bool:
        transport = self._transports.get(device_id)
        if transport is None:
            return False
        return bool(transport.write(report))  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # XInput config-channel session (Apex 4 and friends)
    #
    # Ported from GameControllerServiceHandler.XInputDataManager:
    #   ApplyFlashLEDConfigInfo -> WriteGamePadConfig(list, isFlash: true)
    #     FullConfigList[0]               = StartFLashLEDDataKMPC (40) header
    #     FullConfigList[1..N]            = WriteLed (41) chunks
    #   on every ack  -> ReadPackageId++, send the next packet
    #   100 ms silent -> ResendDataPacket(): same packet, checksum byte
    #                    bumped by the retry count, up to 5 retries (k2)
    #   whole write  -> 3 s watchdog (Task.Delay(3000) in the service)
    # The handle stays open only for the session so ``xpad`` re-binds and
    # game input resumes the moment we close.
    # ------------------------------------------------------------------

    @staticmethod
    def _read_report(handle, timeout_s: float) -> Optional[bytes]:
        """One hidapi read; ``None`` on timeout/error."""
        try:
            data = handle.read(
                xinput_proto.ACK_REPORT_LEN, max(1, int(timeout_s * 1000))
            )
        except Exception:
            return None
        return bytes(data) if data else None

    def _drain_input(self, handle, last_report: bytes, max_ms: int = 30) -> bytes:
        """Discard stale input so an old ack cannot satisfy a new wait.

        Mirrors the service's ``LastXinputBuffer`` bookkeeping: reports seen
        here are remembered so later waits can drop identical repeats.
        """
        deadline = time.monotonic() + max_ms / 1000.0
        while time.monotonic() < deadline:
            report = self._read_report(handle, 0.005)
            if report is None:
                break
            last_report = report
        return last_report

    def _wait_ack(self, handle, sub_cmd: int, last_report: bytes,
                  timeout: float, sub_func: int | None = None) -> Optional[bytes]:
        """Wait for the pad to echo ``sub_cmd`` inside an input report.

        ACK framing: ``report[14] == 0xA5`` and ``report[15] == sub_cmd``
        (read dispatch L6915).  For subcmd 80 the sub-function follows at
        ``report[16]`` (dispatch L7011), so pass ``sub_func`` to keep e.g. a
        read-random ack from satisfying a save wait.  Reports identical to
        the previous one are dropped, matching the service's dedupe.
        Returns the ACK report, or ``None`` on timeout.
        """
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            report = self._read_report(handle, min(0.02, remaining))
            if report is None:
                continue
            if report == last_report:
                continue
            last_report = report
            if xinput_proto.ack_matches(report, sub_cmd, sub_func):
                return report

    def _persist_config(self, handle, slot: int, last_report: bytes) -> tuple[bool, bytes]:
        """Commit the just-written config to the pad's non-volatile storage.

        Port of the app's ``ConfigManager.SaveFlashConfig`` (L76463), which
        the original fires on window deactivate / close / tab-change:

          1. ``ReadRandomInfo``  — ``getSendData(80, 2, slot)``; the pad
             answers with the change counter it stores for that slot,
             big-endian, at ``report[17..18]``.
          2. ``SendSaveFlashConfigCmd`` — ``getSendData(80, 3, counter+1)``;
             the pad answers ``report[16] == 3`` with status at
             ``report[17]`` (1 == success).

        Step 1 mirrors the app's ``ConfigRandomBean.Random`` sync: the save
        always sends ``local + 1`` (app L76475), keeping the per-slot version
        monotonic so conflict detection between profile and pad still works.
        A failed read is not fatal — the save then falls back to counter 1.

        Returns ``(committed, last_report)``.
        """
        counter = 1
        for attempt in range(2):
            handle.write(xinput_proto.read_random_packet(slot))
            ack = self._wait_ack(
                handle,
                xinput_proto.CMD_CONFIG_FUNC,
                last_report,
                0.3,
                sub_func=xinput_proto.SUBFUNC_READ_RANDOM,
            )
            if ack is not None:
                counter = (ack[xinput_proto.ACK_RANDOM_OFFSET] << 8) | ack[
                    xinput_proto.ACK_RANDOM_OFFSET + 1
                ]
                last_report = self._drain_input(handle, ack)
                log.debug("pad change counter for slot %d: %d", slot, counter)
                break
            last_report = self._drain_input(handle, last_report)
        else:
            log.debug("change counter read timed out; saving with counter 1")

        target = (counter + 1) & 0xFFFF
        for attempt in range(3):
            payload = bytearray(xinput_proto.save_flash_packet(target))
            if attempt:
                payload[-1] = (payload[-1] + attempt) & 0xFF  # ResendDataPacket
            handle.write(bytes(payload))
            # Flash erase/write is slower than a packet ack — give it room;
            # the original app polls the result for up to 6 s (L76494).
            ack = self._wait_ack(
                handle,
                xinput_proto.CMD_CONFIG_FUNC,
                last_report,
                1.0,
                sub_func=xinput_proto.SUBFUNC_SAVE_FLASH,
            )
            if ack is not None:
                last_report = self._drain_input(handle, ack)
                status = ack[xinput_proto.ACK_STATUS_OFFSET]
                log.debug("save flash ack: counter=%d status=%d", target, status)
                return status == 1, last_report
            last_report = self._drain_input(handle, last_report)
        log.warning("save-to-flash (counter %d) not acked after 3 tries", target)
        return False, last_report

    def send_led_config(self, device_id: str, new_led: dict, config_id: int | None = None,
                        persist: bool = True) -> bool:
        """Push an LED config block (``Config.Basic.NewLedConfig``) to a pad.

        Runs the ACK-paced flash-LED session recovered from the decompiled
        service (see the block comment above): query the pad's active config
        slot (bare ``GetCurConfigId``), send the ``StartFLashLEDDataKMPC``
        header, then every ``WriteLed`` chunk — each one only after the pad
        acked the previous, retrying up to 5x on a 100 ms timeout.  Returns
        ``False`` if any packet went unacknowledged or the 3 s watchdog
        expired.

        The subcmd 40/41 session only reaches the pad's *running* copy of the
        config, so with ``persist=True`` (default) a ``SaveFlashConfig``
        commit follows — without it the colours vanish on power-off.  Pass
        ``persist=False`` for a preview that is deliberately not saved.

        The handle is opened only for the session so the kernel gamepad
        driver (``xpad``) keeps serving input in between.
        """
        dev = self._devices.get(device_id)
        if dev is None or not dev.path or not _HAS_HID:
            return False
        try:
            h = hid.device()
            h.open_path(dev.path)
        except Exception as exc:  # pragma: no cover - hardware dependent
            log.warning("Cannot open %s for LED write: %s", device_id, exc)
            return False

        try:
            last_report = self._drain_input(h, b"")

            # Which config slot is the pad running?  (ReadGamepadConfigId
            # L7747 — bare subcmd 32; slot at report[16].)  Fall back to 0
            # if the pad stays quiet; the shipped default lives in slot 0.
            slot = config_id
            if slot is None:
                h.write(xinput_proto.config_id_packet())
                ack = self._wait_ack(
                    h, xinput_proto.CMD_GET_CUR_CONFIG_ID, last_report, 0.3
                )
                if ack is not None:
                    last_report = self._drain_input(h, ack)
                    slot = ack[xinput_proto.ACK_SLOT_OFFSET]
                    log.debug("Apex config slot: %d", slot)
                else:
                    slot = 0

            packets = xinput_proto.led_packets(new_led, config_id=slot)
            if not packets:
                return False

            watchdog = time.monotonic() + 3.0  # service: Task.Delay(3000)
            total = len(packets)
            for index, packet in enumerate(packets):
                sub_cmd = packet[1]
                acknowledged = False
                for attempt in range(xinput_proto.MAX_RETRIES + 1):
                    if time.monotonic() > watchdog:
                        log.warning(
                            "LED session aborted: 3 s watchdog after %d/%d packets",
                            index,
                            total,
                        )
                        return False
                    payload = bytearray(packet)
                    if attempt:
                        # ResendDataPacket (L7854): fresh copy, checksum byte
                        # bumped by the retry count (1..5).
                        payload[-1] = (payload[-1] + attempt) & 0xFF
                    h.write(bytes(payload))
                    ack = self._wait_ack(
                        h, sub_cmd, last_report, xinput_proto.ACK_TIMEOUT
                    )
                    if ack is not None:
                        last_report = ack
                        acknowledged = True
                        break
                    # Timeout: flush late duplicates before resending.
                    last_report = self._drain_input(h, last_report)
                if not acknowledged:
                    log.warning(
                        "LED packet %d/%d (subcmd %d) not acked after %d retries",
                        index + 1,
                        total,
                        sub_cmd,
                        xinput_proto.MAX_RETRIES,
                    )
                    return False
            log.debug("LED session complete: %d packets acked (slot %d)", total, slot)
            if not persist:
                return True
            committed, last_report = self._persist_config(h, slot, last_report)
            if committed:
                log.debug("config committed to flash (slot %d)", slot)
                return True
            log.warning("LED applied, but the save-to-flash commit failed")
            return False
        except Exception as exc:  # pragma: no cover
            log.warning("LED write failed: %s", exc)
            return False
        finally:
            try:
                h.close()
            except Exception:  # pragma: no cover
                pass

    def shutdown(self) -> None:
        for dev_id in list(self._transports):
            self.disconnect(dev_id)
