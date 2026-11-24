"""Read-only stock geometry profiling; only derived summaries leave installed packages."""
import hashlib
import json
import sys
sys.dont_write_bytecode = True
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parent
DECODER = ROOT / 'gameplay-water-shipping/tools/map-factory/survey'
sys.path.insert(0, str(DECODER))
from craft_anatomy import read_package, parse_water, data_version
from measure_maps import parse_terrain

MAPS = Path('/peach-pool/peach/Games/SteamLibrary/steamapps/common/Cities_Skylines/Files/Maps')
OUT = Path('/home/caleb/experiments/PL-1191-stable-water/stock-calibration/stock-profile')
SELECTED = ['PU Gray Waters.crp', 'MM Weaving Waters.crp', 'PL Mountain Meadows.crp']
CROSS = ndi.generate_binary_structure(2, 1)


def stats(a):
    a = np.asarray(a)
    if not a.size:
        return {'n': 0}
    return dict(n=int(a.size), negative_count=int((a<0).sum()), **{k: float(v) for k, v in zip(
        ['min', 'p10', 'median', 'p90', 'max'], np.quantile(a, [0, .1, .5, .9, 1]))})


def edges(mask):
    result = {}
    for side, row in [('z_minus', mask[0]), ('z_plus', mask[-1]),
                      ('x_minus', mask[:, 0]), ('x_plus', mask[:, -1])]:
        idx = np.flatnonzero(row)
        chunks = np.split(idx, np.flatnonzero(np.diff(idx) > 1) + 1) if idx.size else []
        result[side] = [{'first_node': int(c[0]), 'last_node': int(c[-1]),
                         'first_world_m': int((c[0]-540)*16),
                         'last_world_m': int((c[-1]-540)*16), 'nodes': int(c.size)} for c in chunks]
    return result


