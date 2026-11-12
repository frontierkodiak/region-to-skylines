"""Summarize basemaps.json (+ basemaps-extra.json) into basemaps-tables.md."""

import json
import sys
from collections import Counter, defaultdict

d = [r for r in json.load(open("basemaps.json")) if "error" not in r]
extra = json.load(open("basemaps-extra.json"))
R = ["ore", "oil", "fertility", "forest"]
BASE_244 = {r["file"] for r in d if r["data_version"] < 400 and not r["file"][:2].isupper() or r["data_version"] == 244}


def q(vals, ps=(25, 50, 75), nd=2):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return "–"
    out = []
    for p in ps:
        k = (len(vals) - 1) * p / 100
        f = int(k)
        c = min(f + 1, len(vals) - 1)
        x = vals[f] + (vals[c] - vals[f]) * (k - f)
        out.append(f"{x:.{nd}f}" if nd else f"{x:.0f}")
    return " / ".join(out)


L = []
w = L.append
w(f"Corpus: {len(d)} maps (CO.crp is the system package of blank editor terrains, excluded). "
  "Values are p25 / median / p75 across maps unless noted. 'Central' = the 25 tiles a vanilla city can buy "
  "(9×9 tile grid, tiles 2..6); 1 resource cell = 33.75 m = 0.00114 km²; central area = 92.16 km².\n")

w("### Coverage and New Game bars\n")
w("| | ore | oil | fertile | forest |")
w("|:--|--:|--:|--:|--:|")
w("| maps with none in the 25 tiles | " + " | ".join(str(sum(1 for r in d if r["resources"][k]["central_km2"] == 0)) for k in R) + " |")
w("| share of central land covered (>0) | " + " | ".join(q([r["resources"][k]["central_share_of_land"] for r in d]) for k in R) + " |")
w("| central km² covered | " + " | ".join(q([r["resources"][k]["central_km2"] for r in d], nd=1) for k in R) + " |")
w("| share of the map's cells inside the 25 tiles | " + " | ".join(q([r["resources"][k]["central_fraction_of_cells"] for r in d]) for k in R) + " |")
w("| of 25 tiles, tiles with any | " + " | ".join(q([r["resources"][k]["central_tiles_with"] for r in d], nd=0) for k in R) + " |")
w("| of 25 tiles, tiles ≥ 5 % of a tile's max | " + " | ".join(q([r["resources"][k]["central_tiles_ge5pct"] for r in d], nd=0) for k in R) + " |")
mk = {"ore": "oreAmount", "oil": "oilAmount", "fertility": "fertileLandAmount", "forest": "forestAmount"}
w("| metadata amount ÷ maxResourceAmount (bar fill at exponent 1), p10/p50/p90 | " + " | ".join(
    q([r["meta"][mk[k]] / r["meta"]["maxResourceAmount"] for r in d], (10, 50, 90), 3) for k in R) + " |")
w("| start tile has some (maps) | " + " | ".join(str(sum(1 for r in d if r["resources"][k]["start_km2"] > 0)) for k in R) + " |")
w("| start tile km² | " + " | ".join(q([r["resources"][k]["start_km2"] for r in d]) for k in R) + " |")
w("")
w("Water: metadata waterAmount ÷ max, p10/p50/p90 = " + q([r["meta"]["waterAmount"] / r["meta"]["maxResourceAmount"] for r in d], (10, 50, 90), 3)
  + "; wet share of the 25 tiles = " + q([r["water_central_share"] for r in d]) + ".")
w("buildableArea (New Game %): p10/p25/p50/p75/p90 = " + q([r["meta"]["buildableArea"] for r in d], (10, 25, 50, 75, 90), 0) + ".")
w("Sand (unused by vanilla industries, editor-paintable): none in the 25 tiles on "
  + str(sum(1 for r in d if r["resources"]["sand"]["central_km2"] == 0)) + " maps; central km² " + q([r["resources"]["sand"]["central_km2"] for r in d], nd=1) + ".\n")

