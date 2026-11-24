"""Minimal protobuf wire format (proto3) – just enough for the Zwift Companion messages.

Encoding: `message({field: value, ...})` with ints (varint), str/bytes, nested dicts (messages) and
lists (repeated). Decoding: `decode(data)` returns {field: [values]} where length-delimited values
stay bytes; decode nested messages again where the schema says so.
"""

from __future__ import annotations

import struct


def _varint(n: int) -> bytes:
    if n < 0:
        n += 1 << 64  # int32/int64 negatives are ten-byte varints
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def _field(num: int, value) -> bytes:
    if isinstance(value, bool):
        return _varint(num << 3) + _varint(int(value))
    if isinstance(value, int):
        return _varint(num << 3) + _varint(value)
    if isinstance(value, float):
        return _varint(num << 3 | 5) + struct.pack("<f", value)
    if isinstance(value, str):
        value = value.encode()
    if isinstance(value, dict):
        value = message(value)
    if isinstance(value, (bytes, bytearray)):
        return _varint(num << 3 | 2) + _varint(len(value)) + bytes(value)
    raise TypeError(f"cannot encode {type(value).__name__}")


def message(fields: dict) -> bytes:
    out = bytearray()
    for num in sorted(fields):
        value = fields[num]
        if value is None:
            continue
        for v in (value if isinstance(value, list) else [value]):
            out += _field(num, v)
    return bytes(out)


class DecodeError(ValueError):
    pass


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    shift = result = 0
    while True:
        if pos >= len(data):
            raise DecodeError("truncated varint")
        b = data[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7
        if shift > 70:
            raise DecodeError("varint too long")


def decode(data: bytes) -> dict[int, list]:
    fields: dict[int, list] = {}
    pos = 0
    while pos < len(data):
        key, pos = _read_varint(data, pos)
        num, wire = key >> 3, key & 7
        if wire == 0:
            value, pos = _read_varint(data, pos)
        elif wire == 1:
            value, pos = data[pos:pos + 8], pos + 8
        elif wire == 2:
            n, pos = _read_varint(data, pos)
            if pos + n > len(data):
                raise DecodeError("truncated field")
            value, pos = data[pos:pos + n], pos + n
        elif wire == 5:
            value, pos = data[pos:pos + 4], pos + 4
        else:
            raise DecodeError(f"unsupported wire type {wire}")
        fields.setdefault(num, []).append(value)
    return fields


def first(fields: dict, num: int, default=None):
    v = fields.get(num)
    return v[0] if v else default


def signed(n: int) -> int:
    """Varint as int32/int64 (two's complement)."""
    return n - (1 << 64) if n >= 1 << 63 else n


def text(fields: dict, num: int) -> str:
    v = first(fields, num, b"")
    return v.decode("utf-8", "replace") if isinstance(v, (bytes, bytearray)) else ""
