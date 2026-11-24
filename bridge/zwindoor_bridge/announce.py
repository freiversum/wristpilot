"""mDNS announcement for the OpenBikeControl output.

Linux: through avahi-daemon over the system D-Bus (no second mDNS responder next to Avahi;
works inside the Tretlager Flatpak, which may talk to org.freedesktop.Avahi).
Windows: python-zeroconf.
"""

from __future__ import annotations

import logging
import socket
import sys

log = logging.getLogger(__name__)


class Announcer:
    async def publish(self, name: str, service_type: str, port: int, txt: dict[str, str]) -> None:
        raise NotImplementedError

    async def withdraw(self) -> None:
        raise NotImplementedError


class AvahiAnnouncer(Announcer):
    AVAHI = "org.freedesktop.Avahi"

    def __init__(self) -> None:
        self._bus = None
        self._group = None

    async def _call(self, path, interface, member, signature="", body=None):
        from dbus_fast import BusType, Message, MessageType
        from dbus_fast.aio import MessageBus
        if self._bus is None:
            self._bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
        reply = await self._bus.call(Message(destination=self.AVAHI, path=path, interface=interface,
                                             member=member, signature=signature, body=body or []))
        if reply.message_type == MessageType.ERROR:
            raise RuntimeError(f"avahi {member}: {reply.error_name} {reply.body}")
        return reply.body

    async def publish(self, name, service_type, port, txt):
        await self.withdraw()
        (group,) = await self._call("/", f"{self.AVAHI}.Server", "EntryGroupNew")
        records = [f"{k}={v}".encode() for k, v in txt.items()]
        # interface any, IPv4 only (see Tretlager's mdns.py: link-local AAAA confuses clients)
        await self._call(group, f"{self.AVAHI}.EntryGroup", "AddService", "iiussssqaay",
                         [-1, 0, 0, name, service_type, "", "", port, records])
        await self._call(group, f"{self.AVAHI}.EntryGroup", "Commit")
        self._group = group
        log.info("mDNS: %s %s on port %d", name, service_type, port)

    async def withdraw(self):
        if self._group:
            try:
                await self._call(self._group, f"{self.AVAHI}.EntryGroup", "Free")
            finally:
                self._group = None


class ZeroconfAnnouncer(Announcer):
    def __init__(self) -> None:
        self._zc = None
        self._info = None

    async def publish(self, name, service_type, port, txt):
        from zeroconf import ServiceInfo
        from zeroconf.asyncio import AsyncZeroconf
        await self.withdraw()
        self._zc = AsyncZeroconf()
        host = socket.gethostname()
        addresses = {a[4][0] for a in socket.getaddrinfo(host, None, socket.AF_INET)}
        addresses.discard("127.0.0.1")
        full_type = f"{service_type}.local."
        self._info = ServiceInfo(full_type, f"{name}.{full_type}", port=port, properties=txt,
                                 server=f"{host}.local.", addresses=[socket.inet_aton(a) for a in addresses])
        await self._zc.async_register_service(self._info)
        log.info("mDNS: %s %s on port %d (%s)", name, service_type, port, ", ".join(sorted(addresses)))

    async def withdraw(self):
        if self._zc:
            if self._info:
                await self._zc.async_unregister_service(self._info)
            await self._zc.async_close()
        self._zc = self._info = None


def default_announcer() -> Announcer:
    return ZeroconfAnnouncer() if sys.platform == "win32" else AvahiAnnouncer()
