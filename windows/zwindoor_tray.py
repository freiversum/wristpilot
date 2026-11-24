"""ZWindoor Bridge for Windows: a tray program around the bridge core.

One icon in the notification area. Its menu shows the state (Bluetooth, watch, Zwift, last action)
and holds the switches: remote on/off, OpenBikeControl on the network, bring Zwift to the front,
start with Windows, test actions, open log, quit. Texts in German or English after the Windows
display language.
"""

from __future__ import annotations

import locale
import logging
import logging.handlers
import os
import subprocess
import sys
import time
from pathlib import Path

from zwindoor_bridge import __version__, actions
from zwindoor_bridge.config import Config, default_path
from zwindoor_bridge.protocol import Result, State
from zwindoor_bridge.runner import BridgeRunner
from zwiftlogin import TokenStore, sign_in

APP = "ZWindoor"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
ORANGE = (255, 122, 47)
GREEN = (47, 191, 113)
GREY = (140, 140, 140)
RED = (229, 72, 77)

TEXTS = {
    "en": {
        "bt_ok": "Bluetooth: ready", "bt_err": "Bluetooth: {}", "bt_start": "Bluetooth: starting …",
        "watch_on": "Watch: connected", "watch_off": "Watch: not connected",
        "zwift_front": "Zwift: in front", "zwift_back": "Zwift: running in the background",
        "zwift_off": "Zwift: not running", "obc_on": "OpenBikeControl app connected",
        "last": "Last action: {} · {} s ago", "last_none": "Last action: –",
        "enabled": "Remote active", "obc": "OpenBikeControl on the network", "front": "Bring Zwift to the front",
        "autostart": "Start with Windows", "test": "Test actions", "log": "Open log", "quit": "Quit",
        "not_focused": "Zwift was not in front", "not_running": "Zwift is not running",
        "companion": "Zwift Companion link (turns, power-up)", "login": "Sign in to Zwift …",
        "logout": "Sign out of Zwift", "comp_linked": "Companion: connected to the game",
        "comp_wait": "Companion: waiting for Zwift", "comp_login": "Companion: sign in to Zwift first",
        "comp_error": "Companion: {}",
        "login_title": "ZWindoor – Zwift sign-in",
        "login_prompt": "Sign in to Zwift in the browser. Zwift then shows an error page on launcher.zwift.com –\n"
                        "copy the whole address from the address bar and paste it here:",
        "login_ok": "Signed in. The Companion link starts now.",
        "login_failed": "Sign-in failed: {}",
    },
    "de": {
        "bt_ok": "Bluetooth: bereit", "bt_err": "Bluetooth: {}", "bt_start": "Bluetooth: startet …",
        "watch_on": "Uhr: verbunden", "watch_off": "Uhr: nicht verbunden",
        "zwift_front": "Zwift: im Vordergrund", "zwift_back": "Zwift: läuft im Hintergrund",
        "zwift_off": "Zwift: läuft nicht", "obc_on": "OpenBikeControl-App verbunden",
        "last": "Letzte Aktion: {} · vor {} s", "last_none": "Letzte Aktion: –",
        "enabled": "Fernbedienung aktiv", "obc": "OpenBikeControl im Netzwerk", "front": "Zwift nach vorne holen",
        "autostart": "Mit Windows starten", "test": "Aktionen testen", "log": "Protokoll öffnen", "quit": "Beenden",
        "not_focused": "Zwift war nicht im Vordergrund", "not_running": "Zwift läuft nicht",
        "companion": "Zwift-Companion-Verbindung (Abzweige, Power-up)", "login": "Bei Zwift anmelden …",
        "logout": "Bei Zwift abmelden", "comp_linked": "Companion: mit dem Spiel verbunden",
        "comp_wait": "Companion: wartet auf Zwift", "comp_login": "Companion: erst bei Zwift anmelden",
        "comp_error": "Companion: {}",
        "login_title": "ZWindoor – Zwift-Anmeldung",
        "login_prompt": "Im Browser bei Zwift anmelden. Danach zeigt Zwift eine Fehlerseite auf launcher.zwift.com –\n"
                        "die ganze Adresse aus der Adresszeile kopieren und hier einfügen:",
        "login_ok": "Angemeldet. Die Companion-Verbindung startet jetzt.",
        "login_failed": "Anmeldung fehlgeschlagen: {}",
    },
}