w("### Patch shape\n")
w("Blobs = 8-connected components after a 2-cell closing (fertile: painted area including the forest cells that zero it), inside the 25 tiles, ≥ 0.05 km².\n")
w("| | ore | oil | fertile |")
w("|:--|--:|--:|--:|")
for lab, key, nd in [("blobs per map", "n_ge_0p05km2", 0), ("median blob km²", "median_km2", 2),
                     ("p90 blob km²", "p90_km2", 2), ("largest blob km²", "max_km2", 2),
                     ("share of area in the 3 largest blobs", "share_area_in_top3", 2)]:
    w(f"| {lab} | " + " | ".join(q([extra[r['file']][k + '_blobs'][key] for r in d], nd=nd) for k in ["ore", "oil", "fertility"]) + " |")
for dd in [1, 2, 3, 4, 6]:
    w(f"| mean value {dd} cell(s) in from the edge | " + " | ".join(
        q([extra[r['file']].get(k + '_edge_profile', {}).get(str(dd)) for r in d], nd=0) for k in ["ore", "oil", "fertility"]) + " |")
w("| cells at 255 / ≥192 / <64 (of cells >0) | " + " | ".join(
    q([r["resources"][k]["hist"].get("eq255") for r in d], (50,)) + " / " + q([r["resources"][k]["hist"].get("ge192") for r in d], (50,)) + " / " + q([r["resources"][k]["hist"].get("lt64") for r in d], (50,))
    for k in ["ore", "oil", "fertility"]) + " |")
w("")

w("### Placement against terrain (cells inside the 25 tiles, on land)\n")
w("Per map: the median over resource cells; table shows p25 / median / p75 of those across maps. "
  "Height percentile is against the 25 tiles' land (50 = typical). 'Above water' = height over the surface of the nearest wet (>0.5 m) water cell. "
  "Ratios divide by the same map's all-land median.\n")
w("| | all central land | ore | oil | fertile | forest |")
w("|:--|--:|--:|--:|--:|--:|")
rows = [("slope %", "slope", 1), ("height percentile", "pct", 0), ("m above nearest water", "above", 0), ("m to water", "dist", 0)]
for lab, k, nd in rows:
    w(f"| {lab} | " + q([r["baseline"][k] for r in d], nd=nd) + " | " + " | ".join(
        q([r["resources"][x]["placement"][k] for r in d if r["resources"][x].get("placement")], nd=nd) for x in R) + " |")
for lab, k in [("slope ÷ map median", "slope"), ("m to water ÷ map median", "dist"), ("m above water ÷ map median", "above")]:
    w(f"| {lab} | 1 | " + " | ".join(q([r["resources"][x]["placement"][k] / r["baseline"][k]
                                          for r in d if r["resources"][x].get("placement") and r["baseline"][k]]) for x in R) + " |")
w("| share of cells under water | – | " + " | ".join(q([r["resources"][x]["placement"]["wet_share"] for r in d if r["resources"][x].get("placement")]) for x in R) + " |")
w("")

w("### Trees\n")
w("Total trees p10/p25/p50/p75/p90: " + q([r["trees"]["total"] for r in d], (10, 25, 50, 75, 90), 0)
  + f"; max {max(r['trees']['total'] for r in d)} (MAX_MAP_TREES = 250,000; "
  + str(sum(1 for r in d if r['trees']['total'] >= 245000)) + " maps ≥ 245k). Inside the 25 tiles: " + q([r["trees"]["central"] for r in d], nd=0)
  + ". Trees per km² of forest-resource area: " + q([r["trees"]["total"] / max(r["resources"]["forest"]["km2"], 0.01) for r in d], nd=0) + ".")
fv = Counter()
for r in d:
    for k, v in extra[r["file"]]["forest_values_top"].items():
        fv[int(k)] += v
tot = sum(fv.values())
w("Forest cell values across all maps: " + ", ".join(f"{k}: {v / tot:.0%}" for k, v in sorted(fv.items())) + " (60 per tree, capped at 255).")
w("Grow state: " + str(Counter(tuple(sorted(r["trees"]["grow_state"])) for r in d).most_common(3)) + " — almost every tree is saved at 15 (grown); a few at 0/1 (overlapping a network or building).\n")
env = defaultdict(Counter)
envmaps = defaultdict(Counter)
nmaps = Counter()
for r in d:
    e = r["meta"]["environment"]
    nmaps[e] += 1
    for n, c in r["trees"]["prefabs"].items():
        env[e][n] += c
        envmaps[e][n] += 1
