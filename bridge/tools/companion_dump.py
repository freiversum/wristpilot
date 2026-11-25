#!/usr/bin/env python3
"""Read a Companion capture (config `companion_capture`, JSON Lines) and print what the game sent.

    python tools/companion_dump.py capture.jsonl            # summary and every non-trivial frame
    python tools/companion_dump.py capture.jsonl --summary  # only the counts

The summary answers the open questions of the first real ride (BACKLOG, "Companion link"):
which command types and packet types the game sends, whether action buttons 1010-1012 and
IntersectionAhead show up, which titles/directions/enabled flags junction options carry, and
whether received Ride Ons arrive as SOCIAL_PLAYER_ACTION.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from wristpilot_bridge import companion as cp, pb  # noqa: E402

GC_NAMES = {cp.CLEAR_POWER_UP: "CLEAR_POWER_UP", cp.SET_POWER_UP: "SET_POWER_UP",
            cp.ACTIVATE_POWER_UP: "ACTIVATE_POWER_UP", cp.CUSTOMIZE_ACTION_BUTTON: "CUSTOMIZE_ACTION_BUTTON",
            cp.SOCIAL_PLAYER_ACTION: "SOCIAL_PLAYER_ACTION", cp.PACKET: "PACKET"}
PACKET_NAMES = {cp.GAME_SESSION_INFO: "GAME_SESSION_INFO", cp.CLIENT_INFO: "CLIENT_INFO",
                cp.INTERSECTION_AHEAD: "INTERSECTION_AHEAD", cp.CLIENT_ACTION: "CLIENT_ACTION"}


def tree(data: bytes, depth: int = 0) -> object:
    """Best-effort protobuf tree: nested messages where they parse, text where printable, else hex."""
    if depth > 8:
        return data.hex()
    try:
        fields = pb.decode(data)
    except pb.DecodeError:
        fields = None
    if fields:
        return {k: [tree(v, depth + 1) if isinstance(v, bytes) else v for v in vs] for k, vs in fields.items()}
    try:
        s = data.decode("utf-8")
        if s.isprintable():
            return s
    except UnicodeDecodeError:
        pass
    return data.hex()


def describe(cmd: dict, stats: Counter, junctions: list) -> str:
    """One game command as a short label; collects what the summary needs."""
    t = pb.first(cmd, cp.GC_TYPE, 0)
    name = GC_NAMES.get(t, f"type {t}")
    stats[name] += 1
    if t == cp.CUSTOMIZE_ACTION_BUTTON:
        sub = pb.first(cmd, cp.GC_SUBCOMMAND, 0)
        stats[f"action button {sub}"] += 1
        return f"{name} sub={sub} pos={pb.first(cmd, cp.GC_POSITION, 0)} hide={pb.first(cmd, cp.GC_HIDE, 0)}"
    if t == cp.SOCIAL_PLAYER_ACTION:
        social = pb.decode(pb.first(cmd, cp.GC_SOCIAL, b""))
        kind = pb.first(social, 3, 0)
        stats[f"social type {kind}"] += 1
        return f"{name} social={tree(pb.first(cmd, cp.GC_SOCIAL, b''))}"
    if t == cp.PACKET:
        p = pb.decode(pb.first(cmd, cp.GC_PACKET, b""))
        kind = pb.first(p, cp.P_TYPE, 0)
        pname = PACKET_NAMES.get(kind, f"packet {kind}")
        stats[pname] += 1
        if kind == cp.INTERSECTION_AHEAD:
            inter = pb.decode(pb.first(p, cp.P_INTERSECTION, b""))
            opts = []
            for raw in inter.get(1, []):
                o = pb.decode(raw)
                opts.append((pb.text(o, 3), pb.first(o, 1, None), pb.first(o, 4, None)))
            junctions.append(opts)
            return f"{pname} options (title, direction, enabled)={opts}"
        return f"{pname} {tree(pb.first(cmd, cp.GC_PACKET, b''))}"
    return f"{name} " + str({k: [tree(v) if isinstance(v, bytes) else v for v in vs] for k, vs in cmd.items()})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("capture", type=Path)
    ap.add_argument("--summary", action="store_true", help="only print the counts")
    args = ap.parse_args()

    stats: Counter = Counter()
    junctions: list = []
    frames = {"game": 0, "bridge": 0}
    for n, line in enumerate(args.capture.read_text(encoding="utf-8").splitlines(), 1):
        try:
            rec = json.loads(line)
            data = bytes.fromhex(rec["hex"])
            msg = pb.decode(data)
        except (ValueError, KeyError, pb.DecodeError) as e:
            print(f"line {n}: unreadable ({e})", file=sys.stderr)
            continue
        frames[rec["dir"]] = frames.get(rec["dir"], 0) + 1
        stamp = time.strftime("%H:%M:%S", time.localtime(rec["t"])) + f".{int(rec['t'] * 1000) % 1000:03d}"
        if rec["dir"] == "bridge":
            if not args.summary:
                for raw in msg.get(2, []):
                    print(f"{stamp} -> game  {tree(raw)}")
            continue
        for raw in msg.get(cp.G_COMMANDS, []):
            label = describe(pb.decode(raw), stats, junctions)
            if not args.summary:
                print(f"{stamp} <- game  {label}")

    print(f"\nFrames: {frames.get('game', 0)} from the game, {frames.get('bridge', 0)} commands from the bridge")
    for key, count in sorted(stats.items()):
        print(f"  {key}: {count}")
    titles = Counter(t for opts in junctions for t, _d, _e in opts)
    if titles:
        print("Junction option titles:", dict(titles))
        print("Directions per title:",
              {t: sorted({d for opts in junctions for tt, d, _e in opts if tt == t}, key=str) for t in titles})
        print("Enabled values seen:", sorted({e for opts in junctions for _t, _d, e in opts}, key=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
