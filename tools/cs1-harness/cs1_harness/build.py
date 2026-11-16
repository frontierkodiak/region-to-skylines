"""Compile the harness mod against the installed game's own assemblies."""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import subprocess

from .config import Config

MOD_SOURCES = pathlib.Path(__file__).resolve().parents[1] / "mod"
REFERENCES = [
    "mscorlib",
    "System",
    "System.Core",
    "UnityEngine",
    "UnityEngine.UI",
    "ColossalManaged",
    "ICities",
    "Assembly-CSharp",
]
DOTNET_INSTALL = "https://dot.net/v1/dotnet-install.sh"


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dotnet(cfg: Config) -> pathlib.Path:
    """A .NET SDK for Roslyn's csc; installed once into the cache if missing."""
    exe = cfg.dotnet_root / "dotnet"
    if not exe.exists():
        cfg.dotnet_root.mkdir(parents=True, exist_ok=True)
        script = cfg.dotnet_root.parent / "dotnet-install.sh"
        subprocess.run(["curl", "-fsSL", DOTNET_INSTALL, "-o", str(script)], check=True)
        subprocess.run(
            ["bash", str(script), "--channel", "8.0", "--install-dir", str(cfg.dotnet_root), "--no-path"],
            check=True,
        )
    return exe


def build(cfg: Config, trace_harmony: pathlib.Path | None = None) -> dict:
    managed = cfg.game_dir / "Cities_Data" / "Managed"
    exe = dotnet(cfg)
    sdk = sorted((cfg.dotnet_root / "sdk").iterdir())[-1]
    cfg.build_dir.mkdir(parents=True, exist_ok=True)
    out = cfg.build_dir / "Cs1Harness.dll"
    sources = sorted(MOD_SOURCES.glob("*.cs"))
    refs = [managed / f"{name}.dll" for name in REFERENCES]
    trace = None
    if trace_harmony is not None:
        expected = "e271d22a7c32bfca105d0e471c04eee14eec6142d37a30cd73cb7d32c7d1dd0f"
        engine = "c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1"
        runtime = cfg.game_dir / "Cities_Data/Mono/x86_64/libmono.so"
        if (
            cfg.host != "blade"
            or sha256(trace_harmony) != expected
            or sha256(managed / "Assembly-CSharp.dll") != engine
        ):
            raise ValueError("unsupported disposable trace build")
        if sha256(runtime) != "4cfea7a0d01dcaec3ca23380106a109f6a97659302675388fc06aa42ec7252b2":
            raise ValueError("unsupported trace runtime")
        dependency = cfg.build_dir / "0Harmony.dll"
        shutil.copyfile(trace_harmony, dependency)
        refs.append(dependency)
        trace = {"enabled": True, "disposable_only": True, "harmony_sha256": expected, "engine_sha256": engine}
    else:
        (cfg.build_dir / "0Harmony.dll").unlink(missing_ok=True)
    args = [
        str(exe),
        str(sdk / "Roslyn" / "bincore" / "csc.dll"),
        "-noconfig",
        "-nostdlib+",
        "-target:library",
        "-langversion:7.3",
        "-optimize+",
        "-unsafe+",  # Readback.cs writes a jump over one game method (see there)
        "-deterministic+",
        "-nologo",
        f"-out:{out}",
        *(["-define:TRACE_OBSERVER"] if trace is not None else []),
        *[f"-r:{r}" for r in refs if r.exists()],
        *map(str, sources),
    ]
    env = dict(os.environ, DOTNET_CLI_TELEMETRY_OPTOUT="1", DOTNET_ROOT=str(cfg.dotnet_root))
    subprocess.run(args, check=True, env=env)
    receipt = {
        "dll": str(out),
        "dll_sha256": sha256(out),
        "sources": {s.name: sha256(s) for s in sources},
        "game_assemblies": {r.name: sha256(r) for r in refs if r.exists()},
        "trace": trace,
    }
    (cfg.build_dir / "build-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    return receipt
