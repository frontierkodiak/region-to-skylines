"""Behavioral cross-runtime checks; no native game evidence is fabricated."""

import gzip
import json
import copy
import tempfile
from pathlib import Path
import random
import subprocess
import unittest

import numpy as np
from PIL import Image

from capabilities import (
    STOCK_MEASURES,
    assess_prepared,
    check,
    place_capabilities,
    place_input,
    place_measures,
    prepared_input,
    stock_band,
    stock_metrics,
)
from evidence import parse as parse_mrds
from integrate_outside_evidence import boundary_probe
from transport_paths import ship_path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = json.loads((ROOT / "capabilities.json").read_text())
PLACE_RULES = LEDGER["model_rules"]["place"]


def place_cases():
    """Constructed evidence: every level, threshold and missing-source boundary."""
    size, spacing = 7, 4000
    total = size * size
    # Some wet nodes, but not the whole square: the land mask has to matter.
    depth = [8 if (i % 5 == 0) else 0 for i in range(total)]
    # A 75 percent ramp in the north rows: the game tree brush stops at 50, so
    # the taper must zero it while the flat south keeps full weight.
    ramp = [100 + max(0, 3 - r) * 3000 for r in range(size) for c in range(size)]
    flat = [100] * total
    records = [
        {"kind": "ore", "x": 0, "z": 0, "weight": 1.0},
        {"kind": "oil", "x": 3000, "z": -2000, "weight": 0.8},
        {"kind": "ore", "x": 9000, "z": 0, "weight": 0.35},
        {"kind": "well", "x": 0, "z": 0},
    ]

    # Every row differs by 100 percent, so all central nodes are over the
    # game tree-brush limit; used to prove the screen, not the cover, decides.
    steep = [100 + (size - 1 - r) * 4000 for r in range(size) for c in range(size)]

    def case(
        values, terrain=ramp, records_=records, deposits="available", mode="estimate"
    ):
        return {
            "schema": 1,
            "mode": mode,
            "grid": {"size": size, "spacing_m": spacing, "depth_m": depth},
            "place": {
                "terrain_m": terrain,
                "landcover": {
                    "status": "available",
                    "source": "constructed",
                    "fidelity": "constructed",
                    "cell_m": 10,
                    "sample_m": 40,
                    "tiles": ["N00E000"],
                    "values": values,
                },
                "deposits": {
                    "status": deposits,
                    "source": "constructed",
                    "records": records_,
                },
            },
        }

    mixed = [10, 20, 30, 40, 50, 60, 80, 90, 95, 100]
    values = [mixed[i % len(mixed)] for i in range(total)]
    base = case(values)
    cases = [("mixed evidence on a ramped square", base)]
    no_terrain = copy.deepcopy(base)
    no_terrain["place"].pop("terrain_m")
    cases.append(("terrain absent leaves slope unscreened", no_terrain))
    no_cover = copy.deepcopy(base)
    no_cover["place"].pop("landcover")
    cases.append(("land cover missing is unknown, not No", no_cover))
    no_deposits = copy.deepcopy(base)
    no_deposits["place"].pop("deposits")
    cases.append(("deposits missing, land cover present", no_deposits))
    unavailable = copy.deepcopy(base)
    unavailable["place"]["deposits"]["status"] = "unavailable"
    cases.append(("deposit source unavailable", unavailable))
    cases.append(("full tree cover", case([10] * total)))
    built = case([50] * total, terrain=flat, records_=[])
    cases.append(("built-up only, no deposit", built))
    cases.append(
        (
            "sparse grass is below the tree threshold",
            case([30] * total, terrain=flat, records_=[]),
        )
    )
    cases.append(
        (
            "shrub clears the tree threshold",
            case([20] * total, terrain=flat, records_=[]),
        )
    )
    cases.append(
        (
            "steep shrub is screened to no trees",
            case([20] * total, terrain=steep, records_=[]),
        )
    )
    cases.append(("no land-cover data at all", case([0] * total)))
    partial = copy.deepcopy(base)
    partial["place"]["landcover"]["values"] = [10] * (total // 2) + [0] * (
        total - total // 2
    )
    cases.append(("partial land-cover coverage stays unknown", partial))
    no_records = case(values, records_=[])
    cases.append(("no recorded deposit is not absence", no_records))
    outside = case([50] * total, terrain=flat, records_=[records[2]])
    cases.append(("deposit recorded outside the central tiles", outside))
    wells = case(values, records_=[records[3]])
    cases.append(("a well is not a deposit record", wells))
    all_wet = copy.deepcopy(base)
    all_wet["grid"]["depth_m"] = [8] * total
    cases.append(("no central land to judge", all_wet))
    all_dry = copy.deepcopy(base)
    all_dry["grid"]["depth_m"] = [0] * total
    cases.append(("all dry, coverage complete", all_dry))
    exported = copy.deepcopy(base)
    exported["mode"] = "export"
    cases.append(("export mode keeps the same candidate levels", exported))
    return cases


