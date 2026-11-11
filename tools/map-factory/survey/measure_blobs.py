import glob
import os
import json
import numpy as np
from scipy import ndimage
import measure_maps as m

D = "/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps/"
out = {}
for f in sorted(glob.glob(D + "*.crp")):
    if f.endswith("/CO.crp"):
        continue
    pkg, assets = m.read_any(open(f, "rb").read())
    data = next(a for a in assets if a["kind"] == 52)["payload"]
    v = m.data_version(data)
    g, _ = m.parse_resources(data, v)
    fo = g["forest"]
    vals, cnt = np.unique(fo[fo > 0], return_counts=True)
    top = {int(a): int(b) for a, b in sorted(zip(vals, cnt), key=lambda x: -x[1])[:6]}
    rec = {
        "forest_values_top": top,
        "forest_multiple60_share": round(
            float(np.isin(fo[fo > 0], [60, 120, 180, 240, 255]).mean()), 3
        ),
    }
    for k in ["fertility", "ore", "oil"]:
        mask = g[k] > 0
        if k == "fertility":
            mask = mask | ((fo > 0) & ndimage.binary_dilation(g[k] > 0, iterations=2))
        closed = ndimage.binary_closing(mask, iterations=2)
        lab, n = ndimage.label(closed & m.CENTRAL, structure=np.ones((3, 3)))
        sizes = np.bincount(lab.ravel())[1:] * m.CELL_KM2 if n else np.array([0.0])
        big = sizes[sizes >= 0.05]
        rec[k + "_blobs"] = {
            "n_ge_0p05km2": int(len(big)),
            "median_km2": round(float(np.median(big)), 3) if len(big) else 0,
            "p90_km2": round(float(np.percentile(big, 90)), 3) if len(big) else 0,
            "max_km2": round(float(sizes.max()), 3),
            "share_area_in_top3": round(
                float(np.sort(sizes)[-3:].sum() / max(sizes.sum(), 1e-9)), 3
            ),
        }
        # soft edges: mean value by distance from blob edge (cells)
        if (g[k] > 0).any():
            inside = ndimage.distance_transform_edt(g[k] > 0)
            prof = {
                int(dd): round(float(g[k][(inside == dd)].mean()), 1)
                for dd in [1, 2, 3, 4, 6]
                if (inside == dd).any()
            }
            rec[k + "_edge_profile"] = prof
    out[os.path.basename(f)] = rec
json.dump(out, open("extra.json", "w"), indent=1)
