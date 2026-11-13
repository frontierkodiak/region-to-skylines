"""Run-local silent audio clients; no host mixer, server or permission changes.

ALSA loads only our null PCM (no includes, hardware or server plugins). Pulse
targets a regular file, never a socket; native PipeWire targets an absent socket.
These are application settings, not a security boundary against hostile code.
"""

from __future__ import annotations

import pathlib
import shlex
import stat

from .config import Config

ALSA_CONFIG = "pcm.default { type null }\npcm.null { type null }\n"


def environment(cfg: Config) -> dict[str, str]:
    root = cfg.harness_home / "run-audio"
    return {
        "ALSA_CONFIG_PATH": str(root / "alsa.conf"),
        "PULSE_CLIENTCONFIG": str(root / "pulse.conf"),
        "PULSE_SERVER": f"unix:{root / 'no-pulse'}",
        "PIPEWIRE_REMOTE": str(root / "no-pipewire"),
        "SDL_AUDIODRIVER": "dummy",
    }


def prepare(cfg: Config) -> pathlib.Path:
    root = cfg.harness_home / "run-audio"
    root.mkdir(parents=True, exist_ok=True)
    # Never reuse a real endpoint, even if a prior run left an unexpected file.
    for name in ("no-pulse", "no-pipewire"):
        if (root / name).exists():
            raise RuntimeError(f"silent audio endpoint unexpectedly exists: {root / name}")
    # Flatpak remaps existing Pulse endpoints into nested runtimes. A regular
    # file survives that remapping but connect(2) cannot use it as a socket.
    (root / "no-pulse").touch()
    (root / "alsa.conf").write_text(ALSA_CONFIG)
    (root / "pulse.conf").write_text("autospawn = no\nenable-shm = no\n")
    script = root / "env.sh"
    script.write_text("".join(f"export {k}={shlex.quote(v)}\n" for k, v in environment(cfg).items()))
    return script


def processes(cfg: Config) -> list[dict]:
    """Audio-only /proc receipt for this private display, without unrelated env."""
    rows = []
    keys = environment(cfg)
    catalog = {}
    for proc in pathlib.Path("/proc").glob("[0-9]*"):
        try:
            raw = dict(
                item.decode(errors="replace").split("=", 1)
                for item in (proc / "environ").read_bytes().split(b"\0")
                if b"=" in item
            )
            env = {k: raw[k] for k in (*keys, "DISPLAY") if k in raw}
            ppid = int((proc / "stat").read_text().rsplit(")", 1)[1].split()[1])
            catalog[int(proc.name)] = (proc, ppid, env)
        except OSError:
            continue
    selected = {
        pid
        for pid, (_, _, env) in catalog.items()
        if env.get("DISPLAY") == cfg.display or env.get("ALSA_CONFIG_PATH") == keys["ALSA_CONFIG_PATH"]
    }
    # Helpers can remove DISPLAY. Include descendants rather than silently
    # dropping them from a display-only audit.
    while True:
        children = {pid for pid, (_, ppid, _) in catalog.items() if ppid in selected}
        if children <= selected:
            break
        selected |= children
    for pid in sorted(selected):
        proc, ppid, env = catalog[pid]
        try:
            devices = []
            for fd in (proc / "fd").iterdir():
                try:
                    target = str(fd.readlink())
                except OSError:
                    continue
                if target.startswith(("/dev/snd/", "/dev/dsp", "/dev/audio")):
                    devices.append(target)
            row = {
                "pid": int(proc.name),
                "name": (proc / "comm").read_text().strip(),
                "display": env.get("DISPLAY"),
                "ppid": ppid,
                "audio_environment": {k: env.get(k) for k in keys},
                "physical_audio_fds": devices,
                "pulse_endpoint": pulse_endpoint(proc / "root", env.get("PULSE_SERVER"), cfg),
                "flatpak_pulse_endpoint": pulse_endpoint(proc / "root", "unix:/run/flatpak/pulse/native", cfg),
            }
            if proc.exists():
                rows.append(row)
        except OSError:
            continue
    return rows


def pulse_endpoint(root: pathlib.Path, server: str | None, cfg: Config) -> dict:
    """Resolve a client's actual mount namespace, not its cosmetic server string."""
    if not server:
        return {"server": server, "kind": "unset", "run_owned": False}
    if not server.startswith("unix:/"):
        return {"server": server, "kind": "unsupported", "run_owned": False}
    try:
        target = (root / server.removeprefix("unix:/")).stat()
        owned = (cfg.harness_home / "run-audio/no-pulse").stat()
    except FileNotFoundError:
        return {"server": server, "kind": "absent", "run_owned": False}
    except OSError as exc:
        return {"server": server, "kind": "unreadable", "run_owned": False, "error": str(exc)}
    return {
        "server": server,
        "kind": "regular" if stat.S_ISREG(target.st_mode) else "socket" if stat.S_ISSOCK(target.st_mode) else "other",
        "device": target.st_dev,
        "inode": target.st_ino,
        "run_owned": (target.st_dev, target.st_ino) == (owned.st_dev, owned.st_ino),
    }


def violations(cfg: Config, rows: list[dict], require_game: bool = True) -> list[str]:
    """Reject restored host Pulse routes, including late Steam audio clients."""
    errors = []
    if require_game and not any(row["name"] == "Cities.x64" for row in rows):
        errors.append("no game audio receipt")
    expected = environment(cfg)
    for row in rows:
        label = f"{row['name']} ({row['pid']})"
        if row["physical_audio_fds"]:
            errors.append(f"{label}: physical audio device open")
        for key in ("pulse_endpoint", "flatpak_pulse_endpoint"):
            endpoint = row[key]
            if endpoint["kind"] not in ("unset", "absent") and not (
                endpoint["kind"] == "regular" and endpoint["run_owned"]
            ):
                errors.append(f"{label}: {key} is not the run-owned non-socket")
        if row["name"] not in ("Cities.x64", "steam", "steamwebhelper"):
            continue
        env = row["audio_environment"]
        for key in ("ALSA_CONFIG_PATH", "PIPEWIRE_REMOTE", "SDL_AUDIODRIVER"):
            if env.get(key) != expected[key]:
                errors.append(f"{label}: unexpected {key}")
        endpoint = row["pulse_endpoint"]
        if endpoint["kind"] != "regular" or not endpoint["run_owned"]:
            errors.append(f"{label}: Pulse does not target the run-owned non-socket")
    return errors
