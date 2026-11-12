"""Intentionally replace the Python/JavaScript reference fixtures from captures.

This is a fixture-authoring command, never part of verification. Review changed
hashes and native-game results before accepting an updated reference contract.
"""

import argparse
import gzip
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from crp import Reader, metadata_value, read_package
from generate import ROOT, generate

REGIONS = ["asheville", "innsbruck", "rio", "pittsburgh", "charleston"]


def geographic_identity(geometry):
    """Compare feature collections without changing rings, lines or multiplicity."""
    collections = {"rivers", "streams", "lakes", "riverAreas", "roads", "oceans"}
    return {
        key: sorted(value, key=lambda feature: json.dumps(feature, sort_keys=True))
        if key in collections
        else value
        for key, value in geometry.items()
    }


def freeze_previews(crp, case):
    """Keep expected encoded images available to independent serializer ports."""
    _, assets = read_package(crp.read_bytes())
    reader = Reader(next(a["payload"] for a in assets if a["kind"] == 100))
    assert reader.number("B") == 0 and reader.string().startswith("MapMetaData,")
    reader.string()
    fields = {}
    for _ in range(reader.number("i")):
        if reader.number("B"):
            continue
        typename, name = reader.string().split(",")[0], reader.string()
        fields[name] = metadata_value(reader, typename)
    checksums = {hashlib.md5(a["payload"]).hexdigest(): a for a in assets}
    previews = {}
    for field, name in [
        ("imageRef", "preview-thumbnail.png"),
        ("steamPreviewRef", "preview-large.png"),
    ]:
        asset = checksums[fields[field]]
        assert asset["kind"] == 3
        texture = Reader(asset["payload"])
        assert texture.number("B") == 0
        assert texture.string().startswith("ColossalFramework.Importers.Image,")
        assert texture.string() == asset["name"]
        assert texture.number("B") == 0 and texture.number("i") == 1
        png = texture.take(texture.number("i"))
        assert texture.pos == len(asset["payload"])
        assert png.startswith(b"\x89PNG\r\n\x1a\n")
        (case / name).write_bytes(png)
        previews[field] = {
            "file": name,
            "texture_asset_md5": fields[field],
            "png_sha256": hashlib.sha256(png).hexdigest(),
        }
    return previews


