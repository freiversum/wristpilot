"""Bridge runner: engine + Bluetooth peripheral + optional OpenBikeControl server on one loop.

`BridgeRunner` is what the shells use. `run()` blocks (command line); `start_thread()` runs the
loop in a background thread for Qt/tray programs, which then only call the thread-safe methods.
"""

from __future__ import annotations

import asyncio
import logging
import socket
import threading
from concurrent.futures import Future
from pathlib import Path
from typing import Callable

from . import __version__
from .announce import Announcer, default_announcer
from .ble import Peripheral, PeripheralError, default_peripheral
from .companion import CompanionLink
from .config import Config
from .engine import Engine, Event
from .obc import ObcServer
from .protocol import Command, State, encode_command, encode_haptic
from .sinks import KeySink, default_sink

log = logging.getLogger(__name__)

POLL = 1.0


class BridgeRunner:
    def __init__(self, config: Config | None = None, config_path: Path | None = None,
                 sink: KeySink | None = None, announcer: Announcer | None = None,
                 peripheral_factory: Callable[..., Peripheral] | None = None,
                 token_provider: Callable[[], str | None] | None = None) -> None:
        self.config_path = config_path
        self.config = config or Config.load(config_path)
        self._sink = sink
        self._announcer = announcer
        self._peripheral_factory = peripheral_factory or default_peripheral
        self.engine: Engine | None = None
        self.peripheral: Peripheral | None = None
        self.obc: ObcServer | None = None
        self.companion: CompanionLink | None = None
        self.token_provider = token_provider   # blocking; Zwift access token for the Companion link
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.error = ""                   # last fatal error, for the user interface
        self.running = False
        self._stop: asyncio.Event | None = None
        self.on_event: list[Callable[[Event], None]] = []
        self.on_state: list[Callable[[State], None]] = []
        self.on_status: list[Callable[[], None]] = []   # running/error/watch changes

    # --- Lifecycle on the loop ---

    async def _main(self) -> None:
        self._stop = asyncio.Event()
        sink = self._sink or default_sink()
        self.engine = Engine(sink, self.config)
        self.engine.listeners += [lambda ev: [cb(ev) for cb in self.on_event]]
        self.engine.state_listeners += [lambda s: [cb(s) for cb in self.on_state]]
        info = f"ZWindoor {__version__} · {socket.gethostname()}".encode()
        self.peripheral = self._peripheral_factory(self.engine.handle_write, info, adapter=self.config.adapter)
        try:
            await self.peripheral.start()
            await self._apply_obc()
            await self._apply_companion()
            self.running, self.error = True, ""
            self._changed()
            watch = False
            while not self._stop.is_set():
                msg = await self.engine.poll_state()
                if msg:
                    await self.peripheral.notify(msg)
                msg = self.engine.poll_game()   # turn choices expire after a while
                if msg:
                    await self.peripheral.notify(msg)
                if watch != self.engine.watch_connected:
                    watch = self.engine.watch_connected
                    log.info("watch %s", "connected" if watch else "gone")
                    self._changed()
                try:
                    await asyncio.wait_for(self._stop.wait(), POLL)
                except asyncio.TimeoutError:
                    pass
        except PeripheralError as e:
            self.error = str(e)
            log.error("Bluetooth: %s", e)
        finally:
            self.running = False
            if self.obc:
                await self.obc.stop()
                self.obc = None
            if self.companion:
                await self.companion.stop()
                self.companion = None
            await self.peripheral.stop()
            self.engine.close()
            sink.close()
            self._changed()

    async def _apply_obc(self) -> None:
        want = self.config.obc
        if want and not self.obc:
            self.obc = ObcServer(self.config.obc_port, announcer=self._announcer or default_announcer(),
                                 on_haptic=self._haptic)
            self.obc.watch_connected = lambda: bool(self.engine and self.engine.watch_connected)
            try:
                await self.obc.start()
            except OSError as e:
                log.warning("OBC: port %d: %s", self.config.obc_port, e)
                self.obc = None
        elif not want and self.obc:
            await self.obc.stop()
            self.obc = None
        if self.engine:
            self.engine.obc = self.obc

    async def _apply_companion(self) -> None:
        want = self.config.companion and self.token_provider is not None
        if want and not self.companion:
            self.companion = CompanionLink(self.token_provider, self.config.companion_port,
                                           on_change=self._game_changed)
            try:
                await self.companion.start()
            except OSError as e:
                log.warning("Companion: %s", e)
                self.companion = None
        elif not want and self.companion:
            await self.companion.stop()
            self.companion = None
        if self.engine:
            self.engine.companion = self.companion
            self._game_changed()

    def _game_changed(self) -> None:
        """Push the game state to the watch at once (junctions do not wait for the next poll)."""
        if self.loop and self.engine and self.peripheral:
            msg = self.engine.poll_game()
            if msg:
                self.loop.create_task(self.peripheral.notify(msg))
        self._changed()

    def _haptic(self, pattern: int) -> None:
        if self.peripheral and self.loop:
            self.loop.create_task(self.peripheral.notify(encode_haptic(pattern)))

    def _changed(self) -> None:
        for cb in self.on_status:
            cb()

    # --- Blocking and threaded use ---

    def run(self) -> None:
        asyncio.run(self._run_loop())

    async def _run_loop(self) -> None:
        self.loop = asyncio.get_running_loop()
        await self._main()

    def start_thread(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self.run, name="zwindoor-bridge", daemon=True)
        self.thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        if self.loop and self._stop:
            self.loop.call_soon_threadsafe(self._stop.set)
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout)
        self.thread = None

    def _submit(self, coro) -> Future | None:
        if not self.loop or not self.running:
            coro.close()
            return None
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def update_config(self, **changes) -> None:
        """Change settings from any thread; saved immediately."""
        for k, v in changes.items():
            setattr(self.config, k, v)
        self.config.save(self.config_path)
        self._submit(self._apply_obc())
        self._submit(self._apply_companion())
        self._changed()

    def test_action(self, action: int, value: int = 1) -> Future | None:
        """Run an action as if the watch had sent it ("Test actions" in the shells)."""
        return self._submit(self.engine.handle_write(encode_command(Command(0, action, value))))

    @property
    def watch_connected(self) -> bool:
        return bool(self.engine and self.engine.watch_connected)

    @property
    def zwift_state(self) -> State:
        """Last state seen by the loop (window checks must stay on the loop thread)."""
        return (self.engine._last_state if self.engine else None) or State(0)
