"""Build one study-local staged harness DLL and freeze its exact provenance.

The shared `tools/cs1-harness` sources are not edited.  A staged copy adds the
study's independent pre-request build-index readback and makes the existing
public `CreatePath` overload take the declared float budget and return its
effective constructor arguments.  The receipt records the actual compiler,
command, referenced assembly bytes, staged sources, DLL bytes and the DLL's
module version id (MVID).  It is source binding, not memory attestation.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

from cs1_harness import build as harness_build
from cs1_harness.config import Config

import stock_v2

STAGE_NAME = "outside-readiness-stock-v2-sources"

NETWORK_PATCHES = {
    # Explicit float budget, recorded effective arguments, and one independent
    # build-index sample that does not come from the request/response itself.
    "            uint id;\n            bool created": """            float maxLength = q.ContainsKey("max_length") ? Convert.ToSingle(q["max_length"]) : 100000f;
            if (maxLength != 100000f)
                throw new Exception("study budget is not predeclared");
            var sampled = Singleton<SimulationManager>.instance.m_currentBuildIndex;
            uint id;
            bool created""",
    "Singleton<SimulationManager>.instance.m_currentBuildIndex, from, to,": "sampled, from, to,",
    "VehicleInfo.VehicleCategory.PassengerCar, 100000f);": "VehicleInfo.VehicleCategory.PassengerCar, maxLength);",
    'return Host.Obj("id", id, "mode", mode);': """return Host.Obj("id", id, "mode", mode, "max_length", maxLength,
                "build_index", sampled, "seed", 857, "from", q["from"], "to", q["to"],
                "vehicle", vehicle.ToString(),
                "category", (transport ? VehicleInfo.VehicleCategory.All : VehicleInfo.VehicleCategory.PassengerCar).ToString(),
                "lane_types", (transport ? NetInfo.LaneType.Vehicle | NetInfo.LaneType.TransportVehicle | NetInfo.LaneType.CargoVehicle : NetInfo.LaneType.Vehicle).ToString());""",
}
BUILD_INDEX_REGISTRATION = (
    '            Host.Register("path_result", Needs.City, "poll a harness-owned native path; completed paths are released: {id}", Result);'
)
BUILD_INDEX_OP = """        // Study-local: sample the current build index outside a path request so
        // the effective response cannot be its own oracle.
        static Dictionary<string, object> StudyBuildIndex(Dictionary<string, object> q)
        {
            var sm = Singleton<SimulationManager>.instance;
            return Host.Obj("build_index", sm.m_currentBuildIndex, "frame", sm.m_currentFrameIndex,
                "paused", sm.SimulationPaused);
        }

