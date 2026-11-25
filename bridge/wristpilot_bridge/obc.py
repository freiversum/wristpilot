"""OpenBikeControl output (mDNS + TCP, protocol v1, openbikecontrol.org).

The bridge acts as an OBC *device*: it listens on a TCP port, announces itself as
`_openbikecontrol._tcp`, and sends a button press and release for every command from the watch.
Trainer apps (MyWhoosh, TrainingPeaks Virtual, Incyclist …) connect as clients. Zwift does not
speak OBC; for Zwift the keyboard output is used.

Messages device -> app:  [0x01, button, state] (one button per message), [0x02, battery, connected]
Messages app -> device:  [0x03, pattern, duration, intensity] (haptic), [0x04, …] (app info)
"""

from __future__ import annotations

import asyncio
import logging
import socket
import uuid
from dataclasses import dataclass, field
from typing import Callable

log = logging.getLogger(__name__)

OBC_SERVICE_UUID = "d273f680-d548-419d-b9d1-fa0472345229"
SERVICE_TYPE = "_openbikecontrol._tcp"
MSG_BUTTON = 0x01
MSG_STATUS = 0x02
MSG_HAPTIC = 0x03
MSG_APP_INFO = 0x04
STATUS_INTERVAL = 30.0
PRESS_GAP = 0.05


@dataclass
class AppInfo:
    app_id: str = ""
    version: str = ""
    buttons: list[int] = field(default_factory=list)  # empty = all buttons supported


def parse_app_info(data: bytes) -> tuple[AppInfo, int] | None:
    """App info message at the start of `data`; returns (info, bytes used) or None if incomplete."""
    if len(data) < 3 or data[0] != MSG_APP_INFO:
        return None
    pos = 2
    n = data[pos]; pos += 1
    if len(data) < pos + n + 1:
        return None
    app_id = data[pos:pos + n].decode("utf-8", "replace"); pos += n
    n = data[pos]; pos += 1
    if len(data) < pos + n + 1:
        return None
    version = data[pos:pos + n].decode("utf-8", "replace"); pos += n
    n = data[pos]; pos += 1
    if len(data) < pos + n:
        return None
    return AppInfo(app_id, version, list(data[pos:pos + n])), pos + n


class _Client:
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.reader, self.writer = reader, writer
        self.info = AppInfo()
        self.peer = writer.get_extra_info("peername")

    def supports(self, button: int) -> bool:
        return not self.info.buttons or button in self.info.buttons


class ObcServer:
    def __init__(self, port: int, name: str = "Wristpilot", announcer=None,
                 on_haptic: Callable[[int], None] | None = None) -> None:
        self.port = port
        self.name = name
        self.announcer = announcer          # announce.Announcer or None
        self.on_haptic = on_haptic
        self.clients: list[_Client] = []
        self.watch_connected: Callable[[], bool] = lambda: False
        self.device_id = f"{uuid.getnode():012x}"
        self._server: asyncio.base_events.Server | None = None
        self._status_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._server = await asyncio.start_server(self._serve, host="0.0.0.0", port=self.port,
                                                  family=socket.AF_INET)
        self.port = self._server.sockets[0].getsockname()[1]
        self._status_task = asyncio.create_task(self._status_loop())
        if self.announcer:
            txt = {"version": "1", "id": self.device_id, "name": self.name,
                   "service-uuids": OBC_SERVICE_UUID, "manufacturer": "Wristpilot", "model": "Garmin watch remote"}
            try:
                await self.announcer.publish(self.name, SERVICE_TYPE, self.port, txt)
            except Exception as e:
                log.warning("OBC: mDNS announcement failed: %s", e)
        log.info("OBC: listening on port %d", self.port)

    async def stop(self) -> None:
        if self._status_task:
            self._status_task.cancel()
        if self.announcer:
            try:
                await self.announcer.withdraw()
            except Exception as e:
                log.debug("OBC: withdraw: %s", e)
        for c in list(self.clients):
            c.writer.close()
        self.clients.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    async def button(self, button: int, value: int) -> bool:
        """Press and release `button` on every connected app; True if at least one app got it."""
        targets = [c for c in self.clients if c.supports(button)]
        if not targets:
            return False
        state = value if value > 1 else 0x01
        await self._send(targets, bytes((MSG_BUTTON, button, state)))
        await asyncio.sleep(PRESS_GAP)
        await self._send(targets, bytes((MSG_BUTTON, button, 0x00)))
        return True

    def status_message(self) -> bytes:
        return bytes((MSG_STATUS, 0xFF, 0x01 if self.watch_connected() else 0x00))

    async def _send(self, targets: list[_Client], data: bytes) -> None:
        for c in targets:
            try:
                c.writer.write(data)
                await c.writer.drain()
            except (ConnectionError, OSError):
                self._drop(c)

    def _drop(self, c: _Client) -> None:
        if c in self.clients:
            self.clients.remove(c)
            log.info("OBC: %s disconnected", c.info.app_id or c.peer)
        c.writer.close()

    async def _status_loop(self) -> None:
        while True:
            await asyncio.sleep(STATUS_INTERVAL)
            await self._send(list(self.clients), self.status_message())

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        c = _Client(reader, writer)
        self.clients.append(c)
        log.info("OBC: app connected from %s", c.peer)
        await self._send([c], self.status_message())
        buf = b""
        try:
            while True:
                chunk = await reader.read(256)
                if not chunk:
                    break
                buf += chunk
                buf = self._consume(c, buf)
        except (ConnectionError, OSError):
            pass
        finally:
            self._drop(c)

    def _consume(self, c: _Client, buf: bytes) -> bytes:
        while buf:
            kind = buf[0]
            if kind == MSG_HAPTIC:
                if len(buf) < 4:
                    return buf
                if self.on_haptic:
                    self.on_haptic(buf[1])
                buf = buf[4:]
            elif kind == MSG_APP_INFO:
                parsed = parse_app_info(buf)
                if parsed is None:
                    return buf if len(buf) < 80 else b""  # incomplete, or garbage: drop
                c.info, used = parsed
                log.info("OBC: app %s %s", c.info.app_id, c.info.version)
                buf = buf[used:]
            else:
                log.debug("OBC: unexpected byte %#04x from %s", kind, c.peer)
                buf = buf[1:]
        return buf
