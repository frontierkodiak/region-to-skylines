"""Behavioral serialization checks, not hydraulic qualification."""

from dataclasses import replace
import struct
import unittest

import numpy as np

from water_codec_audit import (
    FIXTURES,
    ROOT,
    declarations,
    equal_values,
    fixture_state,
    load,
)
from water_value_codec import (
    TAG,
    WaterValues,
    decode_chunk,
    domains,
    encode_chunk,
    encode_geographic_change,
    grow_depth,
)


class CodecTests(unittest.TestCase):
    def setUp(self):
        self.spec = load(ROOT / FIXTURES)
        self.state = fixture_state(self.spec)

    def test_growth_preserves_raw_values_and_explicit_new_keys(self):
        for fixture in self.spec["growth_cases"]:
            with self.subTest(name=fixture["name"]):
                d = self.state.depth.copy()
                for r, c, value in fixture["set_depth"]:
                    d[r, c] = value
                dec = declarations(self.state.depth, d)
                grown = grow_depth(self.state, d, dec)
                raw = encode_chunk(grown)
                result, end = decode_chunk(raw, d.shape)
                self.assertEqual(end, len(raw))
                self.assertTrue(equal_values(result, grown))
                for i, (old, new) in enumerate(
                    zip(domains(self.state.depth), domains(d), strict=True)
                ):
                    before = dict(zip(map(int, old), self.state.compact[i]))
                    after = dict(zip(map(int, new), result.compact[i]))
                    self.assertEqual(after, before | dec[i])
                self.assertEqual(result.controls, self.state.controls)
                self.assertEqual(result.trailer, self.state.trailer)
                self.assertEqual(result.tail, self.state.tail)

    def test_no_hidden_zero_or_old_value_overwrite(self):
        d = self.state.depth.copy()
        d[0, 0] = 7
        with self.assertRaisesRegex(ValueError, "exactly new"):
            grow_depth(self.state, d, ({}, {}, {}))
        dec = list(declarations(self.state.depth, d))
        dec[0][int(domains(self.state.depth)[0][0])] = 0
        with self.assertRaisesRegex(ValueError, "no overwrite"):
            grow_depth(self.state, d, tuple(dec))

    def test_decrease_type_and_raw_overflow_refused(self):
        d = self.state.depth.copy()
        d[2, 2] = 0
        with self.assertRaisesRegex(ValueError, "removal"):
            grow_depth(self.state, d, ({}, {}, {}))
        with self.assertRaisesRegex(ValueError, "uint16"):
            grow_depth(self.state, self.state.depth.astype(float), ({}, {}, {}))
        d[0, 0] = 1
        dec = list(declarations(self.state.depth, d))
        dec[0][0] = 65536
        with self.assertRaisesRegex(ValueError, "uint16"):
            grow_depth(self.state, d, tuple(dec))

    def test_full_parser_rejects_truncation_overruns_and_unknowns(self):
        raw = encode_chunk(self.state)
        for size in (0, len(TAG), len(TAG) + 2, len(raw) - 1):
            with self.subTest(size=size), self.assertRaises(ValueError):
                decode_chunk(raw[:size], self.state.depth.shape)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            decode_chunk(TAG + bytes([255]), (1, 1))
        bad = replace(self.state, trailer=struct.pack(">HfbbI", 1, 90.0, 0, 0, 0))
        with self.assertRaisesRegex(ValueError, "trailer"):
            encode_chunk(bad)
        record = struct.pack(">6fHH", *([float("nan")] * 6), 1, 2) + bytes(15)
        with self.assertRaisesRegex(ValueError, "source-record"):
            encode_chunk(replace(self.state, controls=(record,)))

    def test_no_row_wrap_and_shared_domain_is_single_key(self):
        d = np.zeros((2, 3), dtype=np.uint16)
        d[1, 0] = 1
        self.assertEqual([k.tolist() for k in domains(d)], [[3], [3], [0, 3]])
        d[0, 0] = 1
        self.assertEqual([k.tolist() for k in domains(d)], [[0, 3], [0, 3], [0, 3]])

    def test_noncanonical_rle_keeps_values_without_false_byte_claim(self):
        from crp import encode_u16

        s = WaterValues(
            np.array([[1, 2, 3]], dtype=np.uint16),
            tuple(np.array([1, 32768, 65535], dtype=np.uint16) for _ in range(3)),
            self.state.controls,
            self.state.trailer,
            self.state.tail,
        )
        canonical = encode_chunk(s)
        alternate = (
            TAG
            + bytes.fromhex("000001400080")
            + canonical[len(TAG) + len(encode_u16(s.depth)) :]
        )
        decoded, end = decode_chunk(alternate, (1, 3))
        self.assertEqual(end, len(alternate))
        self.assertTrue(equal_values(s, decoded))
        self.assertNotEqual(canonical, alternate)
        self.assertEqual(encode_chunk(decoded), canonical)

    def test_identity_and_geographic_boundary(self):
        unchanged = grow_depth(self.state, self.state.depth.copy(), ({}, {}, {}))
        self.assertEqual(encode_chunk(unchanged), encode_chunk(self.state))
        for plan in (None, {}, {"selected": True, "stage": 90}):
            with self.assertRaisesRegex(ValueError, "No complete selected"):
                encode_geographic_change(plan)


if __name__ == "__main__":
    unittest.main()
