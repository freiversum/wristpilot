"""Zwift Companion link: the bridge poses as the phone of the Zwift Companion app.

The bridge listens on TCP and registers that address with Zwift's relay; the running game then
connects and streams its state (power-up, turn choices at the next junction, social actions). The
bridge sends commands the same way – turns including straight on, U-turn, Ride On, power-up and
emotes – without keyboard and without window focus.

Plain mode as used by Sauce for Zwift: every message is a 4-byte big-endian length plus a
protobuf message (GameToCompanion from the game, CompanionToGame to the game). Field numbers
from Sauce's zwift.proto (GPL-3.0) and RoadCaptain (Artistic 2.0); see docs/architecture.md.

Only one phone per Zwift account: registering replaces the real Companion app. Opt-in; using the
undocumented relay contradicts Zwift's terms of service.
"""

from __future__ import annotations

import asyncio
import json
import logging
import socket
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import actions, pb, zwiftapi

log = logging.getLogger(__name__)

REGISTER_RETRY = 60.0      # re-register while no game is connected
HEARTBEAT = 1.0            # the real Companion sends {athleteId, seqno} about once a second
JUNCTION_TTL = 30.0        # forget turn choices that were not refreshed
MAX_FRAME = 1 << 20

# GameToCompanion
G_ATHLETE, G_COMMANDS = 3, 11
# GameToCompanionCommand
GC_TYPE, GC_POWERUP_ID, GC_SUBCOMMAND, GC_POSITION, GC_BUTTON, GC_HIDE, GC_SOCIAL, GC_PACKET = 2, 3, 8, 9, 10, 13, 16, 21
CLEAR_POWER_UP, SET_POWER_UP, ACTIVATE_POWER_UP, CUSTOMIZE_ACTION_BUTTON, SOCIAL_PLAYER_ACTION, PACKET = 1, 2, 3, 4, 6, 13
# GamePacket
P_TYPE, P_SESSION, P_INTERSECTION = 1, 4, 7
GAME_SESSION_INFO, CLIENT_INFO, INTERSECTION_AHEAD, CLIENT_ACTION = 3, 4, 6, 15
# CompanionToGameCommand types
CMD_CAMERA, CMD_ELBOW, CMD_WAVE, CMD_RIDE_ON, CMD_BELL, CMD_HAMMER, CMD_TOAST, CMD_NICE = 1, 4, 5, 6, 7, 8, 9, 10
CMD_SCREENSHOT, CMD_POWERUP, CMD_CUSTOM, CMD_U_TURN, CMD_PAIRING, CMD_PACKET, CMD_VIDEO = 17, 21, 22, 23, 28, 29, 31
SUB_LEFT, SUB_STRAIGHT, SUB_RIGHT, SUB_HUD_ON, SUB_HUD_OFF = 1010, 1011, 1012, 1080, 1081
START_CONNECTED_SESSION, ACTION_BAR_OPEN = 5, 10
RIDE_ON_SOCIAL = 2

# Zwift POWERUP_TYPE (powerUpId - 1) -> Wristpilot power-up id (watch: Protocol.PU_*)
PU_NONE, PU_UNKNOWN = 0, 10
POWERUPS = {0: 1, 1: 2, 2: 9, 3: 9, 4: 5, 5: 3, 6: 4, 7: 6, 8: 7}  # feather, draft, XP, burrito, aero, ghost …

# Game flags sent to the watch (protocol.MSG_GAME)
F_LINKED, F_JUNCTION, F_LEFT, F_STRAIGHT, F_RIGHT, F_POWERUP = 0x01, 0x02, 0x04, 0x08, 0x10, 0x20
TURN_BITS = {SUB_LEFT: F_LEFT, SUB_STRAIGHT: F_STRAIGHT, SUB_RIGHT: F_RIGHT}


