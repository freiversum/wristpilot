"""Tray logic without Windows and without a tray: texts, icon, menu wiring."""

import pytest

from zwindoor_bridge import actions
from zwindoor_bridge.config import Config
from zwindoor_bridge.engine import Event
from zwindoor_bridge.protocol import Result, State
from zwindoor_bridge.runner import BridgeRunner
from zwindoor_tray import TEST_ACTIONS, TrayApp, make_icon


class FakeRunner(BridgeRunner):
    def __init__(self):
        super().__init__(Config())
        self.saved = {}

    def update_config(self, **changes):
        self.saved.update(changes)
        for k, v in changes.items():
            setattr(self.config, k, v)


def test_status_lines_german_and_english():
    r = FakeRunner()
    app = TrayApp(r, lang="de")
    assert app.status_lines() == ["Bluetooth: startet …", "Uhr: nicht verbunden", "Zwift: läuft nicht",
                                  "Letzte Aktion: –"]
    r.running = True
    r.error = ""
    app.last = Event(0, "Ride On", "Ride On", Result.OK, 3)
    assert TrayApp(r, lang="en").status_lines()[0] == "Bluetooth: ready"
    r.error = "no adapter"
    assert app.status_lines()[0] == "Bluetooth: no adapter"


def test_zwift_state_line(monkeypatch):
    r = FakeRunner()
    monkeypatch.setattr(BridgeRunner, "zwift_state", property(lambda self: State.ZWIFT_RUNNING))
    assert TrayApp(r, lang="de").status_lines()[2] == "Zwift: läuft im Hintergrund"


def test_icon_draws():
    img = make_icon((47, 191, 113), size=64)
    assert img.size == (64, 64) and img.getpixel((32, 4))[3] == 255


def test_test_actions_exist():
    assert all(actions.find(a, v) for a, v in TEST_ACTIONS)


def test_toggle_updates_config():
    pytest.importorskip("pystray")
    r = FakeRunner()
    app = TrayApp(r, lang="de")
    app._toggle("obc")(None, None)
    assert r.saved == {"obc": True}


def test_token_store_refresh(tmp_path, monkeypatch):
    import time
    from zwindoor_bridge import zwiftapi
    from zwiftlogin import TokenStore
    store = TokenStore(tmp_path / "t.bin")
    assert store.access_token() is None and not store.signed_in()
    now = int(time.time())
    store.save({"access_token": "a1", "refresh_token": "r1", "obtained_at": now, "expires_in": 3600,
                "refresh_expires_in": 86400})
    assert store.access_token() == "a1" and store.signed_in()
    store.save({"access_token": "old", "refresh_token": "r1", "obtained_at": now - 7200, "expires_in": 3600,
                "refresh_expires_in": 86400})
    monkeypatch.setattr(zwiftapi, "refresh", lambda tok: {"access_token": "a2", "refresh_token": "r2",
                        "obtained_at": now, "expires_in": 3600, "refresh_expires_in": 86400})
    assert store.access_token() == "a2" and store.load()["refresh_token"] == "r2"
    store.clear()
    assert store.load() is None


def test_companion_status_line():
    r = FakeRunner()
    app = TrayApp(r, lang="de", store=type("S", (), {"access_token": lambda self: None, "signed_in": lambda self: False})())
    r.config.companion = True

    class C:
        linked, error = False, "no Zwift sign-in"
    r.companion = C()
    assert "Companion: erst bei Zwift anmelden" in app.status_lines()
    C.error = ""
    C.linked = True
    assert "Companion: mit dem Spiel verbunden" in app.status_lines()


def test_parse_redirect():
    from zwindoor_bridge import zwiftapi
    url = "https://launcher.zwift.com/launcher?state=abc&session_state=x&code=XYZ"
    assert zwiftapi.parse_redirect(url, "abc") == "XYZ"
    with pytest.raises(zwiftapi.ZwiftApiError):
        zwiftapi.parse_redirect(url, "other")


def test_bluetooth_setup_items_only_on_error():
    pytest.importorskip("pystray")
    r = FakeRunner()
    app = TrayApp(r, lang="en")
    texts = [item.text for item in app.menu().items]
    assert "Set up a Bluetooth adapter …" not in texts
    r.error = "no USB Bluetooth adapter with the WinUSB driver found"
    texts = [item.text for item in app.menu().items]
    assert "Set up a Bluetooth adapter …" in texts and "Start Bluetooth again" in texts


def test_test_actions_greyed_out_without_bluetooth():
    pytest.importorskip("pystray")
    r = FakeRunner()
    app = TrayApp(r, lang="en")

    def test_item():
        return next(item for item in app.menu().items if item.text == "Test actions")
    assert not test_item().enabled
    r.running = True
    assert test_item().enabled
