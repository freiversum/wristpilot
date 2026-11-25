"""Bluetooth LE peripheral backends: offer the Wristpilot GATT service to the watch.

A backend calls `on_write(data)` for every write to the command characteristic and sends what that
coroutine returns as a notification on the status characteristic. `notify(data)` sends unsolicited
state changes.
"""

from __future__ import annotations

import sys
from typing import Awaitable, Callable

OnWrite = Callable[[bytes], Awaitable[bytes | None]]


class PeripheralError(Exception):
    pass


class Peripheral:
    name = "none"

    def __init__(self, on_write: OnWrite, info: bytes, local_name: str = "Wristpilot") -> None:
        self.on_write = on_write
        self.info = info
        self.local_name = local_name
        self.subscribed = False

    async def start(self) -> None:
        raise NotImplementedError

    async def notify(self, data: bytes) -> None:
        raise NotImplementedError

    async def stop(self) -> None:
        raise NotImplementedError


def default_peripheral(on_write: OnWrite, info: bytes, adapter: str = "") -> Peripheral:
    """Pick the backend. An adapter with a colon is a Bumble transport ("usb:0", "hci-socket:1").

    Windows uses Bumble on a dedicated adapter by default: the Windows stack advertises with a
    private address, which Garmin watches do not connect to ("winrt" selects it anyway)."""
    if adapter and ":" in adapter:
        from .bumble_backend import BumblePeripheral
        return BumblePeripheral(on_write, info, transport=adapter)
    if sys.platform.startswith("linux"):
        from .bluez import BluezPeripheral
        return BluezPeripheral(on_write, info, adapter=adapter)
    if sys.platform == "win32":
        if adapter == "winrt":
            from .winrt_backend import WinRTPeripheral
            return WinRTPeripheral(on_write, info)
        from .bumble_backend import BumblePeripheral
        return BumblePeripheral(on_write, info, transport=adapter)
    from .bless_backend import BlessPeripheral   # macOS (CoreBluetooth)
    return BlessPeripheral(on_write, info)
