"""Virtual steering device for Zwift: an Elite Sterzo Smart offered over DIRCON.

Found on 2026-11-25 (Tretlager branch sim-rider, Zwift under Wine): Zwift pairs a Sterzo that it
finds over Wahoo Direct Connect (mDNS `_wahoo-fitness-tnp._tcp`), subscribes to the angle
characteristic and steers with it. It wrote no handshake; the answers below (protocol as in
vincent290587/steering_challenge, 2023) are only there in case a newer Zwift asks.

The watch sends lane changes (actions.LANE); each one becomes a short, smooth steering pulse
(`angle` degrees for `duration` seconds, then straight again). The angle is sent ten times a
second while Zwift listens, as the real plate does.
"""

from __future__ import annotations

import asyncio
import logging
import struct
import time

from . import dircon

log = logging.getLogger(__name__)

SERVICE_TYPE = "_wahoo-fitness-tnp._tcp"
STERZO = "347b0001-7635-408b-8918-8ff3949ce592"
ANGLE = "347b0030-7635-408b-8918-8ff3949ce592"   # notify: float32 little-endian, degrees
RX = "347b0031-7635-408b-8918-8ff3949ce592"      # write: commands from Zwift
TX = "347b0032-7635-408b-8918-8ff3949ce592"      # indicate/read: answers to Zwift
MAC = "D6:3A:7E:21:5C:91"
NAME = "STERZO SMART 5C91"
HZ = 10.0
SMOOTH = 0.12          # s, time constant of the angle (no jumps)
MAX_ANGLE = 35.0


def sterzo_hash(seed: int) -> int:
    """Answer to a 32-bit seed (vincent290587/steering_challenge, ble_cus.c `hashed`)."""
    seed &= 0xFFFFFFFF
    n = (seed % 11) & 0x0F
    rot = ((seed << n) | (seed >> (32 - n))) & 0xFFFFFFFF if n else seed
    return ((seed + 0x16FA5717) & 0xFFFFFFFF) ^ rot


class _Backend:
    """GATT values of the Sterzo for the DIRCON server."""

    def __init__(self, server: "SteeringServer") -> None:
        self.owner = server
        self.tx = bytes([0x03, 0x10, 0xFF, 0xFF])

    def services(self) -> list[dircon.Service]:
        return [dircon.Service(STERZO, [
            dircon.Characteristic(ANGLE, dircon.PROP_NOTIFY),
            dircon.Characteristic(RX, dircon.PROP_WRITE),
            dircon.Characteristic(TX, dircon.PROP_INDICATE | dircon.PROP_READ),
        ])]

    async def read(self, char_uuid: str) -> bytes:
        return self.tx if char_uuid == TX else b""

    async def write(self, char_uuid: str, data: bytes) -> bytes | None:
        log.info("steering: Zwift writes %s to %s", data.hex(" "), char_uuid[4:8])
        if char_uuid != RX or len(data) < 2 or data[0] != 0x03:
            return None
        cmd = data[1]
        if cmd == 0x10:
            answer = bytes([0x03, 0x10, 0x12, 0x34])
        elif cmd == 0x11:
            answer = bytes([0x03, 0x11, 0xFF, 0xFF])
        elif cmd == 0x12 and len(data) >= 6:
            answer = bytes([0x03, 0x12]) + struct.pack("<I", sterzo_hash(struct.unpack_from("<I", data, 2)[0]))
        elif cmd == 0x13:
            answer = bytes([0x03, 0x13, 0xFF])
        else:
            return None
        self.tx = answer
        asyncio.get_running_loop().call_later(0.02, self.owner.server.notify, TX, answer)
        return None

    async def set_notify(self, char_uuid: str, enabled: bool) -> None:
        if enabled:
            log.info("steering: Zwift listens to %s", char_uuid[4:8])


class SteeringServer:
    def __init__(self, port: int, announcer=None, angle: float = 12.0, duration: float = 0.45) -> None:
        self.port = port
        self.announcer = announcer
        self.angle = max(1.0, min(MAX_ANGLE, angle))
        self.duration = max(0.1, duration)
        self.server = dircon.Server(_Backend(self), port=port)
        self._task: asyncio.Task | None = None
        self._current = 0.0
        self._direction = 0
        self._until = 0.0

    async def start(self) -> None:
        await self.server.start()
        self._task = asyncio.get_running_loop().create_task(self._loop(), name="steering")
        if self.announcer:
            txt = {"ble-service-uuids": STERZO.upper(), "mac-address": MAC,
                   "serial-number": MAC.replace(":", "")}
            try:
                await self.announcer.publish(NAME, SERVICE_TYPE, self.port, txt)
            except Exception as e:  # Zwift on the same computer still finds nothing; log and go on
                log.warning("steering: mDNS announcement failed: %s", e)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            self._task = None
        if self.announcer:
            try:
                await self.announcer.withdraw()
            except Exception:
                pass
        await self.server.stop()

    @property
    def paired(self) -> bool:
        """Zwift is connected and listens to the angle."""
        return ANGLE in self.server.subscribed()

    def lane(self, direction: int) -> bool:
        """Start a lane change: -1 left, +1 right. Again in the same direction extends it,
        the other direction replaces it. False if Zwift does not listen (not paired)."""
        now = time.monotonic()
        if direction == self._direction and now < self._until:
            self._until += self.duration
        else:
            self._direction = -1 if direction < 0 else 1
            self._until = now + self.duration
        return self.paired

    def target(self, now: float) -> float:
        return self._direction * self.angle if now < self._until else 0.0

    def step(self, dt: float, now: float) -> float:
        t = self.target(now)
        self._current += (t - self._current) * min(1.0, dt / SMOOTH)
        if abs(self._current) < 0.05 and t == 0.0:
            self._current = 0.0
        return self._current

    async def _loop(self) -> None:
        last = time.monotonic()
        while True:
            await asyncio.sleep(1.0 / HZ)
            now = time.monotonic()
            angle = self.step(now - last, now)
            last = now
            if self.server.client_count:
                self.server.notify(ANGLE, struct.pack("<f", angle))
