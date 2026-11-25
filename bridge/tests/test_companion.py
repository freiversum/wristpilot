"""Companion link (phase 4): protobuf codec, game messages, commands, a fake game over TCP."""

import asyncio
import struct

import pytest

from wristpilot_bridge import actions, companion as cp, pb
from wristpilot_bridge.config import Config
from wristpilot_bridge.engine import Engine
from wristpilot_bridge.protocol import Result, State
from wristpilot_bridge.sinks import RecordingSink


# --- protobuf ---

def test_pb_roundtrip_nested_and_repeated():
    data = pb.message({1: 42, 2: [{1: 7, 2: 22, 10: 1010}, {1: 8}], 10: 3, 4: "hi", 5: True})
    f = pb.decode(data)
    assert pb.first(f, 1) == 42 and pb.first(f, 10) == 3 and pb.text(f, 4) == "hi" and pb.first(f, 5) == 1
    cmds = [pb.decode(c) for c in f[2]]
    assert pb.first(cmds[0], 10) == 1010 and pb.first(cmds[1], 1) == 8


def test_pb_negative_and_truncated():
    assert pb.signed(pb.first(pb.decode(pb.message({1: -1})), 1)) == -1
    with pytest.raises(pb.DecodeError):
        pb.decode(b"\x0a\x05ab")


# --- mapping ---

def test_command_mapping():
    assert cp.command_for(actions.STEER_LEFT, 1) == {2: 22, 10: 1010}
    assert cp.command_for(actions.UP, 1) == {2: 22, 10: 1011}
    assert cp.command_for(actions.U_TURN, 1) == {2: 23, 10: 23}
    assert cp.command_for(actions.EMOTE, actions.EMOTE_RIDE_ON)[2] == 6
    assert cp.command_for(actions.POWERUP, 1)[2] == 21
    assert cp.command_for(actions.HUD, 1, hud_on=True) == {2: 22, 10: 1081}
    assert cp.command_for(actions.HARDER, 1) is None          # workout: keyboard only
    assert cp.command_for(actions.CAMERA, actions.CAMERA_NEXT + 3) is None


def test_turn_bit_from_titles():
    assert cp.turn_bit("TURN LEFT", 9) == cp.F_LEFT
    assert cp.turn_bit("Rechts abbiegen", 9) == cp.F_RIGHT
    assert cp.turn_bit("GO STRAIGHT", 9) == cp.F_STRAIGHT
    assert cp.turn_bit("", 2) == cp.F_RIGHT and cp.turn_bit("", 7) == 0


# --- game messages ---

def game_msg(*commands):
    return pb.message({1: 5, 3: 1234, 11: list(commands)})


def link():
    l = cp.CompanionLink(lambda: "token")
    l.state = cp.GameState(linked=True)
    return l


def test_power_up_set_and_cleared():
    l = link()
    l.handle_game_message(game_msg({2: cp.SET_POWER_UP, 3: 2, 4: "DRAFT"}))   # powerUpId-1 = 1 DRAFTBOOST
    assert l.state.powerup == 2 and l.state.flags() & cp.F_POWERUP
    l.handle_game_message(game_msg({2: cp.ACTIVATE_POWER_UP}))
    assert l.state.powerup == cp.PU_NONE
    l.handle_game_message(game_msg({2: cp.SET_POWER_UP, 3: 12}))             # unknown type
    assert l.state.powerup == cp.PU_UNKNOWN


def test_legacy_turn_buttons():
    l = link()
    l.handle_game_message(game_msg({2: cp.CUSTOMIZE_ACTION_BUTTON, 8: 1010, 9: 1, 10: "TURN LEFT"},
                                   {2: cp.CUSTOMIZE_ACTION_BUTTON, 8: 1011, 9: 1}), now=100)
    f = l.state.flags(now=101)
    assert f & cp.F_JUNCTION and f & cp.F_LEFT and f & cp.F_STRAIGHT and not f & cp.F_RIGHT
    l.handle_game_message(game_msg({2: cp.CUSTOMIZE_ACTION_BUTTON, 8: 1010, 9: 0}), now=102)
    assert not l.state.flags(now=103) & cp.F_LEFT
    assert not l.state.flags(now=200) & cp.F_JUNCTION          # expires without updates


def test_intersection_ahead_packet():
    l = link()
    inter = {1: [{1: 0, 3: "Turn Left", 4: True}, {1: 2, 3: "Turn Right", 4: False}, {1: 1, 3: "Go Straight", 4: True}]}
    l.handle_game_message(game_msg({2: cp.PACKET, 21: {1: cp.INTERSECTION_AHEAD, 7: inter}}), now=10)
    f = l.state.flags(now=10)
    assert f & cp.F_LEFT and f & cp.F_STRAIGHT and not f & cp.F_RIGHT
    assert l.state.message(now=10)[0] == 0x04


