"""Bridge settings, stored as JSON (Windows: %APPDATA%\\Wristpilot, Linux: ~/.config/wristpilot).

Tretlager passes its own path so that the setting lives with its other state.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path


def default_path() -> Path:
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "Wristpilot"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "wristpilot"
    return base / "config.json"


@dataclass
class Config:
    enabled: bool = True            # master switch: when off, every command is answered with DISABLED
    keyboard: bool = True           # type Zwift shortcuts
    obc: bool = False               # also offer the watch as an OpenBikeControl controller on the network
    obc_port: int = 36870
    bring_to_front: bool = True     # activate the Zwift window if another window has the focus
    hold_ms: int = 40               # time between key press and release
    keys: dict[str, str] = field(default_factory=dict)  # action slug -> key name ("" = no key)
    companion: bool = False         # act as Zwift Companion: game state to the watch, commands without keyboard
    companion_port: int = 21587     # TCP port the game connects to (Zwift's default for the Companion app)
    companion_capture: str = ""     # file that records every Companion frame (JSON Lines), empty = off
    adapter: str = ""               # BlueZ adapter (hciN), empty = default
    autostart: bool = False         # Windows: start with the user session

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or default_path()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return cls()
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known})

    def save(self, path: Path | None = None) -> None:
        path = path or default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        tmp.replace(path)
