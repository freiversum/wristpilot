"""Command line: `python -m zwindoor_bridge [--obc] [--dry-run] [--test ACTION]`."""

from __future__ import annotations

import argparse
import logging
import sys

from . import __version__, actions
from .config import Config
from .runner import BridgeRunner
from .sinks import RecordingSink


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="zwindoor-bridge", description="Garmin watch -> Zwift remote bridge")
    p.add_argument("--obc", action="store_true", help="also offer an OpenBikeControl controller on the network")
    p.add_argument("--dry-run", action="store_true", help="log actions instead of typing them")
    p.add_argument("--adapter", default=None, help="BlueZ adapter, e.g. hci1")
    p.add_argument("--list-actions", action="store_true", help="print the action table and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--version", action="version", version=__version__)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if a.list_actions:
        for act in actions.ACTIONS:
            val = "any" if act.value == actions.ANY else f"{act.value:#04x}"
            print(f"{act.id:#04x} {val:>5}  {act.key or '-':9} {act.name}")
        return 0
    config = Config.load()
    if a.obc:
        config.obc = True
    if a.adapter is not None:
        config.adapter = a.adapter
    runner = BridgeRunner(config, sink=RecordingSink() if a.dry_run else None)
    try:
        runner.run()
    except KeyboardInterrupt:
        pass
    return 1 if runner.error else 0


if __name__ == "__main__":
    sys.exit(main())
