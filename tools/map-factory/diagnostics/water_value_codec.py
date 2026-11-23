"""Experimental raw-value codec. No geographic edit authority or flow semantics."""

from dataclasses import dataclass
import math
import struct

import numpy as np

from crp import encode_u16
from template import manager_tag

TAG = manager_tag("WaterSimulation")
DOMAIN_NAMES = ("wet", "wet_or_east", "wet_or_south")


@dataclass(frozen=True)
class WaterValues:
    depth: np.ndarray
    compact: tuple[np.ndarray, np.ndarray, np.ndarray]
    controls: tuple[bytes, ...]
    trailer: bytes
    tail: bytes


def u16(values, shape=None):
    a = np.asarray(values)
    if a.dtype.kind != "u" or a.dtype.itemsize != 2:
        raise ValueError("Exact uint16 values required; no truncation or coercion")
    if shape is not None and a.shape != shape:
        raise ValueError("Wrong array shape")
    return a


def domains(depth):
    a = u16(depth)
    if a.ndim != 2 or not all(a.shape):
        raise ValueError("Nonempty two-dimensional grid required")
    wet = a > 0
    east, south = wet.copy(), wet.copy()
    east[:, :-1] |= wet[:, 1:]
    south[:-1, :] |= wet[1:, :]
    return tuple(np.flatnonzero(x.ravel()) for x in (wet, east, south))


def validate(state):
    keys = domains(state.depth)
    if len(state.compact) != 3:
        raise ValueError("Exactly three compact arrays required")
    for k, values in zip(keys, state.compact, strict=True):
        u16(values, (len(k),))
    if len(state.controls) > 65535:
        raise ValueError("Source table exceeds uint16 count")
    for raw in state.controls:
        if not isinstance(raw, bytes) or len(raw) != 43:
            raise ValueError("Expected opaque 43-byte control record")
        fields = struct.unpack(">6fHH", raw[:28])
        if (
            not all(math.isfinite(v) for v in fields[:6])
            or raw[:12] != raw[12:24]
            or fields[6] != 1
        ):
            raise ValueError("Unsupported initial source-record layout")
    if len(state.trailer) != 12 or len(state.tail) != 2:
        raise ValueError("Unsupported manager trailer/tail length")
    unknown, sea, a, b, _ = struct.unpack(">HfbbI", state.trailer)
    if unknown or a or b or not math.isfinite(sea):
        raise ValueError("Unsupported initial manager trailer")
    return keys


class Cursor:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, count):
        if count < 0 or self.pos + count > len(self.data):
            raise ValueError("Truncated initial-water payload")
        value = self.data[self.pos : self.pos + count]
        self.pos += count
        return value

    def array(self, count):
        """Checked legal local delta/RLE algorithm, including noncanonical forms."""
        result = np.empty(count, dtype=np.uint16)
        i, previous, delta = 0, 0, 0
        while i < count:
            code = self.take(1)[0]
            length = code - 127 if code >= 128 else (code & 63) + 1
            if i + length > count:
                raise ValueError("Encoded run exceeds declared domain")
            for _ in range(length):
                if code < 64:
                    value = int.from_bytes(self.take(2), "big")
                    delta = (value - previous + 32768) % 65536 - 32768
                elif code < 128:
                    extra = struct.unpack("b", self.take(1))[0]
                    delta = (delta + extra + 32768) % 65536 - 32768
                    value = (previous + delta) % 65536
                else:
                    value = (previous + delta) % 65536
                result[i] = value
                previous = value
                i += 1
        return result


def decode_chunk(data, shape=(1081, 1081)):
    """Decode one manager chunk; return state and exact consumed length."""
    if len(shape) != 2 or any(type(v) is not int or not 0 < v <= 1081 for v in shape):
        raise ValueError("Unsupported grid shape")
    c = Cursor(data)
    if c.take(len(TAG)) != TAG:
        raise ValueError("Expected exact initial-water manager tag")
    depth = c.array(math.prod(shape)).reshape(shape)
    compact = tuple(c.array(len(k)) for k in domains(depth))
    count = int.from_bytes(c.take(2), "big")
    state = WaterValues(
        depth, compact, tuple(c.take(43) for _ in range(count)), c.take(12), c.take(2)
    )
    validate(state)
    return state, c.pos


def encode_chunk(state):
    validate(state)
    return b"".join(
        [TAG, encode_u16(state.depth)]
        + [encode_u16(a) for a in state.compact]
        + [
            struct.pack(">H", len(state.controls)),
            b"".join(state.controls),
            state.trailer,
            state.tail,
        ]
    )


def grow_depth(state, depth, new_values):
    """Serialization-only operation: preserve every persistent raw domain value."""
    old_keys = validate(state)
    depth = u16(depth, state.depth.shape)
    if np.any(depth < state.depth):
        raise ValueError("Depth removal/decrease is outside this operation contract")
    if len(new_values) != 3:
        raise ValueError("Declare new values for all three domains")
    arrays = []
    for before, after, values, declared in zip(
        old_keys, domains(depth), state.compact, new_values, strict=True
    ):
        added = np.setdiff1d(after, before, assume_unique=True)
        if not isinstance(declared, dict) or any(type(k) is not int for k in declared):
            raise ValueError("New domain keys must be exact integer-keyed declarations")
        if set(declared) != set(map(int, added)):
            raise ValueError("Declare exactly new domain keys; no overwrite/default")
        if any(type(v) is not int or not 0 <= v <= 65535 for v in declared.values()):
            raise ValueError("New raw values must be exact uint16 integers")
        a = np.empty(len(after), dtype=np.uint16)
        a[np.searchsorted(after, before)] = values
        a[np.searchsorted(after, added)] = [declared[int(k)] for k in added]
        arrays.append(a)
    result = WaterValues(
        depth.copy(), tuple(arrays), state.controls, state.trailer, state.tail
    )
    validate(result)
    return result


def encode_geographic_change(*args, **kwargs):
    """No current selected/admitted joint plan exists; never emit a geographic map."""
    raise ValueError("No complete selected joint initialization/safety/port plan")
