# /// script
# dependencies = ["pillow>=11"]
# ///
"""Audit native CS1 build/check receipts and assemble a review page and contact sheets."""

import argparse
import hashlib
import html
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw


VIEWS = {
    "close": "day-close",
    "gameplay": "day-gameplay",
    "lod": "day-distant",
    "night": "night-close",
    "reload": "reloaded-close",
}
TARGETS = ("bungalow", "storefront", "apartment")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("game", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    out = args.destination
    out.mkdir(parents=True, exist_ok=True)
    manifest = {
        "renderer": "CS1 1.21.1-f9, native Building/Default shader",
        "assets": [],
    }
    cards = []
    for target in TARGETS:
        for arm in ("A", "B", "C"):
            name = arm + "-" + target
            build_dir = args.game / "build" / name
            check_dir = args.game / "check" / name
            build = json.loads((build_dir / "asset-build.json").read_text())
            check = json.loads((check_dir / "asset-check.json").read_text())
            assert "error" not in build["result"], name
            assert "error" not in check["result"], name
            for run in (build, check):
                assert run["session"]["cleanup"] == {
                    "game": [],
                    "steam_instances": [],
                    "units_active": [],
                }, name
                assert run["result"]["menu_status"]["enabled_mod_count"] == 0, name
            crp = build_dir / build["result"]["crp"]
            assert digest(crp) == build["result"]["crp_sha256"], name
            result = check["result"]
            asset = result["asset"]
            assert result["after_reload"]["name"] == asset["name"], name
            assert result["after_reload"]["exists"], name
            assert all(not p["embedded_mods"] for p in result["packages"]), name
            source = json.loads((args.inputs / name / "receipt.json").read_text())
            assert asset["cells"] == source["spec"]["lot"], name
            for level, key in (("main", "mesh"), ("lod", "lod")):
                mesh = asset[key] if level == "main" else asset[key]["mesh"]
                assert mesh["triangles"] == source[level]["triangles"], (name, level)
                expected = source[level]["dimensions_m"]
                expected = [expected[0], expected[2], expected[1]]
                assert all(
                    abs(a - b) < 0.03 * b + 0.05 for a, b in zip(mesh["size"], expected)
                ), (name, level)
            dest = out / name
            dest.mkdir(exist_ok=True)
            images = {}
            for label, shot in VIEWS.items():
                p = check_dir / "shots" / (shot + ".png")
                shutil.copy2(p, dest / (label + ".png"))
                images[label] = {"path": f"{name}/{label}.png", "sha256": digest(p)}
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
                    "images": images,
                }
            )
            cards.append(
                f'<article><h2>{html.escape(name)}{" (B1 clean concept)" if arm == "B" else ""}</h2><img src="{name}/close.png" alt="Native CS1 render of {name}"><p>{asset["mesh"]["triangles"]} main triangles; {asset["lod"]["mesh"]["triangles"]} LOD</p></article>'
            )
    for view in VIEWS:
        sheet = Image.new("RGB", (1920, 3 * 396 + 50), "#101612")
        draw = ImageDraw.Draw(sheet)
        draw.text(
            (20, 14),
            "CS1 native renderer / "
            + view
            + " / columns A procedural, B1 image-to-3D, C hybrid",
            fill="white",
        )
        for row, target in enumerate(TARGETS):
            for col, arm in enumerate(("A", "B", "C")):
                image = Image.open(
                    out / (arm + "-" + target) / (view + ".png")
                ).convert("RGB")
                image.thumbnail((640, 360))
                x, y = col * 640, row * 396 + 50
                draw.text((x + 10, y + 10), arm + " / " + target, fill="white")
                sheet.paste(image, (x, y + 30))
        sheet.save(out / ("cs1-" + view + ".png"))
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (out / "index.html").write_text(
        """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Asheville — native CS1 comparison</title><style>body{margin:auto;max-width:1600px;padding:24px;background:#101612;color:#edf1e8;font:16px system-ui}a{color:#c6e58c}nav{display:flex;gap:10px;flex-wrap:wrap;position:sticky;top:0;background:#101612;padding:12px}button{padding:12px;background:#273626;color:white;border:1px solid #9cab8b;border-radius:6px}section{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}article{min-width:0}img{width:100%;height:auto}h2{font-size:18px}@media(max-width:700px){section{grid-template-columns:1fr}}</style><h1>Asheville in CS1's renderer</h1><p>Nine unchanged study designs, imported and placed in fresh paused cities. Matched cameras, native shaders. B is the clean-concept TRELLIS control, not a surveyed reconstruction. Click any render for its original resolution.</p><nav>"""
        + "".join(f'<button data-view="{v}">{v}</button>' for v in VIEWS)
        + "</nav><section>"
        + "".join(cards)
        + r"""</section><p><a href="manifest.json">Exact asset and image receipts</a></p><script>document.querySelectorAll('button').forEach(b=>b.onclick=()=>document.querySelectorAll('article img').forEach(i=>i.src=i.src.replace(/(close|gameplay|lod|night|reload)\.png$/,b.dataset.view+'.png')));document.querySelectorAll('article img').forEach(i=>i.onclick=()=>window.open(i.src,'_blank'));</script></html>"""
    )
    print(
        "PASS: 9 CRPs, native scale/triangle/lot and save/reload receipts; 45 image hashes"
    )


if __name__ == "__main__":
    main()
