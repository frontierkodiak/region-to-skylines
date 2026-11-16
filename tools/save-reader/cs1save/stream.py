"""Reader for the game's DataSerializer stream and its EncodedArray codecs.

Numbers are big-endian. Strings, types and objects use serializer-local tables,
exactly as ColossalFramework.IO.DataSerializer reads them in CS1 1.21.1-f9.
"""

import struct

import numpy as np


class FormatError(ValueError):
    """The bytes do not follow the format this reader implements."""


class Stream:
    def __init__(self, data, pos=0, version=None):
        self.data = data
        self.pos = pos
        self.version = version
        self.strings = []
        self.types = []
        self.objects = []
        self.strings_exact = True

    # Primitives -----------------------------------------------------------

    def take(self, count):
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise FormatError(f"read of {count} bytes past end at {self.pos}")
        value = self.data[self.pos : end]
        self.pos = end
        return value

    def u8(self):
        if self.pos >= len(self.data):
            raise FormatError(f"read past end at {self.pos}")
        value = self.data[self.pos]
        self.pos += 1
        return value

    def i8(self):
        value = self.u8()
        return value - 256 if value >= 128 else value

    def bool(self):
        return self.u8() == 1

    def u16(self):
        return int.from_bytes(self.take(2), "big")

    def i16(self):
        return int.from_bytes(self.take(2), "big", signed=True)

    def u24(self):
        return int.from_bytes(self.take(3), "big")

    def i24(self):
        return int.from_bytes(self.take(3), "big", signed=True)

    def u32(self):
        return int.from_bytes(self.take(4), "big")

    def i32(self):
        return int.from_bytes(self.take(4), "big", signed=True)

    def u64(self):
        return int.from_bytes(self.take(8), "big")

    def i64(self):
        return int.from_bytes(self.take(8), "big", signed=True)

    def f32(self):
        return struct.unpack(">f", self.take(4))[0]

    def f64(self):
        return struct.unpack(">d", self.take(8))[0]

    def vec2(self):
        return struct.unpack(">2f", self.take(8))

    def vec3(self):
        return struct.unpack(">3f", self.take(12))

    def vec4(self):
        return struct.unpack(">4f", self.take(16))

    # Strings, types, objects ------------------------------------------------

    def unique_string(self):
        head = self.u8()
        if head == 255:
            return None
        size = (head << 16) | self.u16()
        if size & 0x800000:
            size &= 0x7FFFFF
            raw = np.frombuffer(self.take(size), dtype=np.uint8)
            chars = (np.cumsum(raw, dtype=np.int64) + 0x80) & 0xFF
            return bytes(chars.astype(np.uint8)).decode("latin-1")
        raw = np.frombuffer(self.take(2 * size), dtype=">u2")
        chars = (np.cumsum(raw, dtype=np.int64) + 0x80) & 0xFFFF
        return "".join(map(chr, chars.tolist()))

    def shared_string(self):
        head = self.u8()
        if head == 255:
            return None
        if head == 254:
            value = self.unique_string()
            self.strings.append(value)
            return value
        index = (head << 8) | self.u8()
        if index >= len(self.strings):
            # Only possible after a skipped manager defined strings we never saw.
            return SharedRef(index)
        return self.strings[index]

    def shared_type(self):
        head = self.u8()
        if head == 255:
            return None
        if head == 254:
            value = self.unique_string()
            self.types.append(value)
            return value
        index = (head << 8) | self.u8()
        if index >= len(self.types):
            # Defined inside a block this reader passed over by its tags.
            return TypeRef(index)
        return self.types[index]

    def object(self):
        """Return the queued object's type name, an ObjectRef, or None."""
        head = self.u8()
        if head == 255:
            return None
        if head == 254:
            name = self.shared_type()
            self.objects.append(name)
            return name
        index = (head << 16) | self.u16()
        return ObjectRef(index)

    def object_array(self):
        head = self.u8()
        if head == 255:
            return None
        count = (head << 16) | self.u16()
        return [self.object() for _ in range(count)]

    def byte_array(self):
        head = self.u8()
        if head == 255:
            return None
        count = (head << 16) | self.u16()
        return self.take(count)

    def unique_string_array(self):
        head = self.u8()
        if head == 255:
            return None
        count = (head << 16) | self.u16()
        return [self.unique_string() for _ in range(count)]

    # Encoded arrays ----------------------------------------------------------

    def encoded(self, kind, count):
        return decode(self, kind, count)

    def encoded_bool(self, count):
        packed = decode(self, "u8", (count + 7) // 8)
        return np.unpackbits(packed, bitorder="little")[:count].astype(bool)


class SharedRef(int):
    """Index of a shared string defined inside a manager this reader skipped."""


class TypeRef(int):
    """Index of a shared type defined inside a manager this reader skipped."""


class ObjectRef(int):
    """Reference to an object already queued in this stream."""


# kind: (numpy dtype of full values, bytes per full value,
#        dtype of close deltas or None, bit width)
_KINDS = {
    "u8": (">u1", None, 8),
    "u16": (">u2", ">i1", 16),
    "i16": (">i2", ">i1", 16),
    "u32": (">u4", ">i2", 32),
    "i32": (">i4", ">i2", 32),
    "u64": (">u8", ">i4", 64),
    "i64": (">i8", ">i4", 64),
}
_OUT = {
    "u8": np.uint8,
    "u16": np.uint16,
    "i16": np.int16,
    "u32": np.uint32,
    "i32": np.int32,
    "u64": np.uint64,
    "i64": np.int64,
}


def decode(stream, kind, count):
    """Decode one EncodedArray of `count` values read contiguously.

    Header byte h: h >= 128 repeats the previous delta (h - 127 times);
    64 <= h < 128 reads h - 63 second differences (not for bytes or floats);
    h < 64 (h < 128 for bytes and floats) reads h + 1 literal values.
    Arithmetic wraps at the element width, as in the C# implementation.
    """
    if kind == "f32":
        return _decode_float(stream, count)
    full_dtype, close_dtype, bits = _KINDS[kind]
    width = np.dtype(full_dtype).itemsize
    close_width = np.dtype(close_dtype).itemsize if close_dtype else 0
    out = np.empty(count, dtype=np.uint64)
    mask = (1 << bits) - 1
    data = stream.data
    pos = stream.pos
    prev = 0
    delta = 0
    i = 0
    while i < count:
        if pos >= len(data):
            raise FormatError("encoded array runs past end of data")
        head = data[pos]
        pos += 1
        if head >= 128:
            n = head - 127
            if i + n > count:
                raise FormatError("encoded same-run exceeds array length")
            if delta == 0:
                out[i : i + n] = prev
            else:
                steps = np.arange(1, n + 1, dtype=np.uint64)
                out[i : i + n] = (np.uint64(prev) + np.uint64(delta) * steps) & np.uint64(mask)
            prev = (prev + delta * n) & mask
            i += n
        elif close_dtype is not None and head >= 64:
            n = head - 63
            if i + n > count:
                raise FormatError("encoded close-run exceeds array length")
            seconds = np.frombuffer(data, dtype=close_dtype, count=n, offset=pos).astype(np.int64)
            pos += n * close_width
            deltas = (np.uint64(delta) + np.cumsum(seconds).astype(np.uint64)) & np.uint64(mask)
            values = (np.uint64(prev) + np.cumsum(deltas, dtype=np.uint64)) & np.uint64(mask)
            out[i : i + n] = values
            delta = int(deltas[-1])
            prev = int(values[-1])
            i += n
        else:
            n = head + 1
            if i + n > count:
                raise FormatError("encoded literal run exceeds array length")
            values = np.frombuffer(data, dtype=full_dtype, count=n, offset=pos)
            pos += n * width
            values = values.astype(np.uint64) & np.uint64(mask)
            out[i : i + n] = values
            last = int(values[-1])
            before = int(values[-2]) if n > 1 else prev
            delta = (last - before) & mask
            prev = last
            i += n
    stream.pos = pos
    return out.astype(_unsigned(bits)).view(_OUT[kind])


def _unsigned(bits):
    return {8: np.uint8, 16: np.uint16, 32: np.uint32, 64: np.uint64}[bits]


def _decode_float(stream, count):
    out = np.empty(count, dtype=np.float32)
    prev = np.float32(0)
    delta = np.float32(0)
    i = 0
    while i < count:
        head = stream.u8()
        if head >= 128:
            n = head - 127
            if i + n > count:
                raise FormatError("encoded same-run exceeds array length")
            for _ in range(n):
                prev = np.float32(prev + delta)
                out[i] = prev
                i += 1
        else:
            n = head + 1
            if i + n > count:
                raise FormatError("encoded literal run exceeds array length")
            for _ in range(n):
                value = np.float32(stream.f32())
                delta = np.float32(value - prev)
                prev = np.float32(prev + delta)
                out[i] = prev
                i += 1
    return out