def test_ride_ons_counted_and_reset_after_ride():
    l = link()
    l.handle_game_message(game_msg({2: cp.PACKET, 21: {1: cp.GAME_SESSION_INFO, 4: {2: 99}}}))
    for _ in range(3):
        l.handle_game_message(game_msg({2: cp.SOCIAL_PLAYER_ACTION, 16: {1: 77, 3: 2}}))
    l.handle_game_message(game_msg({2: cp.SOCIAL_PLAYER_ACTION, 16: {1: 77, 3: 1, 6: "hello"}}))
    assert l.state.ride_ons == 3 and l.state.message()[3:] == bytes((3, 0))
    l.handle_game_message(game_msg({2: cp.PACKET, 21: {1: cp.GAME_SESSION_INFO, 4: {2: 0}}}))
    assert l.state.ride_ons == 0


# --- fake game over TCP ---

class FakeApi:
    ZwiftApiError = cp.zwiftapi.ZwiftApiError

    def __init__(self):
        self.registered = []

    def athlete_id(self, token):
        assert token == "token"
        return 1234

    def register_phone(self, token, address, port):
        self.registered.append((address, port))


async def read_frame(reader):
    size = struct.unpack(">I", await reader.readexactly(4))[0]
    return pb.decode(await reader.readexactly(size))


async def test_fake_game_pairs_receives_state_and_commands():
    api = FakeApi()
    changes = []
    l = cp.CompanionLink(lambda: "token", port=0, address="127.0.0.1", api=api, on_change=lambda: changes.append(1))
    await l.start()
    try:
        for _ in range(100):
            if api.registered:
                break
            await asyncio.sleep(0.01)
        assert api.registered == [("127.0.0.1", l.port)] and l.athlete_id == 1234
        reader, writer = await asyncio.open_connection("127.0.0.1", l.port)
        frames = [await read_frame(reader) for _ in range(4)]
        assert all(pb.first(f, 1) == 1234 for f in frames)
        assert [pb.first(f, 10) for f in frames] == [1, 2, 3, 4]
        cmds = [pb.decode(f[2][0]) for f in frames]
        assert [pb.first(c, 2) for c in cmds] == [29, 28, 29, 29] and pb.first(cmds[1], 19) == 1234
        assert l.linked

        msg = game_msg({2: cp.SET_POWER_UP, 3: 6})                     # AERO
        writer.write(struct.pack(">I", len(msg)) + msg)
        await writer.drain()
        for _ in range(100):
            if l.state.powerup:
                break
            await asyncio.sleep(0.01)
        assert l.state.powerup == 3

        e = Engine(RecordingSink(running=False, focused=False), Config(hold_ms=1), companion=l)
        assert State.COMPANION in await e.state()
        ack = await e.handle_write(bytes((5, actions.STEER_LEFT, 1)))
        assert ack[2] == Result.OK
        while True:                                                    # skip heartbeats
            f = await asyncio.wait_for(read_frame(reader), 3)
            if 2 in f:
                break
        turn = pb.decode(f[2][0])
        assert (pb.first(turn, 2), pb.first(turn, 10)) == (22, 1010)

        # workout keys have no Companion command: keyboard path (Zwift not running here)
        ack = await e.handle_write(bytes((6, actions.HARDER, 1)))
        assert ack[2] == Result.NOT_RUNNING

        writer.close()
        for _ in range(100):
            if not l.linked:
                break
            await asyncio.sleep(0.01)
        assert not l.linked
        e.close()
    finally:
        await l.stop()


async def test_no_token_reports_error():
    l = cp.CompanionLink(lambda: None, port=0, address="127.0.0.1", api=FakeApi())
    await l.start()
    try:
        for _ in range(100):
            if l.error:
                break
            await asyncio.sleep(0.01)
        assert l.error == "no Zwift sign-in" and not l.registered
    finally:
        await l.stop()


# --- capture for the first real ride ---

def test_capture_file_and_dump_tool(tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    path = tmp_path / "capture.jsonl"
    l = cp.CompanionLink(lambda: "token", port=0, address="127.0.0.1", api=FakeApi(), capture=path)
    junction = {1: [{1: 0, 3: "TURN LEFT", 4: 1}, {1: 2, 3: "TURN RIGHT", 4: 0}]}
    for cmd in ({2: cp.PACKET, 21: {1: cp.INTERSECTION_AHEAD, 7: junction}},
                {2: cp.CUSTOMIZE_ACTION_BUTTON, 8: 1010, 9: 1},
                {2: cp.SOCIAL_PLAYER_ACTION, 16: {3: cp.RIDE_ON_SOCIAL}}):
        l._capture("game", game_msg(cmd))
    l._capture("bridge", pb.message({1: 1234, 2: [{1: 1, 2: 22, 10: 1010}], 10: 1}))
    lines = [json.loads(s) for s in path.read_text().splitlines()]
    assert [r["dir"] for r in lines] == ["game", "game", "game", "bridge"]

    tool = Path(__file__).resolve().parents[1] / "tools" / "companion_dump.py"
    out = subprocess.run([sys.executable, str(tool), str(path), "--summary"],
                         capture_output=True, text=True, check=True).stdout
    assert "INTERSECTION_AHEAD: 1" in out and "action button 1010: 1" in out
    assert f"social type {cp.RIDE_ON_SOCIAL}: 1" in out
    assert "'TURN LEFT': 1" in out and "Enabled values seen: [0, 1]" in out
