"""Read-only imports of the exact accepted adapter and measurement definitions."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V5 = HERE.parent / "outside-native-adapter-v5"
sys.path.insert(0, str(V5))
import api as api  # noqa: E402
import adapter as adapter  # noqa: E402
import adapter_spec as adapter_spec  # noqa: E402
import fresh_build as fresh_build  # noqa: E402
import protocol as protocol  # noqa: E402
import collect_v2 as collect_v2  # noqa: E402
import stock_v2 as stock_v2  # noqa: E402
from api import (  # noqa: E402
    spec as spec,
    consumer as consumer,
    pipeline as pipeline,
    lifecycle as lifecycle,
)  # noqa: E402
