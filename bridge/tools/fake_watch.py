"""Pretend to be the watch: scan for the Wristpilot service, connect, send commands, print the answers.

    python tools/fake_watch.py                  # left, right, ride on, power-up + pings
    python tools/fake_watch.py --count 50       # latency series with "left"

Needs bleak and a second Bluetooth adapter/computer (an adapter cannot connect to itself).
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import sys
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wristpilot_bridge import actions, protocol  # noqa: E402

DEMO = [(actions.STEER_LEFT, 1), (actions.STEER_RIGHT, 1), (actions.EMOTE, actions.EMOTE_RIDE_ON),
        (actions.POWERUP, 1), (actions.CAMERA, actions.CAMERA_NEXT), (0x7E, 1)]


async def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--count", type=int, default=0)
    p.add_argument("--timeout", type=float, default=15)
    p.add_argument("--address", help="connect to this address instead of scanning for the service")
    a = p.parse_args()
    print("scanning …")
    if a.address:
        dev = await BleakScanner.find_device_by_address(a.address, timeout=a.timeout)
    else:
        dev = await BleakScanner.find_device_by_filter(
            lambda d, adv: protocol.SERVICE_UUID in [u.lower() for u in adv.service_uuids], timeout=a.timeout)
    if not dev:
        print("no Wristpilot bridge found")
        return 1
    print(f"found {dev.name} {dev.address}")
    replies: asyncio.Queue = asyncio.Queue()
    async with BleakClient(dev) as c:
        info = await c.read_gatt_char(protocol.INFO_UUID)
        print("info:", info.decode())
        await c.start_notify(protocol.STATUS_UUID, lambda _h, d: replies.put_nowait((time.perf_counter(), bytes(d))))

        async def send(seq, action, value, response=True):
            t0 = time.perf_counter()
            await c.write_gatt_char(protocol.COMMAND_UUID, bytes((seq, action, value)), response=response)
            while True:
                t, data = await asyncio.wait_for(replies.get(), 3)
                if data[0] == protocol.MSG_ACK and data[1] == seq or action == 0 and data[0] == protocol.MSG_STATE:
                    return data, (t - t0) * 1000

        data, ms = await send(0, 0, 0)
        print(f"ping -> state {protocol.State(data[1])!r} ({ms:.0f} ms)")
        if a.count:
            times = []
            for i in range(a.count):
                _, ms = await send((i + 1) & 0xFF, actions.STEER_LEFT, 1, response=False)
                times.append(ms)
            print(f"{a.count}x left without response: median {statistics.median(times):.0f} ms, "
                  f"max {max(times):.0f} ms")
            return 0
        for i, (act, val) in enumerate(DEMO, 1):
            data, ms = await send(i, act, val)
            found = actions.find(act, val)
            print(f"{found.name if found else hex(act):18} -> {protocol.Result(data[2]).name:15} {ms:5.0f} ms")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
