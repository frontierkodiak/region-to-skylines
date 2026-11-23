"""Version 1 public-harness wire boundary. No game imports or implicit truthiness."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import json
import math


class ProtocolError(ValueError):
    """Missing, ambiguous or unsupported protocol evidence; caller must abstain."""


class Label(StrEnum):
    UNKNOWN = "unknown"
    SUCCESS = "success"
    NO_PATH = "no_path"


@dataclass(frozen=True)
class Position:
    segment: int
    lane: int
    offset: int


@dataclass(frozen=True)
class Request:
    mode: str
    start: Position
    end: Position
    max_length: float
    build_index: int
    seed: int = 857

    def __post_init__(self):
        if self.mode not in MODES or self.max_length not in (100000, 200000, 1000000):
            raise ProtocolError("unsupported request mode/budget")
        number(self.max_length)
        integer(self.build_index, 0, 2**32 - 1)
        if integer(self.seed, 0, 2**32 - 1) != 857:
            raise ProtocolError("study seed differs")
        for endpoint in (self.start, self.end):
            if not isinstance(endpoint, Position):
                raise ProtocolError("typed endpoints required")
            integer(endpoint.segment, 1, 65535)
            integer(endpoint.lane, 0, 255)
            integer(endpoint.offset, 0, 255)


@dataclass(frozen=True)
class NativeResult:
    handle: int
    complete: bool
    success: bool
    released: bool
    positions: tuple[Position, ...]
    length: float


@dataclass(frozen=True)
class Decision:
    transport_success: bool | None
    native: NativeResult | None
    literal_label: Label
    reason: str
    qualification: str = "unknown"


def exact(value: object, keys: set[str], where: str) -> dict:
    if type(value) is not dict or set(value) != keys:
        raise ProtocolError(f"{where}: expected exactly {sorted(keys)}")
    return value


def strict_bool(value: object) -> bool:
    if type(value) is not bool:
        raise ProtocolError("RPC boolean must be JSON true/false, not 0/1 or string")
    return value


def meta_bool(value: object) -> bool:
    # CityOps Stats calls MetaBool.ToString(); JSON bool is an explicit alternate
    # representation, not a license to accept numeric or case-folded values.
    if type(value) is bool:
        return value
    if type(value) is str and value in ("True", "False"):
        return value == "True"
    raise ProtocolError("unsupported MetaBool (require True/False or JSON boolean)")


def integer(value: object, low: int, high: int) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ProtocolError(f"integer outside [{low}, {high}]")
    return value


def number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ProtocolError("expected finite nonnegative number")
    return float(value)


def position(value: object) -> Position:
    if type(value) is not list or len(value) != 3:
        raise ProtocolError("position must be [segment,lane,offset]")
    return Position(
        integer(value[0], 1, 65535),
        integer(value[1], 0, 255),
        integer(value[2], 0, 255),
    )


def decode(data: bytes) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProtocolError(f"duplicate field {key}")
            result[key] = value
        return result

    try:
        value = json.loads(
            data,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ProtocolError("nonfinite JSON")
            ),
        )
    except (ValueError, UnicodeError) as error:
        raise ProtocolError(str(error)) from error
    if type(value) is not dict:
        raise ProtocolError("expected JSON object")
    return value


def envelope(value: object, body_keys: set[str]) -> dict:
    if type(value) is not dict or "ok" not in value:
        raise ProtocolError("missing transport ok")
    if strict_bool(value["ok"]) is False:
        exact(value, {"ok", "error", "exception"}, "RPC failure")
        if type(value["error"]) is not str or type(value["exception"]) is not str:
            raise ProtocolError("malformed transport failure")
        raise ProtocolError(f"transport failed: {value['exception']}: {value['error']}")
    return exact(value, body_keys | {"ok"}, "RPC success")


EFFECTIVE = {
    "id",
    "mode",
    "max_length",
    "build_index",
    "seed",
    "from",
    "to",
    "vehicle",
    "category",
    "lane_types",
}
RESULT = {"id", "flags", "complete", "success", "length", "positions", "released"}
MODES = {
    "road": ("car", "Car", "PassengerCar", frozenset({"Vehicle"})),
    "ship": (
        "ship",
        "Ship",
        "All",
        frozenset({"Vehicle", "TransportVehicle", "CargoVehicle"}),
    ),
    "air": (
        "plane",
        "Plane",
        "All",
        frozenset({"Vehicle", "TransportVehicle", "CargoVehicle"}),
    ),
}


def effective(value: object, request: Request) -> int:
    row = envelope(value, EFFECTIVE)
    if request.mode not in MODES:
        raise ProtocolError("unsupported study mode")
    mode, vehicle, category, lanes = MODES[request.mode]
    lane_string = row["lane_types"]
    if type(lane_string) is not str:
        raise ProtocolError("invalid lane mask")
    tokens = lane_string.split(", ")
    if len(tokens) != len(set(tokens)) or frozenset(tokens) != lanes:
        raise ProtocolError("lane mask differs")
    if (row["mode"], row["vehicle"], row["category"]) != (mode, vehicle, category):
        raise ProtocolError("mode/vehicle/category differs")
    if (position(row["from"]), position(row["to"])) != (request.start, request.end):
        raise ProtocolError("effective endpoints differ")
    if (
        integer(row["build_index"], 0, 2**32 - 1) != request.build_index
        or integer(row["seed"], 0, 2**32 - 1) != request.seed
        or number(row["max_length"]) != request.max_length
    ):
        raise ProtocolError("build index/seed/maxLength differs")
    return integer(row["id"], 1, 2**32 - 1)


def native_result(value: object, handle: int) -> NativeResult:
    row = envelope(value, RESULT)
    if integer(row["id"], 1, 2**32 - 1) != handle:
        raise ProtocolError("result handle differs")
    flags = integer(row["flags"], 0, 255)
    # Bits 4/8 are the terminal states in the owned public Result wrapper.
    # Other bits have no established meaning here; fail closed rather than infer.
    if flags not in (0, 1, 2, 3, 4, 8):
        raise ProtocolError("unsupported/ambiguous path flags")
    complete, success, released = (
        strict_bool(row[k]) for k in ("complete", "success", "released")
    )
    if (
        complete != bool(flags & 12)
        or success != bool(flags & 4)
        or released != complete
    ):
        raise ProtocolError("flags and native booleans disagree")
    if type(row["positions"]) is not list:
        raise ProtocolError("positions must be a list")
    positions = tuple(position(p) for p in row["positions"])
    if (not success and positions) or (success and not positions):
        raise ProtocolError("positions disagree with native success")
    return NativeResult(
        handle, complete, success, released, positions, number(row["length"])
    )


def decide(start: object, result: object, request: Request) -> Decision:
    transport = None
    try:
        # Preserve transport state separately even when body validation fails.
        for row in (start, result):
            if type(row) is not dict or type(row.get("ok")) is not bool:
                raise ProtocolError("missing/invalid transport status")
            if row["ok"] is False:
                transport = False
                envelope(row, set())
        transport = True
        handle = effective(start, request)
        native = native_result(result, handle)
        if not native.complete or not native.released:
            return Decision(True, native, Label.UNKNOWN, "incomplete or unreleased")
        if not native.success:
            return Decision(
                True, native, Label.NO_PATH, "this exact literal request failed"
            )
        if (native.positions[0], native.positions[-1]) != (request.start, request.end):
            return Decision(
                True, native, Label.UNKNOWN, "returned literal endpoints differ"
            )
        return Decision(
            True, native, Label.SUCCESS, "literal endpoints match; not qualification"
        )
    except ProtocolError as error:
        return Decision(transport, None, Label.UNKNOWN, str(error))


def entry(context: object) -> None:
    row = exact(
        context,
        {"frame", "invert_traffic", "mods_enabled", "no_workshop", "update_mode"},
        "entry",
    )
    integer(row["frame"], 0, 2**32 - 1)
    if (
        meta_bool(row["invert_traffic"]) is not False
        or strict_bool(row["mods_enabled"]) is not True
        or strict_bool(row["no_workshop"]) is not True
        or row["update_mode"] != "NewGameFromMap"
    ):
        raise ProtocolError("entry differs from declared native context")
