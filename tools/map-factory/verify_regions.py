"""Verify the committed reference fixtures, not native game playability."""

import argparse
import gzip
import hashlib
from io import BytesIO
import json
import struct
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

from crp import (
    N,
    Reader,
    decode_u16,
    encode_u16,
    metadata_value,
    mono_hash,
    read_package,
    write_map,
    write_package,
)
from generate import generate
from region import prepare
from template import decode_array, describe, encode_array, manager_tag, saved_camera

ROOT = Path(__file__).resolve().parent


def unpack(source, target):
    target.write_bytes(gzip.decompress(source.read_bytes()))


def verify(folder):
    manifest = json.loads((folder / "manifest.json").read_text())
    template = ROOT / manifest["template"]
    layout = ROOT / manifest["layout"]
    spec = json.loads(layout.read_text())
    native = template.read_bytes()
    package, assets = read_package(native)
    assert write_package(package, assets) == native
    original_data = next(a["payload"] for a in assets if a["kind"] == 52)
    assert hashlib.sha256(native).hexdigest() == manifest["template_sha256"]
    assert mono_hash("Asheville - Ready to Play") == -1740401844
    for width in [1, 2, 4, 8]:
        values = np.array(
            [0] * 129 + [2 ** (width * 8) - 1, 0, 1, 2] + [2] * 130, dtype=f"u{width}"
        )
        encoded = encode_array(values, width)
        decoded, end = decode_array(encoded, len(values), 0, width)
        assert np.array_equal(values, decoded) and end == len(encoded)
        if width == 2:
            assert encoded == encode_u16(values)
        try:
            decode_array(encoded[:-1], len(values), 0, width)
        except ValueError:
            pass
        else:
            raise AssertionError("Truncated arrays must be refused")
    reports = []
    with tempfile.TemporaryDirectory(
        prefix=".verify-regions-", dir=folder
    ) as temporary:
        scratch = Path(temporary)
        original_layout = scratch / "original-layout.json"
        original_layout.write_text(
            json.dumps({k: spec[k] for k in ["template_sha256", "ranges"]})
        )
        actual_layout = scratch / "actual-layout.json"
        describe(template, original_layout, actual_layout)
        assert json.loads(actual_layout.read_text()) == spec
        for case in manifest["cases"]:
            slug = case["slug"]
            fixture = folder / slug
            for name, expected_hash in case["files_sha256"].items():
                assert (
                    hashlib.sha256((fixture / name).read_bytes()).hexdigest()
                    == expected_hash
                ), (slug, name)
            work = scratch / slug
            work.mkdir()
            for name in [
                "terrain.u16",
                "water.u16",
                "banks.f32",
                "geometry.json",
                "hydrology.json",
            ]:
                unpack(fixture / (name + ".gz"), work / name)
            raw = np.fromfile(work / "terrain.u16", dtype="<u2")
            depth = np.fromfile(work / "water.u16", dtype="<u2")
            if (fixture / "landmarks.json").exists():
                landmarks = json.loads((fixture / "landmarks.json").read_text())
                assert len(landmarks["points"]) >= 2 and landmarks["reference"]
                for point in landmarks["points"]:
                    value = ndimage.map_coordinates(
                        raw.reshape(1081, 1081).astype(float) / 64,
                        [[point["z"] / 16 + 540], [point["x"] / 16 + 540]],
                        order=1,
                    )[0]
                    assert (
                        abs(value - point["expected_height_m"]) <= point["tolerance_m"]
                    ), (slug, point["name"], "independent geographic DEM check", value)
            for name, expected_hash in case["prepared_sha256"].items():
                assert (
                    hashlib.sha256((work / name).read_bytes()).hexdigest()
                    == expected_hash
                )
            assert len(raw) == len(depth) == N
            hydro = json.loads((work / "hydrology.json").read_text())
            output = work / (slug + ".crp")
            receipt = write_map(
                template,
                layout,
                work / "terrain.u16",
                work / "water.u16",
                work / "hydrology.json",
                output,
            )
            assert receipt["sha256"] == case["expected_crp_sha256"], slug
            assert receipt["bytes"] == case["expected_crp_bytes"], slug
            assert receipt["simulation_sha256"] == case["expected_simulation_sha256"], (
                slug
            )
            generated_package, generated_assets = read_package(output.read_bytes())
            assert generated_package["author"] == ""
            assert (
                write_package(generated_package, generated_assets)
                == output.read_bytes()
            )
            data = next(a["payload"] for a in generated_assets if a["kind"] == 52)
            metadata = next(a["payload"] for a in generated_assets if a["kind"] == 100)
            reader = Reader(metadata)
            assert reader.number("B") == 0
            assert reader.string().startswith("MapMetaData,")
            reader.string()
            fields = {}
            for _ in range(reader.number("i")):
                if reader.number("B"):
                    continue
                typename, field = reader.string().split(",")[0], reader.string()
                fields[field] = metadata_value(reader, typename)
            assert fields["mapName"] == hydro["map_name"]
            assert fields["publishedHash"] == mono_hash(hydro["map_name"])
            assert fields["assetRef"] == hashlib.md5(data).hexdigest()
            assert fields["mods"] == [] and fields["waterAmount"] > 0
            # Inspect independently through the package's public texture stream:
            # references must resolve to real, useful PNG images, not just flags.
            by_checksum = {
                hashlib.md5(asset["payload"]).hexdigest(): asset
                for asset in generated_assets
            }
            for field, size in [
                ("imageRef", (400, 224)),
                ("steamPreviewRef", (1800, 1008)),
            ]:
                asset = by_checksum[fields[field]]
                assert asset["kind"] == 3
                texture = Reader(asset["payload"])
                assert texture.number("B") == 0
                assert texture.string().startswith("ColossalFramework.Importers.Image,")
                assert texture.string() == asset["name"]
                assert texture.number("B") == 0 and texture.number("i") == 1
                png = texture.take(texture.number("i"))
                assert texture.pos == len(asset["payload"])
                with Image.open(BytesIO(png)) as image:
                    assert image.format == "PNG" and image.size == size
                    assert np.asarray(image).std() > 10, "Blank map preview"
            assert 0 <= fields["buildableArea"] <= 100
            assert abs(fields["maxResourceAmount"] - 20631704) < 2
            offset = data.index(manager_tag("TerrainManager")) + len(
                manager_tag("TerrainManager")
            )
            actual, end = decode_u16(data, N, offset)
            assert np.array_equal(actual, raw)
            deltas, _ = decode_u16(data, int(np.count_nonzero(raw)), end)
            assert not deltas.any()
            water_start = data.index(manager_tag("WaterSimulation")) + len(
                manager_tag("WaterSimulation")
            )
            actual, _ = decode_u16(data, N, water_start)
            assert np.array_equal(actual, depth)
            # Check every unmodified network byte, including flags, lane IDs,
            # connection IDs and prefab references, against the native oracle.
            net = next(r for r in spec["ranges"] if r["type"] == "NetManager+Data")
            delta = data.index(manager_tag("NetManager")) - net["start"]
            expected_net = bytearray(original_data[net["start"] : net["end"]])
            actual_net = bytearray(data[net["start"] + delta : net["end"] + delta])
            for node in spec["nodes"]:
                at = node["offset"] - net["start"]
                expected_position = struct.pack(
                    ">3f", *hydro["node_positions"][str(node["id"])]
                )
                assert actual_net[at : at + 12] == expected_position
                actual_net[at : at + 12] = expected_net[at : at + 12]
            for segment in spec["segments"]:
                at = segment["direction_offset"] - net["start"]
                vectors = struct.unpack_from(">6f", actual_net, at)
                assert abs(sum(v * v for v in vectors[:3]) - 1) < 1e-5
                assert all(abs(a + b) < 1e-6 for a, b in zip(vectors[:3], vectors[3:]))
                actual_net[at : at + 24] = expected_net[at : at + 24]
            assert expected_net == actual_net, "Unexpected topology or lane mutation"
            node_index = {n["id"]: n for n in spec["nodes"]}
            for building in spec["buildings"]:
                # BuildingManager precedes the resource rewrite, so its shift
                # equals NetManager's terrain/water-induced shift.
                at = building["offset"] + delta
                x, y, z, angle = struct.unpack_from(">4f", data, at)
                position = hydro["node_positions"][str(building["node"])]
                assert abs(x - position[0]) < 0.002 and abs(z - position[2]) < 0.002
                old_offset = (
                    building["position"][1]
                    - node_index[building["node"]]["position"][1]
                )
                assert abs(y - position[1] - old_offset) < 0.002
                assert 0 <= angle <= 2 * np.pi + 1e-5
            points = [point for group in hydro["samples"].values() for point in group]
            grid = depth.reshape(1081, 1081)
            wet = int(
                sum(
                    grid[round((z + 8640) / 16), round((x + 8640) / 16)] > 6
                    for x, _, z in points
                )
            )
            assert wet == len(points), (slug, "initial wet samples", wet, len(points))
            start_offset = (
                data.index(manager_tag("GameAreaManager"))
                + len(manager_tag("GameAreaManager"))
                + 1
            )
            assert data[start_offset] == hydro["start_tile"]
            camera = saved_camera(data, start_offset)
            mode, x, y, z, size, yaw, pitch, height = struct.unpack_from(
                ">h7f", data, camera["offset"]
            )
            assert (mode, size, yaw, pitch, height) == (2, 1000, 0, 60, 0)
            assert (x, z) == (
                (hydro["start_tile"] % 5 - 2) * 1920,
                (hydro["start_tile"] // 5 - 2) * 1920,
            )
            assert (
                y == raw.reshape(1081, 1081)[int(z / 16 + 540), int(x / 16 + 540)] / 64
            )
            resource_offset = data.index(manager_tag("NaturalResourceManager")) + len(
                manager_tag("NaturalResourceManager")
            )
            for _ in range(4):
                forest, resource_offset = decode_array(
                    data, 512 * 512, resource_offset, 1
                )
            _, resource_offset = decode_array(
                data, int(np.count_nonzero(forest)), resource_offset, 1
            )
            _, resource_offset = decode_array(
                data, int(np.count_nonzero(forest == 0)), resource_offset, 1
            )
            for _ in range(5):
                _, resource_offset = decode_array(data, 512 * 512, resource_offset, 1)
            areas, _ = decode_array(data, 81 * 10, resource_offset, 4)
            assert fields["waterAmount"] == int(
                areas[9 * 81 : 10 * 81].reshape(9, 9)[2:7, 2:7].sum()
            ), "Listing resources must describe the 25 unlockable tiles"
            tile = (hydro["start_tile"] // 5 + 2) * 9 + hydro["start_tile"] % 5 + 2
            assert areas[9 * 81 + tile] > 0, (
                "Serialized start tile has no resource water"
            )
            assert hydro["start_area"]["has_water"]
            assert hydro["max_channel_lowering_m"] <= 3.001
            assert hydro["max_corridor_cut_m"] <= 3.001
            assert hydro["max_corridor_fill_m"] <= 3.001
            assert all(
                c["maximum_grade"] <= (0.04001 if c["kind"] == "rail" else 0.12001)
                for c in hydro["corridors"]
            )
            # Independently rerun the geographic preparation from the frozen
            # browser inputs, then compare its real output with the fixture.
            prepared = work / "reprepared"
            prepare(
                fixture / "input.png",
                work / "geometry.json",
                layout,
                prepared,
                work / "banks.f32",
            )
            for name in ["terrain.u16", "water.u16"]:
                assert (prepared / name).read_bytes() == (work / name).read_bytes(), (
                    slug,
                    name,
                )
            assert json.loads((prepared / "hydrology.json").read_text()) == hydro
            reports.append(
                {
                    "region": slug,
                    "crp_sha256": receipt["sha256"],
                    "initial_wet_samples": wet,
                    "sample_count": len(points),
                    "native_topology_bytes_preserved": True,
                    "frozen_inputs_reproduced": True,
                    "in_game_verified": False,
                }
            )
        # Constructed cases cover edge orientations absent from the five real
        # captures and the explicit dry-region fallback. They are not geodata.
        flat = scratch / "flat.png"
        bank_file = scratch / "flat-banks.f32"
        Image.fromarray(np.full((1081, 1081), 3200, dtype=np.uint16)).save(flat)
        np.full((1081, 1081), 50, dtype="<f4").tofile(bank_file)
        for edge, x, z in [
            ("west", -9000, 0),
            ("east", 9000, 0),
            ("south", 0, -9000),
            ("north", 0, 9000),
        ]:
            lon = float(np.rad2deg(x / 6378137))
            lat = float(np.rad2deg(z / (6378137 * (1 - 0.00669437999014))))
            geometry = {
                "sq": {
                    "name": "Constructed dry case",
                    "slug": edge,
                    "lon": 0,
                    "lat": 0,
                    "rotation": 0,
                    "scale": 1,
                },
                "rivers": [],
                "lakes": [],
                "riverAreas": [],
                "seaLevel": None,
                "roads": [{"class": "motorway", "pts": [[lon, lat], [0, 0]]}],
            }
            geometry_file = scratch / (edge + "-geometry.json")
            geometry_file.write_text(json.dumps(geometry))
            target = scratch / edge
            generate(flat, geometry_file, target, bank_file)
            hydro = json.loads((target / "hydrology.json").read_text())
            assert hydro["road_entry"]["edge"] == edge
            assert hydro["starter_reservoir"] and hydro["start_tile"] == 12
            for node in spec["nodes"]:
                if max(abs(node["position"][axis]) for axis in [0, 2]) >= 8639:
                    position = hydro["node_positions"][str(node["id"])]
                    assert (
                        abs(max(abs(position[axis]) for axis in [0, 2]) - 8640) < 0.01
                    )
    return {
        "native_template_roundtrip": True,
        "native_descriptor_reproduced": True,
        "encoded_array_widths_roundtrip": True,
        "truncated_arrays_refused": True,
        "constructed_four_edge_and_dry_region_cases": True,
        "cases": reports,
        "in_game_verified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path, nargs="?", default=ROOT / "fixtures")
    print(json.dumps(verify(parser.parse_args().folder), indent=2))