TEST_ACTIONS = [  # (action, value) shown in the "Test actions" submenu
    (actions.STEER_LEFT, 1), (actions.STEER_RIGHT, 1), (actions.UP, 1), (actions.U_TURN, 1),
    (actions.EMOTE, actions.EMOTE_RIDE_ON), (actions.POWERUP, 1), (actions.EMOTE, actions.EMOTE_ELBOW),
    (actions.BELL, 1), (actions.CAMERA, actions.CAMERA_NEXT), (actions.SCREENSHOT, actions.SHOT_PHOTO),
]


def language() -> str:
    if sys.platform == "win32":
        import ctypes
        lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
        return "de" if lang_id & 0x3FF == 0x07 else "en"
    return "de" if (locale.getlocale()[0] or "").startswith("de") else "en"


def log_path() -> Path:
    return default_path().with_name("zwindoor.log")


def setup_logging() -> None:
    path = log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(path, maxBytes=512_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, handlers=[handler],
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")


# --- Autostart (HKCU Run key) ---

def autostart_command() -> str:
    exe = sys.executable if getattr(sys, "frozen", False) or "__compiled__" in globals() else \
        f'"{sys.executable}" "{os.path.abspath(__file__)}"'
    return exe if exe.startswith('"') else f'"{exe}"'


def set_autostart(on: bool) -> None:
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, APP, 0, winreg.REG_SZ, autostart_command())
        else:
            try:
                winreg.DeleteValue(key, APP)
            except FileNotFoundError:
                pass


def single_instance() -> bool:
    """False if another ZWindoor bridge already runs in this session (named mutex)."""
    if sys.platform != "win32":
        return True
    import ctypes
    ctypes.windll.kernel32.CreateMutexW(None, False, "Local\\ZWindoorBridge")
    return ctypes.windll.kernel32.GetLastError() != 183  # ERROR_ALREADY_EXISTS


# --- Icon ---

