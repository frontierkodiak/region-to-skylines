"""Build the comparison page: acceptance numbers for the fresh and the development set, then every building.

    uv run shelf_page.py   # writes <experiment>/asheville-lod2-round2/, then `shelf add` it
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
    out = EXP / "asheville-lod2-round2"
    if out.exists():
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    S = read_json(EXP / "results" / "summary.json")
    S2 = read_json(EXP / "results" / "summary-second.json")
    old = read_json(EXP / "results" / "round1-summary-rescue.json") if (EXP / "results" / "round1-summary-rescue.json").exists() else None

    def pref(A, view):
        p = A.get(f"prefer_lod2_over_height_{view}")
        return f"{p['lod2']}–{p['height']}, {p['tie']} ties ({p['share']:.0%})" if p else "–"

    def cls(ok):
        return "hit" if ok else "miss"

    def table(name, title):
        A, B = S["acceptance"][name], S2["acceptance"][name]
        tf = A["roof_form"]
        judgeable = sum(tf.values()) - tf.get("cannot-judge", 0)
        both = lambda v: all(X.get(f"prefer_lod2_over_height_{v}", {"share": 0})["share"] >= 0.7 for X in (A, B))
        x = A.get("x2025")
        return f"""<table>
<tr><th>{title}</th><th>Bar</th><th>Result</th></tr>
<tr><td>Usable LoD2 with no per-building change</td><td>80%</td><td class="{cls(A['usable_share'] >= 0.8)}">{A['usable']}/{A['attempts']} ({A['usable_share']:.0%})</td></tr>
<tr><td>Roof form and ridge direction right (blind judge)</td><td>80%</td><td class="{cls(A['roof_form_correct_share'] >= 0.8)}">{tf.get('correct', 0)} of {judgeable} judgeable ({A['roof_form_correct_share']:.0%}); {tf.get('partly', 0)} partly, {tf.get('wrong', 0)} wrong, {tf.get('cannot-judge', 0)} hidden by trees</td></tr>
<tr><td>LoD2 more faithful than height-only, city view (blind A/B)</td><td>70%</td><td class="{cls(both('city'))}">first judge {pref(A, 'city')}; second judge {pref(B, 'city')}</td></tr>
<tr><td>LoD2 more faithful than height-only, close view</td><td>70%</td><td class="{cls(both('close'))}">first judge {pref(A, 'close')}; second judge {pref(B, 'close')}</td></tr>
<tr><td>Ridge and eave heights within 1 m of withheld points</td><td>about 1 m</td><td>ridge {A['ridge_within_1m'][0]}/{A['ridge_within_1m'][1]}, eave {A['eave_within_1m'][0]}/{A['eave_within_1m'][1]}</td></tr>
<tr><td>Median height error against withheld lidar</td><td>–</td><td>current {A['median_abs_error_m']['current']} m · height-only {A['median_abs_error_m']['height']} m · LoD2 {A['median_abs_error_m']['lod2']} m</td></tr>
{f"<tr><td>Against the 2025 lidar ({x['n']} buildings under the one tile held)</td><td>–</td><td>current {x['current']['median_abs']} m · height-only {x['height']['median_abs']} m · LoD2 {x['lod2']['median_abs']} m</td></tr>" if x else ""}
</table>"""

    rows = {"locked": [], "dev": []}
    for r in S["rows"]:
        name = f"{r['set']}-{r['hood']}-{r['id']}"
        jpg(EXP / "sheets" / f"{name}.png", out / "img" / f"{name}.jpg")
        l = r["held"]["lod2"] or {}
        h = r["held"]["height"] or {}
        parts = f" Split into {r['parts']} buildings, {r['parts_standard']} reconstructed." if r["parts"] > 1 else ""
        rows[r["set"]].append(
            f"<section id='b{r['id']}'><h3>{r['id']} · {r['hood']} · {', '.join(r['flags']) or 'plain'} · {r['area']} m²</h3>"
            f"<p>Withheld-point median error: height-only {h.get('median_abs', '–')} m, LoD2 {l.get('median_abs', '–')} m; LoD2 within 1 m: {l.get('within_1', '–')}. "
            f"Usable: {'yes' if r['usable'] else 'no'}.{parts} "
            f"Roof form (blind judge): {html.escape(str(r['roof_form']))}{' — ' + html.escape(r['roof_note']) if r.get('roof_note') else ''}.</p>"
            f"<img loading='lazy' src='img/{name}.jpg' alt='Building {r['id']}: aerial photo, lidar surface, and the three arms in close, top and city views'></section>")
    page = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Asheville buildings, round 2: measured LoD2 on split outlines</title>
<style>
body{{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#1c1c1c;background:#fafaf7}}
img{{max-width:100%;height:auto;border:1px solid #ddd;background:#fff}} table{{border-collapse:collapse;margin:1rem 0}}
td,th{{border:1px solid #ccc;padding:.35rem .6rem;text-align:left;vertical-align:top}} th{{background:#eee}}
section{{margin:2.5rem 0}} h3{{margin:.2rem 0}} .miss{{color:#a33}} .hit{{color:#272}}
</style>
<h1>Asheville buildings, round 2: measured LoD2 on split outlines</h1>
<p>PL-909. Measured LoD2 roofs (Roofer 1.0.0, 2017 USGS lidar) against the same outline raised to one measured height. Since
PL-900: downtown block outlines are cut into their buildings along OpenStreetMap lines, the small-building rule applies only
where the lidar has no building points, and Roofer no longer clips outlines where it sees ground. The method was tuned on
PL-900's fifty buildings, frozen, and then run once on forty buildings it had never seen.</p>
<h2>Forty fresh buildings, frozen method</h2>{table('locked', 'Check (fresh 40)')}
<h2>PL-900's fifty, used for development</h2>{table('dev', 'Check (the 50, tuned on)')}
<p>Each sheet: the spring-2025 aerial photo with the county outline, the lidar surface (2025 where the tile covers the
building, else 2017), then the current generator, height-only and LoD2. Rows are a close view, straight down (north up), and
the size the building has in the city view.</p>
<h2>The fresh forty</h2>{''.join(rows['locked'])}
<h2>The fifty</h2>{''.join(rows['dev'])}
</html>"""
    (out / "index.html").write_text(page)
    print(out, sum(f.stat().st_size for f in (out / "img").iterdir()) // 1e6, "MB")


if __name__ == "__main__":
    main()
