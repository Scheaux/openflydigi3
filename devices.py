"""Device models and definitions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ConnectionType(Enum):
    HID = "hid"
    BLUETOOTH = "bluetooth"
    SERIAL = "serial"
    USB_CDC = "usb_cdc"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CONFIGURING = "configuring"
    UPDATING = "updating"
    ERROR = "error"


@dataclass
class DeviceInfo:
    """Information about a connected Flydigi device."""

    device_id: str
    name: str
    model: str
    connection_type: ConnectionType
    status: DeviceStatus = DeviceStatus.DISCONNECTED
    vendor_id: Optional[int] = None
    product_id: Optional[int] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    path: Optional[str] = None
    address: Optional[str] = None  # Bluetooth address
    port: Optional[str] = None  # Serial port
    config_path: Optional[str] = None
    capabilities: list = field(default_factory=list)

    @property
    def is_connected(self) -> bool:
        return self.status == DeviceStatus.CONNECTED

    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.model})"


@dataclass
class ButtonMapping:
    """Button mapping configuration."""

    button_id: str
    button_name: str
    action: str
    action_value: str = ""
    macro: Optional[str] = None


@dataclass
class DeviceConfig:
    """Full device configuration."""

    model: str
    buttons: list[ButtonMapping] = field(default_factory=list)
    sensitivity: dict = field(default_factory=dict)
    vibration: dict = field(default_factory=dict)
    screen_settings: dict = field(default_factory=dict)
    macro_settings: dict = field(default_factory=dict)