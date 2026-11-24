"""Logical key names -> codes for each output (X11 keysym, Windows scan code, Linux evdev)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Key:
    keysym: int         # X11
    scan: int           # Windows scan code set 1
    extended: bool      # Windows: E0-prefixed key
    vk: int             # Windows virtual key (for logs and fallbacks)
    evdev: int          # Linux input event code


_F = {f"f{n}": Key(0xFFBE + n - 1, (0x3B + n - 1) if n <= 10 else (0x57 + n - 11), False, 0x70 + n - 1,
                   (59 + n - 1) if n <= 10 else (87 + n - 11)) for n in range(1, 13)}
_DIGITS = {str(d): Key(0x30 + d, 0x0B if d == 0 else 0x01 + d, False, 0x30 + d, 11 if d == 0 else 1 + d)
           for d in range(10)}

KEYS: dict[str, Key] = {
    "left": Key(0xFF51, 0x4B, True, 0x25, 105),
    "up": Key(0xFF52, 0x48, True, 0x26, 103),
    "right": Key(0xFF53, 0x4D, True, 0x27, 106),
    "down": Key(0xFF54, 0x50, True, 0x28, 108),
    "space": Key(0x0020, 0x39, False, 0x20, 57),
    "tab": Key(0xFF09, 0x0F, False, 0x09, 15),
    "pageup": Key(0xFF55, 0x49, True, 0x21, 104),
    "pagedown": Key(0xFF56, 0x51, True, 0x22, 109),
    "h": Key(0x0068, 0x23, False, 0x48, 35),
    **_F,
    **_DIGITS,
}


def lookup(name: str) -> Key | None:
    return KEYS.get(name.lower())
