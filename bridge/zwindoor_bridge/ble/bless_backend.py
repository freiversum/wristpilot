"""GATT server through `bless` – used on Windows (WinRT GattServiceProvider) and macOS.

bless calls the write handler synchronously from its own thread on Windows; the handler hands
the bytes to our loop and the reply goes out as a notification.
"""

from __future__ import annotations

import asyncio
import logging

from .. import protocol
from . import Peripheral, PeripheralError

log = logging.getLogger(__name__)


class BlessPeripheral(Peripheral):
    name = "bless"

    def __init__(self, on_write, info, local_name="Zwindoor") -> None:
        super().__init__(on_write, info, local_name)
        self.server = None
        self.loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        try:
            from bless import (BlessServer, GATTAttributePermissions as Perm,
                               GATTCharacteristicProperties as Prop)
        except ImportError as e:
            raise PeripheralError("the Python package 'bless' is missing") from e
        self.loop = asyncio.get_running_loop()
        self.server = BlessServer(name=self.local_name, loop=self.loop)
        self.server.read_request_func = self._read
        self.server.write_request_func = self._write
        s = protocol.SERVICE_UUID
        await self.server.add_new_service(s)
        await self.server.add_new_characteristic(s, protocol.COMMAND_UUID, Prop.write | Prop.write_without_response,
                                                 None, Perm.writeable)
        await self.server.add_new_characteristic(s, protocol.STATUS_UUID, Prop.read | Prop.notify,
                                                 bytearray(b"\x02\x00"), Perm.readable)
        await self.server.add_new_characteristic(s, protocol.INFO_UUID, Prop.read, bytearray(self.info), Perm.readable)
        try:
            await self.server.start()
        except Exception as e:  # WinRT: adapter without peripheral role, Bluetooth off …
            raise PeripheralError(f"could not start the GATT server: {e}") from e
        log.info("bless: GATT service started, advertising as %r", self.local_name)

    def _read(self, characteristic, **_kwargs) -> bytearray:
        return characteristic.value

    def _write(self, characteristic, value, **_kwargs) -> None:
        if str(characteristic.uuid).lower() != protocol.COMMAND_UUID:
            return
        data = bytes(value)
        asyncio.run_coroutine_threadsafe(self._handle(data), self.loop)

    async def _handle(self, data: bytes) -> None:
        reply = await self.on_write(data)
        if reply:
            await self.notify(reply)

    async def notify(self, data: bytes) -> None:
        if not self.server:
            return
        ch = self.server.get_characteristic(protocol.STATUS_UUID)
        if ch is None:
            return
        ch.value = bytearray(data)
        self.server.update_value(protocol.SERVICE_UUID, protocol.STATUS_UUID)

    async def stop(self) -> None:
        if self.server:
            try:
                await self.server.stop()
            finally:
                self.server = None
