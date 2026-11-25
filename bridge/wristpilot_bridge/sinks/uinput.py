"""Linux fallback: a virtual keyboard through /dev/uinput (python-evdev).

For setups where XTest events do not reach Wine. uinput types into whatever has the focus, so the
window state still comes from X11 (XTestSink without typing). Needs write access to /dev/uinput
(group "input" or a udev rule); not available inside the Flatpak sandbox.
"""

from __future__ import annotations

from ..keys import KEYS, Key
from . import KeySink, SinkError, WindowState


class UinputSink(KeySink):
    name = "uinput"

    def __init__(self, windows: KeySink | None = None) -> None:
        try:
            from evdev import UInput, ecodes
        except ImportError as e:
            raise SinkError("python-evdev is not installed") from e
        try:
            self.ui = UInput({ecodes.EV_KEY: sorted({k.evdev for k in KEYS.values()})}, name="Wristpilot remote")
        except OSError as e:
            raise SinkError(f"/dev/uinput: {e}") from e
        self.ecodes = ecodes
        self.windows = windows

    def window(self) -> WindowState:
        return self.windows.window() if self.windows else WindowState(running=True, focused=True)

    def activate(self) -> bool:
        return self.windows.activate() if self.windows else True

    def _send(self, key: Key, value: int) -> None:
        self.ui.write(self.ecodes.EV_KEY, key.evdev, value)
        self.ui.syn()

    def press(self, key: Key) -> None:
        self._send(key, 1)

    def release(self, key: Key) -> None:
        self._send(key, 0)

    def close(self) -> None:
        self.ui.close()
        if self.windows:
            self.windows.close()