@dataclass
class GameState:
    linked: bool = False
    turns: dict[int, float] = field(default_factory=dict)  # F_LEFT/… -> time last offered
    powerup: int = PU_NONE
    ride_ons: int = 0
    in_game: bool = False

    def flags(self, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        if not self.linked:
            return 0
        f = F_LINKED
        live = [bit for bit, t in self.turns.items() if now - t < JUNCTION_TTL]
        if live:
            f |= F_JUNCTION
            for bit in live:
                f |= bit
        if self.powerup != PU_NONE:
            f |= F_POWERUP
        return f

    def message(self, now: float | None = None) -> bytes:
        n = min(self.ride_ons, 0xFFFF)
        return bytes((0x04, self.flags(now), self.powerup & 0xFF, n & 0xFF, n >> 8))


def command_for(action: int, value: int, hud_on: bool = True) -> dict | None:
    """CompanionToGameCommand fields for a Wristpilot action, or None if the game has no command."""
    simple = {actions.U_TURN: CMD_U_TURN, actions.POWERUP: CMD_POWERUP, actions.BELL: CMD_BELL}
    if action in simple:
        t = simple[action]
        return {2: t, 10: t}  # old games expect the type repeated in subCommand
    if action in (actions.STEER_LEFT, actions.STEER_RIGHT, actions.UP):
        sub = {actions.STEER_LEFT: SUB_LEFT, actions.STEER_RIGHT: SUB_RIGHT, actions.UP: SUB_STRAIGHT}[action]
        return {2: CMD_CUSTOM, 10: sub}
    if action == actions.EMOTE:
        t = {actions.EMOTE_RIDE_ON: CMD_RIDE_ON, actions.EMOTE_ELBOW: CMD_ELBOW, actions.EMOTE_WAVE: CMD_WAVE,
             actions.EMOTE_HAMMER: CMD_HAMMER, actions.EMOTE_NICE: CMD_NICE, actions.EMOTE_TOAST: CMD_TOAST}.get(value)
        return {2: t, 10: t} if t else None
    if action == actions.SCREENSHOT:
        t = CMD_VIDEO if value == actions.SHOT_VIDEO else CMD_SCREENSHOT
        return {2: t, 10: t}
    if action == actions.CAMERA and value == actions.CAMERA_NEXT:
        return {2: CMD_CAMERA, 10: CMD_CAMERA}
    if action == actions.HUD:
        return {2: CMD_CUSTOM, 10: SUB_HUD_OFF if hud_on else SUB_HUD_ON}
    return None  # workout keys, direct camera views: keyboard only


def frame(payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + payload


class CompanionLink:
    """Owns the TCP server and the game connection. All methods run on the bridge's loop."""

    def __init__(self, token_provider: Callable[[], str | None], port: int = 21587,
                 address: str | None = None, on_change: Callable[[], None] | None = None,
                 api=zwiftapi, capture: Path | None = None) -> None:
        self.token_provider = token_provider   # blocking; returns a valid access token or None
        self.port = port
        self.address = address
        self.on_change = on_change or (lambda: None)
        self.api = api
        self.state = GameState()
        self.athlete_id = 0
        self.error = ""
        self.registered = False
        self.hud_on = True
        self._server: asyncio.base_events.Server | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._tasks: list[asyncio.Task] = []
        self._seqno = 0       # outer CompanionToGame.seqno
        self._cmd_seqno = 0   # per-command seqno
        self.capture = capture  # JSON Lines file with every frame (tools/companion_dump.py reads it)

    # --- Lifecycle ---

    async def start(self) -> None:
        self.address = self.address or zwiftapi.lan_address()
        try:
            self._server = await asyncio.start_server(self._serve, host="0.0.0.0", port=self.port,
                                                      family=socket.AF_INET)
        except OSError:  # port taken (e.g. by another tool): any free port, the relay tells the game
            self._server = await asyncio.start_server(self._serve, host="0.0.0.0", port=0, family=socket.AF_INET)
        self.port = self._server.sockets[0].getsockname()[1]
        log.info("Companion: listening on %s:%d", self.address, self.port)
        self._tasks.append(asyncio.create_task(self._register_loop()))

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        self._tasks.clear()
        if self._writer:
            self._writer.close()
            self._writer = None
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        self._set_linked(False)

    @property
    def linked(self) -> bool:
        return self.state.linked

    async def _register_loop(self) -> None:
        loop = asyncio.get_running_loop()
        while True:
            if not self.linked:
                try:
                    token = await loop.run_in_executor(None, self.token_provider)
                    if not token:
                        self._fail("no Zwift sign-in")
                    else:
                        if not self.athlete_id:
                            self.athlete_id = await loop.run_in_executor(None, self.api.athlete_id, token)
                        await loop.run_in_executor(None, self.api.register_phone, token, self.address, self.port)
                        if not self.registered or self.error:
                            log.info("Companion: registered %s:%d for athlete %d", self.address, self.port,
                                     self.athlete_id)
                        self.registered, self.error = True, ""
                        self.on_change()
                except zwiftapi.ZwiftApiError as e:
                    self._fail(str(e))
            await asyncio.sleep(REGISTER_RETRY)

    def _fail(self, text: str) -> None:
        if text != self.error:
            log.warning("Companion: %s", text)
        self.error, self.registered = text, False
        self.on_change()

    # --- Game connection ---

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        if self._writer:  # a newer connection replaces the old one (game reconnect)
            self._writer.close()
        self._writer = writer
        sock = writer.get_extra_info("socket")
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        log.info("Companion: game connected from %s", writer.get_extra_info("peername"))
        self._seqno = self._cmd_seqno = 0
        self.state = GameState(linked=True)
        self.on_change()
        heartbeat = asyncio.create_task(self._heartbeat(writer))
        try:
            await self._pair()
            while True:
                size = struct.unpack(">I", await reader.readexactly(4))[0]
                if size > MAX_FRAME:
                    raise ConnectionError(f"frame of {size} bytes")
                data = await reader.readexactly(size)
                self._capture("game", data)
                self.handle_game_message(data)
        except (asyncio.IncompleteReadError, ConnectionError, OSError, pb.DecodeError) as e:
            log.info("Companion: game connection closed (%s)", e.__class__.__name__)
        finally:
            heartbeat.cancel()
            if self._writer is writer:
                self._writer = None
                self._set_linked(False)
            writer.close()

    def _capture(self, direction: str, data: bytes) -> None:
        """Append one frame to the capture file: what the game really sends is still unverified."""
        if not self.capture:
            return
        line = json.dumps({"t": round(time.time(), 3), "dir": direction, "hex": data.hex()})
        try:
            with self.capture.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            log.warning("Companion: capture to %s failed (%s), stopped", self.capture, e)
            self.capture = None

    def _set_linked(self, on: bool) -> None:
        if self.state.linked != on:
            self.state = GameState(linked=on)
            self.on_change()

    async def _pair(self) -> None:
        """What Sauce sends after the game connected: client info, pairing, session start, action bar."""
        info = {1: CLIENT_INFO, 5: {1: "3.81.0", 2: "14", 3: "Android", 4: "Wristpilot", 5: {1: False, 2: False},
                                   6: "en_US", 7: 1}}
        await self._send([{2: CMD_PACKET, 21: info}])
        await self._send([{2: CMD_PAIRING, 19: self.athlete_id}])
        await self._send([{2: CMD_PACKET, 21: {1: CLIENT_ACTION, 16: {1: START_CONNECTED_SESSION}}}])
        await self._send([{2: CMD_PACKET, 21: {1: CLIENT_ACTION, 16: {1: ACTION_BAR_OPEN}}}])

    async def _heartbeat(self, writer: asyncio.StreamWriter) -> None:
        while True:
            await asyncio.sleep(HEARTBEAT)
            await self._send([], writer)

    async def _send(self, commands: list[dict], writer: asyncio.StreamWriter | None = None) -> bool:
        writer = writer or self._writer
        if writer is None:
            return False
        cmds = []
        for c in commands:
            self._cmd_seqno += 1
            cmds.append({1: self._cmd_seqno, **c})
        self._seqno += 1
        msg = pb.message({1: self.athlete_id, 2: cmds, 10: self._seqno})
        if cmds:   # heartbeats (no commands) would only fill the file
            self._capture("bridge", msg)
        try:
            writer.write(frame(msg))
            await writer.drain()
        except (ConnectionError, OSError):
            return False
        return True

    async def command(self, action: int, value: int) -> bool | None:
        """Send a Wristpilot action to the game. None = the game has no such command (use the keyboard)."""
        cmd = command_for(action, value, self.hud_on)
        if cmd is None:
            return None
        if not self.linked:
            return False
        ok = await self._send([cmd])
        if ok and action == actions.HUD:
            self.hud_on = not self.hud_on
        if ok and action == actions.POWERUP:
            self.state.powerup = PU_NONE  # the game confirms with ACTIVATE/CLEAR, but show it at once
            self.on_change()
        return ok

    # --- What the game tells us ---

    def handle_game_message(self, data: bytes, now: float | None = None) -> None:
        now = time.monotonic() if now is None else now
        msg = pb.decode(data)
        changed = False
        for raw in msg.get(G_COMMANDS, []):
            changed |= self._game_command(pb.decode(raw), now)
        if changed:
            self.on_change()

    def _game_command(self, c: dict, now: float) -> bool:
        t = pb.first(c, GC_TYPE, 0)
        st = self.state
        if t == SET_POWER_UP:
            pid = pb.first(c, GC_POWERUP_ID, 0) - 1
            new = POWERUPS.get(pid, PU_NONE if pid in (-1, 15) else PU_UNKNOWN)
        elif t in (CLEAR_POWER_UP, ACTIVATE_POWER_UP):
            new = PU_NONE
        elif t == CUSTOMIZE_ACTION_BUTTON:
            sub = pb.first(c, GC_SUBCOMMAND, 0)
            bit = TURN_BITS.get(sub)
            if bit is None:
                return False
            shown = pb.first(c, GC_POSITION, 0) != 0 and not pb.first(c, GC_HIDE, 0)
            if shown:
                st.turns[bit] = now
            else:
                st.turns.pop(bit, None)
            return True
        elif t == SOCIAL_PLAYER_ACTION:
            social = pb.decode(pb.first(c, GC_SOCIAL, b""))
            if pb.first(social, 3, 0) == RIDE_ON_SOCIAL:
                st.ride_ons += 1
                return True
            return False
        elif t == PACKET:
            return self._packet(pb.decode(pb.first(c, GC_PACKET, b"")), now)
        else:
            return False
        if new != st.powerup:
            st.powerup = new
            return True
        return False

    def _packet(self, p: dict, now: float) -> bool:
        kind = pb.first(p, P_TYPE, 0)
        st = self.state
        if kind == INTERSECTION_AHEAD:
            inter = pb.decode(pb.first(p, P_INTERSECTION, b""))
            st.turns.clear()
            for raw in inter.get(1, []):
                opt = pb.decode(raw)
                if not pb.first(opt, 4, 1):          # enabled (default true when missing)
                    continue
                bit = turn_bit(pb.text(opt, 3), pb.first(opt, 1, -1))
                if bit:
                    st.turns[bit] = now
            return True
        if kind == GAME_SESSION_INFO:
            session = pb.decode(pb.first(p, P_SESSION, b""))
            in_game = pb.first(session, 2, 0) != 0     # activityId, 0 = not riding
            if in_game != st.in_game:
                st.in_game = in_game
                if not in_game:
                    st.ride_ons, st.powerup = 0, PU_NONE
                    st.turns.clear()
                return True
        return False


def turn_bit(title: str, direction: int) -> int:
    """Which turn an IntersectionAhead option means. The title is the reliable part ("TURN LEFT",
    "GO STRAIGHT", localised variants); the numeric direction is unverified (0/1/2 = left/straight/right
    assumed) and only used without a usable title."""
    t = title.lower()
    if any(w in t for w in ("left", "links", "gauche", "izquierda", "sinistra")):
        return F_LEFT
    if any(w in t for w in ("right", "rechts", "droite", "derecha", "destra")):
        return F_RIGHT
    if any(w in t for w in ("straight", "geradeaus", "tout droit", "recto", "dritto", "ahead")):
        return F_STRAIGHT
    return {0: F_LEFT, 1: F_STRAIGHT, 2: F_RIGHT}.get(direction, 0)
