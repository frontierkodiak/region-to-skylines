"""Frozen native configuration and bounded cleanup primitives. Uninvoked off-game."""

import dataclasses
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

from loopback_fixture import identity
from wire import Unknown

UNITS = (
    "audio_unit",
    "steam_unit",
    "xvfb_unit",
    "dbus_unit",
    "gpu_unit",
    "rec_unit",
    "live_unit",
    "vnc_unit",
)
PATHS = {
    "steam_root",
    "game_dir",
    "data_dir",
    "harness_home",
    "virtualgl",
    "live_dir",
    "ffmpeg",
    "x11vnc",
    "cache_dir",
}


def tool_paths():
    result = {"python": str(Path(sys.executable).absolute())}
    for name in ("multica", "systemctl", "flatpak"):
        found = shutil.which(name)
        if not found:
            raise Unknown("required native dependency absent: " + name)
        result[name] = str(Path(found).resolve())
    return result


def configuration(receipt):
    from cs1_harness.config import Config

    cfg = Config.for_host()
    return dict(
        fields={
            f.name: str(getattr(cfg, f.name))
            if isinstance(getattr(cfg, f.name), Path)
            else getattr(cfg, f.name)
            for f in dataclasses.fields(Config)
        },
        build_directory=receipt["directory"],
        lock=str(cfg.lock_file),
        runtime=str(cfg.runtime_dir),
    )


def config_from(value):
    from cs1_harness.config import Config

    class RetainedConfig(Config):
        @property
        def build_dir(self):
            return Path(value["build_directory"])

    if set(value) != {"fields", "build_directory", "lock", "runtime"} or set(
        value["fields"]
    ) != {f.name for f in dataclasses.fields(Config)}:
        raise Unknown("native configuration role differs")
    cfg = RetainedConfig(
        **{k: Path(v) if k in PATHS else v for k, v in value["fields"].items()}
    )
    if str(cfg.lock_file) != value["lock"] or str(cfg.runtime_dir) != value["runtime"]:
        raise Unknown("shared queue/guard configuration changed")
    return cfg


def build_descriptor(native, store, source, freeze_file):
    import accepted_api as api

    paths = tool_paths()
    session = "PL1321-" + uuid.uuid4().hex
    return dict(
        session_id=session,
        configuration=configuration(native.descriptor["fresh_build"]),
        tools={
            name: dict(path=path, sha256=api.spec.put(store, Path(path).read_bytes()))
            for name, path in paths.items()
        },
        output=str(store.root.parent / ("native-" + session)),
        freeze_file=str(Path(freeze_file).resolve()),
        source_directory=str(source),
        argv=[
            paths["python"],
            str(source / "native_cli.py"),
            "--freeze",
            str(Path(freeze_file).resolve()),
            "--store",
            str(store.root),
            "--acceptance-comment",
            "EXTERNAL_PARENT_ACCEPTANCE_COMMENT",
            "--budget-comment",
            "EXTERNAL_PARENT_BUDGET_COMMENT",
        ],
    )


def validate(value, native, store, source):
    import accepted_api as api

    api.spec.exact(
        value,
        {
            "session_id",
            "configuration",
            "tools",
            "output",
            "argv",
            "freeze_file",
            "source_directory",
        },
        "native invocation",
    )
    if (
        type(value["session_id"]) is not str
        or not value["session_id"].startswith("PL1321-")
        or len(value["session_id"]) != 39
    ):
        raise Unknown("fresh native study session id required")
    if value["configuration"] != configuration(native.descriptor["fresh_build"]):
        raise Unknown("native configuration differs from frozen host/build")
    tools = api.spec.exact(
        value["tools"], set(tool_paths()), "native executable dependencies"
    )
    for name, path in tool_paths().items():
        row = api.spec.exact(tools[name], {"path", "sha256"}, "native dependency")
        if (
            not Path(row["path"]).is_absolute()
            or api.adapter_spec.raw(store, row["sha256"]) != Path(path).read_bytes()
            or Path(row["path"]).read_bytes() != Path(path).read_bytes()
        ):
            raise Unknown("native executable byte/location changed: " + name)
    expected_output = str(store.root.parent / ("native-" + value["session_id"]))
    expected_argv = [
        tools["python"]["path"],
        str(Path(value["source_directory"]) / "native_cli.py"),
        "--freeze",
        value["freeze_file"],
        "--store",
        str(store.root),
        "--acceptance-comment",
        "EXTERNAL_PARENT_ACCEPTANCE_COMMENT",
        "--budget-comment",
        "EXTERNAL_PARENT_BUDGET_COMMENT",
    ]
    if value["output"] != expected_output or value["argv"] != expected_argv:
        raise Unknown("native invocation/output role differs")


