"""GATT server on a dedicated Bluetooth adapter through Bumble (own BLE host stack in Python).

Why: the operating system's Bluetooth stack on Windows advertises GATT servers with a resolvable
private address, and Garmin watches refuse to connect to private addresses of devices they are
not bonded with (Connect IQ has no bonding API). Bumble talks HCI to the adapter directly and
advertises with the adapter's public address, like BlueZ does on Linux.

The adapter is used exclusively: on Windows it needs the WinUSB driver (Zadig), on Linux the
"hci-socket:N" transport needs the adapter powered off in BlueZ and CAP_NET_ADMIN. Realtek and
Intel adapters load their firmware through Bumble's drivers.

Transport examples: "usb:0" (first USB Bluetooth adapter with WinUSB/libusb), "usb:2357:0604",
"hci-socket:1".
"""

from __future__ import annotations

import asyncio
import logging
import os
import pathlib

from .. import protocol
from . import Peripheral, PeripheralError

log = logging.getLogger(__name__)

DEFAULT_TRANSPORT = "usb:0"
FIRMWARE_DIR = pathlib.Path(__file__).resolve().parent.parent / "firmware" / "realtek"


def use_bundled_firmware() -> None:
    """Point Bumble's Realtek driver at the firmware packed into the .exe (tools/fetch_rtk_firmware.py),
    unless the user set BUMBLE_RTK_FIRMWARE_DIR. Without bundled files Bumble searches its own places."""
    if "BUMBLE_RTK_FIRMWARE_DIR" not in os.environ and (FIRMWARE_DIR / "rtl8761bu_fw.bin").is_file():
        os.environ["BUMBLE_RTK_FIRMWARE_DIR"] = str(FIRMWARE_DIR)


def advertising_data(name: str) -> bytes:
    """Flags + complete 128-bit service UUID + name, all in the advertising packet (31 bytes max):
    the fēnix ignores scan responses."""
    from bumble.core import UUID, AdvertisingData
    uuid = bytes(UUID(protocol.SERVICE_UUID).to_bytes(force_128=True))
    fields = [
        (AdvertisingData.FLAGS, bytes([0x06])),   # LE General Discoverable, BR/EDR not supported
        (AdvertisingData.COMPLETE_LIST_OF_128_BIT_SERVICE_CLASS_UUIDS, uuid),
    ]
    used = sum(2 + len(v) for _, v in fields)
    raw = name.encode()[: max(0, 31 - used - 2)]
    if raw:
        fields.append((AdvertisingData.COMPLETE_LOCAL_NAME if raw == name.encode()
                       else AdvertisingData.SHORTENED_LOCAL_NAME, raw))
    return bytes(AdvertisingData(fields))


class BumblePeripheral(Peripheral):
    name = "bumble"

    def __init__(self, on_write, info, local_name="ZWindoor", transport: str = "") -> None:
        super().__init__(on_write, info, local_name)
        self.transport_spec = transport or DEFAULT_TRANSPORT
        self.transport = None
        self.device = None
        self.status_char = None
        self.status_value = bytes((protocol.MSG_STATE, 0))
        self.loop: asyncio.AbstractEventLoop | None = None

    async def start(self) -> None:
        try:
            from bumble.device import Device
            from bumble.gatt import Characteristic, CharacteristicValue, Service
            from bumble.hci import Address, OwnAddressType
            from bumble.transport import open_transport
        except ImportError as e:
            raise PeripheralError(f"the Python package 'bumble' cannot be loaded ({e})") from e
        self.loop = asyncio.get_running_loop()
        use_bundled_firmware()
        try:
            self.transport = await open_transport(self.transport_spec)
        except Exception as e:  # no adapter, wrong driver, adapter in use …
            log.warning("Bumble: cannot open %s: %s", self.transport_spec, e)
            if self.transport_spec.startswith("usb"):
                raise PeripheralError("no USB Bluetooth adapter with the WinUSB driver found") from e
            raise PeripheralError(f"cannot open the Bluetooth adapter {self.transport_spec}") from e

        P = Characteristic.Properties
        command = Characteristic(protocol.COMMAND_UUID, P.WRITE | P.WRITE_WITHOUT_RESPONSE,
                                 Characteristic.WRITEABLE, CharacteristicValue(write=self._write))
        self.status_char = Characteristic(protocol.STATUS_UUID, P.READ | P.NOTIFY,
                                          Characteristic.READABLE, CharacteristicValue(read=self._read))
        info = Characteristic(protocol.INFO_UUID, P.READ, Characteristic.READABLE, bytes(self.info))
        self.status_char.on("subscription", self._on_subscription)

        try:
            # The random address is required by the API but not used: we advertise with the public one.
            self.device = Device.with_hci(self.local_name, Address("F0:F1:F2:F3:F4:F5"),
                                          self.transport.source, self.transport.sink)
            self.device.add_service(Service(protocol.SERVICE_UUID, [command, self.status_char, info]))
            self.device.on("connection", self._on_connection)
            await self.device.power_on()
            await self.device.start_advertising(own_address_type=OwnAddressType.PUBLIC,
                                                advertising_data=advertising_data(self.local_name),
                                                auto_restart=True)
        except Exception as e:
            await self.stop()
            raise PeripheralError(f"could not start the GATT server on {self.transport_spec!r}: {e}") from e
        log.info("Bumble: GATT service on %s (%s), advertising as %r", self.transport_spec,
                 self.device.public_address, self.local_name)

    # --- Bumble callbacks (on the loop) ---

    def _on_connection(self, connection) -> None:
        log.info("Bumble: connection from %s", connection.peer_address)
        connection.on("disconnection", lambda reason: log.info("Bumble: disconnected (%s)", reason))

    def _on_subscription(self, _connection, notify_enabled, _indicate_enabled=False) -> None:
        self.subscribed = bool(notify_enabled)
        log.info("watch %s notifications", "subscribed to" if self.subscribed else "unsubscribed from")

    def _read(self, _connection) -> bytes:
        return self.status_value

    def _write(self, _connection, value) -> None:
        self.loop.create_task(self._handle(bytes(value)))

    async def _handle(self, data: bytes) -> None:
        reply = await self.on_write(data)
        if reply:
            await self.notify(reply)

    async def notify(self, data: bytes) -> None:
        self.status_value = data
        if self.device is None or self.status_char is None:
            return
        try:
            await self.device.notify_subscribers(self.status_char, data)
        except Exception as e:
            log.warning("Bumble notify: %s", e)

    async def stop(self) -> None:
        if self.device is not None:
            try:
                await self.device.stop_advertising()
                await self.device.power_off()
            except Exception as e:
                log.debug("Bumble stop: %s", e)
            self.device = None
        if self.transport is not None:
            try:
                await self.transport.close()
            except Exception as e:
                log.debug("Bumble close: %s", e)
            self.transport = None
