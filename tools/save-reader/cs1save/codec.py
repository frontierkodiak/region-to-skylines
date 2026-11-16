"""The one NetManager/BuildingManager codec, shared with the map writer.

It lives in `tools/map-factory/netcodec.py`, beside the writer that encodes
maps with it; this reader decodes saves with the same classes. The reader
keeps the save-wide tables of shared strings, types and objects by passing
`StreamObjects` for the few references those sections contain.
"""

import importlib.util
import sys
from pathlib import Path

_FACTORY = Path(__file__).resolve().parents[2] / "map-factory"
_SOURCE = _FACTORY / "netcodec.py"
if not _SOURCE.is_file():
    raise ImportError(f"cs1save needs the shared codec at {_SOURCE} (same repository)")


def _load():
    """Load exactly this repository's netcodec, never another on sys.path."""
    loaded = sys.modules.get("netcodec")
    if loaded is not None and Path(loaded.__file__).resolve() == _SOURCE:
        return loaded
    spec = importlib.util.spec_from_file_location("netcodec", _SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(_FACTORY))  # its own imports (template) resolve beside it
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(_FACTORY))
    if Path(module.decode_array.__code__.co_filename).resolve().parent != _FACTORY:
        raise ImportError("netcodec's template module did not come from map-factory")
    return module


netcodec = _load()


class StreamObjects:
    """netcodec's object hook, backed by this reader's Stream and its tables."""

    def __init__(self, stream):
        self.stream = stream

    def object(self, data, offset):
        self.stream.pos = offset
        self.stream.object()
        return self.stream.pos

    def shared_string(self, data, offset):
        self.stream.pos = offset
        value = self.stream.shared_string()
        return value, self.stream.pos


__all__ = ["netcodec", "StreamObjects"]
