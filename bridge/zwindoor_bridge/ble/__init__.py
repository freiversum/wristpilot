"""Bluetooth LE peripheral backends: offer the ZWindoor GATT service to the watch.

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

    def __init__(self, on_write: OnWrite, info: bytes, local_name: str = "Zwindoor") -> None:
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
    if sys.platform.startswith("linux"):
        from .bluez import BluezPeripheral
        return BluezPeripheral(on_write, info, adapter=adapter)
    if sys.platform == "win32":
        from .winrt_backend import WinRTPeripheral
        return WinRTPeripheral(on_write, info)
    from .bless_backend import BlessPeripheral   # macOS (CoreBluetooth)
    return BlessPeripheral(on_write, info)
