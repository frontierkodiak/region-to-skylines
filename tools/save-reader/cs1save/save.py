"""Walk a CS1 save (or map) Data asset manager by manager.

LoadingManager.SaveSimulationData writes two DataSerializer streams back to
back: SimulationMetaData, then SimulationManager.Data. The second lists every
manager's IDataContainer type up front, then serializes them in that order.
Each manager's block opens with its name as a new shared string and closes with
a reference to that string (LoadingProfiler.BeginSerialize/EndSerialize).

A manager this reader decodes must end exactly on its closing tag. A manager it
does not decode is passed over by locating the next manager's opening tag, which
is a new shared string and so has one exact byte form.
"""

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from . import districts, managers
from .package import read_metadata, read_package
from .stream import FormatError, ObjectRef, Stream

PARSERS = {**managers.PARSERS, **districts.PARSERS}

SUPPORTED_VERSION = 121034  # BuildConfig.SAVE_DATA_FORMAT_VERSION in 1.21.1-f9

# Vanilla managers whose blocks call WriteSharedString (messages, custom names).
WRITES_SHARED_STRINGS = {"BuildingManager", "TransportManager", "MessageManager"}


@dataclass
class Save:
    path: str
    sha256: str
    package: dict
    assets: list
    metadata: dict
    simulation_meta: dict
    simulation: dict
    manager_order: list
    blocks: dict = field(default_factory=dict)  # name -> (start, end) in Data
    data: dict = field(default_factory=dict)  # name -> decoded manager
    skipped: list = field(default_factory=list)
    mod_data: dict = field(default_factory=dict)  # key -> bytes


def begin_tag(name):
    """Bytes of a new shared string `name`, as WriteSharedString emits it."""
    out = bytearray([254, 0x80, (len(name) >> 8) & 0xFF, len(name) & 0xFF])
    previous = 0x80
    for ch in name.encode("latin-1"):
        out.append((ch - previous) & 0xFF)
        previous = ch
    return bytes(out)


def read_header(s):
    high, low = s.u16(), s.u16()
    if low <= 322 and high <= 6:
        return low
    if high & 0x8000:
        s.u32()
        return ((high << 16) | low) & 0x7FFFFFFF
    return (high << 16) | low


def read_simulation_metadata(s):
    s.version = read_header(s)
    if s.object() != "SimulationMetaData, Assembly-CSharp, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null":
        raise FormatError("expected SimulationMetaData")
    meta = {
        "version": s.version,
        "game_instance": s.unique_string(),
        "environment": s.unique_string(),
        "scenario_asset": s.unique_string(),
        "scenario_name": s.unique_string(),
        "scenario_won": s.bool(),
        "scenario_failed": s.bool(),
        "starting_ticks": s.i64(),
        "map_name": s.unique_string(),
    }
    meta["mod_overrides"] = {s.unique_string(): s.bool() for _ in range(s.i32())}
    meta.update(
        invert_traffic=s.u8(),
        disable_achievements=s.u8(),
        current_ticks=s.i64(),
        current_day_hour=s.f32(),
        new_map_app_version=s.u32(),
        new_game_app_version=s.u32(),
        app_version=s.u32(),
        format_version=s.u32(),
    )
    return meta


def read_save(path, only=None):
    """Decode a .crp save or map. `only` limits decoding to a set of manager
    names (every other manager is passed over by its tags)."""
    path = Path(path)
    raw = path.read_bytes()
    header, assets = read_package(raw)
    data_asset = next((a for a in assets if a["kind"] == 52), None)
    if data_asset is None:
        raise FormatError("package has no Data asset")
    metadata = {}
    for a in assets:
        if a["kind"] in (100, 101):
            typename, fields = read_metadata(raw[a["offset"] : a["offset"] + a["size"]])
            metadata = {"type": typename, **fields}
    data = raw[data_asset["offset"] : data_asset["offset"] + data_asset["size"]]

    s = Stream(data)
    sim_meta = read_simulation_metadata(s)
    if sim_meta["version"] > SUPPORTED_VERSION:
        raise FormatError(f"save format {sim_meta['version']} is newer than {SUPPORTED_VERSION}")

    s = Stream(data, s.pos)
    s.version = read_header(s)
    if s.version != SUPPORTED_VERSION:
        raise FormatError(f"this reader implements format {SUPPORTED_VERSION} only, not {s.version}")
    root = s.object()
    if not str(root).startswith("SimulationManager+Data,"):
        raise FormatError("expected SimulationManager+Data")
    if s.shared_string() != "SimulationManager":
        raise FormatError("missing SimulationManager tag")
    simulation = {
        "tick_index": s.u32(),
        "frame_index": s.u32(),
        "build_index": s.u32(),
        "random_seed": s.u64(),
        "day_time_offset_frames": s.u32(),
        "build_index_history": [s.u32() for _ in range(32)],
    }
    order = []
    for entry in s.object_array():
        if entry is None or isinstance(entry, ObjectRef):
            raise FormatError("unexpected manager entry")
        order.append(entry.split(",")[0].removesuffix("+Data"))
    mod_data = {}
    for _ in range(s.u32()):
        key = s.unique_string()
        mod_data[key] = s.byte_array()
    if s.shared_string() != "SimulationManager":
        raise FormatError("SimulationManager block did not end on its tag")

    save = Save(
        path=str(path),
        sha256=hashlib.sha256(raw).hexdigest(),
        package=header,
        assets=[{k: v for k, v in a.items()} for a in assets],
        metadata=metadata,
        simulation_meta=sim_meta,
        simulation=simulation,
        manager_order=order,
        mod_data=mod_data,
    )

    for index, name in enumerate(order):
        start = s.pos
        tag = begin_tag(name)
        if data[start : start + len(tag)] != tag:
            raise FormatError(f"{name} block does not start with its tag at {start}")
        s.pos += len(tag)
        # After a skipped block that defined shared strings, table indices are
        # unknown; the closing reference then tells us this name's true index.
        name_index = len(s.strings) if s.strings_exact else None
        s.strings.append(name)
        parser = PARSERS.get(name)
        if parser is not None and (only is None or name in only):
            try:
                save.data[name] = parser(s)
            except FormatError as error:
                raise FormatError(f"{name}: {error}") from error
            except (IndexError, ValueError, KeyError) as error:
                raise FormatError(f"{name}: {error!r} at {s.pos}") from error
            end = s.pos
            _closing(s, data, end, name, name_index)
            s.pos = end + 2
            save.blocks[name] = (start, s.pos)
            continue
        save.skipped.append(name)
        if index + 1 == len(order):
            save.blocks[name] = (start, None)
            break
        found = data.find(begin_tag(order[index + 1]), s.pos)
        if found < 0:
            raise FormatError(f"could not find the block after {name}")
        _closing(s, data, found - 2, name, name_index)
        if name in WRITES_SHARED_STRINGS or name not in managers.KNOWN:
            s.strings_exact = False
        s.pos = found
        save.blocks[name] = (start, found)
    return save


def _closing(s, data, at, name, name_index):
    """Check the two-byte shared-string reference that closes a block."""
    if at < 0 or data[at] >= 254:
        raise FormatError(f"{name} block does not end on a tag reference at {at}")
    index = int.from_bytes(data[at : at + 2], "big")
    if name_index is not None and index != name_index:
        raise FormatError(f"{name} closing reference {index} is not its tag {name_index} (at {at})")
    if name_index is None:
        # Re-anchor the table: pad unknown strings so the name sits at its index.
        s.strings.pop()
        while len(s.strings) < index:
            s.strings.append(None)
        s.strings[index : index + 1] = [name]
