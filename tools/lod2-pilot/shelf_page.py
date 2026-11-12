"""Build the comparison page: acceptance numbers, then every building's three arms.

    uv run shelf_page.py   # writes <experiment>/asheville-lod2-pilot/, then `shelf add` it
"""

from __future__ import annotations

import html
import shutil

from PIL import Image

from common import EXP, read_json


def jpg(src, dst, width=1700):
    im = Image.open(src).convert("RGB")
    if im.width > width:
        im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
    im.save(dst, quality=82)


def main():
    out = EXP / "asheville-lod2-pilot"
    if out.exists():
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    S = read_json(EXP / "results" / "summary.json")
    second = read_json(EXP / "results" / "judged-second.json")
    A = S["acceptance"]["locked"]

    def share2(view):
        r = [x for x in second if x["set"] == "locked" and x["view"] == view]
        return sum(x["winner"] == "lod2" for x in r), sum(x["winner"] == "height" for x in r), sum(x["winner"] == "tie" for x in r)

    rows = []
    for r in S["rows"]:
        name = f"{r['set']}-{r['hood']}-{r['id']}"
        jpg(EXP / "sheets" / f"{name}.png", out / "img" / f"{name}.jpg")
        l = r["held"]["lod2"] or {}
        h = r["held"]["height"] or {}
        c = r["held"]["current"] or {}
        rows.append(
            f"<section id='b{r['id']}'><h3>{r['id']} · {r['hood']} · {r['set']} · {', '.join(r['flags']) or 'plain'} · {r['area']} m²</h3>"
            f"<p>Withheld-point median error: current {c.get('median_abs', '–')} m, height-only {h.get('median_abs', '–')} m, LoD2 {l.get('median_abs', '–')} m. "
            f"LoD2 within 1 m: {l.get('within_1', '–')}. Geometry check: {'pass' if r['geometry_pass'] else 'fail'}. "
            f"Roof form (blind judge): {html.escape(str(r['roof_form']))}{' — ' + html.escape(r['roof_note']) if r.get('roof_note') else ''}. "
            f"Current generator: {html.escape(r['current'])}, height from {r['current_height_source']}.</p>"
            f"<img loading='lazy' src='img/{name}.jpg' alt='Building {r['id']}: aerial photo, lidar surface, and the three arms in close, top and city views'></section>")
    extra = []
    for f, cap in (("sheet-city.png", "In the real pixel-asheville scene, city zoom: generator above, measured LoD2 below"),
                   ("sheet-close.png", "The same four buildings close in")):
        jpg(EXP / "pixel-import-shots" / f, out / "img" / f.replace(".png", ".jpg"), 1900)
        extra.append(f"<figure><img loading='lazy' src='img/{f.replace('.png', '.jpg')}' alt='{cap}'><figcaption>{cap}</figcaption></figure>")
    boston = []
    for p in sorted((EXP / "boston" / "sheets").glob("*.png")):
        jpg(p, out / "img" / f"boston-{p.stem}.jpg")
        boston.append(f"<img loading='lazy' src='img/boston-{p.stem}.jpg' alt='Boston building {p.stem}: lidar surface, height-only and LoD2'>")
    s2c, s2k = share2("city"), share2("close")
    pc, pk = A["prefer_lod2_over_height_city"], A["prefer_lod2_over_height_close"]
    cc, ck = A["prefer_lod2_over_current_city"], A["prefer_lod2_over_current_close"]
    tf = A["roof_form"]
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asheville buildings: measured LoD2, height-only, current generator</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#1c1c1c;background:#fafaf7}}
img{{max-width:100%;height:auto;border:1px solid #ddd;background:#fff}} table{{border-collapse:collapse;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:.35rem .6rem;text-align:left;vertical-align:top}} th{{background:#eee}}
section{{margin:2.5rem 0}} h3{{margin:.2rem 0}} figcaption{{color:#555;font-size:.9rem}} .miss{{color:#a33}} .hit{{color:#272}}
</style>
<h1>Asheville buildings: measured LoD2, height-only, current generator</h1>
<p>Fifty buildings in Montford and downtown, three ways of making each: the current pixel-asheville generator, the county outline
raised to its lidar-measured height, and a measured LoD2 roof from Roofer 1.0.0 on the 2017 USGS lidar. All three wear the same plain
materials. Ten buildings set the method; the numbers below are the forty that stayed locked until it was frozen. PL-900.</p>
<table>
<tr><th>Check (locked 40)</th><th>Bar</th><th>Result</th></tr>
<tr><td>Usable LoD2 with no per-building change</td><td>80%</td><td class="miss">{A['usable']}/{A['attempts']} ({A['usable_share']:.0%}); Roofer returned a model for {A['standard_mode']}</td></tr>
<tr><td>Dominant roof form and ridge direction right (blind judge)</td><td>80%</td><td class="miss">{tf.get('correct', 0)} of {sum(tf.values()) - tf.get('cannot-judge', 0)} judgeable ({A['roof_form_correct_share']:.0%}); {tf.get('partly', 0)} partly, {tf.get('wrong', 0)} wrong, {tf.get('cannot-judge', 0)} hidden by trees</td></tr>
<tr><td>Ridge and eave heights within 1 m of withheld points</td><td>about 1 m</td><td class="hit">ridge {A['ridge_within_1m'][0]}/{A['ridge_within_1m'][1]}, eave {A['eave_within_1m'][0]}/{A['eave_within_1m'][1]}</td></tr>
<tr><td>LoD2 more faithful than height-only, city view (blind A/B)</td><td>70%</td><td>first judge {pc['lod2']}–{pc['height']}, {pc['tie']} ties ({pc['share']:.0%}); second judge {s2c[0]}–{s2c[1]}, {s2c[2]} ties ({s2c[0] / 39:.0%})</td></tr>
<tr><td>LoD2 more faithful than height-only, close view</td><td>70%</td><td>first judge {pk['lod2']}–{pk['height']}, {pk['tie']} ties ({pk['share']:.0%}); second judge {s2k[0]}–{s2k[1]}, {s2k[2]} ties ({s2k[0] / 39:.0%})</td></tr>
<tr><td>LoD2 more faithful than the current generator</td><td>–</td><td>city {cc['lod2']}–{cc['current']}, {cc['tie']} ties ({cc['share']:.0%}); close {ck['lod2']}–{ck['current']}, {ck['tie']} ties ({ck['share']:.0%})</td></tr>
<tr><td>Median height error against withheld lidar</td><td>–</td><td>current {A['median_abs_error_m']['current']} m · height-only {A['median_abs_error_m']['height']} m · LoD2 {A['median_abs_error_m']['lod2']} m</td></tr>
<tr><td>Against the 2025 lidar ({A['x2025']['n']} buildings under the one tile held)</td><td>–</td><td>median error current {A['x2025']['current']['median_abs']} m · height-only {A['x2025']['height']['median_abs']} m · LoD2 {A['x2025']['lod2']['median_abs']} m</td></tr>
</table>
<p>Each sheet below: the spring-2025 aerial photo with the county outline, the lidar surface (2025 where the tile covers the building,
else 2017), then the three arms. Rows are a close view, straight down (north up), and the size the building has in the city view.</p>
<h2>In pixel-asheville</h2>{''.join(extra)}
<h2>The fifty buildings</h2>{''.join(rows)}
<h2>Boston, same method, nothing retuned</h2>
<p>Twelve random outlines in Dorchester on the 2021 USGS lidar. No current-generator arm exists there.</p>{''.join(boston)}
</html>"""
    (out / "index.html").write_text(page)
    print(out, sum(f.stat().st_size for f in (out / "img").iterdir()) // 1e6, "MB")


if __name__ == "__main__":
    main()
