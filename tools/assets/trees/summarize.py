"""Build the review table and portable gallery from actual trial receipts."""

import argparse
import html
import json
import pathlib
import shutil
import statistics


def read(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def percentile(values, q):
    values = sorted(values)
    index = (len(values) - 1) * q
    lower = int(index)
    return values[lower] + (values[min(lower + 1, len(values) - 1)] - values[lower]) * (
        index - lower
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("inputs", type=pathlib.Path)
    p.add_argument("native", type=pathlib.Path)
    p.add_argument("out", type=pathlib.Path)
    p.add_argument("--trellis", type=pathlib.Path)
    p.add_argument(
        "--legacy-v6-ui",
        action="store_true",
        help="frozen 2e08973 driver: B/A2 both HUD-visible",
    )
    p.add_argument(
        "--frames-native",
        type=pathlib.Path,
        required=True,
        help="corrected renderer run; do not use stale-cache timings",
    )
    a = p.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    images = a.out / "images"
    images.mkdir(exist_ok=True)
    frames = read(a.frames_native / "fresh-city" / "frames.json", [])
    if any(
        not f.get("count", {}).get("render_groups_refreshed_while_paused")
        for f in frames
    ):
        raise ValueError("Stale-cache frame data is not a valid comparison")
    assets = []
    cards = []
    inference = read(a.trellis, {}) if a.trellis else {}
    for path in sorted(a.inputs.glob("*/receipt.json")):
        r = read(path)
        name = r["name"]
        build = read(a.native / ("build-" + name) / "result.json", {})
        timing = read(a.native / ("build-" + name) / "timing.json", {})
        groups = {}
        for sample in frames:
            if sample["candidate"].split(".")[0] == name:
                groups.setdefault((sample["size"], sample["repeat"]), []).append(sample)
        comparisons = []
        for (zoom, repeat), group in groups.items():
            if len(group) != 3:
                raise ValueError(f"{name}: incomplete A/B/A group")
            first, candidate, last = group
            if (
                first["target"] != last["target"]
                or candidate["target"] != candidate["candidate"]
            ):
                raise ValueError("Unexpected A/B/A target order")
            if len({f["instances"] for f in group}) != 1:
                raise ValueError("Timing tree counts differ")
            if "timing_ui_visible" not in candidate or "timing_ui_visible" not in last:
                if not a.legacy_v6_ui:
                    raise ValueError(
                        "Missing timing UI state; only frozen v6 is eligible for --legacy-v6-ui"
                    )
                timing_ui_visible = True
            else:
                timing_ui_visible = candidate["timing_ui_visible"]
                if timing_ui_visible != last["timing_ui_visible"]:
                    raise ValueError("Candidate and stock timing UI states differ")
            # V6's screenshot helper restores the HUD. B and A2 match; the first
            # A1 at each zoom does not. Use the same post-hoc B/A2 policy for all.
            baseline = percentile(last["frame_ms"], 0.95)
            comparisons.append(
                {
                    "camera_size": zoom,
                    "repeat": repeat,
                    "stock_instances": candidate["instances"],
                    "candidate_median_ms": statistics.median(candidate["frame_ms"]),
                    "candidate_p95_ms": percentile(candidate["frame_ms"], 0.95),
                    "last_stock_p95_ms": baseline,
                    "comparison_basis": "B/A2 only; post-hoc screening for frozen v6",
                    "timing_ui_visible": timing_ui_visible,
                    "paired_p95_fraction": percentile(candidate["frame_ms"], 0.95)
                    / baseline
                    - 1,
                    "diagnostic_a1_a2_p95_drift_fraction": percentile(
                        last["frame_ms"], 0.95
                    )
                    / percentile(first["frame_ms"], 0.95)
                    - 1,
                }
            )
        preview = path.parent / "billboard-preview.png"
        preview_name = ""
        if preview.exists():
            preview_name = f"images/{name}-authoring.png"
            shutil.copy2(preview, a.out / preview_name)
        shots = {}
        for view in ("close", "gameplay", "billboard"):
            shot = a.native / "fresh-city" / "session" / "shots" / f"{name}-{view}.png"
            if shot.exists():
                shots[view] = f"images/{name}-{view}.png"
                shutil.copy2(shot, a.out / shots[view])
        row = {
            "name": name,
            "genus": r["genus"],
            "route": r["route"],
            "height_m": r["nominal_height_m"],
            "main_triangles": r["main_triangles"],
            "native_main_triangles": build.get("build", {})
            .get("imported_mesh", {})
            .get("triangles"),
            "import_errors": build.get("build", {}).get("errors_during_build", []),
            "authoring_seconds": r.get(
                "generation_and_preview_seconds", r.get("conversion_seconds")
            ),
            "native_build_wall_seconds": timing.get("wall_seconds"),
            "native_import_job_seconds": build.get("build", {}).get("seconds"),
            "crp_sha256": build.get("crp_sha256"),
            "shots": shots,
            "preview": preview_name,
            "frames": comparisons,
            "dollars": {
                "new_external_generation_api_spend": 0,
                "full_cost": None,
                "unknown_components": [
                    "Codex subscription allocation",
                    "electricity/depreciation",
                    "review labour rate",
                    "review/rework duration and quality-accepted yield",
                ],
            },
        }
        # Job duration is logged in the timeline, not inferred from the build result.
        timeline = a.native / ("build-" + name) / "timeline.jsonl"
        if timeline.exists():
            for line in timeline.read_text().splitlines():
                job = json.loads(line)
                if job.get("state") == "done" and job.get("kind") == "asset_build":
                    row["native_import_job_seconds"] = job["seconds"]
        if r["route"] == "trellis":
            row["inference"] = inference.get("assets", {}).get(r["genus"])
            row["shared_cold_setup_seconds"] = inference.get("setup_seconds")
        assets.append(row)
        actual = shots.get("close")
        picture = actual or preview_name
        pic = (
            f'<img src="{picture}" loading="lazy" alt="{html.escape(name)}">'
            if picture
            else '<div class="empty">Native image pending</div>'
        )
        reference = "YoungLinden" if r["genus"] == "Tilia" else "Tree2"
        stage = (
            f"CS1 · generated left, {reference} right"
            if actual
            else "Blender preview · not native evidence"
        )
        cards.append(
            f'<article data-genus="{r["genus"]}" data-route="{r["route"]}"><h2>{r["genus"]} · {r["nominal_height_m"]} m</h2><p>{r["route"]} · {r["main_triangles"]:,} triangles</p>{pic}<small>{stage}</small></article>'
        )
    report = {
        "schema": 1,
        "assets": assets,
        "accounting": {
            "under_five_dollars_established": False,
            "new_external_generation_api_spend": 0,
            "full_cost_per_asset": None,
            "reason": "Owned hardware and a subscription are not priced marginal API calls; full dollars require an explicit allocation and review rate.",
        },
        "performance": "Render-group-corrected B/A2 wall-frame screening. Frozen v6 uses post-hoc matching HUD-visible pairs and excludes every A1; future driver windows record UI state explicitly. Six candidates, one pair at two zooms; other candidates have no valid timing. Earlier v5 cache-stale timings discarded. No renderer-isolated GPU time or quality-bar pass.",
    }
    (a.out / "measurements.json").write_text(json.dumps(report, indent=2) + "\n")
    document = """<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PL-1328 · Tree trial</title>
<style>body{font:16px/1.5 system-ui;background:#eef0e8;color:#182b22;margin:0;padding:32px}main{max-width:1400px;margin:auto}h1{font-size:36px;line-height:1.1}header{max-width:900px}nav{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}select{font:inherit;padding:8px}section{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}article{padding:16px;background:white;border:1px solid #c9d1c6}h2{font-size:20px;margin:0}article p{margin:5px 0 14px}img{width:100%;display:block;aspect-ratio:16/9;object-fit:contain;background:#e5e9df}small{display:block;margin-top:10px}.empty{padding:60px 10px;background:#e5e9df}a{color:#16513b}footer{margin-top:32px;max-width:900px}[hidden]{display:none}</style>
<main><header><p>PL-1328 · Native tree trial</p><h1>Three genera, four authoring routes</h1><p>Gleditsia, Tilia and Ulmus. Sand3D variants at 9, 15 and 22 metres; 15-metre controls from direct Blender, Sapling and TRELLIS.2.</p><p><b>Prototypes, not an approved palette.</b> The form profiles need botanical review. TRELLIS has no bark mask. Native performance screening does not establish renderer cost, and full cost below $5 is not yet established.</p><p><a href="measurements.json">Measurements and cost fields</a> · <a href="pl1328-tree-trial.zip">18 import sets and native packages</a> · <a href="REPORT.md">Trial report</a></p></header>
<nav><label>Genus <select id="genus"><option value="">All</option><option>Gleditsia</option><option>Tilia</option><option>Ulmus</option></select></label><label>Route <select id="route"><option value="">All</option><option>sand3d</option><option>blender</option><option>sapling</option><option>trellis</option></select></label><label>Native view <select id="view"><option>close</option><option>gameplay</option><option>billboard</option></select></label></nav><section>"""
    document += "".join(cards)
    document += """</section><footer><p>No Workshop content is redistributed. Sand3D library: Apache-2.0; Sapling external generator: GPL-3.0-or-later; TRELLIS.2: MIT. These newly written trial programs do not redistribute Sand3D Nature programs or meshes.</p></footer></main><script>
const data=DATA;const cards=[...document.querySelectorAll('article')];const genus=document.querySelector('#genus'),route=document.querySelector('#route'),view=document.querySelector('#view');
function update(){cards.forEach((card,i)=>{card.hidden=Boolean((genus.value&&card.dataset.genus!==genus.value)||(route.value&&card.dataset.route!==route.value));const img=card.querySelector('img');if(img){const shot=data[i].shots[view.value];img.src=shot||data[i].preview;}})}
[genus,route,view].forEach(select=>select.addEventListener('change',update));</script>""".replace(
        "DATA", json.dumps(assets).replace("<", "\\u003c")
    )
    (a.out / "index.html").write_text(document)


if __name__ == "__main__":
    main()