BASE = ["Tree2variant", "Tree3variant", "Conifer", "Conifer2", "treeForest", "Pine01low", "Beech01low", "Alder01",
        "Bush01", "Bush02", "palm01", "palmplant01"]
WINTER = ["WintertreeForest", "Coniferwinter", "Conifer2Winter", "Pine01Winter", "Bush01Winter"]
w("Original-release tree prefabs (the only ones in the 2015/Snowfall maps, data versions 244–316): "
  + ", ".join(f"`{n}`" for n in BASE) + "; winter theme: " + ", ".join(f"`{n}`" for n in WINTER) + ".\n")
w("| environment | maps | share of trees by prefab (maps using it), original-release prefabs only |")
w("|:--|--:|:--|")
for e in ["Sunny", "North", "Europe", "Tropical", "Winter"]:
    t = sum(env[e].values())
    names = BASE if e != "Winter" else WINTER
    w(f"| {e} | {nmaps[e]} | " + ", ".join(f"{n} {env[e][n] / t:.0%} ({envmaps[e][n]})" for n in sorted(names, key=lambda n: -env[e][n]) if env[e][n]) + " |")
w("")
w("Original-release maps by environment and their prefab mix:\n")
for r in sorted(d, key=lambda r: (r["meta"]["environment"], r["display"])):
    if r["data_version"] <= 320 or r["file"] in ("Garden Rivers2.crp", "Lavender Lake2.crp", "Eden Valley2.crp", "Tropical3FINAL.crp", "NorthEurope2FINAL.crp"):
        t = r["trees"]["total"]
        w(f"- {r['display']} ({r['meta']['environment']}, {t:,} trees): " + ", ".join(f"{n} {c / t:.0%}" for n, c in list(r["trees"]["prefabs"].items())[:6]))
w("")
w("### Forest resource versus trees\n")
w("Exact cell match with min(60 × trees in cell, 255): p0/p10/p50 = " + q([r["forest_check"]["exact_match_share"] for r in d], (0, 10, 50), 3)
  + ". Forest cells with no tree: p50/p90/max = " + q([r["forest_check"]["forest_cells_without_trees"] for r in d], (50, 90, 100), 0)
  + ". Worst: " + ", ".join(f"{r['display']} {r['forest_check']['forest_cells_without_trees']}" for r in sorted(d, key=lambda r: -r["forest_check"]["forest_cells_without_trees"])[:5])
  + ". Fertility on forest cells: " + str(sum(r["fert_forest_overlap"] for r in d)) + " cells in the whole corpus; ore and oil in the same cell: "
  + str(sum(r["ore_oil_overlap"] for r in d)) + ".\n")

w("### Connections and start tile\n")
w("Start tile index (5×5, 12 = centre): " + ", ".join(f"{k}: {v}" for k, v in Counter(r["start_tile"]["index"] for r in d).most_common()) + ".")
for k in ["incomingRoads", "incomingTrainTracks", "incomingShipPath", "incomingPlanePath"]:
    w(f"- {k}: " + ", ".join(f"{a}×{b}" for a, b in sorted(Counter(r['meta'][k] for r in d).items())))
w("")

w("### Per map\n")
w("| map (file) | env | ver | build % | trees | ore | oil | fert | forest | water | start | ore/oil/fert blobs |")
w("|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|")
for r in sorted(d, key=lambda r: r["display"]):
    m = r["meta"]
    fill = lambda k: f"{m[k] / m['maxResourceAmount']:.3f}"
    ex = extra[r["file"]]
    w(f"| {r['display']} ({r['file'][:-4]}) | {m['environment']} | {r['data_version']} | {m['buildableArea']} | {r['trees']['total']:,} | "
      f"{fill('oreAmount')} | {fill('oilAmount')} | {fill('fertileLandAmount')} | {fill('forestAmount')} | {fill('waterAmount')} | "
      f"{r['start_tile']['index']} | {ex['ore_blobs']['n_ge_0p05km2']}/{ex['oil_blobs']['n_ge_0p05km2']}/{ex['fertility_blobs']['n_ge_0p05km2']} |")
w("\nResource columns are New Game amounts ÷ maxResourceAmount (25 tiles).")
open("basemaps-tables.md", "w").write("\n".join(L) + "\n")
print("\n".join(L[:80]))
