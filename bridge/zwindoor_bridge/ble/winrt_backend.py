"""Windows GATT server through the WinRT Bluetooth API (pywinrt `winrt-*` packages).

Replaces `bless` on Windows: bless 0.2.6/0.3.0 import the unpublished package `pysetupdi` and
open the Bluetooth adapter device directly (to rename it in the registry), which fails without
admin rights. The WinRT `GattServiceProvider` needs neither.

WinRT events arrive on WinRT threads; they take a deferral and hand the request to the bridge's
asyncio loop, where the WinRT async operations are awaited.
"""

from __future__ import annotations

import asyncio
import logging
import uuid

from .. import protocol
from . import Peripheral, PeripheralError

log = logging.getLogger(__name__)


def _buffer(data: bytes):
    from winrt.windows.storage.streams import Buffer
    buf = Buffer(len(data))
    buf.length = len(data)
    if data:
        with memoryview(buf) as mv:
            mv[:] = data
    return buf


class WinRTPeripheral(Peripheral):
    name = "winrt"

    def __init__(self, on_write, info, local_name="ZWindoor", adapter: str = "") -> None:
        super().__init__(on_write, info, local_name)
        self.loop: asyncio.AbstractEventLoop | None = None
        self.provider = None
        self.status_char = None
        self.status_value = bytes((protocol.MSG_STATE, 0))
        self._tokens: list = []

    async def start(self) -> None:
        try:
            from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
            from winrt.windows.devices.bluetooth.genericattributeprofile import (
                GattCharacteristicProperties as Prop, GattLocalCharacteristicParameters,
                GattProtectionLevel, GattServiceProvider, GattServiceProviderAdvertisingParameters)
        except ImportError as e:
            raise PeripheralError(f"WinRT Bluetooth modules missing ({e})") from e
        self.loop = asyncio.get_running_loop()

        adapter = await BluetoothAdapter.get_default_async()
        if adapter is None:
            raise PeripheralError("no Bluetooth adapter found")
        if not adapter.is_peripheral_role_supported:
            raise PeripheralError("the Bluetooth adapter does not support the peripheral role")

        result = await GattServiceProvider.create_async(uuid.UUID(protocol.SERVICE_UUID))
        if result.error != BluetoothError.SUCCESS:
            raise PeripheralError(f"could not create the GATT service ({result.error})")
        self.provider = result.service_provider
        service = self.provider.service

        async def characteristic(uuid_str: str, props, static: bytes | None = None):
            params = GattLocalCharacteristicParameters()
            params.characteristic_properties = props
            params.read_protection_level = GattProtectionLevel.PLAIN
            params.write_protection_level = GattProtectionLevel.PLAIN
            if static is not None:
                params.static_value = _buffer(static)
            res = await service.create_characteristic_async(uuid.UUID(uuid_str), params)
            if res.error != BluetoothError.SUCCESS:
                raise PeripheralError(f"could not create characteristic {uuid_str} ({res.error})")
            return res.characteristic

        command = await characteristic(protocol.COMMAND_UUID, Prop.WRITE | Prop.WRITE_WITHOUT_RESPONSE)
        self._tokens.append((command, "write", command.add_write_requested(self._on_write_requested)))
        self.status_char = await characteristic(protocol.STATUS_UUID, Prop.READ | Prop.NOTIFY)
        self._tokens.append((self.status_char, "read",
                             self.status_char.add_read_requested(self._on_read_requested)))
        self._tokens.append((self.status_char, "subscribed",
                             self.status_char.add_subscribed_clients_changed(self._on_subscribed)))
        await characteristic(protocol.INFO_UUID, Prop.READ, static=self.info)

        adv = GattServiceProviderAdvertisingParameters()
        adv.is_discoverable = True
        adv.is_connectable = True
        self.provider.start_advertising_with_parameters(adv)
        log.info("WinRT: GATT service started and advertised")

    # --- WinRT event handlers (WinRT thread) ---

    def _on_write_requested(self, _sender, args) -> None:
        deferral = args.get_deferral()
        asyncio.run_coroutine_threadsafe(self._handle_write(args, deferral), self.loop)

    def _on_read_requested(self, _sender, args) -> None:
        deferral = args.get_deferral()
        asyncio.run_coroutine_threadsafe(self._handle_read(args, deferral), self.loop)

    def _on_subscribed(self, sender, _args) -> None:
        self.subscribed = len(sender.subscribed_clients) > 0
        log.info("watch %s notifications", "subscribed to" if self.subscribed else "unsubscribed from")

    # --- on the bridge loop ---

    async def _handle_write(self, args, deferral) -> None:
        from winrt.windows.devices.bluetooth.genericattributeprofile import GattWriteOption
        try:
            request = await args.get_request_async()
            data = bytes(request.value) if request is not None else None
            if request is not None and request.option == GattWriteOption.WRITE_WITH_RESPONSE:
                request.respond()
        except Exception as e:
            log.warning("WinRT write: %s", e)
            data = None
        finally:
            # Complete the write before notifying: Windows holds notifications back while a
            # request on the same connection is still deferred.
            deferral.complete()
        if data is None:
            return
        reply = await self.on_write(data)
        if reply:
            await self.notify(reply)

    async def _handle_read(self, args, deferral) -> None:
        try:
            request = await args.get_request_async()
            if request is not None:
                request.respond_with_value(_buffer(self.status_value))
        except Exception as e:
            log.warning("WinRT read: %s", e)
        finally:
            deferral.complete()

    async def notify(self, data: bytes) -> None:
        self.status_value = data
        if self.status_char is None:
            return
        try:
            results = await self.status_char.notify_value_async(_buffer(data))
        except Exception as e:
            log.warning("WinRT notify: %s", e)
            return
        for r in results or ():
            status = getattr(r, "status", None)
            if status is not None and int(status) != 0:   # GattCommunicationStatus.SUCCESS
                log.warning("WinRT notify to %s: status %s, protocol error %s",
                            getattr(getattr(r, "subscribed_client", None), "session", None) and
                            r.subscribed_client.session.device_id.id, status, getattr(r, "protocol_error", None))

    async def stop(self) -> None:
        for obj, kind, token in self._tokens:
            try:
                getattr(obj, f"remove_{'write_requested' if kind == 'write' else 'read_requested' if kind == 'read' else 'subscribed_clients_changed'}")(token)
            except Exception:
                pass
        self._tokens.clear()
        if self.provider is not None:
            try:
                self.provider.stop_advertising()
            except Exception as e:
                log.debug("WinRT stop: %s", e)
        self.provider = self.status_char = None