def make_icon(dot=None, size: int = 64):
    """Orange disc with an upward arrow; a small dot bottom right shows the state."""
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, size - 3, size - 3), fill=ORANGE)
    w = max(4, size // 10)
    c = size // 2
    d.line((c, size * 0.74, c, size * 0.28), fill="white", width=w)
    d.line((size * 0.3, size * 0.48, c, size * 0.26, size * 0.7, size * 0.48), fill="white", width=w, joint="curve")
    if dot:
        r = size // 5
        d.ellipse((size - 2 * r - 1, size - 2 * r - 1, size - 1, size - 1), fill=dot, outline=(30, 30, 30), width=2)
    return img


class TrayApp:
    def __init__(self, runner: BridgeRunner, lang: str | None = None, store: TokenStore | None = None) -> None:
        self.runner = runner
        self.store = store or TokenStore()
        if runner.token_provider is None:
            runner.token_provider = self.store.access_token
        self.lang = lang or language()
        self.t = TEXTS[self.lang]
        self.last = None  # engine.Event
        self.icon = None
        runner.on_event.append(self._event)
        runner.on_state.append(lambda _s: self.refresh())
        runner.on_status.append(self.refresh)

    # --- State texts (also used by the tests) ---

    def status_lines(self) -> list[str]:
        r, t = self.runner, self.t
        if r.error:
            lines = [t["bt_err"].format(r.error)]
        else:
            lines = [t["bt_ok"] if r.running else t["bt_start"]]
        lines.append(t["watch_on"] if r.watch_connected else t["watch_off"])
        s = r.zwift_state
        lines.append(t["zwift_front"] if s & State.ZWIFT_FOCUSED else
                     t["zwift_back"] if s & State.ZWIFT_RUNNING else t["zwift_off"])
        if s & State.OBC_CONNECTED:
            lines.append(t["obc_on"])
        comp = r.companion
        if r.config.companion and comp is not None:
            if comp.linked:
                lines.append(t["comp_linked"])
            elif comp.error == "no Zwift sign-in":
                lines.append(t["comp_login"])
            elif comp.error:
                lines.append(t["comp_error"].format(comp.error))
            else:
                lines.append(t["comp_wait"])
        if self.last:
            name = self.last.action_de if self.lang == "de" else self.last.action
            lines.append(t["last"].format(name, int(time.time() - self.last.when)))
        else:
            lines.append(t["last_none"])
        return lines

    def dot(self):
        if self.runner.error:
            return RED
        return GREEN if self.runner.watch_connected else GREY

    def _event(self, ev) -> None:
        self.last = ev
        if self.icon and ev.result in (Result.NOT_FOCUSED, Result.NOT_RUNNING):
            key = "not_focused" if ev.result == Result.NOT_FOCUSED else "not_running"
            try:
                self.icon.notify(self.t[key], APP)
            except Exception:
                pass
        self.refresh()

    # --- pystray ---

    def _toggle(self, name: str):
        def run(_icon, _item):
            value = not getattr(self.runner.config, name)
            if name == "autostart":
                set_autostart(value)
            self.runner.update_config(**{name: value})
        return run

    def _checked(self, name: str):
        return lambda _item: bool(getattr(self.runner.config, name))

    def menu(self):
        import pystray
        Item, Menu = pystray.MenuItem, pystray.Menu
        status = [Item(line, None, enabled=False) for line in self.status_lines()]
        tests = [Item(a.name_de if self.lang == "de" else a.name,
                      (lambda act, val: lambda _i, _it: self.runner.test_action(act, val))(act, val))
                 for act, val in TEST_ACTIONS if (a := actions.find(act, val))]
        return Menu(
            *status, Menu.SEPARATOR,
            Item(self.t["enabled"], self._toggle("enabled"), checked=self._checked("enabled")),
            Item(self.t["front"], self._toggle("bring_to_front"), checked=self._checked("bring_to_front")),
            Item(self.t["obc"], self._toggle("obc"), checked=self._checked("obc")),
            Item(self.t["companion"], self._toggle("companion"), checked=self._checked("companion")),
            Item(self.t["logout"] if self.store.signed_in() else self.t["login"], lambda _i, _it: self._login()),
            Item(self.t["autostart"], self._toggle("autostart"), checked=self._checked("autostart")),
            Menu.SEPARATOR,
            Item(self.t["test"], Menu(*tests)),
            Item(self.t["log"], lambda _i, _it: self._open_log()),
            Item(self.t["quit"], lambda icon, _it: self.quit(icon)),
        )

    def _login(self) -> None:
        if self.store.signed_in():
            self.store.clear()
            self.refresh()
            return

        def done(ok: bool) -> None:
            if ok:
                self.runner.update_config(companion=True)
            self.refresh()
        sign_in(self.store, self.t, done)

    def _open_log(self) -> None:
        if sys.platform == "win32":
            os.startfile(log_path())  # noqa: S606 (our own log file)
        else:
            subprocess.Popen(["xdg-open", str(log_path())])

    def refresh(self) -> None:
        if not self.icon:
            return
        self.icon.icon = make_icon(self.dot())
        self.icon.title = f"{APP} – " + " · ".join(self.status_lines()[:3])[:120]
        self.icon.menu = self.menu()
        try:
            self.icon.update_menu()
        except Exception:
            pass

    def quit(self, icon) -> None:
        try:
            self.runner.stop()
        finally:
            icon.stop()   # always leave, even if stopping the bridge failed

    def run(self) -> None:
        import pystray
        self.icon = pystray.Icon(APP, make_icon(self.dot()), f"{APP} {__version__}", self.menu())
        self.runner.start_thread()
        self.icon.run(setup=lambda icon: setattr(icon, "visible", True))


def main() -> int:
    setup_logging()
    if not single_instance():
        return 0
    logging.info("ZWindoor Bridge %s starting", __version__)
    app = TrayApp(BridgeRunner(Config.load()))
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
