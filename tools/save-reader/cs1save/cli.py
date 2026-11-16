"""cs1save: read Cities: Skylines 1 saves and maps offline.

cs1save info SAVE...           headline numbers and the manager layout
cs1save export SAVE OUT.json   the city model: roads, buildings, zones, numbers
cs1save site SAVE... --out DIR timeline page over every city with 2+ saves
     [--session LABEL DIR]   also a series of DIR's saves, e.g. one evening's autosaves
"""

import argparse
import json
import sys

from .save import read_save
from .stream import FormatError


def _info(args):
    for path in args.saves:
        s = read_save(path)
        d = s.data.get("DistrictManager", {}).get("city", {})
        n = s.data["NetManager"]
        b = s.data["BuildingManager"]
        out = {
            "file": path,
            "city": s.metadata.get("cityName"),
            "map": s.simulation_meta["map_name"],
            "saved": s.metadata.get("timeStamp"),
            "population": d.get("population"),
            "nodes": len(n["node_ids"]),
            "segments": len(n["segment_ids"]),
            "buildings": len(b["ids"]),
            "zone_blocks": len(s.data["ZoneManager"]["block_ids"]),
            "trees": len(s.data["TreeManager"]["ids"]),
            "managers_decoded": list(s.data),
            "managers_passed_over": s.skipped,
            "mod_data": sorted(s.mod_data),
        }
        print(json.dumps(out, indent=None if args.compact else 1, default=str))


def _export(args):
    from .city import extract

    s = read_save(args.save)
    model = extract(s)
    with open(args.out, "w") as f:
        json.dump(model, f, default=lambda v: v.tolist() if hasattr(v, "tolist") else str(v))


def _site(args):
    from . import classify
    from .site import build

    if args.catalog:
        classify.load_catalog(args.catalog)
    import glob
    import os

    sessions = [(label, sorted(glob.glob(os.path.join(folder, "*.crp")))) for label, folder in args.session or []]
    data = build(
        args.saves,
        args.out,
        width=args.width,
        only_city=set(args.city) if args.city else None,
        notes=args.notes,
        sessions=sessions,
    )
    for s in data["series"]:
        print(f"{s['name']}: {len(s['saves'])} saves", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(
        prog="cs1save", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("info")
    a.add_argument("saves", nargs="+")
    a.add_argument("--compact", action="store_true")
    a.set_defaults(func=_info)
    a = sub.add_parser("export")
    a.add_argument("save")
    a.add_argument("out")
    a.set_defaults(func=_export)
    a = sub.add_parser("site")
    a.add_argument("saves", nargs="+")
    a.add_argument("--out", required=True)
    a.add_argument("--width", type=int, default=2000)
    a.add_argument("--city", action="append", help="only this city (repeatable)")
    a.add_argument("--notes", help="JSON merged into data.json: observations per series slug, footer")
    a.add_argument("--catalog", help="another prefab catalog from `cs1-harness call dump_prefabs`")
    a.add_argument(
        "--session",
        nargs=2,
        action="append",
        metavar=("LABEL", "DIR"),
        help="the saves in DIR as their own series named LABEL (repeatable)",
    )
    a.set_defaults(func=_site)
    args = p.parse_args(argv)
    try:
        args.func(args)
    except FormatError as error:
        print(f"cs1save: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
