"""One-time, user-level setup on the host. No root, no system service, all reversible."""

from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import tempfile

from .config import Config
from .steam import backend

VGL_VERSION = "3.1.5"
VGL_DEB = f"virtualgl_{VGL_VERSION}_amd64.deb"
VGL_SHA256 = "df3f7788ce41b182a47c0d298e5cd6d2d63579522cb41825970b7726e825485e"

LAUNCH_SH = """#!/bin/sh
# Steam launch wrapper for Cities: Skylines (cs1-harness). Steam runs it as
# LaunchOptions "<this> %command%". Without a harness session on the current
# display it runs the game unchanged.
H="$(dirname "$0")"
S="$H/session.env"
echo "$(date -Is) DISPLAY=$DISPLAY $*" >> "$H/launch.log"
if [ -f "$S" ]; then
  . "$S"
  if [ "${CS1_HARNESS_DISPLAY:-}" = "$DISPLAY" ]; then
    . "$H/run-audio/env.sh" || exit
    export CS1_HARNESS_PORT
    # Steam's target is Paradox's launcher bootstrap (dowser). A harness run
    # starts the game binary itself, keeping Steam's reaper and runtime, so no
    # launcher window, account prompt or launcher terms appear headless.
    # VirtualGL goes on the game itself, inside Steam's runtime container: an
    # LD_PRELOAD set outside it does not survive pressure-vessel.
    V="$CS1_HARNESS_VGL/usr/lib"
    found=
    for a in "$@"; do
      case "$a" in
        */Cities_Skylines/dowser)
          found=1
          set -- "$@" /bin/sh -c 'export LD_LIBRARY_PATH="$0${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \\
            LD_PRELOAD="$0/libdlfaker.so:$0/libvglfaker.so${LD_PRELOAD:+:$LD_PRELOAD}" VGL_DISPLAY="$1"; \\
            . "$2" || exit; shift 2; exec "$@"' \\
            "$V" "$CS1_HARNESS_EGL" "$H/run-audio/env.sh" "${a%/dowser}/Cities.x64" ;;
        *) set -- "$@" "$a" ;;
      esac
      shift
    done
    if [ "$found" != 1 ]; then
      echo "cs1-harness: unknown Steam launch target; refusing an unwrapped game" >&2
      exit 1
    fi
    echo "$(date -Is) harness exec: $*" >> "$H/launch.log"
    # Keep the game's stdout and stderr: Mono writes a native crash's backtrace
    # there, never to -logFile.
    exec "$@" >> "${CS1_HARNESS_STDOUT:-$H/game-stdout.log}" 2>&1
  fi
fi
exec "$@"
"""


def localconfig(cfg: Config) -> pathlib.Path:
    found = sorted((cfg.steam_root / "userdata").glob("*/config/localconfig.vdf"))
    if len(found) != 1:
        raise SystemExit(f"expected one Steam user's localconfig.vdf, found {found}")
    return found[0]


def set_launch_options(cfg: Config, value: str | None) -> str:
    """Set (or with None, remove) LaunchOptions in the app's block of localconfig.vdf."""
    if backend(cfg).instances():
        raise SystemExit("Steam is running; it rewrites localconfig.vdf on exit. Quit Steam first.")
    path = localconfig(cfg)
    text = path.read_text(encoding="utf-8")
    # The app's settings block (LastPlayed, Playtime, ...), not the CDN-token
    # or license blocks that share its id.
    blocks = [
        m
        for m in re.finditer(r'\n(\t+)"%s"\n\1\{\n(.*?)\n\1\}' % cfg.app_id, text, re.S)
        if '"CDN"' not in m.group(2) and re.search(r'"(LastPlayed|Playtime|LaunchOptions)"', m.group(2))
    ]
    if len(blocks) != 1:
        raise SystemExit(
            f"expected one app {cfg.app_id} settings block in {path}, found {len(blocks)}; "
            "launch the game from Steam once first"
        )
    m = blocks[0]
    indent, body = m.group(1), m.group(2)
    body = re.sub(r'\n?\t+"LaunchOptions"\t\t"[^"]*"', "", body)
    if value is not None:
        body += f'\n{indent}\t"LaunchOptions"\t\t"{value}"'
    backup = path.with_suffix(".vdf.cs1-harness-backup")
    if not backup.exists():
        shutil.copy2(path, backup)
    path.write_text(text[: m.start(2)] + body + text[m.end(2) :], encoding="utf-8")
    return str(path)


def install_virtualgl(cfg: Config):
    if (cfg.virtualgl / "opt/VirtualGL/bin/vglrun").exists():
        return "present"
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(
            ["gh", "release", "download", VGL_VERSION, "-R", "VirtualGL/virtualgl", "-p", VGL_DEB, "-D", tmp],
            check=True,
        )
        deb = pathlib.Path(tmp) / VGL_DEB
        digest = subprocess.run(["sha256sum", str(deb)], check=True, capture_output=True, text=True).stdout.split()[0]
        if digest != VGL_SHA256:
            raise SystemExit(f"{VGL_DEB} sha256 {digest} != pinned {VGL_SHA256}")
        cfg.virtualgl.mkdir(parents=True, exist_ok=True)
        subprocess.run(["dpkg-deb", "-x", str(deb), str(cfg.virtualgl)], check=True)
    # The Freedesktop runtime has no GLU; VirtualGL's tools want it.
    glu = pathlib.Path("/usr/lib/x86_64-linux-gnu/libGLU.so.1")
    if glu.exists():
        shutil.copy2(glu.resolve(), cfg.virtualgl / "usr/lib/libGLU.so.1")
    return "installed"


def setup(cfg: Config) -> dict:
    done = {"virtualgl": install_virtualgl(cfg)}
    (cfg.harness_home / "bin").mkdir(parents=True, exist_ok=True)
    launch = cfg.harness_home / "launch.sh"
    launch.write_text(LAUNCH_SH)
    launch.chmod(0o755)
    # The Flatpak wrapper blocks on a zenity warning about udev input rules at
    # every start; nobody can dismiss it on a headless display.
    zenity = cfg.harness_home / "bin" / "zenity"
    zenity.write_text("#!/bin/sh\nexit 0\n")
    zenity.chmod(0o755)
    done["launch_options"] = set_launch_options(cfg, f"{launch} %command%")
    # A stable command for people and agents: ~/.local/bin/cs1-harness runs this checkout.
    shim = pathlib.Path.home() / ".local/bin/cs1-harness"
    shim.parent.mkdir(parents=True, exist_ok=True)
    tool_dir = pathlib.Path(__file__).resolve().parents[1]
    uv = shutil.which("uv") or str(pathlib.Path.home() / ".local/bin/uv")
    shim.write_text(
        f'#!/bin/sh\n# Installed by `cs1-harness setup` from {tool_dir}\nexec {uv} run --quiet --project {tool_dir} cs1-harness "$@"\n'
    )
    shim.chmod(0o755)
    done["command"] = str(shim)
    done["launch_wrapper"] = str(launch)
    return done


def undo(cfg: Config) -> dict:
    done = {"launch_options": set_launch_options(cfg, None)}
    for path in (cfg.harness_home, cfg.virtualgl, cfg.mod_dir):
        if path.exists():
            shutil.rmtree(path)
            done[str(path)] = "removed"
    return done
