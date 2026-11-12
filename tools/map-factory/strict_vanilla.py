"""Task-local strict New Game checks against observed, fixed-resolution UI.

Only known game-screen controls are driven. Unknown screens fail closed and
are captured before the named session is cleaned up.
"""

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from crp import read_package

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("output", type=Path)
parser.add_argument(
    "--issue", default="PL-918", help="issue key and evidence prefix (default: PL-918)"
)
parser.add_argument("--harness", type=Path, required=True)
parser.add_argument("--references", type=Path, required=True)
parser.add_argument(
    "--only",
    nargs="+",
    default=["charleston", "rio", "asheville", "innsbruck", "pittsburgh"],
)
args = parser.parse_args()
HARNESS = args.harness.resolve()
sys.path.insert(0, str(HARNESS))
Client = importlib.import_module("cs1_harness.client").Client
Config = importlib.import_module("cs1_harness.config").Config
GameWindow = importlib.import_module("cs1_harness.x11").GameWindow

ROOT = args.output.resolve()
REFERENCES = args.references.resolve()
cfg = Config.for_host()
env = dict(os.environ)


def command(*args):
    return subprocess.run(
        ["uv", "run", "--locked", "cs1-harness", *args],
        cwd=HARNESS,
        env=env,
        check=True,
    )


def match(path, reference, box):
    with Image.open(path) as actual, Image.open(REFERENCES / reference) as expected:
        if actual.size != (1920, 1080):
            raise RuntimeError(f"unexpected game resolution {actual.size}")
        delta = np.abs(
            np.asarray(actual.convert("RGB").crop(box), dtype=float)
            - np.asarray(expected.convert("RGB").crop(box), dtype=float)
        ).mean()
    return delta < 16


def run(slug):
    stage = args.issue + "-vanilla-" + slug
    crp = ROOT / "soaks/maps" / slug / ("PL857-" + slug + ".crp")
    if (ROOT / (stage + "-validation.json")).exists():
        raise ValueError("Refusing to replace completed strict vanilla evidence")
    began = time.time()
    print(f"{slug}: queueing ordinary vanilla start", flush=True)
    while True:
        try:
            command(
                "up",
                "--name",
                stage,
                "--map",
                str(crp),
                "--label",
                args.issue + " strict vanilla " + slug,
                "--game-arg=--disableMods",
                "--game-arg=-screen-width",
                "--game-arg=1920",
                "--game-arg=-screen-height",
                "--game-arg=1080",
                "--game-arg=-screen-fullscreen",
                "--game-arg=0",
                "--wait-minutes",
                "120",
            )
            break
        except subprocess.CalledProcessError as error:
            if error.returncode != 75:
                raise
            print(
                f"{slug}: temporary Steam/slot block; retrying after30min without answering any prompt",
                flush=True,
            )
            for _ in range(30):
                time.sleep(60)
    try:
        state = json.loads(cfg.state_file.read_text())
        assert Path(state["stage"]).name == stage
        assert state["receipt"]["control"] is False
        assert {"--disableMods", "--noWorkshop"} <= set(state["receipt"]["launch_args"])
        assert (
            state["receipt"]["map"]["sha256"]
            == hashlib.sha256(crp.read_bytes()).hexdigest()
        )
        assert Client(cfg.port).try_status() is None
        assert list(cfg.maps_dir.glob("*.crp")) == [cfg.maps_dir / crp.name]
        current = ROOT / (stage + "-current.png")
        with GameWindow(stage) as window:
            deadline = time.monotonic() + 90
            while True:
                window.capture(current)
                if match(current, "strict-asheville-menu.png", (850, 498, 1080, 531)):
                    window.click(1286, 607)  # Decline optional Paradox login.
                elif match(
                    current, "strict-reach-rio-whats-new.png", (901, 202, 1018, 228)
                ):
                    window.click(960, 837)  # Dismiss What's New, no checkbox change.
                elif match(current, "strict-asheville-main.png", (850, 376, 1070, 417)):
                    window.capture(ROOT / (stage + "-main.png"))
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "unrecognized game screen; see current screenshot"
                    )
                time.sleep(2)
            window.click(960, 395)
            time.sleep(2)
            window.capture(ROOT / (stage + "-new-game.png"))
            # The observed base-game list has 12 stock maps, then our sole map.
            window.click(700, 636)
            window.click(1160, 535)
            window.keys("Control_L", "a")
            for char in "pl857-" + slug:
                window.keys("minus" if char == "-" else char)
            time.sleep(4)  # Native resource bars animate after selection.
            window.capture(ROOT / (stage + "-selected.png"))
            window.click(1170, 894)
            deadline = time.monotonic() + 240
            log = Path(state["stage"]) / "game.log"
            _, assets = read_package(crp.read_bytes())
            native_asset_name = next(a["name"] for a in assets if a["kind"] == 52)
            needle = "Loaded simulation data from: " + native_asset_name
            while needle not in log.read_text(errors="replace"):
                if time.monotonic() > deadline:
                    window.capture(current)
                    raise RuntimeError(
                        "correct map did not load from ordinary New Game"
                    )
                time.sleep(2)
            deadline = time.monotonic() + 120
            while True:
                window.capture(current)
                if match(current, "strict-asheville-city.png", (1110, 992, 1260, 1030)):
                    break
                if time.monotonic() > deadline:
                    raise RuntimeError(
                        "native data loaded but city toolbar not observed"
                    )
                time.sleep(2)
            window.capture(ROOT / (stage + "-city.png"))
        (ROOT / (stage + "-validation.json")).write_text(
            json.dumps(
                {
                    "slug": slug,
                    "map_sha256": hashlib.sha256(crp.read_bytes()).hexdigest(),
                    "strict_disableMods": True,
                    "noWorkshop": True,
                    "control_socket_absent": True,
                    "ordinary_new_game_loaded": True,
                    "city_toolbar_observed": True,
                    "native_load_log": needle,
                    "wall_seconds_including_queue": time.time() - began,
                    "screenshots_require_visual_review": True,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"{slug}: ordinary New Game loaded exact map", flush=True)
    finally:
        if (
            cfg.state_file.exists()
            and Path(json.loads(cfg.state_file.read_text())["stage"]).name == stage
        ):
            command("down", "--out", str(ROOT / (stage + "-session")))


results = []
for slug in args.only:
    try:
        run(slug)
        results.append({"slug": slug, "ordinary_new_game_loaded": True})
    except Exception as error:
        results.append(
            {"slug": slug, "ordinary_new_game_loaded": False, "error": str(error)}
        )
        print(f"{slug}: {error}; continuing with the other maps", flush=True)
(ROOT / "strict-vanilla-summary.json").write_text(json.dumps(results, indent=2) + "\n")
sys.exit(0 if all(r["ordinary_new_game_loaded"] for r in results) else 1)
