"""Behavioral checks for package measurements and evidence-gated assessments."""

import copy
import hashlib
import json
import itertools
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from assemble import assess, classify, frame_summary, lod_mesh
from catalog import DependencyParser, StateParser, enrich, request
from installed import crp, natural_prop, prefab_collisions
from framing import pair_framing
from normalize_ugc import closure
from review_ledger import add_reviews, palette_estimate


def string(text):
    raw = text.encode()
    if len(raw) >= 128:
        raise ValueError("Fixture strings must be short")
    return bytes([len(raw)]) + raw


def package(payload, fmt=7):
    prefix = (
        b"CRAP" + struct.pack("<H", fmt) + string("test") + string("") + struct.pack("<I", 0) + string("tree")
    )
    directory = (
        string("mesh") + string(hashlib.md5(payload).hexdigest()) + struct.pack("<iqq", 4, 0, len(payload))
    )
    return prefix + struct.pack("<iq", 1, len(prefix) + 12 + len(directory)) + directory + payload


def mesh():
    payload = b"\0" + string("UnityEngine.Mesh, UnityEngine") + string("tree")
    payload += struct.pack("<i9f", 3, -2, 0, -1, 2, 5, -1, 0, 0, 3)
    payload += struct.pack("<6i", *([0] * 6))
    return payload + struct.pack("<5i", 1, 3, 0, 1, 2)


