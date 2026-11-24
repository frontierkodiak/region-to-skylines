"""GPU selection and checks by PCI bus ID.

VirtualGL names EGL devices egl0, egl1, ... in the driver's enumeration order,
which isn't the PCI order nvidia-smi uses. The harness probes each EGL device's
GLX renderer on the harness display and matches it to the GPU at the configured
bus ID. After launch it checks that the game process sits on that GPU.
"""

from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET

from .client import HarnessError


def norm_bus(bus: str) -> str:
    """'0000:05:00.0', '00000000:05:00.0' and '05:00.0' all become '05:00.0'."""
    return bus.lower().split(":", bus.count(":") - 1)[-1]


def gpus() -> list[dict]:
    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=index,pci.bus_id,name,memory.used,memory.total", "--format=csv,noheader,nounits"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    rows = []
    for line in out.strip().splitlines():
        index, bus, name, used, total = [x.strip() for x in line.split(",")]
        rows.append(
            {"index": int(index), "bus": norm_bus(bus), "name": name, "mem_used": int(used), "mem_total": int(total)}
        )
    return rows


def gpu_at(bus: str) -> dict:
    for g in gpus():
        if g["bus"] == norm_bus(bus):
            return g
    raise HarnessError(f"no NVIDIA GPU at PCI bus {bus}")


def resolve_egl(bus: str, run_glxinfo) -> tuple[str, str]:
    """Find the VirtualGL EGL device for the GPU at `bus`. run_glxinfo(dev) returns glxinfo -B output."""
    target = gpu_at(bus)
    same_name = [g for g in gpus() if g["name"] == target["name"]]
    if len(same_name) > 1:
        raise HarnessError(f"{len(same_name)} GPUs are named {target['name']}; renderer names can't tell them apart")
    seen = {}
    for i in range(8):
        dev = f"egl{i}"
        out = run_glxinfo(dev)
        m = re.search(r"OpenGL renderer string: (.+?)(/PCIe.*)?$", out, re.M)
        if not m:
            break
        seen[dev] = m.group(1).strip()
        if seen[dev] == target["name"]:
            return dev, target["name"]
    raise HarnessError(f"no EGL device renders on {target['name']} at {bus}; saw {seen}")


def processes() -> list[dict]:
    """Every process on every GPU, graphics included (nvidia-smi -q -x)."""
    xml = subprocess.run(["nvidia-smi", "-q", "-x"], check=True, capture_output=True, text=True).stdout
    rows = []
    for g in ET.fromstring(xml).iter("gpu"):
        bus = norm_bus(g.get("id", ""))
        for p in g.iter("process_info"):
            mem = p.findtext("used_memory") or "0 MiB"
            rows.append(
                {
                    "bus": bus,
                    "pid": int(p.findtext("pid") or 0),
                    "type": p.findtext("type"),
                    "name": p.findtext("process_name") or "",
                    "mib": int(mem.split()[0]) if mem.split()[0].isdigit() else 0,
                }
            )
    return rows


def game_placement(name: str = "Cities.x64") -> list[dict]:
    return [p for p in processes() if p["name"].endswith(name)]
