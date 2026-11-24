"""BlueZ GATT server and LE advertisement over D-Bus (dbus-fast), for Linux and Tretlager.

Registers one GATT application (GattManager1.RegisterApplication) and one advertisement
(LEAdvertisingManager1.RegisterAdvertisement) on the adapter. Works next to Tretlager's sensor
bridge, which uses the same adapter in the central role.
"""

# No `from __future__ import annotations`: dbus-fast reads the D-Bus signatures from annotations.
import asyncio
import logging

from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus
from dbus_fast.service import PropertyAccess, ServiceInterface, dbus_property, method

from .. import protocol
from . import Peripheral, PeripheralError

log = logging.getLogger(__name__)

BLUEZ = "org.bluez"
APP_PATH = "/de/linuxundich/zwindoor"
SERVICE_PATH = APP_PATH + "/service0"
ADV_PATH = APP_PATH + "/advertisement0"


class _Service(ServiceInterface):
    def __init__(self) -> None:
        super().__init__("org.bluez.GattService1")

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":  # noqa: N802
        return protocol.SERVICE_UUID

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> "b":  # noqa: N802
        return True


class _Characteristic(ServiceInterface):
    def __init__(self, owner: "BluezPeripheral", uuid: str, flags: list, value: bytes = b"") -> None:
        super().__init__("org.bluez.GattCharacteristic1")
        self.owner, self.uuid, self.flags, self.value = owner, uuid, flags, value

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> "s":  # noqa: N802
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> "o":  # noqa: N802
        return SERVICE_PATH

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> "as":  # noqa: N802
        return self.flags

    @dbus_property(access=PropertyAccess.READ)
    def Value(self) -> "ay":  # noqa: N802
        return self.value

    @method()
    def ReadValue(self, options: "a{sv}") -> "ay":  # noqa: N802
        return self.value

    @method()
    async def WriteValue(self, value: "ay", options: "a{sv}"):  # noqa: N802
        if self.uuid == protocol.COMMAND_UUID:
            await self.owner._written(bytes(value))

    @method()
    def StartNotify(self):  # noqa: N802
        self.owner._subscription(True)

    @method()
    def StopNotify(self):  # noqa: N802
        self.owner._subscription(False)

    def set(self, value: bytes) -> None:
        self.value = value
        self.emit_properties_changed({"Value": value})


class _Advertisement(ServiceInterface):
    def __init__(self, local_name: str) -> None:
        super().__init__("org.bluez.LEAdvertisement1")
        self.local_name = local_name

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> "s":  # noqa: N802
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> "as":  # noqa: N802
        return [protocol.SERVICE_UUID]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> "s":  # noqa: N802
        return self.local_name

    @dbus_property(access=PropertyAccess.READ)
    def Discoverable(self) -> "b":  # noqa: N802
        return True  # flags 0x06: Connect IQ ignores devices without "LE General Discoverable"

    @method()
    def Release(self):  # noqa: N802
        log.info("BlueZ released the advertisement")


class _ObjectManager(ServiceInterface):
    def __init__(self, owner: "BluezPeripheral") -> None:
        super().__init__("org.freedesktop.DBus.ObjectManager")
        self.owner = owner

    @method()
    def GetManagedObjects(self) -> "a{oa{sa{sv}}}":  # noqa: N802
        objs = {SERVICE_PATH: {"org.bluez.GattService1": {
            "UUID": Variant("s", protocol.SERVICE_UUID), "Primary": Variant("b", True)}}}
        for path, ch in self.owner.chars.items():
            objs[path] = {"org.bluez.GattCharacteristic1": {
                "UUID": Variant("s", ch.uuid), "Service": Variant("o", SERVICE_PATH),
                "Flags": Variant("as", ch.flags)}}
        return objs


class BluezPeripheral(Peripheral):
    name = "bluez"

    def __init__(self, on_write, info, local_name="Zwindoor", adapter: str = "") -> None:
        super().__init__(on_write, info, local_name)
        self.adapter = adapter
        self.bus: MessageBus | None = None
        self.adapter_path = ""
        self.command = _Characteristic(self, protocol.COMMAND_UUID, ["write", "write-without-response"])
        self.status = _Characteristic(self, protocol.STATUS_UUID, ["read", "notify"])
        self.info_char = _Characteristic(self, protocol.INFO_UUID, ["read"], info)
        self.chars = {SERVICE_PATH + "/char0": self.command, SERVICE_PATH + "/char1": self.status,
                      SERVICE_PATH + "/char2": self.info_char}
        self.advertised = False
        self.registered = False

    async def _bluez(self, path, interface, member, signature="", body=None):
        reply = await self.bus.call(Message(destination=BLUEZ, path=path, interface=interface,
                                            member=member, signature=signature, body=body or []))
        if reply.message_type == MessageType.ERROR:
            raise PeripheralError(f"{member}: {reply.error_name} {' '.join(map(str, reply.body))}")
        return reply.body

    async def _find_adapter(self) -> str:
        (objs,) = await self._bluez("/", "org.freedesktop.DBus.ObjectManager", "GetManagedObjects")
        adapters = sorted(p for p, ifs in objs.items()
                          if "org.bluez.GattManager1" in ifs and "org.bluez.LEAdvertisingManager1" in ifs)
        if not adapters:
            raise PeripheralError("no Bluetooth adapter with GATT server and advertising support")
        wanted = f"/org/bluez/{self.adapter}" if self.adapter else ""
        return wanted if wanted in adapters else adapters[0]

    async def start(self) -> None:
        self.bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        self.adapter_path = await self._find_adapter()
        self.bus.export(APP_PATH, _ObjectManager(self))
        self.bus.export(SERVICE_PATH, _Service())
        for path, ch in self.chars.items():
            self.bus.export(path, ch)
        await self._bluez(self.adapter_path, "org.bluez.GattManager1", "RegisterApplication", "oa{sv}",
                          [APP_PATH, {}])
        self.registered = True
        for name in (self.local_name, ""):  # name + 128-bit UUID can exceed 31 bytes on some stacks
            adv = _Advertisement(name)
            self.bus.export(ADV_PATH, adv)
            try:
                await self._bluez(self.adapter_path, "org.bluez.LEAdvertisingManager1", "RegisterAdvertisement",
                                  "oa{sv}", [ADV_PATH, {}])
                self.advertised = True
                break
            except PeripheralError as e:
                self.bus.unexport(ADV_PATH)
                if not name:
                    raise
                log.info("advertisement with name refused (%s), retrying without", e)
        log.info("BlueZ: GATT service on %s, advertising as %r", self.adapter_path, self.local_name)

    async def _written(self, data: bytes) -> None:
        reply = await self.on_write(data)
        if reply:
            self.status.set(reply)

    def _subscription(self, on: bool) -> None:
        self.subscribed = on
        log.info("watch %s notifications", "subscribed to" if on else "unsubscribed from")

    async def notify(self, data: bytes) -> None:
        self.status.set(data)

    async def stop(self) -> None:
        if not self.bus:
            return
        for registered, iface, member, path in (
                (self.advertised, "org.bluez.LEAdvertisingManager1", "UnregisterAdvertisement", ADV_PATH),
                (self.registered, "org.bluez.GattManager1", "UnregisterApplication", APP_PATH)):
            if registered:
                try:
                    await self._bluez(self.adapter_path, iface, member, "o", [path])
                except Exception as e:
                    log.debug("%s: %s", member, e)
        self.bus.disconnect()
        self.bus = None
        self.advertised = self.registered = False
        await asyncio.sleep(0)
