"""Engine: decides what a command from the watch does and answers it.

Independent of Bluetooth and of the platform; the radio backend feeds bytes in, the engine
returns the bytes to notify. Runs on one asyncio loop.
"""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Callable

from . import actions, keys
from .config import Config
from .protocol import Command, Result, State, decode_command, encode_ack, encode_state
from .sinks import KeySink, SinkError, WindowState

log = logging.getLogger(__name__)

PING = 0x00              # keep-alive from the watch; answered with the state instead of an ack
WATCH_TIMEOUT = 15.0     # seconds without any write before the watch counts as gone
FOCUS_WAIT = 0.15        # seconds the window manager gets to raise Zwift
SINK_TIMEOUT = 2.0       # a sink call that takes longer is treated as blocked


@dataclass
class Event:
    """One handled command, for the user interfaces (Tretlager page, tray menu)."""
    when: float
    action: str
    action_de: str
    result: Result
    ms: float


class Engine:
    def __init__(self, sink: KeySink, config: Config | None = None, obc=None, companion=None) -> None:
        self.sink = sink
        self.config = config or Config()
        self.obc = obc                       # obc.ObcServer or None
        self.companion = companion           # companion.CompanionLink or None
        self._last_game: bytes | None = None
        self.camera = actions.CameraCycle()
        self.last_write = 0.0
        self.watch_name = ""
        self._last_state: State | None = None
        self.listeners: list[Callable[[Event], None]] = []
        self.state_listeners: list[Callable[[State], None]] = []
        # All sink calls run on one worker thread: X11 connections are not thread-safe, and a
        # blocked display (Plasma's consent dialog for XTest) must not stall the Bluetooth loop.
        self._worker = ThreadPoolExecutor(1, thread_name_prefix="wristpilot-sink")
        self.blocked = False            # last sink call timed out (shown in the shells)

    async def _call(self, fn, *args):
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(loop.run_in_executor(self._worker, fn, *args), SINK_TIMEOUT)
        except asyncio.TimeoutError:
            if not self.blocked:
                log.warning("keyboard output blocked (%s did not return)", getattr(fn, "__name__", fn))
            self.blocked = True
            raise SinkError("keyboard output blocked") from None
        self.blocked = False
        return result

    def close(self) -> None:
        self._worker.shutdown(wait=False, cancel_futures=True)

    # --- State ---

    @property
    def watch_connected(self) -> bool:
        return bool(self.last_write) and time.monotonic() - self.last_write < WATCH_TIMEOUT

    def _window_sync(self) -> WindowState:
        try:
            return self.sink.window()
        except Exception as e:  # never let a broken display take the radio down
            log.debug("window state: %s", e)
            return WindowState(False, False)

    async def window(self) -> WindowState:
        try:
            return await self._call(self._window_sync)
        except SinkError:
            return WindowState(False, False)

    async def state(self) -> State:
        s = State(0)
        if self.config.enabled:
            s |= State.ENABLED
        if self.config.keyboard:
            s |= State.KEYBOARD_ON
        w = await self.window()
        if w.running:
            s |= State.ZWIFT_RUNNING
        if w.focused:
            s |= State.ZWIFT_FOCUSED
        if self.obc and self.obc.clients:
            s |= State.OBC_CONNECTED
        if self.companion and self.companion.linked:
            s |= State.COMPANION
        return s

    def poll_game(self, force: bool = False) -> bytes | None:
        """Game state message for the watch if it changed (or `force`), else None."""
        msg = self.companion.state.message() if self.companion else bytes((0x04, 0, 0, 0, 0))
        if msg == self._last_game and not force:
            return None
        self._last_game = msg
        return msg

    async def poll_state(self) -> bytes | None:
        """State message if it changed since the last call, else None (called about once a second)."""
        s = await self.state()
        if s == self._last_state:
            return None
        self._last_state = s
        for cb in self.state_listeners:
            cb(s)
        return encode_state(s)

    # --- Commands ---

    async def handle_write(self, data: bytes) -> bytes:
        was_connected = self.watch_connected
        self.last_write = time.monotonic()
        cmd = decode_command(data)
        if cmd is None:
            return encode_ack(data[0] if data else 0, Result.MALFORMED)
        if cmd.action == PING:
            if not was_connected:
                self._last_game = None   # a (re)connected watch gets the game state with the next poll
            self._last_state = await self.state()
            return encode_state(self._last_state)
        start = time.perf_counter()
        action = actions.find(cmd.action, cmd.value)
        result = await self._run(cmd, action)
        ms = (time.perf_counter() - start) * 1000
        name = action.name if action else f"unknown {cmd.action:#04x}/{cmd.value}"
        log.info("%s -> %s (%.0f ms)", name, result.name, ms)
        ev = Event(time.time(), name, action.name_de if action else name, result, ms)
        for cb in self.listeners:
            cb(ev)
        return encode_ack(cmd.seq, result)

    async def _run(self, cmd: Command, action: actions.Action | None) -> Result:
        if not self.config.enabled:
            return Result.DISABLED
        if action is None:
            return Result.UNKNOWN_ACTION
        delivered = False
        if self.config.obc and self.obc and self.obc.clients:
            delivered = await self.obc.button(cmd.action, cmd.value)
        if self.companion and self.companion.linked:
            sent = await self.companion.command(cmd.action, cmd.value)
            if sent:
                return Result.OK
            # None: the game has no command for it (workout keys) -> keyboard below
        if not self.config.keyboard:
            return Result.OK if delivered else Result.NOT_RUNNING
        result = await self._type(action)
        return Result.OK if delivered else result

    def key_name(self, action: actions.Action) -> str:
        name = self.config.keys.get(actions.slug(action), action.key)
        if name == "camera":
            return self.camera.next_key()
        self.camera.set_view(name)
        return name

    async def _type(self, action: actions.Action) -> Result:
        name = self.key_name(action)
        if not name:
            return Result.OK  # deliberately unmapped
        key = keys.lookup(name)
        if key is None:
            log.warning("unknown key %r for %s", name, action.name)
            return Result.OUTPUT_FAILED
        w = await self.window()
        if not w.running:
            return Result.NOT_RUNNING
        try:
            if not w.focused:
                if not self.config.bring_to_front or not await self._call(self.sink.activate):
                    return Result.NOT_FOCUSED
                await asyncio.sleep(FOCUS_WAIT)
                if not (await self.window()).focused:
                    return Result.NOT_FOCUSED
            await self._call(self.sink.press, key)
            await asyncio.sleep(self.config.hold_ms / 1000)
            await self._call(self.sink.release, key)
        except SinkError as e:
            log.warning("typing %s failed: %s", name, e)
            return Result.OUTPUT_FAILED
        return Result.OK
