"""Action table: OpenBikeControl button IDs -> Zwift keyboard shortcuts.

The watch sends OpenBikeControl (OBC) button IDs so that the same command works for Zwift
(keyboard) and for trainer apps that speak OBC. Values 0x02-0x1F of Emote/Camera are
"app-specific" in OBC; ZWindoor uses them as listed here.

Zwift shortcuts: Zwift Insider, "Zwift Keyboard Shortcuts", as of 2025-08-04.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# OpenBikeControl button IDs (openbikecontrol.org/protocol, v1)
UP = 0x10
STEER_LEFT = 0x18
STEER_RIGHT = 0x19
EMOTE = 0x20
SCREENSHOT = 0x24
HARDER = 0x30
EASIER = 0x31
SKIP_INTERVAL = 0x32
U_TURN = 0x37
CAMERA = 0x40
HUD = 0x44
POWERUP = 0x50
BELL = 0x80  # app-specific range 0x80-0x9F

# Emote values (OBC: 0x01 = cycle, 0x02-0x1F app-specific)
EMOTE_RIDE_ON = 0x01
EMOTE_ELBOW = 0x02
EMOTE_WAVE = 0x03
EMOTE_HAMMER = 0x05
EMOTE_NICE = 0x06
EMOTE_TOAST = 0x07

SHOT_PHOTO = 0x01
SHOT_VIDEO = 0x02

CAMERA_NEXT = 0x01  # 0x02..0x0B = view 1..10
ANY = -1


@dataclass(frozen=True)
class Action:
    id: int
    value: int        # ANY = every value
    key: str          # logical key name, see keys.py; "" = no keyboard equivalent
    name: str         # English, used in logs and the Tretlager page
    name_de: str


ACTIONS: tuple[Action, ...] = (
    Action(STEER_LEFT, ANY, "left", "Turn left", "Links abbiegen"),
    Action(STEER_RIGHT, ANY, "right", "Turn right", "Rechts abbiegen"),
    # Since mid-2025 the up arrow opens Zwift's action menu; going straight is the default at a
    # junction when no turn is chosen. The key stays configurable (config.py, "keys").
    Action(UP, ANY, "up", "Straight on", "Geradeaus"),
    Action(U_TURN, ANY, "down", "U-turn", "U-Turn"),
    Action(POWERUP, ANY, "space", "Power-up", "Power-up"),
    Action(EMOTE, EMOTE_RIDE_ON, "f3", "Ride On", "Ride On"),
    Action(EMOTE, EMOTE_ELBOW, "f1", "Elbow flick", "Ellbogen-Wink"),
    Action(EMOTE, EMOTE_WAVE, "f2", "Wave", "Winken"),
    Action(EMOTE, EMOTE_HAMMER, "f4", "Hammer Time", "Hammer Time"),
    Action(EMOTE, EMOTE_NICE, "f5", "Nice", "Nice"),
    Action(EMOTE, EMOTE_TOAST, "f7", "I'm toast", "I'm toast"),
    Action(BELL, ANY, "f8", "Bell", "Klingel"),
    Action(SCREENSHOT, SHOT_PHOTO, "f10", "Photo", "Foto"),
    Action(SCREENSHOT, SHOT_VIDEO, "f9", "Video clip", "Video-Clip"),
    Action(CAMERA, CAMERA_NEXT, "camera", "Next camera view", "Nächste Kamera"),
    Action(HUD, ANY, "h", "Toggle HUD", "HUD ein/aus"),
    Action(HARDER, ANY, "pageup", "Workout harder", "Workout schwerer"),
    Action(EASIER, ANY, "pagedown", "Workout easier", "Workout leichter"),
    Action(SKIP_INTERVAL, ANY, "tab", "Skip interval", "Intervall überspringen"),
)
for _view in range(1, 11):
    ACTIONS += (Action(CAMERA, CAMERA_NEXT + _view, str(_view % 10), f"Camera view {_view}",
                       f"Kamera {_view}"),)

CAMERA_KEYS = [str(v % 10) for v in range(1, 11)]


def find(action: int, value: int) -> Action | None:
    exact = next((a for a in ACTIONS if a.id == action and a.value == value), None)
    return exact or next((a for a in ACTIONS if a.id == action and a.value == ANY), None)


def slug(a: Action) -> str:
    """Stable name for the key override table in the configuration."""
    return re.sub(r"[^a-z0-9]+", "-", a.name.lower().replace("'", "")).strip("-")


class CameraCycle:
    """Zwift has no "next view" key; the bridge remembers the last view and types the next number."""

    def __init__(self) -> None:
        self.index = 0  # 0 = view 1 (Zwift's default)

    def next_key(self) -> str:
        self.index = (self.index + 1) % len(CAMERA_KEYS)
        return CAMERA_KEYS[self.index]

    def set_view(self, key: str) -> None:
        if key in CAMERA_KEYS:
            self.index = CAMERA_KEYS.index(key)
