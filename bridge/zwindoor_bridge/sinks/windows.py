"""Windows output: SendInput with scan codes into ZwiftApp.exe.

Zwift reads the keyboard through raw input; virtual key codes alone are not always enough, so the
events carry hardware scan codes (KEYEVENTF_SCANCODE), arrow and page keys with the E0 prefix
(KEYEVENTF_EXTENDEDKEY). Only types when ZwiftApp.exe owns the foreground window.
"""

from __future__ import annotations

import ctypes
import os
from ctypes import wintypes

from ..keys import Key
from . import ZWIFT_PROCESS, KeySink, SinkError, WindowState

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SW_RESTORE = 9
VK_MENU = 0x12
ULONG_PTR = ctypes.c_size_t


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _anonymous_ = ("u",)
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


class SendInputSink(KeySink):
    name = "sendinput"

    def __init__(self, process: str = ZWIFT_PROCESS) -> None:
        if os.name != "nt":
            raise SinkError("SendInput is only available on Windows")
        self.user32 = ctypes.WinDLL("user32", use_last_error=True)
        self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self.process = process.lower()
        u = self.user32
        u.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
        u.SendInput.restype = wintypes.UINT
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.IsIconic.argtypes = [wintypes.HWND]
        u.IsWindowVisible.argtypes = [wintypes.HWND]
        u.keybd_event.argtypes = [wintypes.BYTE, wintypes.BYTE, wintypes.DWORD, ULONG_PTR]
        k = self.kernel32
        k.OpenProcess.restype = wintypes.HANDLE
        k.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        k.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                                 ctypes.POINTER(wintypes.DWORD)]
        k.CloseHandle.argtypes = [wintypes.HANDLE]

    # --- Windows and processes ---

    def _exe(self, hwnd) -> str:
        pid = wintypes.DWORD()
        self.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = self.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
        if not h:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(1024)
            size = wintypes.DWORD(len(buf))
            if not self.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                return ""
            return os.path.basename(buf.value).lower()
        finally:
            self.kernel32.CloseHandle(h)

    def _zwift_windows(self) -> list:
        found = []
        proc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def cb(hwnd, _lparam):
            if self.user32.IsWindowVisible(hwnd) and self._exe(hwnd) == self.process:
                found.append(hwnd)
            return True

        self.user32.EnumWindows(proc(cb), 0)
        return found

    def window(self) -> WindowState:
        fg = self.user32.GetForegroundWindow()
        if fg and self._exe(fg) == self.process:
            return WindowState(running=True, focused=True)
        return WindowState(running=bool(self._zwift_windows()), focused=False)

    def activate(self) -> bool:
        wins = self._zwift_windows()
        if not wins:
            return False
        hwnd = wins[0]
        if self.user32.IsIconic(hwnd):
            self.user32.ShowWindow(hwnd, SW_RESTORE)
        # Windows only lets the process with the last input event change the foreground window;
        # a synthetic Alt press counts as such an event.
        self.user32.keybd_event(VK_MENU, 0, 0, 0)
        self.user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)
        return bool(self.user32.SetForegroundWindow(hwnd))

    # --- Keys ---

    def _send(self, key: Key, up: bool) -> None:
        flags = KEYEVENTF_SCANCODE | (KEYEVENTF_EXTENDEDKEY if key.extended else 0) | (KEYEVENTF_KEYUP if up else 0)
        inp = INPUT(type=INPUT_KEYBOARD, ki=KEYBDINPUT(wVk=0, wScan=key.scan, dwFlags=flags, time=0, dwExtraInfo=0))
        if self.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT)) != 1:
            raise SinkError(f"SendInput failed ({ctypes.get_last_error()})")

    def press(self, key: Key) -> None:
        self._send(key, up=False)

    def release(self, key: Key) -> None:
        self._send(key, up=True)