def command(argv, deadline, check=True):
    return subprocess.run(
        argv, capture_output=True, timeout=min(2, deadline.remaining()), check=check
    )


def unit_state(cfg, deadline):
    rows = {}
    for field in UNITS:
        name = getattr(cfg, field)
        r = command(
            [
                "systemctl",
                "--user",
                "show",
                name,
                "--all",
                "--no-pager",
                "--property=Id,MainPID,InvocationID,ActiveState",
            ],
            deadline,
            check=False,
        )
        values = {}
        for line in r.stdout.decode().splitlines():
            key, sep, value = line.partition("=")
            if not sep or key in values:
                raise Unknown("ambiguous unit ownership read")
            values[key] = value
        if (
            set(values) != {"Id", "MainPID", "InvocationID", "ActiveState"}
            or values["Id"] != name + ".service"
        ):
            raise Unknown("unit identity/coverage unresolved")
        pid = int(values["MainPID"])
        rows[name] = dict(values, identity=identity(pid) if pid else None)
        if pid and rows[name]["identity"] is None:
            raise Unknown("unit PID disappeared during inventory")
    return rows


def cleanup(cfg, directory, deadline, lease_held):
    """No default-unit operation without the original shared guard lease."""
    if not lease_held:
        return dict(clean=False, unresolved=["original shared lease not retained"])
    unresolved, instances = [], []
    for record in sorted(directory.glob("flatpak-*.json")):
        from wire import decode

        value = decode(record.read_bytes())
        if value.get("instance"):
            instances.append(value)
        else:
            unresolved.append("Flatpak helper lacks instance identity: " + record.name)
    for value in instances:
        try:
            r = command(
                ["flatpak", "ps", "--columns=instance,pid,application"], deadline
            )
            matches = [
                line.split()
                for line in r.stdout.decode().splitlines()
                if line.split() and line.split()[0] == value["instance"]
            ]
            if not matches:
                continue
            if (
                len(matches) != 1
                or len(matches[0]) != 3
                or matches[0][2] != "com.valvesoftware.Steam"
            ):
                raise Unknown("Flatpak instance ownership differs")
            pid = int(matches[0][1])
            if value.get("identity") != identity(pid):
                raise Unknown("Flatpak PID/start reused or missing")
            command(["flatpak", "kill", value["instance"]], deadline)
        except (ValueError, OSError, subprocess.SubprocessError):
            unresolved.append("Flatpak instance " + value["instance"])
    try:
        before = unit_state(cfg, deadline)
        for name in before:
            command(["systemctl", "--user", "stop", name], deadline, check=False)
        after = unit_state(cfg, deadline)
        unresolved.extend(
            name
            for name, row in after.items()
            if row["identity"] or row["ActiveState"] not in {"inactive", "failed"}
        )
    except (ValueError, OSError, subprocess.SubprocessError):
        before, after = {}, {}
        unresolved.append("unit cleanup acknowledgment unavailable")
    return dict(
        clean=not unresolved,
        unresolved=unresolved,
        units_before=before,
        units_after=after,
        flatpak_instances=instances,
    )
