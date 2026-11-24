import asyncio

import pytest

from zwindoor_bridge import actions, keys
from zwindoor_bridge.config import Config
from zwindoor_bridge.engine import PING, Engine
from zwindoor_bridge.obc import ObcServer, parse_app_info
from zwindoor_bridge.protocol import (MSG_ACK, MSG_STATE, Command, Result, State, decode_command,
                                      encode_command)
from zwindoor_bridge.sinks import RecordingSink


def cmd(action, value=1, seq=7):
    return encode_command(Command(seq, action, value))


def typed(sink):
    return [(kind, k) for kind, k in sink.events]


# --- protocol / tables ---

def test_command_roundtrip():
    assert decode_command(cmd(0x18, 3, 200)) == Command(200, 0x18, 3)
    assert decode_command(bytes((1, 0x50))) == Command(1, 0x50, 1)
    assert decode_command(b"\x01") is None


def test_every_action_has_a_known_key():
    for a in actions.ACTIONS:
        assert a.key == "camera" or keys.lookup(a.key), a


def test_find_prefers_exact_value():
    assert actions.find(actions.EMOTE, actions.EMOTE_WAVE).key == "f2"
    assert actions.find(actions.STEER_LEFT, 99).key == "left"
    assert actions.find(actions.EMOTE, 0x1E) is None
    assert actions.find(0x7F, 1) is None


def test_windows_scan_codes():
    assert keys.lookup("f10").scan == 0x44 and keys.lookup("f11").scan == 0x57
    assert keys.lookup("0").scan == 0x0B and keys.lookup("1").scan == 0x02
    assert keys.lookup("left").extended and not keys.lookup("space").extended


# --- engine ---

async def test_turn_left_types_left_arrow():
    sink = RecordingSink()
    ack = await Engine(sink, Config(hold_ms=1)).handle_write(cmd(actions.STEER_LEFT))
    assert ack == bytes((MSG_ACK, 7, Result.OK))
    assert typed(sink) == [("press", keys.KEYS["left"]), ("release", keys.KEYS["left"])]


async def test_ride_on_is_f3():
    sink = RecordingSink()
    await Engine(sink, Config(hold_ms=1)).handle_write(cmd(actions.EMOTE, actions.EMOTE_RIDE_ON))
    assert sink.events[0][1] == keys.KEYS["f3"]


async def test_not_running_and_not_focused():
    sink = RecordingSink(running=False, focused=False)
    e = Engine(sink, Config(hold_ms=1))
    assert (await e.handle_write(cmd(actions.POWERUP)))[2] == Result.NOT_RUNNING
    sink.running = True
    e.config.bring_to_front = False
    assert (await e.handle_write(cmd(actions.POWERUP)))[2] == Result.NOT_FOCUSED
    assert sink.events == []
    e.config.bring_to_front = True
    assert (await e.handle_write(cmd(actions.POWERUP)))[2] == Result.OK


async def test_disabled_and_unknown():
    e = Engine(RecordingSink(), Config(enabled=False))
    assert (await e.handle_write(cmd(actions.POWERUP)))[2] == Result.DISABLED
    e.config.enabled = True
    assert (await e.handle_write(cmd(0x7E)))[2] == Result.UNKNOWN_ACTION
    assert (await e.handle_write(b"\x05"))[2] == Result.MALFORMED


async def test_key_override_and_unmapped():
    sink = RecordingSink()
    e = Engine(sink, Config(hold_ms=1, keys={"straight-on": ""}))
    assert (await e.handle_write(cmd(actions.UP)))[2] == Result.OK
    assert sink.events == []
    e.config.keys = {"straight-on": "right"}
    await e.handle_write(cmd(actions.UP))
    assert sink.events[0][1] == keys.KEYS["right"]


async def test_camera_cycles_and_follows_direct_views():
    sink = RecordingSink()
    e = Engine(sink, Config(hold_ms=1))
    for _ in range(2):
        await e.handle_write(cmd(actions.CAMERA, actions.CAMERA_NEXT))
    await e.handle_write(cmd(actions.CAMERA, actions.CAMERA_NEXT + 10))  # view 10 = key 0
    await e.handle_write(cmd(actions.CAMERA, actions.CAMERA_NEXT))       # wraps to view 1
    pressed = [k for kind, k in sink.events if kind == "press"]
    assert pressed == [keys.KEYS["2"], keys.KEYS["3"], keys.KEYS["0"], keys.KEYS["1"]]