"""
BUILD_INDEX_REGISTER_LINE = (
    '            Host.Register("study_build_index", Needs.City, '
    '"current SimulationManager build index sampled outside a path request", StudyBuildIndex);'
)


def sha(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def module_version_id(path: Path) -> str:
    """Read the Module table MVID from CLI metadata bytes."""
    data = Path(path).read_bytes()
    if data[:2] != b"MZ":
        raise ValueError("not a PE file")
    pe = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe : pe + 4] != b"PE\0\0":
        raise ValueError("missing PE signature")
    coff = pe + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    optional_size = struct.unpack_from("<H", data, coff + 16)[0]
    optional = coff + 20
    magic = struct.unpack_from("<H", data, optional)[0]
    directories = optional + (96 if magic == 0x10B else 112 if magic == 0x20B else 0)
    if not directories:
        raise ValueError("unknown optional header")
    cli_rva = struct.unpack_from("<I", data, directories + 14 * 8)[0]
    if not cli_rva:
        raise ValueError("no CLI header")
    table = []
    for index in range(sections):
        row = optional + optional_size + index * 40
        table.append(
            (
                struct.unpack_from("<I", data, row + 12)[0],
                struct.unpack_from("<I", data, row + 8)[0],
                struct.unpack_from("<I", data, row + 20)[0],
                struct.unpack_from("<I", data, row + 16)[0],
            )
        )

    def offset(rva):
        for virtual, size, raw, raw_size in table:
            if virtual <= rva < virtual + max(size, raw_size):
                return raw + (rva - virtual)
        raise ValueError("unmapped RVA")

    cli = offset(cli_rva)
    metadata = offset(struct.unpack_from("<I", data, cli + 8)[0])
    if data[metadata : metadata + 4] != b"BSJB":
        raise ValueError("missing metadata signature")
    version = struct.unpack_from("<I", data, metadata + 12)[0]
    cursor = metadata + 16 + ((version + 3) // 4) * 4
    streams_count = struct.unpack_from("<H", data, cursor + 2)[0]
    cursor += 4
    streams = {}
    for _ in range(streams_count):
        start = struct.unpack_from("<I", data, cursor)[0]
        cursor += 8
        end = data.index(b"\0", cursor)
        name = data[cursor:end].decode()
        cursor = end + 1
        relative = cursor - metadata
        cursor = metadata + ((relative + 3) & ~3)
        streams[name] = start
    if "#~" not in streams and "#-" not in streams:
        raise ValueError("no table stream")
    header = metadata + streams.get("#~", streams.get("#-"))
    heap_sizes = data[header + 6]
    valid = struct.unpack_from("<Q", data, header + 8)[0]
    cursor = header + 24
    counts = {}
    for index in range(64):
        if valid >> index & 1:
            counts[index] = struct.unpack_from("<I", data, cursor)[0]
            cursor += 4
    if counts.get(0, 0) < 1:
        raise ValueError("no Module table row")
    string_size = 4 if heap_sizes & 1 else 2
    guid_size = 4 if heap_sizes & 2 else 2
    at = cursor + 2 + string_size
    guid_index = (
        struct.unpack_from("<I", data, at)[0]
        if guid_size == 4
        else struct.unpack_from("<H", data, at)[0]
    )
    guid = metadata + streams["#GUID"] + (guid_index - 1) * 16
    a = struct.unpack_from("<I", data, guid)[0]
    b = struct.unpack_from("<H", data, guid + 4)[0]
    c = struct.unpack_from("<H", data, guid + 6)[0]
    tail = data[guid + 8 : guid + 16].hex()
    return f"{a:08x}-{b:04x}-{c:04x}-{tail[:4]}-{tail[4:]}"


def stage_sources(cfg: Config) -> Path:
    stage = cfg.build_dir / STAGE_NAME
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    sources = sorted((stock_v2.HARNESS / "mod").glob("*.cs"))
    for path in sources:
        shutil.copyfile(path, stage / path.name)
    target = stage / "NetworkOps.cs"
    text = target.read_text()
    for old, new in NETWORK_PATCHES.items():
        if text.count(old) != 1:
            raise ValueError("NetworkOps source anchor changed")
        text = text.replace(old, new)
    if text.count(BUILD_INDEX_REGISTRATION) != 1:
        raise ValueError("path_result registration anchor changed")
    text = text.replace(
        BUILD_INDEX_REGISTRATION,
        BUILD_INDEX_REGISTRATION + "\n" + BUILD_INDEX_REGISTER_LINE,
    )
    if text.count("        static Dictionary<string, object> Result(") != 1:
        raise ValueError("Result method anchor changed")
    text = text.replace(
        "        static Dictionary<string, object> Result(",
        BUILD_INDEX_OP + "        static Dictionary<string, object> Result(",
    )
    target.write_text(text)
    return stage


def build() -> dict:
    cfg = Config.for_host()
    stage = stage_sources(cfg)
    managed = cfg.game_dir / "Cities_Data" / "Managed"
    dotnet = harness_build.dotnet(cfg)
    sdk = sorted((cfg.dotnet_root / "sdk").iterdir())[-1]
    compiler = sdk / "Roslyn" / "bincore" / "csc.dll"
    output = cfg.build_dir / "Cs1Harness.dll"
    cfg.build_dir.mkdir(parents=True, exist_ok=True)
    references = [managed / f"{name}.dll" for name in harness_build.REFERENCES]
    sources = sorted(stage.glob("*.cs"))
    command = [
        str(dotnet),
        str(compiler),
        "-noconfig",
        "-nostdlib+",
        "-target:library",
        "-langversion:7.3",
        "-optimize+",
        "-unsafe+",
        "-deterministic+",
        "-nologo",
        f"-out:{output}",
        *[f"-r:{ref}" for ref in references if ref.exists()],
        *map(str, sources),
    ]
    subprocess.run(
        command,
        check=True,
        env={**__import__("os").environ, "DOTNET_CLI_TELEMETRY_OPTOUT": "1", "DOTNET_ROOT": str(cfg.dotnet_root)},
    )
    receipt = {
        "built_at": stock_v2.now(),
        "schema": 2,
        "issue": "PL-1313",
        "compiler": {
            "dotnet": subprocess.check_output([str(dotnet), "--version"], text=True).strip(),
            "csc_path": str(compiler),
            "csc_sha256": sha(compiler),
        },
        "command": command,
        "source_stage": str(stage),
        "original_sources": {
            path.name: sha(path) for path in sorted((stock_v2.HARNESS / "mod").glob("*.cs"))
        },
        "staged_sources": {path.name: sha(path) for path in sources},
        "staged_NetworkOps": (stage / "NetworkOps.cs").read_text(),
        "patches": sorted(NETWORK_PATCHES) + [BUILD_INDEX_REGISTER_LINE, BUILD_INDEX_OP.strip()],
        "reference_assemblies": {
            path.name: sha(path) for path in references if path.exists()
        },
        "game_executable_sha256": sha(cfg.game_dir / "Cities.x64"),
        "dll": {
            "path": str(output),
            "sha256": sha(output),
            "bytes": output.stat().st_size,
            "mvid": module_version_id(output),
        },
        "scope": "staged source closure and public overload arguments; not compiler trust, memory attestation or strict-no-mods",
    }
    (cfg.build_dir / "study-build-receipt.json").write_bytes(stock_v2.canonical(receipt))
    return receipt
