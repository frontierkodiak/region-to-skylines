"""Offline compiler invocation in a new private stage, never deployment."""

from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess

from api import spec, build_v2

FLAGS = [
    "-noconfig",
    "-nostdlib+",
    "-target:library",
    "-langversion:7.3",
    "-optimize+",
    "-unsafe+",
    "-deterministic+",
    "-nologo",
]


def command(directory, dotnet, compiler, references, sources):
    return [
        str(dotnet),
        str(compiler),
        *FLAGS,
        "-out:" + str(directory / "Cs1Harness.dll"),
        *["-r:" + str(directory / "references" / n) for n in sorted(references)],
        *[str(directory / "sources" / n) for n in sorted(sources)],
    ]


def build(store, directory, dotnet_root):
    directory = directory.resolve()
    directory.mkdir(parents=True, exist_ok=False)
    old = spec.read(spec.OLD / "freeze.json")["build"]
    sources = spec.staged_sources(old)
    references = old["reference_assemblies"]
    for folder, values in [
        ("sources", {n: spec.hashed(b) for n, b in sources.items()}),
        ("references", references),
    ]:
        (directory / folder).mkdir()
        for name, key in values.items():
            data = sources[name] if folder == "sources" else store.read(key, name)
            (directory / folder / name).write_bytes(data)
            spec.put(store, data)
    dotnet = dotnet_root / "dotnet"
    compiler = dotnet_root / "sdk/8.0.427/Roslyn/bincore/csc.dll"
    if spec.hashed(compiler.read_bytes()) != old["compiler"]["csc_sha256"]:
        raise ValueError("licensed compiler holding differs")
    # Full declared tool runtime, not just csc.dll. No SDK install/download occurs.
    tool_files = [dotnet]
    for rel in ["host", "shared", "sdk/8.0.427/Roslyn/bincore"]:
        tool_files.extend(p for p in (dotnet_root / rel).rglob("*") if p.is_file())
    tools = {
        str(p.relative_to(dotnet_root)): spec.put(store, p.read_bytes())
        for p in sorted(tool_files)
    }
    argv = command(directory, dotnet, compiler, references, sources)
    env = dict(
        os.environ,
        DOTNET_ROOT=str(dotnet_root),
        DOTNET_CLI_TELEMETRY_OPTOUT="1",
        DOTNET_SKIP_FIRST_TIME_EXPERIENCE="1",
    )
    started = datetime.now(timezone.utc).isoformat()
    version = subprocess.run(
        [str(dotnet), "--version"], env=env, capture_output=True, check=True, timeout=30
    )
    csc_version = subprocess.run(
        [str(dotnet), str(compiler), "-version"],
        env=env,
        capture_output=True,
        check=True,
        timeout=30,
    )
    result = subprocess.run(argv, env=env, capture_output=True, timeout=120)
    log = spec.put(store, result.stdout + result.stderr)
    if result.returncode:
        raise RuntimeError("fresh compiler failed; retained log " + log)
    output = directory / "Cs1Harness.dll"
    receipt = dict(
        version=5,
        kind="ACTUAL_OFFLINE_COMPILATION",
        started=started,
        finished=datetime.now(timezone.utc).isoformat(),
        directory=str(directory),
        dotnet_root=str(dotnet_root),
        argv=argv,
        dotnet_version=version.stdout.decode().strip(),
        compiler_version=csc_version.stdout.decode().strip(),
        tool_files=tools,
        references=references,
        original_sources=old["original_sources"],
        staged_sources={n: spec.hashed(b) for n, b in sources.items()},
        exit_code=result.returncode,
        compiler_log=log,
        dll=spec.put(store, output.read_bytes()),
        mvid=build_v2.module_version_id(output),
    )
    spec.put_json(store, receipt)
    return receipt


def validate(receipt, store):
    spec.exact(
        receipt,
        {
            "version",
            "kind",
            "started",
            "finished",
            "directory",
            "dotnet_root",
            "argv",
            "dotnet_version",
            "compiler_version",
            "tool_files",
            "references",
            "original_sources",
            "staged_sources",
            "exit_code",
            "compiler_log",
            "dll",
            "mvid",
        },
        "fresh receipt",
    )
    old = spec.read(spec.OLD / "freeze.json")["build"]
    if (
        receipt["version"] != 5
        or receipt["kind"] != "ACTUAL_OFFLINE_COMPILATION"
        or type(receipt["exit_code"]) is not int
        or receipt["exit_code"] != 0
        or receipt["original_sources"] != old["original_sources"]
        or receipt["references"] != old["reference_assemblies"]
    ):
        raise ValueError("fresh build role/receipt mismatch")
    staged = {n: spec.hashed(b) for n, b in spec.staged_sources(old).items()}
    if receipt["staged_sources"] != staged:
        raise ValueError("full staged file closure differs")
    directory = Path(receipt["directory"])
    dotnet_root = Path(receipt["dotnet_root"])
    if receipt["argv"] != command(
        directory,
        dotnet_root / "dotnet",
        dotnet_root / "sdk/8.0.427/Roslyn/bincore/csc.dll",
        receipt["references"],
        staged,
    ):
        raise ValueError("effective compiler arguments differ")
    # Exact tool closure is frozen by the descriptor too. Validate all retained bytes.
    for group in ("tool_files", "references", "staged_sources"):
        if type(receipt[group]) is not dict or not receipt[group]:
            raise ValueError("missing complete build role: " + group)
        for key in receipt[group].values():
            data = (store.root / key).read_bytes()
            if spec.hashed(data) != key:
                raise ValueError("retained build bytes differ")
    for key in ("compiler_log", "dll"):
        data = (store.root / receipt[key]).read_bytes()
        if spec.hashed(data) != receipt[key]:
            raise ValueError("retained build output differs")
    if build_v2.module_version_id(store.root / receipt["dll"]) != receipt["mvid"]:
        raise ValueError("fresh DLL MVID differs")
    if (
        receipt["tool_files"]["sdk/8.0.427/Roslyn/bincore/csc.dll"]
        != old["compiler"]["csc_sha256"]
    ):
        raise ValueError("compiler differs")