def components(mask, depth, height, sea):
    lab, n = ndi.label(mask, CROSS)
    objects = ndi.find_objects(lab)
    surface = height + depth
    # Full-domain padding makes distance to off-map background explicit, not an assumed ocean width.
    distance = ndi.distance_transform_edt(np.pad(mask, 1))[1:-1, 1:-1] * 16
    ridge = mask & (distance == ndi.maximum_filter(distance, size=3, mode='constant'))
    records = []
    for cid, sl in enumerate(objects, 1):
        zsl, xsl = sl
        local = lab[sl] == cid
        zz, xx = np.nonzero(local)
        zz += zsl.start
        xx += xsl.start
        em = {side: [] for side in ['z_minus', 'z_plus', 'x_minus', 'x_plus']}
        touches = zsl.start == 0 or xsl.start == 0 or zsl.stop == 1081 or xsl.stop == 1081
        if touches:
            full = lab == cid
            em = edges(full)
        # Actual dry-node/wet-node neighbor pairs. Films below cutoff are excluded from dry banks.
        pair_freeboards = []
        bank_top = []
        for dz, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            z2, x2 = zz + dz, xx + dx
            valid = (z2 >= 0) & (z2 < 1081) & (x2 >= 0) & (x2 < 1081)
            za, xa, zb, xb = zz[valid], xx[valid], z2[valid], x2[valid]
            dry = depth[zb, xb] == 0
            pair_freeboards.extend((height[zb[dry], xb[dry]] - surface[za[dry], xa[dry]]).tolist())
            # Four steps along cardinal outward ray (16..64m), using only truly dry nodes.
            za, xa = za[dry], xa[dry]
            top = np.full(za.size, -np.inf)
            for step in range(1,5):
                zt, xt = za+dz*step, xa+dx*step
                ok = (zt>=0)&(zt<1081)&(xt>=0)&(xt<1081)
                inds = np.flatnonzero(ok)
                inds = inds[depth[zt[inds], xt[inds]] == 0]
                top[inds] = np.maximum(top[inds], height[zt[inds], xt[inds]] - surface[za[inds], xa[inds]])
            bank_top.extend(top[np.isfinite(top)].tolist())
        vals = surface[zz, xx]
        records.append({'id': cid, 'nodes': int(zz.size), 'node_area_km2': zz.size*256/1e6,
                        'bbox_world_xz_m': [[int((xx.min()-540)*16),int((zz.min()-540)*16)],
                                            [int((xx.max()-540)*16),int((zz.max()-540)*16)]],
                        'edge_intervals': em, 'touches_edge': touches,
                        'sea_level_candidate_nodes_abs_surface_minus_sea_le_3m': int((np.abs(vals-sea)<=3).sum()),
                        'above_sea_plus_3m_nodes': int((vals>sea+3).sum()),
                        'depth_m': stats(depth[zz,xx]), 'surface_m': stats(vals),
                        'surface_extrema_witnesses': [{'world_xz_m': [int((xx[i]-540)*16), int((zz[i]-540)*16)], 'terrain_m': float(height[zz[i],xx[i]]), 'depth_m': float(depth[zz[i],xx[i]]), 'surface_m': float(vals[i])} for i in [int(vals.argmin()), int(vals.argmax())]],
                        'ridge_diameter_estimate_m': stats(2*distance[zz,xx][ridge[zz,xx]]),
                        'shore_neighbor_freeboard_m': stats(pair_freeboards),
                        'bank_top_proxy_within64m_m': stats(bank_top)})
    return lab, records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'selection': SELECTED, 'decoder_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in [DECODER/'craft_anatomy.py', DECODER/'measure_maps.py']}, 'maps': []}
    for name in SELECTED:
        raw = (MAPS/name).read_bytes()
        pkg, assets = read_package(raw)
        entry = {'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                 'package': pkg, 'all_asset_md5_pass': all(a['md5_ok'] for a in assets), 'simulations': []}
        for asset in assets:
            if asset['kind'] != 52:
                continue
            data = asset['payload']
            version = data_version(data)
            w, h = parse_water(data, version), parse_terrain(data)
            d = w['depth']
            sim = {'asset': asset['name'], 'serialized_version': version,
                   'sea_level_m': w['sea_level'], 'frame': w['frame'], 'next_tag': w['next_tag'],
                   'source_count': len(w['sources']), 'sources': [], 'threshold_profiles': {}}
            labels = {}
            for threshold in [0, .125]:
                lab, records = components(d > threshold, d, h, w['sea_level'])
                labels[threshold] = lab
                sim['threshold_profiles'][str(threshold)] = records
            # A near-sea subset is a separate morphology, not a flow/river identity join.
            lab, records = components((d>0)&(np.abs(h+d-w['sea_level'])<=3), d, h, w['sea_level'])
            sim['near_sea_subset_components'] = records
            _, records = components((d>0)&(np.abs(h+d-w['sea_level'])>3), d, h, w['sea_level'])
            sim['non_sea_level_subset_components'] = records
            sim['wet_nodes_total'] = int((d>0).sum())
            sim['eight_neighbor_component_counts'] = {str(t): int(ndi.label(d>t, np.ones((3,3)))[1]) for t in [0,.125]}
            assert sum(c['nodes'] for c in sim['threshold_profiles']['0']) == sim['wet_nodes_total']
            assert sum(c['nodes'] for c in sim['threshold_profiles']['0.125']) == int((d>.125).sum())
            assert sim['next_tag'] == {'gap_bytes': 2, 'name': 'InstanceManager'}
            sim['wet_nodes_above_sea_plus3m'] = int(((d>0)&(h+d>w['sea_level']+3)).sum())
            source_edt = ndi.distance_transform_edt(np.pad(d>0, 1))[1:-1, 1:-1] * 16
            source_components = {c['id']: c for c in sim['threshold_profiles']['0']}
            largest_id = max(source_components, key=lambda cid: source_components[cid]['nodes'])
            for index, source in enumerate(w['sources']):
                s = {'serialized_index_zero_based': index, **source, 'target_m': source['target_raw']/64}
                for field in ['input', 'output']:
                    x, y, z = source[field]
                    ix, iz = int(np.clip(np.floor(x/16+540+.5),0,1080)), int(np.clip(np.floor(z/16+540+.5),0,1080))
                    s[field+'_terrain_witness'] = {'node_xz': [ix,iz], 'node_world_xz_m': [(ix-540)*16,(iz-540)*16],
                        'terrain_m': float(h[iz,ix]), 'depth_m': float(d[iz,ix]), 'surface_m': float(h[iz,ix]+d[iz,ix]),
                        'position_y_minus_terrain_m': float(y-h[iz,ix]),
                        'target_minus_terrain_m': float(s['target_m']-h[iz,ix]),
                        'wet_component_at_same_node': int(labels[0][iz,ix]),
                        'deep_component_at_same_node': int(labels[.125][iz,ix])}
                if s['type'] == 1:
                    witness = s['input_terrain_witness']
                    ix, iz = witness['node_xz']
                    cid = witness['wet_component_at_same_node']
                    component = source_components.get(cid)
                    group = ('unsupported' if component is None else
                             'main_largest_body' if cid == largest_id else
                             'other_edge_body' if component['touches_edge'] else 'isolated_body')
                    s['source_local_geometry'] = {
                        'sample_position_field': 'input',
                        'group': group, 'component_id': cid,
                        'component_is_largest_body': cid == largest_id,
                        'component_touches_edge': None if component is None else component['touches_edge'],
                        'component_edge_intervals': None if component is None else component['edge_intervals'],
                        'initial_depth_m': witness['depth_m'],
                        'saved_stage_m': witness['surface_m'],
                        'saved_stage_minus_target_m': witness['surface_m'] - s['target_m'],
                        'edt_diameter_at_source_node_m': float(2*source_edt[iz,ix]),
                        'input_output_positions_equal': s['input'] == s['output'],
                        'source_world_xz_outside_native_grid': not (-8640 <= s['input'][0] <= 8640 and -8640 <= s['input'][2] <= 8640),
                    }
                sim['sources'].append(s)
            sim['source_local_group_summaries'] = source_group_summaries(sim['sources'])
            entry['simulations'].append(sim)
        report['maps'].append(entry)
        print(name, 'sources', [s['source_count'] for s in entry['simulations']], flush=True)
    (OUT/'stock-profile.json').write_text(json.dumps(report, indent=2)+'\n')
    print(OUT/'stock-profile.json')
    render_markdown(report)

def source_group_summaries(sources):
    result = {}
    for group in ['main_largest_body', 'isolated_body', 'other_edge_body', 'unsupported']:
        selected = [s for s in sources if s['type'] == 1 and s['source_local_geometry']['group'] == group]
        result[group] = {
            'count': len(selected),
            'source_indices': [s['serialized_index_zero_based'] for s in selected],
            'input_rate_raw': stats([s['input_rate'] for s in selected]),
            'output_rate_raw': stats([s['output_rate'] for s in selected]),
            'input_rate_raw_histogram': {str(v): sum(s['input_rate']==v for s in selected) for v in sorted({s['input_rate'] for s in selected})},
            'initial_depth_m': stats([s['source_local_geometry']['initial_depth_m'] for s in selected]),
            'source_local_edt_diameter_m': stats([s['source_local_geometry']['edt_diameter_at_source_node_m'] for s in selected]),
            'saved_stage_minus_target_m': stats([s['source_local_geometry']['saved_stage_minus_target_m'] for s in selected]),
        }
    assert sum(g['count'] for g in result.values()) == sum(s['type'] == 1 for s in sources)
    return result


def source_local_markdown(report):
    lines = ["", "## Source-local geometry and settings (type 1 only)", "",
             "Membership is sampled at the rounded native input-position node already used by the terrain witnesses, not by source name or proximity to a component. Main means the largest depth>0 four-neighbor component; isolated means a smaller component with no edge contact. Other edge bodies and unsupported points remain separate, even when empty. This topology does not identify hydraulic river/lake function. Input/output positions match for all selected records.", "",
             "Source-local width is 2 × EDT at that exact source node using the full nonzero-water mask, not the ridge statistic or sea-threshold partition. It is a local inscribed-diameter proxy, not a surveyed cross section; an off-center source can severely understate channel width, and exterior padding censors edge bodies. Gap = saved stage (terrain + initial depth) minus serialized target; neither equality nor target validity is assumed. Each range below is min–max, in metres except raw settings.", "",
             "| Map | Exact-membership group | Controls | Input/output rate raw range | Initial depth m | Local EDT diameter m | Saved stage−target m |",
             "|---|---|---:|---:|---:|---:|---:|"]
    histograms = []
    for m in report['maps']:
        sim = m['simulations'][0]
        for name, group in sim['source_local_group_summaries'].items():
            def span(key):
                st = group[key]
                return f"{st['min']:.5f}–{st['max']:.5f}" if st['n'] else 'no controls'
            lines.append(f"| {m['file']} | {name} | {group['count']} | {span('input_rate_raw')} | {span('initial_depth_m')} | {span('source_local_edt_diameter_m')} | {span('saved_stage_minus_target_m')} |")
        histograms.append(f"\nRaw rate histograms for {m['file']}: " + '; '.join(f"{name}: {g['input_rate_raw_histogram']}" for name,g in sim['source_local_group_summaries'].items()) + '.')
    lines.extend(histograms)
    lines.extend(["", "**Literal 0.5-river / 0.01-lake rule: not supported.** Serialized 32767/65535≈0.499992 and 655/65535≈0.00999466 are descriptive normalized settings, not discharge. Exact main-versus-isolated histograms above supply counterexamples without promoting topology labels to hydraulic identities. Concrete counterexamples: Weaving main-body indices 0,1,2,3,8 all use 655 (approximately 0.01), while its six isolated-body indices 4,5,6,7,9,10 all use 32767 (approximately 0.5), the reverse of that simple rule. Gray has 24 isolated controls at 32767, two at 655 and two at 4587; its 12 main-body controls range 3932–65535, with seven at 65535 (1.0). Mountain alone has a main-body control at 32767, but its source-local diameter is 1267.94 m (broad pool/basin scale) and stage−target is −248.421875 m, so this is not evidence for a universal narrow-channel recipe. All source-local fields and exact source indices remain in JSON; zero-count groups are explicit. No type 1 points are unsupported or outside the native grid in this selection."])
    return lines

def render_markdown(report):
    lines = ["# Preselected stock-water static geometry", "",
             "Read-only installed-package recheck at shipping A8 (`a8da051ae562da28e790ae59e7d4fdad952d882b`). No native load or stability claim. All three named maps retained; no substitution.", "",
             "## Main connected saved-water body", "",
             "These are the largest whole water components, **not isolated river channels**. Depth and freeboard in metres; widths are raster ridge-diameter estimates. Brackets give p10–p90; all extremes and all components are in JSON.", "",
             "| Map | Records (type1/type0) | Wet components >0 / >0.125m | Main depth median [p10–p90] | Width median [p10–p90] | Immediate freeboard median | 64m bank-top proxy median |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    def interval(st):
        return f"{st['median']:.2f} [{st['p10']:.2f}–{st['p90']:.2f}]"
    for m in report['maps']:
        s = m['simulations'][0]
        c = max(s['threshold_profiles']['0'], key=lambda c:c['nodes'])
        types = [sum(a['type']==t for a in s['sources']) for t in [1,0]]
        lines.append(f"| {m['file']} | {s['source_count']} ({types[0]}/{types[1]}) | {len(s['threshold_profiles']['0'])} / {len(s['threshold_profiles']['0.125'])} | {interval(c['depth_m'])} | {interval(c['ridge_diameter_estimate_m'])} | {c['shore_neighbor_freeboard_m']['median']:.2f} | {c['bank_top_proxy_within64m_m']['median']:.2f} |")
    lines.extend(["", "## Exact records and source settings", "",
                  "`stock-profile.json` keeps every serialized source record in order, including disabled type0 records, exact input/output float positions, raw target, raw input/output rates, water/pollution/flow counters. Source-to-component labels are sampled at the source coordinate, never nearest/source-name joins; label 0 means no support. Five Gray type0 records (indices26,39,40,45,49) sample dry nodes and remain explicitly unsupported; every type1 record samples nonzero saved water. Targets are raw/64 metres. Rates and flow counters are game settings/state, **not m³/s or demonstrated direction**.", ""])
    for m in report['maps']:
        s = m['simulations'][0]
        lines.append(f"- **{m['file']}**: sea={s['sea_level_m']!r} m; raw rate range {min(a['input_rate'] for a in s['sources'])}–{max(a['input_rate'] for a in s['sources'])}; raw saved flow {stats([a['flow'] for a in s['sources']])}. Input/output positions and rates symmetric for every record: {all(a['input']==a['output'] and a['input_rate']==a['output_rate'] for a in s['sources'])}.")
    lines.extend(["", "## Mountain Meadows: inland river support first", "",
                  "The one whole wet component spans x=-8640..4992 and z=-8640..8480 m. Its saved surface ranges 76.4375..110.265625 m, sea=78.31200408935547 m. The largest non-sea-level subset (|surface−sea|>3m), entirely inland, has 34,605 nodes (8.85888 node-km²), x=-3792..4992, z=-4640..8480 m and surface 81.3125..110.265625 m. Its elongated connected geometry, joining the near-sea body at x<0, z<0 in the whole mask and extending to the inland source, supports an **inland river-like channel**, not an isolated lake. It does not establish a hydraulic river classification or flow direction.", "",
                  "Only wet edge contacts are z_minus (z=-8640), x=-8640..-7344 and x_minus (x=-8640), z=-8640..-7744 m, both at the near-sea end at x<0, z<0. No x_plus or z_plus contacts. The source is inland input=output [4300.4296875,52.06236267089844,7794.0546875], type1, rates32767/32767, target_raw22901 (357.828125m); sampled node bed52.109375m, depth57.296875m, saved surface109.40625m. The large target/saved-surface difference is retained, not silently reconciled. Thus geometry supports **an inland-source/sea-connected topology**, not proof of upstream edge feeding or actual inflow/outflow.", "",
                  "Mountain's largest non-sea subset depth median49.05m [12.07–56.27], ridge diameter400.96m [32.00–611.36], immediate freeboard2.20m and 64m bank proxy11.55m. Its sea-threshold cut produces artificial width boundaries: these are not surveyed channel cross sections.", "",
                  "## Edge/sea ambiguity and small inland bodies", "",
                  "- Gray Waters' largest component contacts all four edges (full intervals in JSON); additional edge components and 50 disconnected inland wet components remain. Of those inland components,28 have >10 nodes,22 have 1–4 nodes. The former range0.013824–0.556288 node-km² and provide multiple **small inland lake/pool candidates**, not a blanket claim every component is a lake.",
                  "- Weaving Waters' principal network reaches only x_minus (x=-8640) at z=-3168..-2928 and -2640..-2400m. Its positive-x wet endpoint stops at x=8624 (one 16m node short of the boundary); its five positive-x controls are near, not on, the edge. Sea-level subset reaches the x_minus edge; most network surfaces are below the serialized sea setting. There are six separate inland lake/pool candidates of0.103680–0.447488 node-km² plus one single wet node (0.0625m deep). The latter vanishes at >0.125m while another1-node fragment splits off, so equal component totals do not mean identical support.",
                  "- Mountain Meadows has **zero disconnected inland water bodies at either threshold**, not zero inland water. Its inland water belongs to its single connected main body. Connected side basins cannot be independently called lakes by this component test.", "",
                  "The near-sea rule (within±3m) is only a descriptive candidate, never a sea identity or flow classification. A river may meet that elevation inland; a lake may sit at sea level; a sea may vary outside the tolerance. All near-sea and non-sea subset components are retained separately. No enter/leave direction is inferred from static geometry.", "",
                  "## Reproducible method and limitations", "",
                  "1. Read exact installed CRP bytes using existing legal decoders only; verify every asset MD5. Decode each kind52 asset (one each here), terrain, stored water depth and complete controls. All water endpoints agree with InstanceManager,gap2. This is structural consistency, not independent decoder validation.",
                  "2. Grid nodes have16m spacing, world coordinate(i−540)×16; serialized row index increases with z, z=-8640+16×row; compass names are intentionally not used; depth and terrain are raw/64m. Label every depth>0 node with4-neighbor connectivity; repeat at depth>0.125m. JSON also reports8-neighbor component counts to expose diagonal-contact ambiguity: Gray37/40,Weaving7/8,Mountain1/1 at the two thresholds, versus4-neighbor56/71,8/8,1/1. These are graph definitions, not disagreements silently resolved. Node area=nodes×256m² is a raster proxy, not polygon-survey area.",
                  "3. Depth statistics weight every wet node. Width proxy=2×Euclidean distance to the nearest excluded/background node, sampled at3×3 local maxima. Pads map exterior as dry; therefore edge-truncated widths are censored/biased. Single-node width proxy32m, with roughly16–32m discretization error; ridges/plateaus and wide lakes/ocean can bias the distribution. No centerline identity or surveyed channel width is claimed.",
                  "4. Immediate freeboard=terrain at truly dry cardinal neighbor minus saved surface at adjacent wet node; each shoreline pair counts, including duplicates. Bank-top proxy=max dry terrain along the same outward cardinal ray16..64m minus that wet surface. Rays may cross gaps; no true crest, floodplain elevation, levee top or current native floor is identified. Negative freeboards remain (Gray main min−31.55m,Weaving−59.80m,Mountain−48.08m); they expose raster/save discontinuities or unresolved geometry, not an overflow/stability conclusion. Full negative counts and extremes are retained.",
                  "5. Component IDs are local to each threshold/subset only. No cross-threshold identities are asserted. Every component, source sample with zero wet support, and sea/edge ambiguity remains in JSON. No original package or proprietary assembly is copied or redistributed.", "",
                  "**Comparison supported:** stock authoring is far sparser (40,11,1 active controls across these complete maps) than the previously surveyed frozen-v4 dense low-setting pools. Stock includes connected edge/near-sea networks and disconnected inland pools, but Mountain disproves a universal upstream-edge-fed rule. These static maps neither validate failed dense pools nor prove stock stability, native equilibrium, instantaneous discharge, or a causal prescription for rates/geometry.", "",
                  "## Inputs and rerun", ""])
    for m in report['maps']:
        lines.append(f"- `{m['file']}` SHA-256 `{m['sha256']}`; all asset MD5 checks pass.")
    for name, sha in report['decoder_sha256'].items():
        lines.append(f"- Decoder `{name}` SHA-256 `{sha}`.")
    lines.extend(["", "Run from the PL-1191 workspace (existing environment,no install/sync):", "", "```bash", "uv run --project gameplay-water-shipping/tools/map-factory --no-sync python stock-profile.py", "```", "", "Outputs: `stock-calibration/stock-profile/stock-profile.json` and `stock-profile.md` under the existing PL-1191 experiment root. The script asserts component node conservation and all three decoder endpoint tags. Full source state is in JSON, not abbreviated to the table."])
    lines.extend(source_local_markdown(report))
    text = '\n'.join(lines)+'\n'
    (OUT/'stock-profile.md').write_text(text)
    (ROOT/'stock-profile.md').write_text(text)

if __name__ == '__main__':
    main()
