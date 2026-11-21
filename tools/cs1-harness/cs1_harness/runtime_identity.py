"""Bind the controlled running process to its build; no install-path assumptions."""

import datetime
import hashlib
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_identity(identity, build):
    if identity["executable"]["sha256"] != build["game_executable_sha256"]:
        raise ValueError("running executable differs from build receipt")
    loaded = {Path(a["path"]).name: a["sha256"] for a in identity["assemblies"]}
    for name, expected in {**build["game_assemblies"], "Cs1Harness.dll": build["dll_sha256"]}.items():
        if loaded.get(name) != expected:
            raise ValueError(f"loaded assembly missing or differs from build: {name}")


def bind_runtime(session, build):
    reported = session.client.call("runtime_identity")
    candidates = {row["pid"] for row in session.receipt["game_gpu"]}
    if len(candidates) != 1:
        raise ValueError("cannot bind one owned runtime process")
    pid = candidates.pop()
    proc = Path("/proc") / str(pid)
    status = (proc / "status").read_text()
    namespace_pids = next(line.split()[1:] for line in status.splitlines() if line.startswith("NSpid:"))
    if int(namespace_pids[-1]) != reported["pid"]:
        raise ValueError("mod response does not belong to the rendering process")
    start = (proc / "stat").read_text().rsplit(")", 1)[1].split()[19]
    exe = proc / "exe"
    identity = {
        "observed_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "host_pid": pid,
        "namespace_pid": reported["pid"],
        "process_start_ticks": start,
        "executable": {"path": str(exe.readlink()), "sha256": digest(exe)},
        "command_line": (proc / "cmdline").read_bytes().decode().split("\0"),
        "assemblies": reported["assemblies"],
        "unresolved_loaded_assemblies": reported.get("unresolved_loaded_assemblies", []),
        "build_matches": False,
        "launch_args": session.receipt["launch_args"],
        "scope": "Loaded assembly file bytes at menu readiness, not an in-memory code attestation.",
    }
    session.receipt["runtime_identity"] = identity
    for assembly in reported["assemblies"]:
        path = Path(assembly["path"])
        if not path.is_absolute() or digest(proc / "root" / path.relative_to("/")) != assembly["sha256"]:
            raise ValueError(f"cannot bind loaded assembly bytes: {path.name}")
    if (proc / "stat").read_text().rsplit(")", 1)[1].split()[19] != start:
        raise ValueError("runtime changed while hashing")
    validate_identity(identity, build)
    identity["build_matches"] = True
    session.receipt["runtime_identity"] = identity
    return identity