FIXTURES = ("asheville", "charleston", "innsbruck", "pittsburgh", "rio")


def extract_fixture(slug, folder):
    """Lay a committed fixture out as a prepared export, without changing it."""
    source = ROOT / "tools/map-factory/fixtures" / slug
    folder.mkdir(parents=True, exist_ok=True)
    for name in ("terrain.u16", "water.u16", "hydrology.json"):
        (folder / name).write_bytes(
            gzip.decompress((source / (name + ".gz")).read_bytes())
        )
    for name in ("evidence.json", "plan.npz", "landcover.u8.gz"):
        (folder / name).write_bytes((source / name).read_bytes())
    return folder


def constructed_qualified_ledger():
    """Constructed launch identity for gate tests, never real native evidence."""
    ledger = copy.deepcopy(LEDGER)
    ledger["native_path_certificates"] = copy.deepcopy(
        ledger["evidence_studies"]["outside-v1"]["qualification_candidates"]
    )
    for certificate in ledger["native_path_certificates"]:
        del certificate["blocked_by"]
        context = certificate["native_context"]
        context["runtime_game_sha256"] = "a" * 64
        context["runtime_game_assemblies"] = copy.deepcopy(context["game_assemblies"])
        context["protocol"]["entry"] = "NewGameFromMap"
        context["protocol"]["inverted_traffic"] = False
        certificate["runtime_identity_evidence"] = {
            "file": "tools/map-factory/capability-evidence/runtime-identities/"
            + "a" * 64
            + ".json",
            "sha256": "a" * 64,
        }
    return ledger


QUALIFIED = constructed_qualified_ledger()


def qualification_cases():
    certificate = next(
        c for c in QUALIFIED["native_path_certificates"] if c["capability"] == "ship"
    )
    identity = {
        name: copy.deepcopy(certificate[name])
        for name in ("artifact_sha256", "inputs_sha256", "native_context")
    }
    base = {
        "schema": 1,
        "mode": "export",
        "graph": {
            "nodes": [{"outside": "west"}, {"outside": "east"}],
            "edges": [{"a": 0, "b": 1, "kind": "ship"}],
        },
        "export_identity": identity,
    }
    cases = [base]
    for path, value in (
        (("mode",), "estimate"),
        (("export_identity",), None),
        (("export_identity",), True),
        (("export_identity", "artifact_sha256"), "0" * 64),
        (("export_identity", "inputs_sha256"), {}),
        (("export_identity", "inputs_sha256", "water.u16"), "0" * 64),
        (("export_identity", "native_context"), None),
        (("export_identity", "native_context"), {}),
        (("export_identity", "native_context", "mod_sha256"), "0" * 64),
        (("export_identity", "native_context", "collector_sha256"), "0" * 64),
        (("export_identity", "native_context", "runtime_game_sha256"), None),
        (("export_identity", "native_context", "runtime_game_assemblies"), None),
        (
            (
                "export_identity",
                "native_context",
                "game_assemblies",
                "Assembly-CSharp.dll",
            ),
            "0" * 64,
        ),
        (("export_identity", "native_context", "protocol", "no_workshop"), False),
        (("planner_enabled",), {"ship": False}),
        (("graph",), None),
    ):
        data = copy.deepcopy(base)
        parent = data
        for key in path[:-1]:
            parent = parent[key]
        parent[path[-1]] = value
        cases.append(data)
    air = next(
        c for c in QUALIFIED["native_path_certificates"] if c["capability"] == "air"
    )
    data = copy.deepcopy(base)
    data["graph"]["edges"][0]["kind"] = "air"
    data["export_identity"] = {name: copy.deepcopy(air[name]) for name in identity}
    cases.append(data)
    return cases


