"""Keyboard outputs. Each sink types into the Zwift window and knows whether that window exists
and has the keyboard focus. Sinks are synchronous and fast; the engine calls them from its event
loop and waits between press and release itself.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass, field

from ..keys import Key

log = logging.getLogger(__name__)

ZWIFT_PROCESS = "zwiftapp.exe"  # Windows process name and Wine's WM_CLASS


class SinkError(Exception):
    pass


@dataclass
class WindowState:
    running: bool
    focused: bool


class KeySink:
    """Base class; the default does nothing (dry run)."""

    name = "none"

    def window(self) -> WindowState:
        return WindowState(running=False, focused=False)

    def activate(self) -> bool:
        """Bring the Zwift window to the front; True if it has the focus afterwards."""
        return False

    def press(self, key: Key) -> None:
        pass

    def release(self, key: Key) -> None:
        pass

    def close(self) -> None:
        pass


@dataclass
class RecordingSink(KeySink):
    """For tests and the "test actions" button without Zwift: records instead of typing."""

    running: bool = True
    focused: bool = True
    events: list[tuple[str, Key]] = field(default_factory=list)
    name = "recording"

    def window(self) -> WindowState:
        return WindowState(self.running, self.focused)

    def activate(self) -> bool:
        if self.running:
            self.focused = True
        return self.focused

    def press(self, key: Key) -> None:
        self.events.append(("press", key))

    def release(self, key: Key) -> None:
        self.events.append(("release", key))


def default_sink() -> KeySink:
    """Best available sink for this platform."""
    if sys.platform == "win32":
        from .windows import SendInputSink
        return SendInputSink()
    try:
        from .xtest import XTestSink
        return XTestSink()
    except SinkError as e:
        log.warning("no keyboard output: %s", e)
        return KeySink()
