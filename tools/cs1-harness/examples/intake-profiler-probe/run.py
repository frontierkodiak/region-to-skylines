"""CPU-only test of accessor observability in the exact installed Mono runtime.

No Session/Steam/game path is invoked. This does not provide a native trace.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
HARNESS = HERE.parents[1]
sys.path.insert(0, str(HARNESS))

from cs1_harness.config import Config  # noqa: E402

ENGINE = "c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1"
RUNTIME = "4cfea7a0d01dcaec3ca23380106a109f6a97659302675388fc06aa42ec7252b2"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def run(args: list[str], output: Path, env: dict[str, str]) -> str:
    result = subprocess.run(args, env=env, capture_output=True, text=True, timeout=30)
    output.with_suffix(".stdout").write_text(result.stdout)
    output.with_suffix(".stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{args[0]} failed ({result.returncode}); see {output}")
    return result.stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("out", type=Path, help="new absolute experiment output directory")
    args = parser.parse_args()
    out = args.out
    if not out.is_absolute():
        parser.error("out must be absolute")
    out.mkdir(parents=True, exist_ok=False)
    cfg = Config.for_host()
    managed = cfg.game_dir / "Cities_Data/Managed"
    runtime = cfg.game_dir / "Cities_Data/Mono/x86_64/libmono.so"
    engine = managed / "Assembly-CSharp.dll"
    refs = [managed / f"{name}.dll" for name in ["mscorlib", "UnityEngine", "Assembly-CSharp"]]
    input_hashes = {str(p): sha(p) for p in [runtime, *refs]}
    if sha(runtime) != RUNTIME or sha(engine) != ENGINE:
        raise RuntimeError("unsupported runtime/engine; no probe was executed")
    dotnet = cfg.dotnet_root / "dotnet"
    sdk = sorted((cfg.dotnet_root / "sdk").iterdir())[-1]
    env = dict(os.environ, DOTNET_ROOT=str(cfg.dotnet_root), DOTNET_CLI_TELEMETRY_OPTOUT="1")
    embed, fixture = out / "embed", out / "Probe.exe"
    run(
        [
            "gcc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-Wl,--export-dynamic",
            str(HERE / "embed.c"),
            "-o",
            str(embed),
            "-ldl",
        ],
        out / "compile-c",
        env,
    )
    run(
        [
            str(dotnet),
            str(sdk / "Roslyn/bincore/csc.dll"),
            "-noconfig",
            "-nostdlib+",
            "-target:exe",
            "-optimize+",
            "-deterministic+",
            "-nologo",
            f"-out:{fixture}",
            *[f"-r:{p}" for p in refs],
            str(HERE / "Probe.cs"),
        ],
        out / "compile-csharp",
        env,
    )
    cases = {}
    for mode in ["off", "early", "late", "early-noinline", "metadata"]:
        text = run([str(embed), str(runtime), str(managed), str(fixture), mode], out / mode, env)
        if mode == "metadata":
            cases[mode] = {key: value for key, value in re.findall(r"^(solver_il_\w+)=(\w+)$", text, re.M)}
            require(
                cases[mode]
                == {
                    "solver_il_sha256": "eef2d18b29f0ff396b792dd45ec06c26c5181652985975a7cd93b9e46bb432bc",
                    "solver_il_bytes": "8425",
                },
                "unexpected original solver IL",
            )
            continue
        require("checksum=84100" in text, f"{mode}: fixture computation changed")
        match = re.search(r"events=(\d+) dropped=(\d+) mode=(\S+) result=(\d+)", text)
        require(match and int(match[2]) == 0 and int(match[4]) == 0, f"{mode}: missing/failed/dropped events")
        counts = Counter(line for line in text.splitlines() if re.match(r"^[+-] ", line))
        getters = counts["+ FastList`1 get_Item"]
        setters = counts["+ FastList`1 set_Item"]
        require(getters == counts["- FastList`1 get_Item"], f"{mode}: unpaired getter event")
        require(setters == counts["- FastList`1 set_Item"], f"{mode}: unpaired setter event")
        expected = 580 if mode == "early-noinline" else 0
        require(getters == setters == expected, f"{mode}: unexpected accessor counts {getters}/{setters}")
        cases[mode] = {
            "checksum": 84100,
            "events": int(match[1]),
            "dropped": 0,
            "getter_entries": getters,
            "setter_entries": setters,
        }
    # Even the noinline case proves only accessor events on a CPU fixture.
    result = {
        "source_head": subprocess.check_output(["git", "-C", str(HARNESS), "rev-parse", "HEAD"], text=True).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "-C", str(HARNESS), "status", "--porcelain"], text=True).strip()
        ),
        "source_files_sha256": {p.name: sha(p) for p in HERE.iterdir() if p.is_file()},
        "input_sha256": input_hashes,
        "binary_sha256": {p.name: sha(p) for p in [embed, fixture]},
        "cases": cases,
        "atomic_intake_observer_ready": False,
        "game_launched": False,
        "installed_game_modified": False,
        "limits": [
            "Fixture uses the real FastList<WaterSource>, not a water simulation.",
            "Default-JIT profiling does not observe accessor boundaries.",
            "early-noinline changes optimization defaults in its disposable process only.",
            "No game-instance source/buffer/transport phases were captured.",
        ],
    }
    # Recheck read-only inputs after every owned process has completed.
    require(all(sha(Path(p)) == h for p, h in input_hashes.items()), "installed input changed during probe")
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"atomic_intake_observer_ready": False, "game_launched": False, "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
