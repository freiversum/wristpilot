"""X11 output: XTest key events into the display Wine runs on (Zwift under Wine/XWayland).

Plain ctypes on libX11 and libXtst, no extra Python package (both libraries are part of the KDE
and GNOME Flatpak runtimes). Window state comes from EWMH (_NET_CLIENT_LIST, _NET_ACTIVE_WINDOW).
On Wayland desktops _NET_ACTIVE_WINDOW only names X11 windows; when a Wayland window is in front
it points to none, which is exactly "Zwift not focused".
"""

from __future__ import annotations

import ctypes
import ctypes.util

from ..keys import Key
from . import ZWIFT_PROCESS, KeySink, SinkError, WindowState

XA_WINDOW = 33
CLIENT_MESSAGE = 33
SUBSTRUCTURE_NOTIFY_REDIRECT = (1 << 19) | (1 << 20)
_ERROR_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p)
_ignore_errors = _ERROR_HANDLER(lambda _d, _e: 0)  # the default handler would end the process


class _ClassHint(ctypes.Structure):
    _fields_ = [("res_name", ctypes.c_void_p), ("res_class", ctypes.c_void_p)]


class _ClientMessage(ctypes.Structure):
    _fields_ = [("type", ctypes.c_int), ("serial", ctypes.c_ulong), ("send_event", ctypes.c_int),
                ("display", ctypes.c_void_p), ("window", ctypes.c_ulong), ("message_type", ctypes.c_ulong),
                ("format", ctypes.c_int), ("data", ctypes.c_long * 5)]


def _load(name: str):
    path = ctypes.util.find_library(name)
    if not path:
        raise SinkError(f"lib{name} not found")
    return ctypes.CDLL(path)


class X11:
    """Thin libX11/libXtst wrapper around one display connection."""

    def __init__(self, display: str | None = None) -> None:
        x = self.x = _load("X11")
        t = self.t = _load("Xtst")
        x.XOpenDisplay.restype = ctypes.c_void_p
        x.XOpenDisplay.argtypes = [ctypes.c_char_p]
        x.XDefaultRootWindow.restype = ctypes.c_ulong
        x.XDefaultRootWindow.argtypes = [ctypes.c_void_p]
        x.XInternAtom.restype = ctypes.c_ulong
        x.XInternAtom.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int]
        x.XSetErrorHandler.argtypes = [_ERROR_HANDLER]
        x.XGetClassHint.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(_ClassHint)]
        x.XGetWindowProperty.argtypes = [
            ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_long, ctypes.c_long, ctypes.c_int,
            ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_int),
            ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_ulong), ctypes.POINTER(ctypes.c_void_p)]
        x.XSendEvent.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_int, ctypes.c_long, ctypes.c_void_p]
        x.XFree.argtypes = [ctypes.c_void_p]
        x.XFlush.argtypes = [ctypes.c_void_p]
        x.XCloseDisplay.argtypes = [ctypes.c_void_p]
        x.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        x.XKeysymToKeycode.restype = ctypes.c_ubyte
        t.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_ulong]
        t.XTestQueryExtension.argtypes = [ctypes.c_void_p] + [ctypes.POINTER(ctypes.c_int)] * 4
        x.XSetErrorHandler(_ignore_errors)
        self.dpy = x.XOpenDisplay(display.encode() if display else None)
        if not self.dpy:
            raise SinkError("no X11 display (DISPLAY not set?)")
        a, b, c, d = (ctypes.c_int() for _ in range(4))
        if not t.XTestQueryExtension(self.dpy, ctypes.byref(a), ctypes.byref(b), ctypes.byref(c), ctypes.byref(d)):
            self.close()
            raise SinkError("X server without XTEST extension")
        self.root = x.XDefaultRootWindow(self.dpy)
        self._atoms: dict[bytes, int] = {}

    def atom(self, name: bytes) -> int:
        if name not in self._atoms:
            self._atoms[name] = self.x.XInternAtom(self.dpy, name, 0)
        return self._atoms[name]

    def _windows_prop(self, win: int, prop: bytes) -> list[int]:
        x = self.x
        kind, fmt, count, rest, data = ctypes.c_ulong(), ctypes.c_int(), ctypes.c_ulong(), ctypes.c_ulong(), ctypes.c_void_p()
        if x.XGetWindowProperty(self.dpy, win, self.atom(prop), 0, 4096, 0, XA_WINDOW, ctypes.byref(kind),
                                ctypes.byref(fmt), ctypes.byref(count), ctypes.byref(rest),
                                ctypes.byref(data)) != 0 or not data.value:
            return []
        out = list(ctypes.cast(data, ctypes.POINTER(ctypes.c_ulong))[:count.value])
        x.XFree(data)
        return out

    def wm_class(self, win: int) -> set[str]:
        hint = _ClassHint()
        if not win or not self.x.XGetClassHint(self.dpy, win, ctypes.byref(hint)):
            return set()
        names = {(ctypes.string_at(p) if p else b"").decode(errors="replace").lower()
                 for p in (hint.res_name, hint.res_class)}
        for p in (hint.res_name, hint.res_class):
            if p:
                self.x.XFree(p)
        return names

    def find(self, wm_class: str) -> list[int]:
        return [w for w in self._windows_prop(self.root, b"_NET_CLIENT_LIST") if wm_class in self.wm_class(w)]

    def active(self) -> int:
        wins = self._windows_prop(self.root, b"_NET_ACTIVE_WINDOW")
        return wins[0] if wins else 0

    def activate(self, win: int) -> None:
        ev = _ClientMessage(type=CLIENT_MESSAGE, send_event=1, window=win, format=32,
                            message_type=self.atom(b"_NET_ACTIVE_WINDOW"))
        ev.data[:] = [2, 0, 0, 0, 0]  # source 2 = pager: window managers honour it without focus-stealing rules
        buf = (ctypes.c_long * 24)()  # XEvent is a union of 24 longs
        ctypes.memmove(buf, ctypes.byref(ev), ctypes.sizeof(ev))
        self.x.XSendEvent(self.dpy, self.root, 0, SUBSTRUCTURE_NOTIFY_REDIRECT, buf)
        self.x.XFlush(self.dpy)

    def key(self, keysym: int, down: bool) -> None:
        code = self.x.XKeysymToKeycode(self.dpy, keysym)
        if not code:
            raise SinkError(f"no keycode for keysym {keysym:#x}")
        self.t.XTestFakeKeyEvent(self.dpy, code, 1 if down else 0, 0)
        self.x.XFlush(self.dpy)

    def close(self) -> None:
        if self.dpy:
            self.x.XCloseDisplay(self.dpy)
            self.dpy = None


class XTestSink(KeySink):
    name = "xtest"

    def __init__(self, display: str | None = None, wm_class: str = ZWIFT_PROCESS) -> None:
        self.x11 = X11(display)
        self.wm_class = wm_class

    def window(self) -> WindowState:
        wins = self.x11.find(self.wm_class)
        return WindowState(running=bool(wins), focused=self.x11.active() in wins if wins else False)

    def activate(self) -> bool:
        wins = self.x11.find(self.wm_class)
        if not wins:
            return False
        self.x11.activate(wins[0])
        return True  # the engine checks the focus again after a short wait

    def press(self, key: Key) -> None:
        self.x11.key(key.keysym, True)

    def release(self, key: Key) -> None:
        self.x11.key(key.keysym, False)

    def close(self) -> None:
        self.x11.close()
