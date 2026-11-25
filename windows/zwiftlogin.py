"""Zwift sign-in for the Windows bridge (Companion link, phase 4).

Same route as Tretlager: the Zwift sign-in page opens in the user's browser (password manager,
Google/Apple sign-in work there); afterwards Zwift redirects to launcher.zwift.com/launcher?code=…,
which shows an error page – the user copies that address into a small dialog. Wristpilot never sees
the password. The token is stored encrypted with DPAPI (only this Windows user can read it).
"""

from __future__ import annotations

import base64
import ctypes
import json
import logging
import os
import sys
import threading
import webbrowser
from ctypes import wintypes
from pathlib import Path

from wristpilot_bridge import zwiftapi
from wristpilot_bridge.config import default_path

log = logging.getLogger(__name__)
MARGIN = 300


class _Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _dpapi(data: bytes, protect: bool) -> bytes:
    crypt = ctypes.WinDLL("crypt32")
    kernel = ctypes.WinDLL("kernel32")
    buf = ctypes.create_string_buffer(data, len(data))
    src = _Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))
    dst = _Blob()
    fn = crypt.CryptProtectData if protect else crypt.CryptUnprotectData
    if not fn(ctypes.byref(src), None, None, None, None, 0, ctypes.byref(dst)):
        raise OSError("DPAPI failed")
    try:
        return ctypes.string_at(dst.pbData, dst.cbData)
    finally:
        kernel.LocalFree(dst.pbData)


class TokenStore:
    """Token file next to the settings. DPAPI on Windows; elsewhere (tests) base64 with mode 600."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or default_path().with_name("zwift-token.bin")
        self._lock = threading.Lock()

    def load(self) -> dict | None:
        try:
            raw = self.path.read_bytes()
            data = _dpapi(raw, False) if sys.platform == "win32" else base64.b64decode(raw)
            return json.loads(data)
        except (OSError, ValueError):
            return None

    def save(self, token: dict) -> None:
        data = json.dumps(token).encode()
        raw = _dpapi(data, True) if sys.platform == "win32" else base64.b64encode(data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_bytes(raw)
        if sys.platform != "win32":
            os.chmod(self.path, 0o600)

    def clear(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass

    def access_token(self, api=zwiftapi) -> str | None:
        """Valid access token, refreshed if needed; None = sign in again. Blocking."""
        with self._lock:
            token = self.load()
            if not token:
                return None
            if api.access_left(token) > MARGIN:
                return token["access_token"]
            if api.refresh_left(token) > MARGIN and token.get("refresh_token"):
                try:
                    token = api.refresh(token)
                except zwiftapi.ZwiftApiError as e:
                    log.warning("Zwift token refresh: %s", e)
                    return None
                self.save(token)
                return token["access_token"]
            return None

    def signed_in(self) -> bool:
        token = self.load()
        return bool(token) and zwiftapi.refresh_left(token) > MARGIN


def sign_in(store: TokenStore, texts: dict, done=None) -> None:
    """Open the sign-in page and ask for the redirect address (Tk dialog on its own thread)."""
    def run():
        state = zwiftapi.new_state()
        webbrowser.open(zwiftapi.auth_url(state))
        try:
            import tkinter
            from tkinter import messagebox, simpledialog
        except ImportError:
            log.error("tkinter missing, cannot ask for the sign-in address")
            return
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        ok = False
        try:
            url = simpledialog.askstring(texts["login_title"], texts["login_prompt"], parent=root)
            if url:
                try:
                    store.save(zwiftapi.exchange_code(zwiftapi.parse_redirect(url, state)))
                    ok = True
                    messagebox.showinfo(texts["login_title"], texts["login_ok"], parent=root)
                except zwiftapi.ZwiftApiError as e:
                    messagebox.showerror(texts["login_title"], texts["login_failed"].format(e), parent=root)
        finally:
            root.destroy()
        if done:
            done(ok)

    threading.Thread(target=run, name="zwift-sign-in", daemon=True).start()
