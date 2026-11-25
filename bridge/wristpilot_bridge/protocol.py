"""Wire protocol between watch and bridge (GATT service "Wristpilot").

Command characteristic (watch -> bridge, write / write without response), 3 bytes:
    [seq, action, value]
    seq     0-255, wraps; echoed in the acknowledgement
    action  OpenBikeControl button ID (see actions.py)
    value   1 = press (default); analog value for camera/emote/screenshot (see actions.py)

Status characteristic (bridge -> watch, read / notify):
    [0x01, seq, result]       acknowledgement of a command
    [0x02, flags]             bridge state, sent on subscribe and whenever it changes
    [0x03, pattern]           haptic request from an OpenBikeControl app (pattern as in OBC 0x03)
    [0x04, flags, powerup, rideOnsLo, rideOnsHi]
                              game state from the Zwift Companion link (companion.py): flags 0x01 linked,
                              0x02 junction ahead, 0x04/0x08/0x10 left/straight/right offered, 0x20 power-up

Info characteristic (read): UTF-8 text "Wristpilot <version> · <host>".

The watch advertises nothing; the bridge advertises the service UUID with flags 0x06 (LE General
Discoverable, BR/EDR not supported) - Connect IQ drops scan results without "general discoverable".
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, IntFlag

SERVICE_UUID = "ae279be2-4f9c-4165-ab88-060ee241b936"
COMMAND_UUID = "ae279be2-4f9c-4165-ab88-060ee241b937"
STATUS_UUID = "ae279be2-4f9c-4165-ab88-060ee241b938"
INFO_UUID = "ae279be2-4f9c-4165-ab88-060ee241b939"
CCCD_UUID = "00002902-0000-1000-8000-00805f9b34fb"

MSG_ACK = 0x01
MSG_STATE = 0x02
MSG_HAPTIC = 0x03
MSG_GAME = 0x04


class Result(IntEnum):
    OK = 0
    NOT_FOCUSED = 1      # Zwift runs but another window has the keyboard focus
    NOT_RUNNING = 2      # no Zwift window and no OpenBikeControl app connected
    UNKNOWN_ACTION = 3
    OUTPUT_FAILED = 4
    DISABLED = 5         # remote switched off in the bridge
    MALFORMED = 6
    NO_STEERING = 7      # lane change, but Zwift has not paired the bridge's steering device


class State(IntFlag):
    ZWIFT_RUNNING = 0x01
    ZWIFT_FOCUSED = 0x02
    OBC_CONNECTED = 0x04
    KEYBOARD_ON = 0x08
    ENABLED = 0x10
    COMPANION = 0x20     # linked to the game as Zwift Companion


@dataclass(frozen=True)
class Command:
    seq: int
    action: int
    value: int = 1


def decode_command(data: bytes) -> Command | None:
    """Command from the watch; None if it is too short. Extra bytes are ignored (future fields)."""
    if len(data) < 2:
        return None
    return Command(seq=data[0], action=data[1], value=data[2] if len(data) > 2 else 1)


def encode_command(cmd: Command) -> bytes:
    return bytes((cmd.seq & 0xFF, cmd.action & 0xFF, cmd.value & 0xFF))


def encode_ack(seq: int, result: Result) -> bytes:
    return bytes((MSG_ACK, seq & 0xFF, int(result)))


def encode_state(flags: State) -> bytes:
    return bytes((MSG_STATE, int(flags) & 0xFF))


def encode_haptic(pattern: int) -> bytes:
    return bytes((MSG_HAPTIC, pattern & 0xFF))