def freeze(inputs, output, resource_inputs=None, captures=None, shipping_captures=None):
    output.mkdir(parents=True, exist_ok=True)
    template = ROOT / "templates/native-corridors.crp"
    manifest = {
        "format": 1,
        "template": "templates/native-corridors.crp",
        "layout": "templates/native-corridors.json",
        "template_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
        "native_template_origin": "PL-848 editor factory; region-to-skylines PR #1 at 4011a6b717e50bebd92f0b9caf8547a7a16e5c8c",
        "status": "byte reference; native qualification tracked separately in NATIVE_FINDINGS.md",
        "cases": [],
    }
    if captures is not None:
        manifest["capture_module"] = "inputs.js"
        manifest["capture_sources_sha256"] = {
            name: hashlib.sha256((ROOT.parents[1] / name).read_bytes()).hexdigest()
            for name in ["inputs.js", "terrain.js"]
        }
    with tempfile.TemporaryDirectory(prefix=".freeze-", dir=output) as temporary:
        scratch = Path(temporary)
        for slug in REGIONS:
            case = output / slug
            case.mkdir(exist_ok=True)
            generated = scratch / slug
            result = generate(
                inputs / f"{slug}.png",
                inputs / f"{slug}-geometry.json",
                generated,
                inputs / f"{slug}-banks.f32",
                landcover=resource_inputs / slug / "landcover.u8.gz"
                if resource_inputs
                else None,
                evidence=resource_inputs / slug / "evidence.json"
                if resource_inputs
                and (resource_inputs / slug / "evidence.json").exists()
                else None,
            )
            shutil.copyfile(inputs / f"{slug}.png", case / "input.png")
            landmarks = inputs / f"{slug}-landmarks.json"
            if landmarks.exists():
                shutil.copyfile(landmarks, case / "landmarks.json")
            elif (case / "landmarks.json").exists():
                raise ValueError(f"Refusing to silently reuse stale {slug} landmarks")
            files = {
                "geometry.json": inputs / f"{slug}-geometry.json",
                "banks.f32": inputs / f"{slug}-banks.f32",
                "terrain.u16": generated / "terrain.u16",
                "water.u16": generated / "water.u16",
                "hydrology.json": generated / "hydrology.json",
            }
            capture = None
            if captures is not None:
                receipt = json.loads((captures / slug / "capture.json").read_text())
                if receipt["cli_sha256"] != receipt["crp_sha256"]:
                    raise ValueError(f"Capture did not reproduce the live CLI: {slug}")
                capture = {
                    "source_commit": receipt["source_commit"],
                    "source_files_sha256": receipt["source_files_sha256"],
                    "cli_sha256": receipt["cli_sha256"],
                    "files_sha256": {},
                    "prepared_sha256": {},
                }
                for name, path in {
                    "input.png": inputs / f"{slug}.png",
                    "geometry.json": files["geometry.json"],
                    "banks.f32": files["banks.f32"],
                }.items():
                    expected = receipt["files_sha256"][name]
                    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                        raise ValueError(
                            f"Input differs from inputs.js capture: {slug}/{name}"
                        )
                    capture["files_sha256"][name] = expected
                for name in ["terrain.u16", "water.u16"]:
                    expected = receipt["files_sha256"]["out/" + name]
                    if hashlib.sha256(files[name].read_bytes()).hexdigest() != expected:
                        raise ValueError(
                            f"Terrain/water no longer match live pin: {slug}/{name}"
                        )
                    capture["prepared_sha256"][name] = expected
            shipping = None
            if shipping_captures is not None:
                source = shipping_captures / slug
                shipped = json.loads((source / "capture.json").read_text())
                for name in [
                    "input.png",
                    "geometry.json",
                    "banks.f32",
                    "landcover.u8.gz",
                ]:
                    if (
                        hashlib.sha256((source / name).read_bytes()).hexdigest()
                        != shipped["files_sha256"][name]
                    ):
                        raise ValueError(
                            f"Shipping capture files changed: {slug}/{name}"
                        )
                for name, path in {
                    "input.png": inputs / f"{slug}.png",
                    "banks.f32": files["banks.f32"],
                }.items():
                    if (
                        hashlib.sha256(path.read_bytes()).hexdigest()
                        != shipped["files_sha256"][name]
                    ):
                        raise ValueError(
                            f"Shipping capture changed geographic inputs: {slug}/{name}"
                        )
                if geographic_identity(
                    json.loads(files["geometry.json"].read_text())
                ) != geographic_identity(
                    json.loads((source / "geometry.json").read_text())
                ):
                    raise ValueError(
                        f"Shipping geographic features changed, not just their order: {slug}"
                    )
                if (
                    not resource_inputs
                    or (source / "landcover.u8.gz").read_bytes()
                    != (resource_inputs / slug / "landcover.u8.gz").read_bytes()
                ):
                    raise ValueError(f"Shipping/reference land cover differs: {slug}")
                evidence = source / "evidence.json"
                shipping_work = scratch / (slug + "-shipping")
                shipping_result = generate(
                    inputs / f"{slug}.png",
                    source / "geometry.json",
                    shipping_work,
                    files["banks.f32"],
                    landcover=source / "landcover.u8.gz",
                    evidence=evidence if evidence.exists() else None,
                )
                if (
                    shipping_result["package"]["sha256"] != shipped["cli_sha256"]
                    or shipped["cli_sha256"] != shipped["crp_sha256"]
                ):
                    raise ValueError(
                        f"Shipping fixture does not reproduce the current CLI: {slug}"
                    )
                for name in ["terrain.u16", "water.u16"]:
                    if (shipping_work / name).read_bytes() != files[name].read_bytes():
                        raise ValueError(
                            f"Shipping resources changed native-tested grids: {slug}/{name}"
                        )
                reference_hydro = json.loads(files["hydrology.json"].read_text())
                shipping_hydro = json.loads(
                    (shipping_work / "hydrology.json").read_text()
                )
                for name in ["sources", "node_positions", "start_tile", "sea_level_m"]:
                    if reference_hydro[name] != shipping_hydro[name]:
                        raise ValueError(
                            f"Shipping water/connection controls changed: {slug}/{name}"
                        )
                (case / "shipping-geometry.json.gz").write_bytes(
                    gzip.compress(
                        (source / "geometry.json").read_bytes(),
                        compresslevel=9,
                        mtime=0,
                    )
                )
                if evidence.exists():
                    shutil.copyfile(evidence, case / "shipping-evidence.json")
                shipping = {
                    "source_commit": shipped["source_commit"],
                    "source_files_sha256": shipped["source_files_sha256"],
                    "evidence_file": "shipping-evidence.json"
                    if evidence.exists()
                    else None,
                    "geometry_file": "shipping-geometry.json.gz",
                    "input_files_sha256": {
                        name: shipped["files_sha256"][name]
                        for name in ["input.png", "geometry.json", "banks.f32"]
                    },
                    "expected_crp_sha256": shipped["cli_sha256"],
                    "expected_crp_bytes": shipping_result["package"]["bytes"],
                    "expected_simulation_sha256": shipping_result["package"][
                        "simulation_sha256"
                    ],
                }
            for name, source in files.items():
                (case / (name + ".gz")).write_bytes(
                    gzip.compress(source.read_bytes(), compresslevel=9, mtime=0)
                )
            if resource_inputs:
                for name in ["landcover.u8.gz", "landcover.json", "evidence.json"]:
                    source = resource_inputs / slug / name
                    if source.exists():
                        shutil.copyfile(source, case / name)
                if shipping_captures is not None:
                    shutil.copyfile(
                        shipping_captures / slug / "landcover.json",
                        case / "landcover.json",
                    )
                shutil.copyfile(generated / "plan.npz", case / "plan.npz")
                shutil.copyfile(generated / "resources.json", case / "resources.json")
            previews = freeze_previews(next(generated.glob("*.crp")), case)
            fixture = {
                "slug": slug,
                "expected_crp_sha256": result["package"]["sha256"],
                "expected_crp_bytes": result["package"]["bytes"],
                "expected_simulation_sha256": result["package"]["simulation_sha256"],
                "preview_assets": previews,
                "prepared_sha256": {
                    name: hashlib.sha256((generated / name).read_bytes()).hexdigest()
                    for name in ["terrain.u16", "water.u16"]
                },
                "files_sha256": {
                    p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(case.iterdir())
                    if p.is_file()
                },
            }
            if resource_inputs:
                fixture["resource_plan"] = "plan.npz"
                fixture["resource_knobs"] = result["resources"]["knobs"]
            if capture is not None:
                fixture["input_capture"] = capture
            if shipping is not None:
                fixture["shipping"] = shipping
            manifest["cases"].append(fixture)
            print(json.dumps(fixture, ensure_ascii=False), flush=True)
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("output", type=Path, nargs="?", default=ROOT / "fixtures")
    parser.add_argument(
        "--captures",
        type=Path,
        help="Per-region capture-inputs.mjs receipts; require live-pin input and prepared-grid identity",
    )
    parser.add_argument(
        "--shipping-captures",
        type=Path,
        help="Current CLI captures; retain rich reference evidence and add exact shipping-output goldens",
    )
    parser.add_argument(
        "--resource-inputs",
        type=Path,
        help="Per-region pinned landcover/evidence; freezes and checks resource plans too",
    )
    args = parser.parse_args()
    freeze(
        args.inputs,
        args.output,
        args.resource_inputs,
        args.captures,
        args.shipping_captures,
    )
