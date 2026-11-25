"""Virtual steering device (Sterzo over DIRCON) and the lane-change action."""

import asyncio
import struct

from wristpilot_bridge import actions, dircon, steering
from wristpilot_bridge.config import Config
from wristpilot_bridge.engine import Engine
from wristpilot_bridge.protocol import Command, Result, encode_command
from wristpilot_bridge.sinks import RecordingSink

PORT = 36989


def test_lane_pulse_rises_and_returns_to_straight():
    s = steering.SteeringServer(PORT, angle=20.0, duration=0.7)
    s.lane(-1)
    now = steering.time.monotonic()
    a = 0.0
    for i in range(1, 6):          # 0.5 s into the pulse
        a = s.step(0.1, now + i * 0.1)
    assert -20.0 <= a < -18.0
    for i in range(6, 20):         # pulse over, back to straight
        a = s.step(0.1, now + i * 0.1)
    assert a == 0.0


def test_same_direction_extends_other_replaces():
    s = steering.SteeringServer(PORT)
    s.lane(1)
    first = s._until
    s.lane(1)
    assert s._until > first and s._direction == 1
    s.lane(-1)
    assert s._direction == -1


def _pkt(msg, payload=b"", seq=1):
    return dircon.Packet(msg, seq, payload=payload).encode()


async def _read_packet(reader):
    head = await reader.readexactly(6)
    _v, msg, seq, resp, n = dircon.HEADER.unpack(head)
    return msg, resp, await reader.readexactly(n)


def test_dircon_pairing_lane_and_engine_result():
    async def run():
        s = steering.SteeringServer(PORT, angle=20.0, duration=0.5)
        await s.start()
        engine = Engine(RecordingSink(), Config(), steering=s)
        try:
            # not paired yet: the watch hears "steering not paired"
            ack = await engine.handle_write(encode_command(Command(1, actions.LANE, actions.LANE_LEFT)))
            assert ack[2] == Result.NO_STEERING
            reader, writer = await asyncio.open_connection("127.0.0.1", PORT)
            writer.write(_pkt(dircon.MSG_DISCOVER_SERVICES))
            msg, resp, payload = await _read_packet(reader)
            assert resp == 0 and dircon.uuid_from_bytes(payload) == steering.STERZO
            writer.write(_pkt(dircon.MSG_ENABLE_NOTIFICATIONS, dircon.uuid_bytes(steering.ANGLE) + b"\x01", 2))
            await writer.drain()
            await _read_packet(reader)
            ack = await engine.handle_write(encode_command(Command(2, actions.LANE, actions.LANE_RIGHT)))
            assert ack[2] == Result.OK
            angles = []
            for _ in range(6):
                msg, _resp, payload = await _read_packet(reader)
                if msg == dircon.MSG_NOTIFICATION:
                    angles.append(struct.unpack("<f", payload[16:20])[0])
            assert max(angles) > 5.0
            writer.close()
        finally:
            engine.close()
            await s.stop()
    asyncio.run(run())


def test_hash_reference():
    for seed in (0, 7, 0x12345678, 0xFFFFFFFF):
        n = seed % 11
        rot = ((seed << n) | (seed >> (32 - n))) & 0xFFFFFFFF if n else seed
        assert steering.sterzo_hash(seed) == ((seed + 0x16FA5717) & 0xFFFFFFFF) ^ rot
