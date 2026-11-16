"""EncodedArray and string decoding against a literal transcription of the
game's element-by-element Read() methods, on random well-formed streams."""

import random
import struct

import pytest

from cs1save.save import begin_tag
from cs1save.stream import Stream, decode

# kind: (full width, close width or None, bits, signed)
KINDS = {
    "u8": (1, None, 8, False),
    "u16": (2, 1, 16, False),
    "i16": (2, 1, 16, True),
    "u32": (4, 2, 32, False),
    "i32": (4, 2, 32, True),
    "u64": (8, 4, 64, False),
    "i64": (8, 4, 64, True),
}


def random_stream(kind, count, rng):
    """Random chunk headers and payloads, valid by construction."""
    width, close, _, _ = KINDS[kind]
    out = bytearray()
    left = count
    while left:
        choice = rng.choice(["same", "close", "full"] if close else ["same", "full"])
        if choice == "same":
            n = rng.randint(1, min(128, left))
            out.append(127 + n)
        elif choice == "close":
            n = rng.randint(1, min(64, left))
            out.append(63 + n)
            for _ in range(n):
                out += rng.randrange(-(1 << (8 * close - 1)), 1 << (8 * close - 1)).to_bytes(close, "big", signed=True)
        else:
            n = rng.randint(1, min(64 if close else 128, left))
            out.append(n - 1)
            for _ in range(n):
                out += rng.randrange(0, 1 << (8 * width)).to_bytes(width, "big")
        left -= n
    return bytes(out)


def reference_read(data, kind, count):
    """One value per call, as EncodedArray.<Kind>.Read does, with wrap-around."""
    width, close, bits, signed = KINDS[kind]
    mask = (1 << bits) - 1
    pos = prev = delta = same = closes = full = 0
    out = []
    for _ in range(count):
        while True:
            if same:
                prev = (prev + delta) & mask
                same -= 1
                break
            if closes:
                d = int.from_bytes(data[pos : pos + close], "big", signed=True)
                pos += close
                delta = (delta + d) & mask
                prev = (prev + delta) & mask
                closes -= 1
                break
            if full:
                value = int.from_bytes(data[pos : pos + width], "big")
                pos += width
                delta = (value - prev) & mask
                prev = value & mask
                full -= 1
                break
            head = data[pos]
            pos += 1
            if head >= 128:
                same = head - 127
            elif close and head >= 64:
                closes = head - 63
            else:
                full = head + 1
        out.append(prev - (1 << bits) if signed and prev >> (bits - 1) else prev)
    return out, pos


@pytest.mark.parametrize("kind", sorted(KINDS))
def test_encoded_matches_reference(kind):
    rng = random.Random(kind)
    for trial in range(40):
        count = rng.randint(1, 900)
        data = random_stream(kind, count, rng) + b"\xaa"
        expected, end = reference_read(data, kind, count)
        s = Stream(data)
        got = decode(s, kind, count)
        assert [int(v) for v in got] == expected
        assert s.pos == end


def test_float_same_run_accumulates_in_float32():
    data = bytes([1]) + struct.pack(">2f", 1.0, 1.5) + bytes([127 + 3])
    got = Stream(data).encoded("f32", 5)
    assert got.tolist() == [1.0, 1.5, 2.0, 2.5, 3.0]


def test_bool_bits_are_little_endian_within_bytes():
    data = bytes([1, 0b00000101, 0b00000010])
    assert Stream(data).encoded_bool(10).tolist() == [True, False, True] + [False] * 5 + [False, True]


def test_unique_string_latin1_and_utf16():
    latin = "TerrainManager"
    s = Stream(begin_tag(latin))
    assert s.shared_string() == latin and s.strings == [latin]
    text = "Ē€"
    raw = bytearray([0, 0, len(text)])
    prev = 0x80
    for ch in text:
        raw += ((ord(ch) - prev) & 0xFFFF).to_bytes(2, "big")
        prev = ord(ch)
    assert Stream(bytes(raw)).unique_string() == text
    assert Stream(b"\xff").unique_string() is None


def test_shared_string_reference():
    s = Stream(begin_tag("A") + begin_tag("B") + b"\x00\x01\x00\x00")
    assert [s.shared_string() for _ in range(4)] == ["A", "B", "B", "A"]