class VegetationTest(unittest.TestCase):
    def test_larger_lod_is_not_reported_as_main_and_unreadable_main_stays_unknown(self):
        source = {
            "workshop_packages": [
                {
                    "workshop_id": "1",
                    "name": "1",
                    "file": "plant.crp",
                    "sha256": "container",
                    "prefabs": [
                        {
                            "kind": "PropInfo",
                            "name": "Grass_Data",
                            "meshes": [
                                {"triangles": 30, "size_m": [1, 1, 1]},
                                {"triangles": 50, "size_m": [1, 1, 1]},
                            ],
                            "textures": [],
                        }
                    ],
                }
            ]
        }
        result = {
            "assembly_sha256": "game",
            "base": [],
            "biome_scheme": {"biomes": []},
            "quality_bar": {"forest_texture_target_px": 1024, "forest_main_triangle_target": 1500},
            "workshop": [
                {"id": "1", "dependencies": [], "assessment": {"failed": [], "status": "unreviewed"}}
            ],
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run = root / "runs/native"
            run.mkdir(parents=True)
            (root / "near-reviews.json").write_text(json.dumps({"reviews": [], "rubric": {}}))
            (run / "build.json").write_text(json.dumps({"game_assemblies": {"Assembly-CSharp.dll": "game"}}))
            catalog = {
                "trees": [],
                "props": [{"name": "1.Grass_Data", "main": {"triangles": 30}, "lod": {"triangles": 50}}],
            }
            for native_triangles in (30, None):
                catalog["props"][0]["main"]["triangles"] = native_triangles
                (run / "native-catalog.json").write_text(json.dumps(catalog))
                actual = copy.deepcopy(result)
                add_reviews(actual, source, root)
                prefab = actual["prefab_reviews"][0]
                self.assertEqual(prefab["main_triangles"], native_triangles)
                self.assertEqual(prefab["lod_triangles"], 50)
                self.assertEqual(prefab["serialized_mesh_triangle_max"], 50)
                self.assertEqual(prefab["gates"]["geometry"], "pass" if native_triangles else "unknown")

    def test_shared_texture_is_counted_once_across_prefabs_not_per_tree(self):
        texture = {"checksum": "shared-content", "width": 4, "height": 4, "encoding": "DXT1"}
        first = {"name": "oak", "textures": [texture]}
        second = {"name": "birch", "textures": [texture]}
        one = palette_estimate([first])
        two = palette_estimate([first, second])
        self.assertEqual(two["known_compressed_mip_bytes"], one["known_compressed_mip_bytes"])
        self.assertEqual(two["unique_texture_count"], 1)
        second["textures"] = [{**texture, "checksum": "other-content", "encoding": "unmeasured"}]
        estimate = palette_estimate([first, second])
        self.assertEqual(estimate["unknown_format_count"], 1)
        self.assertEqual(estimate["known_compressed_mip_bytes"], one["known_compressed_mip_bytes"])

    def test_embedded_variation_and_standalone_prefab_identity_collision_is_reported(self):
        def package(file, roots):
            return {
                "name": "123",
                "workshop_id": "123",
                "file": file,
                "sha256": file,
                "prefabs": [{"name": name, "kind": kind} for name, kind in roots],
            }

        rows = [
            package("bundle.crp", [("A", "TreeInfo"), ("B", "TreeInfo")]),
            package("A.crp", [("A", "TreeInfo")]),
            package("prop.crp", [("A", "PropInfo")]),
        ]
        found = prefab_collisions(rows)
        self.assertEqual(list(found), ["TreeInfo:123.A"])
        self.assertEqual([r["file"] for r in found["TreeInfo:123.A"]], ["bundle.crp", "A.crp"])

    def test_dependency_cycles_terminate_and_denied_details_remain_unresolved(self):
        records = {
            "1": {"children": ["2"], "result": 1},
            "2": {"children": ["1", "3", "4"], "result": 1},
            "3": {"children": [], "result": 15},
        }
        descendants, unresolved = closure("1", records)
        self.assertEqual(descendants, ["1", "2", "3", "4"])
        self.assertEqual(unresolved, ["3", "4"])

    def test_download_completeness_is_not_a_checksum_or_measurement_pass(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tree.crp"
            raw = bytearray(package(mesh()))
            raw[-1] ^= 1
            path.write_bytes(raw)
            self.assertEqual(
                crp(path, strict_checksums=False, measure=False)["checksum_mismatches"], ["mesh"]
            )
            with self.assertRaisesRegex(ValueError, "checksum"):
                crp(path)

    def test_native_maximum_scale_crowns_fit_the_proposed_pair_frustum(self):
        root = Path(__file__).parent / "observations/native"
        trees = {t["name"]: t for t in json.loads((root / "sheet-catalog.json").read_text())["trees"]}
        pairs = json.loads((root / "specimens.json").read_text())
        pitch, half_fov = math.radians(25), math.tan(math.radians(22.5))
        for pair in pairs:
            left, right = [trees[pair[k]] for k in ("candidate", "base_neighbour")]
            view = pair_framing(left, right)
            for sign, tree in [(-1, left), (1, right)]:
                width, height, depth = [v * max(tree["scale_range"]) for v in tree["main"]["size_m"]]
                for x, y, z in itertools.product(
                    (-width / 2, width / 2), (0, height), (-depth / 2, depth / 2)
                ):
                    x += sign * view["gap"] / 2
                    y -= view["height"] * 0.4
                    distance = view["size"] - y * math.sin(pitch) + z * math.cos(pitch)
                    vertical = y * math.cos(pitch) + z * math.sin(pitch)
                    self.assertLess(abs(x / (distance * half_fov * 16 / 9)), 0.95, pair["candidate"])
                    self.assertLess(abs(vertical / (distance * half_fov)), 0.95, pair["candidate"])

    def test_native_timing_reports_the_delta_without_certifying_an_asset(self):
        samples = [
            {
                "size": 350,
                "repeat": repeat,
                "arm": arm,
                "name": arm,
                "instances": 200000,
                "population": {"instances": 200000},
                "frame_ms": [30.0 if arm == "B" else 20.0] * 300,
            }
            for repeat in range(5)
            for arm in ("A-before", "B", "A-after")
        ]
        result = frame_summary(samples)[0]
        self.assertEqual(result["paired_p95_regression_median"], 0.5)
        self.assertEqual(result["repeats"], 5)
        self.assertIn("inconclusive", result["performance_verdict"])
        samples[0]["instances"] = 100000
        with self.assertRaisesRegex(ValueError, "population"):
            frame_summary(samples)

    def test_rate_limit_stops_the_batch_and_preserves_unknown_dependencies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "metadata.json"
            path.write_text(
                json.dumps(
                    {
                        "dependency_items": {},
                        "items": [
                            {
                                "id": "0",
                                "url": "https://steamcommunity.com/",
                                "dependencies": ["99"],
                                "dependency_status": "public_page_checked",
                            },
                        ]
                        + [
                            {
                                "id": str(i),
                                "url": "https://steamcommunity.com/",
                                "dependencies": None,
                                "dependency_status": "not_yet_inspected",
                            }
                            for i in (1, 2)
                        ],
                    }
                )
            )
            error = HTTPError("https://steamcommunity.com/", 429, "Too Many Requests", {}, None)
            with patch("catalog.request", side_effect=error) as reader:
                enrich(path)
            reader.assert_called_once()
            saved = json.loads(path.read_text())
            self.assertTrue(saved["dependency_page_refresh"]["rate_limited"])
            self.assertEqual(saved["items"][2]["dependency_status"], "not_yet_inspected")
            self.assertIsNone(saved["items"][1]["dependencies"])
            self.assertEqual(saved["items"][0]["unresolved_dependencies"], ["99"])

    def test_rate_limit_is_not_retried(self):
        error = HTTPError("https://steamcommunity.com/", 429, "Too Many Requests", {}, None)
        with patch("urllib.request.urlopen", side_effect=error) as opener:
            with self.assertRaises(HTTPError):
                request("https://steamcommunity.com/")
        opener.assert_called_once()

    def test_mesh_measurements_and_zero_padding_in_old_and_new_packages(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tree.crp"
            for fmt in (5, 7, 12):
                path.write_bytes(package(mesh() + bytes(128), fmt))
                result = crp(path)["meshes"][0]
                self.assertEqual(result["triangles"], 1)
                self.assertEqual(result["size_m"], [4, 5, 4])

    def test_corrupt_and_nonpadding_tail_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "tree.crp"
            raw = bytearray(package(mesh()))
            raw[-1] ^= 1
            path.write_bytes(raw)
            with self.assertRaisesRegex(ValueError, "checksum"):
                crp(path)
            path.write_bytes(package(mesh() + b"\1"))
            with self.assertRaisesRegex(ValueError, "completely decoded"):
                crp(path)

    def test_unknown_evidence_never_becomes_a_pass(self):
        item = {
            "availability": "public",
            "dependency_status": "public_page_checked",
            "required_mods": [],
            "packages": [
                {
                    "contains_assembly": False,
                    "meshes": [{"name": "tree", "triangles": 200}],
                    "textures": [{"name": "_MainTex", "width": 512, "height": 512}],
                }
            ],
        }
        budget = {"forest_main_triangle_target": 1500, "forest_texture_target_px": 1024}
        self.assertEqual(assess(item, budget)["status"], "unreviewed")
        reviewed = copy.deepcopy(item)
        for field in (
            "scale_review",
            "gameplay_visual_review",
            "billboard_review",
            "maintenance_review",
            "recommendation_rights_review",
            "native_frame_review",
        ):
            reviewed[field] = True
        self.assertEqual(assess(reviewed, budget)["status"], "pass")
        reviewed["tags"] = ["Mod"]
        self.assertEqual(assess(reviewed, budget)["status"], "fail")
        reviewed["tags"] = []
        reviewed["required_mods"] = ["123"]
        self.assertEqual(assess(reviewed, budget)["status"], "fail")
        reviewed["required_mods"] = []
        reviewed["packages"][0]["meshes"][0]["triangles"] = 1501
        self.assertIn("over_forest_fill_triangle_target", assess(reviewed, budget)["failed"])

    def test_dependencies_do_not_include_sidebar_collections(self):
        parser = DependencyParser()
        parser.feed(
            '<div id="RequiredItems"><a href="https://steamcommunity.com/workshop/filedetails/?id=123"><div>mod</div></a></div><a href="filedetails/?id=456">collection</a>'
        )
        self.assertEqual(parser.ids, ["123"])

    def test_unrelated_street_props_and_logos_do_not_become_vegetation(self):
        for name in (
            "StreetLamp01",
            "Logo_forestfoundation",
            "MP26_Prop_Sign_Wide_RockBar",
            "combustion plant roof platform",
        ):
            self.assertFalse(natural_prop(name), name)
        for name in ("Tree Sapling Field Pot 01", "MC Decal Grass 01", "Path Rock Small 01"):
            self.assertTrue(natural_prop(name), name)

    def test_steam_nested_state_and_ambiguous_taxonomy(self):
        parser = StateParser()
        parser.feed(
            '<script>{"route":"/workshop/browse","loaderData":["{\\"total_count\\":0,\\"results\\":[]}"]}</script>'
        )
        self.assertTrue(any(s.get("total_count") == 0 for s in parser.states))
        self.assertIsNone(classify("Generic Tree pack")["genus"])
        self.assertEqual(classify("Shore Pine 12m")["genus"], "Pinus")
        self.assertFalse(lod_mesh("Lodgepole Pine 19m"))
        self.assertTrue(lod_mesh("pine_lod"))
        self.assertEqual(classify("Flower Tree 01")["form"], "broadleaf_unknown")
        self.assertNotEqual(classify("Alpine Grass")["genus"], "Pinus")
        self.assertEqual(classify("Acer Rubrum")["genus"], "Acer")
        self.assertEqual(classify("London Planetree")["genus"], "Platanus")
        self.assertEqual(classify("Cistus Rock Rose")["form"], "shrub")
        self.assertNotEqual(classify("Flower-Orange")["genus"], "Citrus")
        self.assertEqual(classify("Fruits - Orange tree")["genus"], "Citrus")


if __name__ == "__main__":
    unittest.main()
