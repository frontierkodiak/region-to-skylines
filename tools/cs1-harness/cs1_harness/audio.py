"""Run-local silent audio clients; no host mixer, server or permission changes.

ALSA loads only our null PCM (no includes, hardware or server plugins). Pulse
and native PipeWire clients target absent sockets, with Pulse autospawn off.
These are application settings, not a security boundary against hostile code.
"""

from __future__ import annotations

import pathlib
import shlex

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
    (root / "alsa.conf").write_text(ALSA_CONFIG)
    (root / "pulse.conf").write_text("autospawn = no\nenable-shm = no\n")
    script = root / "env.sh"
    script.write_text("".join(f"export {k}={shlex.quote(v)}\n" for k, v in environment(cfg).items()))
    return script


def processes(cfg: Config) -> list[dict]:
    """Audio-only /proc receipt for this private display, without unrelated env."""
    rows = []
    keys = environment(cfg)
    for proc in pathlib.Path("/proc").glob("[0-9]*"):
        try:
            env = dict(
                item.decode(errors="replace").split("=", 1)
                for item in (proc / "environ").read_bytes().split(b"\0")
                if b"=" in item
            )
            if env.get("DISPLAY") != cfg.display:
                continue
            devices = []
            for fd in (proc / "fd").iterdir():
                try:
                    target = str(fd.readlink())
                except OSError:
                    continue
                if target.startswith(("/dev/snd/", "/dev/dsp", "/dev/audio")):
                    devices.append(target)
            rows.append(
                {
                    "pid": int(proc.name),
                    "name": (proc / "comm").read_text().strip(),
                    "display": env["DISPLAY"],
                    "audio_environment": {k: env.get(k) for k in keys},
                    "physical_audio_fds": devices,
                }
            )
        except (OSError, ProcessLookupError):
            continue
    return rows