async def test_ping_answers_state_and_marks_watch():
    e = Engine(RecordingSink(), Config())
    assert not e.watch_connected
    reply = await e.handle_write(bytes((0, PING, 0)))
    assert reply[0] == MSG_STATE
    assert State(reply[1]) & State.ZWIFT_FOCUSED and State(reply[1]) & State.ENABLED
    assert e.watch_connected


async def test_poll_state_only_on_change():
    sink = RecordingSink()
    e = Engine(sink, Config())
    assert await e.poll_state() is not None
    assert await e.poll_state() is None
    sink.focused = False
    assert State((await e.poll_state())[1]) & State.ZWIFT_FOCUSED == 0


async def test_blocked_display_does_not_stall(monkeypatch):
    import threading
    from zwindoor_bridge import engine as eng
    monkeypatch.setattr(eng, "SINK_TIMEOUT", 0.2)
    gate = threading.Event()

    class Stuck(RecordingSink):
        def press(self, key):
            gate.wait(5)   # like XTest waiting for Plasma's consent dialog
    e = Engine(Stuck(), Config(hold_ms=1))
    ack = await asyncio.wait_for(e.handle_write(cmd(actions.POWERUP)), 1)
    assert ack[2] == Result.OUTPUT_FAILED and e.blocked
    gate.set()
    e.close()


# --- OpenBikeControl ---

def test_parse_app_info_spec_example():
    raw = bytes([0x04, 0x01, 0x05]) + b"zwift" + bytes([0x06]) + b"1.52.0" + bytes([0x04, 0x01, 0x02, 0x10, 0x14])
    info, used = parse_app_info(raw + b"\x03")
    assert (info.app_id, info.version, info.buttons, used) == ("zwift", "1.52.0", [1, 2, 0x10, 0x14], len(raw))
    assert parse_app_info(raw[:-2]) is None


async def test_obc_server_sends_press_and_release():
    haptics = []
    srv = ObcServer(0, on_haptic=haptics.append)
    await srv.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
        assert await reader.readexactly(3) == bytes((0x02, 0xFF, 0x00))  # status on connect
        writer.write(bytes([0x04, 0x01, 0x03]) + b"app" + bytes([0x01]) + b"1" + bytes([0x00]))
        writer.write(bytes((0x03, 0x02, 0x00, 0x00)))
        await writer.drain()
        for _ in range(50):
            if srv.clients and srv.clients[0].info.app_id and haptics:
                break
            await asyncio.sleep(0.01)
        assert srv.clients[0].info.app_id == "app" and haptics == [0x02]
        assert await srv.button(actions.STEER_LEFT, 1)
        assert await reader.readexactly(6) == bytes((0x01, 0x18, 0x01, 0x01, 0x18, 0x00))
        writer.close()
    finally:
        await srv.stop()


async def test_engine_obc_counts_as_delivered_without_zwift():
    srv = ObcServer(0)
    await srv.start()
    try:
        reader, writer = await asyncio.open_connection("127.0.0.1", srv.port)
        await reader.readexactly(3)
        for _ in range(50):
            if srv.clients:
                break
            await asyncio.sleep(0.01)
        e = Engine(RecordingSink(running=False, focused=False), Config(obc=True, hold_ms=1), obc=srv)
        assert (await e.handle_write(cmd(actions.POWERUP)))[2] == Result.OK
        assert await reader.readexactly(3) == bytes((0x01, 0x50, 0x01))
        writer.close()
    finally:
        await srv.stop()


# --- config ---

def test_config_roundtrip(tmp_path):
    p = tmp_path / "c.json"
    Config(obc=True, keys={"u-turn": "down"}).save(p)
    c = Config.load(p)
    assert c.obc and c.keys == {"u-turn": "down"}
    p.write_text('{"obc": false, "unknown": 1}')
    assert Config.load(p).obc is False
    assert Config.load(tmp_path / "missing.json") == Config()


def test_slugs_are_unique():
    slugs = [actions.slug(a) for a in actions.ACTIONS]
    assert len(slugs) == len(set(slugs))
    assert "ride-on" in slugs and "straight-on" in slugs
