"""Load the accepted v4 API unchanged; no scorer or game operation is executed."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
V4 = HERE.parent / "outside-freeze-preflight-v4"
sys.path.insert(0, str(V4))
import spec as spec  # noqa: E402
import pipeline as pipeline  # noqa: E402
import consumer as consumer  # noqa: E402
import lifecycle as lifecycle  # noqa: E402
import build_v2 as build_v2  # noqa: E402

ROOT = spec.ROOT
PIN = "3afadcceb5d3378e96aa3cb3cb844d4de281a5f6"
