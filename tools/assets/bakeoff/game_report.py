# /// script
# dependencies = ["pillow>=11"]
# ///
"""Audit native CS1 build/check receipts and assemble a review page and contact sheets."""

import argparse
import csv
import hashlib
import html
import json
import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

VIEWS = {
    "close": "day-close",
    "gameplay": "day-gameplay",
    "lod": "day-distant",
    "night": "night-close",
    "reload": "reloaded-close",
    "back": "day-back",
    "night-lod": "night-distant",
    "high": "day-high",
}
TARGETS = ("bungalow", "storefront", "apartment")


def inspection_crop(image, target, view):
    """Same pixel rectangle for every method in a target/view, no content edits."""
    if view in ("lod", "night-lod"):
        width, height = 256, 192
    elif view == "gameplay":
        width, height = 384, 256
    elif target == "apartment":
        width, height = 768, 512
    else:
        width, height = 512, 384
    cx, cy = 640, 344
    return image.crop(
        (cx - width // 2, cy - height // 2, cx + width // 2, cy + height // 2)
    )


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def zip_entry(bundle, name, data):
    """Stable archive metadata; actual run times live in the hashed receipts."""
    entry = zipfile.ZipInfo(name)
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    bundle.writestr(entry, data)


def session_metrics(folder, receipt):
    """Keep editor-job time distinct from boot/session time and external queue waits."""
    samples = list(csv.DictReader((folder / "gpu.csv").open()))
    stamps = [
        datetime.strptime(row["timestamp"].strip(), "%Y/%m/%d %H:%M:%S.%f")
        for row in samples
    ]
    events = [
        json.loads(line)
        for line in (folder / "timeline.jsonl").read_text().splitlines()
    ]
    return {
        "gpu_logged_session_seconds": (stamps[-1] - stamps[0]).total_seconds(),
        "job_seconds": {
            e["kind"]: e["seconds"] for e in events if e.get("state") == "done"
        },
        "gpu_peak_mib": max(float(r[" memory.used [MiB]"]) for r in samples),
        "gpu_baseline_mib": receipt["session"]["gpu"]["mem_used_before_mib"],
        "game_mib_at_end": [
            int(v)
            for v in re.findall(
                r"Cities\.x64\s+(\d+)MiB", receipt["result"].get("gpu_processes", "")
            )
        ],
        "power_peak_w": max(float(r[" power.draw [W]"]) for r in samples),
        "temperature_peak_c": max(float(r[" temperature.gpu"]) for r in samples),
        "timing_note": "GPU-log span excludes queue wait, with 5-second sampling; job time excludes boot/editor loading",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument(
        "--conclusions",
        type=Path,
        help="Manual findings JSON, kept separate from measured receipts",
    )
    args = parser.parse_args()
    out = args.destination
    out.mkdir(parents=True, exist_ok=True)
    plan = json.loads((args.game / "batch-plan.json").read_text())
    assert digest(args.inputs / "manifest.json") == plan["input_manifest_sha256"]
    manifest = {
        "renderer": "CS1 1.21.1-f9, native Building/Default shader",
        "batch_plan": plan,
        "assets": [],
    }
    cards = []
    conclusions = json.loads(args.conclusions.read_text()) if args.conclusions else {}
    for target in TARGETS:
        for arm in ("A", "B", "C"):
            name = arm + "-" + target
            marker = json.loads((args.game / (name + ".complete.json")).read_text())
            assert all(
                digest(args.game / p) == h for p, h in marker["files"].items()
            ), name
            build_dir = args.game / "build" / name
            check_dir = args.game / "check" / name
            build = json.loads((build_dir / "asset-build.json").read_text())
            check = json.loads((check_dir / "asset-check.json").read_text())
            assert "error" not in build["result"], name
            assert "error" not in check["result"], name
            for run in (build, check):
                manifest.setdefault("native_mod_sha256", run["session"]["mod_sha256"])
                assert run["session"]["mod_sha256"] == manifest["native_mod_sha256"], (
                    name
                )
                assert run["session"]["cleanup"] == {
                    "game": [],
                    "steam_instances": [],
                    "units_active": [],
                }, name
                assert run["result"]["menu_status"]["enabled_mod_count"] == 0, name
            crp = build_dir / build["result"]["crp"]
            assert digest(crp) == build["result"]["crp_sha256"], name
            result = check["result"]
            assert check["session"]["map"]["sha256"] == plan["map_sha256"], name
            assert all(
                abs(result["placed"]["position"][i] - value) < 0.01
                for i, value in ((0, 0), (2, 300))
            ), name
            asset = result["asset"]
            assert (
                asset["sub_service"]
                == {
                    "bungalow": "ResidentialLow",
                    "storefront": "CommercialLow",
                    "apartment": "ResidentialHigh",
                }[target]
            ), name
            assert build["result"]["build"]["lod_from_file"], name
            assert build["result"]["build"]["lod_textures_from_file"], name
            for material, size in (
                (asset["material"], 1024),
                (asset["lod"]["material"], 256),
            ):
                assert material["shader"] == "Custom/Buildings/Building/Default", name
                for channel in ("_MainTex", "_XYSMap", "_ACIMap"):
                    assert material["textures"][channel][:2] == [size, size], (
                        name,
                        channel,
                    )
            assert result["after_reload"]["name"] == asset["name"], name
            assert result["after_reload"]["exists"], name
            assert result["after_reload"]["cells"] == result["placed"]["cells"], name
            for state in (result["placed"], result["after_reload"]):
                assert (
                    state["construct_state"] == 255 and "Completed" in state["flags"]
                ), name
            reload_delta = [
                b - a
                for a, b in zip(
                    result["placed"]["position"], result["after_reload"]["position"]
                )
            ]
            assert abs(reload_delta[0]) < 0.01 and abs(reload_delta[2]) < 0.01, name
            assert all(not p["embedded_mods"] for p in result["packages"]), name
            source = json.loads((args.inputs / name / "receipt.json").read_text())
            assert asset["cells"] == source["spec"]["lot"], name
            for level, key in (("main", "mesh"), ("lod", "lod")):
                mesh = asset[key] if level == "main" else asset[key]["mesh"]
                authored = mesh["authored"]
                assert authored["triangles"] == source[level]["triangles"], (
                    name,
                    level,
                )
                assert (
                    mesh["triangles"]
                    <= source["spec"]["budget" if level == "main" else "lod"]
                ), (name, level)
                expected = source[level]["dimensions_m"]
                expected = [expected[0], expected[2], expected[1]]
                assert all(
                    abs(a - b) < 0.03 * b + 0.05
                    for a, b in zip(authored["size"], expected)
                ), (name, level)
            dest = out / name
            dest.mkdir(exist_ok=True)
            images = {}
            for label, shot in VIEWS.items():
                p = check_dir / "shots" / (shot + ".png")
                shutil.copy2(p, dest / (label + ".png"))
                images[label] = {"path": f"{name}/{label}.png", "sha256": digest(p)}
                inspection_crop(Image.open(p).convert("RGB"), target, label).save(
                    dest / (label + "-crop.png")
                )
            manifest["assets"].append(
                {
                    "name": name,
                    "crp_sha256": digest(crp),
                    "input_receipt_sha256": digest(args.inputs / name / "receipt.json"),
                    "build_receipt_sha256": digest(build_dir / "asset-build.json"),
                    "check_receipt_sha256": digest(check_dir / "asset-check.json"),
                    "asset": asset,
                    "placement": result["placed"],
                    "after_reload": result["after_reload"],
                    "reload_position_delta_m": reload_delta,
                    "reload_height_preserved_within_1cm": abs(reload_delta[1]) < 0.01,
                    "reported_errors": {
                        "build": build["result"]["errors"],
                        "check": result["errors"],
                    },
                    "images": images,
                    "session_metrics": {
                        "build": session_metrics(build_dir, build),
                        "check": session_metrics(check_dir, check),
                    },
                    "seconds_including_queue": marker["seconds_including_queue"],
                }
            )
            cards.append(
                f'<article><h2>{html.escape(name)}{" (B1 clean concept)" if arm == "B" else ""}</h2><a class="render" href="{name}/close.png"><img src="{name}/close-crop.png" alt="Matched crop of native CS1 render of {name}"></a><p>{asset["mesh"]["triangles"]} main triangles; {asset["lod"]["mesh"]["triangles"]} LOD</p></article>'
            )
    for view in VIEWS:
        sheet = Image.new("RGB", (1800, 3 * 446 + 92), "#101612")
        draw = ImageDraw.Draw(sheet)
        font = ImageFont.load_default(size=22)
        draw.text(
            (20, 12),
            "CS1 native renderer / "
            + view
            + " / columns A procedural, B1 image-to-3D, C hybrid",
            fill="white",
            font=font,
        )
        draw.text(
            (20, 46),
            "Matched pixel crops, magnified for inspection; full unaltered frames linked in gallery",
            fill="#b9c7b8",
            font=font,
        )
        for row, target in enumerate(TARGETS):
            for col, arm in enumerate(("A", "B", "C")):
                image = Image.open(
                    out / (arm + "-" + target) / (view + "-crop.png")
                ).convert("RGB")
                image = ImageOps.pad(
                    image, (600, 400), method=Image.Resampling.NEAREST, color="#101612"
                )
                x, y = col * 600, row * 446 + 92
                draw.text(
                    (x + 10, y + 6), arm + " / " + target, fill="white", font=font
                )
                sheet.paste(image, (x, y + 40))
        sheet.save(out / ("cs1-" + view + ".png"))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    archives = []
    packages = {}
    for arm in "ABC":
        archive = out / f"cs1-{arm}-qa-assets.zip"
        assets = [
            asset for asset in manifest["assets"] if asset["name"].startswith(arm + "-")
        ]
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for asset in assets:
                name = asset["name"]
                zip_entry(
                    bundle,
                    name + ".crp",
                    (args.game / "build" / name / (name + ".crp")).read_bytes(),
                )
            zip_entry(
                bundle,
                "manifest.json",
                json.dumps({"batch_plan": plan, "assets": assets}, indent=2),
            )
            zip_entry(
                bundle,
                "README.txt",
                "PL-881 native CS1 QA assets, not Workshop releases.\n"
                "Three fixed study buildings. Local CRPs were imported, placed, saved and reloaded in fresh paused cities.\n"
                "Growth, economics, powered/occupied night lighting and long-running simulation are not certified.\n"
                "B is the B1 clean-concept control; inferred shape and open main-mesh holes remain unchanged.\n"
                "Authored dimensions are study assumptions, not surveyed ground truth.\n"
                "See manifest.json for exact CRP and source hashes.\n",
            )
        archives.append(f'<a href="{archive.name}">{arm} QA CRPs</a>')
        packages[archive.name] = {
            "sha256": digest(archive),
            "bytes": archive.stat().st_size,
            "crps": {asset["name"] + ".crp": asset["crp_sha256"] for asset in assets},
        }
    (out / "native-packages.json").write_text(json.dumps(packages, indent=2))
    findings = (
        "<p><strong>"
        + html.escape(conclusions.get("lead", "Native capture audit complete."))
        + "</strong></p><ul>"
        + "".join(
            "<li>" + html.escape(f) + "</li>" for f in conclusions.get("findings", [])
        )
        + "</ul>"
    )
    (out / "index.html").write_text(
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Asheville — native CS1 comparison</title><link rel="icon" href="data:,"><style>body{margin:auto;max-width:1600px;padding:24px;background:#101612;color:#edf1e8;font:16px/1.5 system-ui}a{color:#c6e58c}nav{display:flex;gap:10px;flex-wrap:wrap;position:sticky;top:0;background:#101612;padding:12px;z-index:1}button{font:inherit;min-height:44px;padding:8px 14px;background:#273626;color:white;border:1px solid #9cab8b;border-radius:6px;cursor:pointer}button[aria-pressed=true]{background:#c6e58c;color:#101612}button:focus-visible,a:focus-visible{outline:3px solid #e6b467;outline-offset:3px}section{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}article{min-width:0}img{width:100%;aspect-ratio:3/2;object-fit:contain;background:#0a100c}h2{font-size:18px}@media(max-width:700px){body{padding:14px}section{grid-template-columns:1fr}nav{position:static;padding:8px 0}}</style><a href="../">Original Blender study and authoring inputs</a><h1>Asheville in CS1's renderer</h1>"""
        + findings
        + "<p>"
        + " · ".join(archives)
        + "</p>"
        + "<p>Nine unchanged study designs, imported and placed in fresh paused cities. Matched close/gameplay cameras, native shaders. B is the clean-concept TRELLIS control, not a surveyed reconstruction. Crops use identical pixel rectangles within each target/view, enlarged for inspection. Click any render for its full unaltered frame. Natural LOD views are taken at 1.05× each asset's own maximum switch distance, so their camera distances differ; they are not close-up LOD previews.</p><nav>"
        + "".join(
            f'<button data-view="{v}" aria-pressed="{"true" if v == "close" else "false"}">{v}</button>'
            for v in VIEWS
        )
        + "</nav><section>"
        + "".join(cards)
        + r"""</section><p><a href="manifest.json">Exact asset and image receipts</a></p><script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>{document.querySelectorAll('button').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));document.querySelectorAll('article img').forEach(i=>{i.src=i.src.replace(/[^/]+\.png$/,b.dataset.view+'-crop.png');i.parentElement.href=i.src.replace('-crop.png','.png')})});document.querySelectorAll('a.render').forEach(a=>a.onclick=()=>{a.href=a.querySelector('img').src.replace('-crop.png','.png')});</script></html>"""
    )
    print(
        f"PASS: 9 native imports/bounds/lots/triangle contracts and reload identities/xz/cells; {9 * len(VIEWS)} image hashes"
    )
    height_changes = {
        a["name"]: a["reload_position_delta_m"][1]
        for a in manifest["assets"]
        if not a["reload_height_preserved_within_1cm"]
    }
    print("Strict reload-height residuals (>1cm):", json.dumps(height_changes))


if __name__ == "__main__":
    main()
