"""Load a saved city and write what the game holds, for checking an offline save reader (PL-984).

`cs1-harness dump-save SAVE --map MAP --out DIR` starts a session, starts a New Game on MAP
(the game's load_game needs a level), loads SAVE over it with the simulation paused, and
writes two files with the mod's ops:

- city-dump.json: every created node, segment, building, zone block and tree, keyed by
  buffer id (`dump_city`);
- prefabs.json: the loaded building, net and tree prefab catalog with each prefab's item
  class, AI type and size (`dump_prefabs`).

Harness runs use --noWorkshop, so a save's Workshop assets and mod-provided prefabs are not
loaded; the game drops items whose prefab is missing as it loads. The saved prefab name of
every remaining item is still reported, and prefabs.json says which names the game had.
"""

from __future__ import annotations

import json
import pathlib
import time

from . import saves


def dump_save(session, save: pathlib.Path, map_crp: pathlib.Path, load_timeout: float, log=print) -> dict:
    s, c = session, session.client
    installed = s.install_map(map_crp)
    s.launch(["--noWorkshop"])
    for name in ("dump_city", "dump_prefabs", "load_game"):
        if not saves.has_ops(c, name):
            raise RuntimeError(f"this mod build has no {name} op; build from this checkout")
    listed = next(
        (
            m["path"]
            for m in c.call("maps")["maps"]
            if m["path"] and pathlib.Path(m["path"]).exists() and pathlib.Path(m["path"]).samefile(installed)
        ),
        None,
    )
    if listed is None:
        raise RuntimeError(f"the game does not list {installed.name} as a map")
    log(f"bridging New Game on {installed.name}, then loading {save.name}")
    t0 = time.monotonic()
    status = saves.load(s, save, load_timeout, listed)
    c.call("run", paused=True)
    loaded_s = round(time.monotonic() - t0, 1)
    prefabs = c.call("dump_prefabs", path=str(s.stage / "prefabs.json"))
    city = c.call("dump_city", path=str(s.stage / "city-dump.json"))
    stats = c.call("stats")
    receipt = {
        "save": str(save),
        "save_sha256": saves_sha256(save),
        "map": str(map_crp),
        "loaded_s": loaded_s,
        "status": status,
        "stats": stats,
        "dump_city": city,
        "dump_prefabs": prefabs,
    }
    (s.stage / "dump-receipt.json").write_text(json.dumps(receipt, indent=2))
    return receipt


def saves_sha256(path: pathlib.Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()