def narrow_ship_export(planner_report=None):
    """Constructed depth, real offline planner; not native game evidence."""
    ground = np.full((1081, 1081), 100.0)
    depth = np.zeros_like(ground)
    depth[540:544, :] = 8.0  # 64 m, narrower than the model's shore buffer.
    geometry = {"sq": {"lon": 0, "lat": 0, "rotation": 0, "scale": 1}, "seaLevel": 108}
    fragment, _ = ship_path(geometry, ground, depth, 12, 108)
    if fragment is None:
        raise AssertionError(
            "Counterexample no longer exercises an authored ship route"
        )
    with tempfile.TemporaryDirectory() as temporary:
        folder = Path(temporary)
        for name, grid in (("terrain.u16", ground), ("water.u16", depth)):
            (np.flipud(grid) * 64).astype("<u2").tofile(folder / name)
        (folder / "hydrology.json").write_text(
            json.dumps({"highways": fragment, "highway_report": planner_report or {}})
        )
        return prepared_input(folder)


class CapabilityParity(unittest.TestCase):
    def test_midpoints_and_unreached_endpoints_are_not_boundary_witnesses(self):
        segments = {
            1: {
                "id": 1,
                "start": 10,
                "end": 11,
                "start_flags": "Created, Outside",
                "end_flags": "Created",
            },
            2: {
                "id": 2,
                "start": 12,
                "end": 13,
                "start_flags": "Created",
                "end_flags": "Created, Outside",
            },
        }
        path = {
            "request": {
                "name": "outside-to-outside",
                "from": [1, 0, 0],
                "to": [2, 0, 255],
            },
            "result": {"success": True, "positions": [[1, 0, 0], [2, 0, 255]]},
        }
        self.assertTrue(boundary_probe(path, segments))
        midpoint = copy.deepcopy(path)
        midpoint["request"]["from"][2] = 128
        midpoint["result"]["positions"][0][2] = 128
        self.assertFalse(boundary_probe(midpoint, segments))
        unreached = copy.deepcopy(path)
        unreached["result"]["positions"][-1][2] = 128
        self.assertFalse(boundary_probe(unreached, segments))
        named = copy.deepcopy(path)
        named["request"]["name"] = "named-midpoint-probe"
        self.assertFalse(boundary_probe(named, segments))
        within = copy.deepcopy(path)
        within["request"]["to"][0] = 1
        self.assertFalse(boundary_probe(within, segments))

    def test_seeded_grids_and_directed_graphs_match_javascript(self):
        rng = random.Random(1119)
        inputs = []
        for iteration in range(40):
            size = 17
            depth = [
                8 if rng.random() < iteration / 39 else 0 for _ in range(size * size)
            ]
            graph = {
                "nodes": [
                    {"outside": "west" if i == 0 else "east" if i == 7 else None}
                    for i in range(8)
                ],
                "edges": [
                    {
                        "a": rng.randrange(8),
                        "b": rng.randrange(8),
                        "kind": rng.choice(["rail", "ship", "air", "highway", "ramp"]),
                    }
                    for _ in range(15)
                ],
            }
            inputs.append(
                {
                    "schema": 1,
                    "mode": "export" if iteration % 2 else "estimate",
                    "grid": {"size": size, "spacing_m": 1080, "depth_m": depth},
                    "graph": graph,
                    "buildable_fraction": iteration / 39,
                }
            )
        inputs.extend(
            [
                {
                    "schema": 1,
                    "mode": "estimate",
                    "transport": {"road": True, "air": False},
                },
                {"schema": 1, "mode": "export"},
            ]
        )
        inputs.append(narrow_ship_export())
        for mode in ("export", "estimate"):
            for depth in (0, 8):
                inputs.append(
                    {
                        "schema": 1,
                        "mode": mode,
                        "planner_enabled": {"ship": False, "air": False},
                        "graph": {"nodes": [], "edges": []},
                        "grid": {
                            "size": 17,
                            "spacing_m": 1080,
                            "depth_m": [depth] * 289,
                        },
                    }
                )
        inputs.extend(qualification_cases())
        javascript = """
          import {readFileSync} from 'node:fs';
          import {checkCapabilities} from './capability-model.js';
          const {ledger,cases} = JSON.parse(readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify(cases.map((input) => checkCapabilities(input, ledger))));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", javascript],
            cwd=ROOT,
            input=json.dumps({"ledger": QUALIFIED, "cases": inputs}),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(
            json.loads(result.stdout), [check(data, QUALIFIED) for data in inputs]
        )

    def test_real_offline_ship_planner_is_not_vetoed_by_coarse_corridor(self):
        ship = check(narrow_ship_export(), LEDGER)["capabilities"]["ship"]
        self.assertTrue(ship["authored_route"]["candidate"])
        self.assertFalse(ship["witness"]["candidate"])
        self.assertEqual(ship["level"], "likely")
        self.assertEqual(ship["reason"], "authored_ship_route_corridor_unconfirmed")

    def test_stock_measure_definitions_and_fixtures_match_javascript(self):
        fixtures = ["asheville", "charleston", "innsbruck", "pittsburgh", "rio"]
        node = """
          import {readFileSync} from 'node:fs';
          import {measureStockMetrics, stockComparison, STOCK_MEASURES} from './capability-model.js';
          const {cases, ledger} = JSON.parse(readFileSync(0, 'utf8'));
          const load = (p) => {
            const b = readFileSync(p), v = new DataView(b.buffer, b.byteOffset, b.byteLength);
            const out = new Float64Array(b.byteLength / 8);
            for (let i = 0; i < out.length; i++) out[i] = v.getFloat64(i * 8, true);
            return out;
          };
          process.stdout.write(JSON.stringify({
            definitions: Object.fromEntries(Object.entries(STOCK_MEASURES).map(([id, m]) => [id, m.definition])),
            values: cases.map((c) => measureStockMetrics(load(c.terrain), load(c.water))),
            bands: cases.map((c) => Object.fromEntries(Object.entries(stockComparison(measureStockMetrics(load(c.terrain), load(c.water)), ledger.stock_reference)).map(([id, row]) => [id, row.band]))),
          }));
        """
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            cases, prepared = [], []
            for slug in fixtures:
                source = ROOT / "tools/map-factory/fixtures" / slug
                terrain, water = [
                    np.frombuffer(
                        gzip.open(source / f"{name}.u16.gz").read(), dtype="<u2"
                    )
                    .reshape(1081, 1081)
                    .astype(float)
                    / 64
                    for name in ("terrain", "water")
                ]
                paths = []
                for name, grid in (("terrain", terrain), ("water", water)):
                    path = folder / f"{slug}-{name}.f64"
                    grid.astype("<f8").tofile(path)
                    paths.append(str(path))
                cases.append({"terrain": paths[0], "water": paths[1]})
                prepared.append(stock_metrics(terrain, water))
            # A dyadic tie: 1 m per 16 m is exactly 6.25%, which round() takes to 6.2.
            tie = np.repeat(np.arange(1081, dtype=float), 1081).reshape(1081, 1081)
            tie_paths = []
            for name, grid in (("terrain", tie), ("water", np.zeros((1081, 1081)))):
                path = folder / f"tie-{name}.f64"
                grid.astype("<f8").tofile(path)
                tie_paths.append(str(path))
            cases.append({"terrain": tie_paths[0], "water": tie_paths[1]})
            prepared.append(stock_metrics(tie, np.zeros((1081, 1081))))
            result = subprocess.run(
                ["node", "--input-type=module", "-e", node],
                cwd=ROOT,
                input=json.dumps({"cases": cases, "ledger": LEDGER}),
                capture_output=True,
                text=True,
                check=True,
            )
        shared = json.loads(result.stdout)
        self.assertEqual(
            shared["definitions"], {key: value for key, value in STOCK_MEASURES.items()}
        )
        self.assertEqual(shared["values"], prepared, "prepared stock values drifted")
        for slug, bands, values in zip(fixtures + ["tie"], shared["bands"], prepared):
            self.assertEqual(
                bands,
                {
                    key: stock_band(value, LEDGER["stock_reference"]["metrics"][key])
                    for key, value in values.items()
                },
                f"{slug}: stock bands drifted",
            )

    def test_capture_fidelity_compares_only_whole_map_relief(self):
        """Evidence for the pan-time policy: which measures keep their stock band."""
        metrics = LEDGER["stock_reference"]["metrics"]
        fixtures = [
            "asheville",
            "innsbruck",
            "pittsburgh",
        ]  # inland: no ocean mask to replay
        comparable, differed = set(), set()
        for slug in fixtures:
            source = ROOT / "tools/map-factory/fixtures" / slug
            prepared = stock_metrics(
                *[
                    np.frombuffer(
                        gzip.open(source / f"{name}.u16.gz").read(), dtype="<u2"
                    )
                    .reshape(1081, 1081)
                    .astype(float)
                    / 64
                    for name in ("terrain", "water")
                ]
            )
            game = (
                np.asarray(Image.open(source / "input.png")).astype(float)
                * 1024
                / 65535
            )
            banks = (
                np.frombuffer(gzip.open(source / "banks.f32.gz").read(), dtype="<f4")
                .reshape(1081, 1081)
                .astype(float)
            )
            capture = stock_metrics(
                np.flipud(game), np.flipud(np.maximum(0.0, banks - game))
            )
            for key in metrics:
                if key not in STOCK_MEASURES:
                    continue
                if stock_band(prepared[key], metrics[key]) == stock_band(
                    capture[key], metrics[key]
                ):
                    comparable.add(key)
                else:
                    differed.add(key)
        self.assertEqual(comparable - differed, {"terrain_relief_m"})
        self.assertIn("wet_central_fraction", differed)
        self.assertIn("median_land_slope_percent", differed)
        # The pan-time policy must agree: only relief is compared.
        policy = subprocess.run(
            [
                "node",
                "--input-type=module",
                "-e",
                "import {CAPTURE_STOCK} from './capability-inputs.js';"
                "process.stdout.write(JSON.stringify(CAPTURE_STOCK));",
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        compared = {
            key
            for key, value in json.loads(policy.stdout).items()
            if value["comparable"]
        }
        self.assertEqual(compared, {"terrain_relief_m"})

    def test_stock_band_boundaries(self):
        metric = {"p25": 1, "p75": 3}
        self.assertEqual(
            [stock_band(v, metric) for v in (0, 1, 2, 3, 4, None)],
            [
                "below_p25",
                "typical",
                "typical",
                "typical",
                "above_p75",
                "not_comparable",
            ],
        )

    def test_only_explicit_exact_native_context_qualifies_sampled_paths(self):
        cases = qualification_cases()
        self.assertEqual(
            check(cases[0], QUALIFIED)["capabilities"]["ship"]["level"], "promised"
        )
        self.assertEqual(
            check(cases[-1], QUALIFIED)["capabilities"]["air"]["level"], "promised"
        )
        for data in cases[1:-1]:
            self.assertNotEqual(
                check(data, QUALIFIED)["capabilities"]["ship"]["level"], "promised"
            )
        self.assertNotEqual(
            check(cases[0], LEDGER)["capabilities"]["ship"]["level"], "promised"
        )

    def test_prepared_opt_out_is_unknown_not_a_negative(self):
        data = narrow_ship_export({"ship": "off", "air": "off"})
        self.assertEqual(data["planner_enabled"], {"ship": False, "air": False})
        for graph in (data["graph"], {"nodes": [], "edges": []}):
            data["graph"] = graph
            report = check(data, LEDGER)["capabilities"]
            for key in ("ship", "air"):
                self.assertEqual(
                    report[key], {"level": "unknown", "reason": "planner_disabled"}
                )
        del data["planner_enabled"]
        self.assertEqual(
            check(data, LEDGER)["capabilities"]["ship"]["level"], "not_possible_here"
        )

    def test_place_evidence_matches_javascript(self):
        cases = place_cases()
        javascript = """
          import {readFileSync} from 'node:fs';
          import {checkCapabilities} from './capability-model.js';
          const {ledger, cases} = JSON.parse(readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify(cases.map((input) => checkCapabilities(input, ledger))));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", javascript],
            cwd=ROOT,
            input=json.dumps({"ledger": LEDGER, "cases": [data for _, data in cases]}),
            capture_output=True,
            text=True,
            check=True,
        )
        shared = json.loads(result.stdout)
        self.assertEqual(len(shared), len(cases))
        for (name, data), report in zip(cases, shared):
            self.assertEqual(report, check(data, LEDGER), name)

    def test_place_evidence_levels_name_their_evidence(self):
        expected = {
            "mixed evidence on a ramped square": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "terrain absent leaves slope unscreened": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "land cover missing is unknown, not No": (
                ("unknown", "no_landcover_evidence"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "deposits missing, land cover present": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "deposit source unavailable": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "full tree cover": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "built-up only, no deposit": (
                ("not_possible_here", "no_tree_supporting_cover"),
                ("unknown", "no_recorded_deposit_or_fertile_cover"),
            ),
            "sparse grass is below the tree threshold": (
                ("not_possible_here", "no_tree_supporting_cover"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "shrub clears the tree threshold": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "steep shrub is screened to no trees": (
                ("not_possible_here", "no_tree_supporting_cover"),
                ("unknown", "no_recorded_deposit_or_fertile_cover"),
            ),
            "no land-cover data at all": (
                ("unknown", "landcover_coverage_incomplete"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "partial land-cover coverage stays unknown": (
                ("unknown", "landcover_coverage_incomplete"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "no recorded deposit is not absence": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "deposit recorded outside the central tiles": (
                ("not_possible_here", "no_tree_supporting_cover"),
                ("unknown", "recorded_deposit_outside_central_tiles"),
            ),
            "a well is not a deposit record": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "crop_and_pasture_cover"),
            ),
            "no central land to judge": (
                ("unknown", "no_central_land"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "all dry, coverage complete": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
            "export mode keeps the same candidate levels": (
                ("likely", "vegetation_suitability_candidate"),
                ("likely", "recorded_deposit_in_central_tiles"),
            ),
        }
        for name, data in place_cases():
            report = check(data, LEDGER)["capabilities"]
            trees = (report["trees"]["level"], report["trees"]["reason"])
            resources = (report["resources"]["level"], report["resources"]["reason"])
            self.assertEqual((trees, resources), expected[name], name)
            # Every positive names its evidence and never claims a promise.
            for key in ("trees", "resources"):
                self.assertIn("evidence", report[key], name)
                self.assertEqual(
                    report[key]["evidence"]["balanced_top_up"], "not_evidence"
                )
                self.assertNotEqual(report[key]["level"], "promised", name)

    def test_place_rules_mirror_the_writer(self):
        import resources

        self.assertEqual(
            {int(k): v for k, v in PLACE_RULES["tree_weight"].items()},
            resources.TREE_WEIGHT,
        )
        self.assertEqual(
            {int(k): v for k, v in PLACE_RULES["fertile_weight"].items()},
            resources.FERTILE_WEIGHT,
        )
        # resources.py: cover *= clip((0.5 - axis) / 0.1)
        self.assertEqual(PLACE_RULES["tree_slope_limit_percent"], 50)
        self.assertEqual(PLACE_RULES["tree_slope_taper_percent"], 10)
        # resources.py: flat = clip((14 - slope) / 8)
        self.assertEqual(PLACE_RULES["fertile_slope_full_percent"], 6)
        self.assertEqual(PLACE_RULES["fertile_slope_none_percent"], 14)
        self.assertEqual(PLACE_RULES["land_depth_m"], 0.25)
        self.assertEqual(PLACE_RULES["central_half_extent_m"], 4800)
        evidence = check(place_cases()[0][1], LEDGER)["capabilities"]["trees"][
            "evidence"
        ]
        produced = set(place_measures(evidence))
        for capability in LEDGER["capabilities"]:
            declared = set(capability.get("evidence_metrics", {}))
            self.assertTrue(declared <= produced, capability["id"])

    def test_committed_fixtures_keep_their_measured_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            for slug in FIXTURES:
                folder = extract_fixture(slug, Path(tmp) / slug)
                grid = prepared_input(folder)["grid"]
                place = place_input(folder)
                levels = place_capabilities(grid, place, PLACE_RULES)
                evidence = levels["trees"]["evidence"]
                self.assertEqual(evidence["landcover"]["status"], "available", slug)
                self.assertEqual(
                    evidence["landcover"]["coverage_of_central_land"], 1.0, slug
                )
                self.assertEqual(levels["trees"]["level"], "likely", slug)
                self.assertGreater(
                    evidence["vegetation"]["tree_suitability"], 0.3, slug
                )
                self.assertLess(evidence["vegetation"]["tree_suitability"], 0.8, slug)
                if slug == "rio":
                    self.assertEqual(levels["resources"]["level"], "unknown", slug)
                    self.assertEqual(
                        levels["resources"]["reason"],
                        "no_recorded_deposit_or_fertile_cover",
                        slug,
                    )
                else:
                    self.assertEqual(levels["resources"]["level"], "likely", slug)
                # The final plan's own cover runs the same direction, and the
                # exporter report keeps evidence beside the plan's level.
                with np.load(folder / "plan.npz") as plan:
                    self.assertGreater(int((plan["forest"] > 0).sum()), 0, slug)
                report = assess_prepared(folder)
                self.assertEqual(report["capabilities"]["trees"]["level"], "likely")
                self.assertEqual(report["capabilities"]["trees"]["evidence"], evidence)
                metric = report["metrics"]["tree_suitability"]
                self.assertEqual(
                    metric["value"], evidence["vegetation"]["tree_suitability"]
                )
                self.assertEqual(metric["band"], "not_comparable")
                self.assertIn("WorldCover", metric["definition"])

    def test_lattice_sampling_reproduces_the_ten_metre_share(self):
        """The pan-time lattice reads 2.4 percent of the 10 m cells."""
        nodes = [min(1727, int(6.4 * row)) for row in range(271) if 60 <= row <= 210]
        for slug in FIXTURES:
            native = np.frombuffer(
                gzip.decompress(
                    (
                        ROOT / "tools/map-factory/fixtures" / slug / "landcover.u8.gz"
                    ).read_bytes()
                ),
                np.uint8,
            ).reshape(1728, 1728)
            window = native[384:1344, 384:1344]
            sample = native[np.ix_(nodes, nodes)]
            for classes, label in (
                ([10, 95], "tree cover"),
                ([40], "crop"),
                ([10, 20, 30, 40, 90, 95, 100], "vegetated"),
            ):
                reference = float(np.isin(window, classes).mean())
                measured = float(np.isin(sample, classes).mean())
                self.assertLess(
                    abs(measured - reference), 0.005, f"{slug}: {label} drifted"
                )

    def test_mrds_records_parse_identically(self):
        square = {"lon": -82.555, "lat": 35.58, "rotation": 0, "scale": 1}
        xml = (ROOT / "test/mrds-sample.xml").read_bytes()
        javascript = """
          import {readFileSync} from 'node:fs';
          import {parseMrdsXml} from './capability-evidence.js';
          const {xml, square} = JSON.parse(readFileSync(0, 'utf8'));
          process.stdout.write(JSON.stringify(parseMrdsXml(xml, square)));
        """
        result = subprocess.run(
            ["node", "--input-type=module", "-e", javascript],
            cwd=ROOT,
            input=json.dumps({"xml": xml.decode("utf8"), "square": square}),
            capture_output=True,
            text=True,
            check=True,
        )
        self.assertEqual(json.loads(result.stdout), parse_mrds(square, xml))


if __name__ == "__main__":
    unittest.main()
