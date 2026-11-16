"""The CRP package container (format 12) and its typed metadata assets.

Package numbers are little-endian and strings are .NET 7-bit length-prefixed
UTF-8, unlike the big-endian DataSerializer stream inside the Data asset.
"""

import hashlib
import struct

from .stream import FormatError

# ColossalFramework.Packaging.Package.AssetType / UserAssetType values seen in CS1.
ASSET_KINDS = {
    1: "Object",
    2: "Material",
    3: "Texture",
    4: "StaticMesh",
    50: "Text",
    51: "Assembly",
    52: "Data",
    53: "Package",
    54: "Locale",
    100: "MapMetaData",
    101: "SaveGameMetaData",
    102: "SystemMapMetaData",
}


class LittleReader:
    def __init__(self, data, pos=0):
        self.data = data
        self.pos = pos

    def take(self, count):
        end = self.pos + count
        if count < 0 or end > len(self.data):
            raise FormatError("package read outside input")
        value = self.data[self.pos : end]
        self.pos = end
        return value

    def number(self, fmt):
        return struct.unpack("<" + fmt, self.take(struct.calcsize("<" + fmt)))[0]

    def string(self):
        size = 0
        for shift in range(0, 35, 7):
            byte = self.number("B")
            size |= (byte & 127) << shift
            if byte < 128:
                return self.take(size).decode("utf8")
        raise FormatError("invalid string length")


def read_package(data, verify=True):
    """Return (header, assets); each asset is a dict with name, checksum, kind,
    offset and size. Payload checksums are MD5 of the bytes, as the game writes."""
    r = LittleReader(data)
    if r.take(4) != b"CRAP":
        raise FormatError("not a CRP package")
    version = r.number("H")
    if version != 12:
        raise FormatError(f"unsupported CRP format {version}")
    header = {"format": version, "name": r.string(), "author": r.string()}
    header["version"] = r.number("I")
    header["main"] = r.string()
    count, start = r.number("i"), r.number("q")
    if not 0 < count <= 100000:
        raise FormatError("unexpected asset count")
    assets = []
    for _ in range(count):
        name, checksum, kind = r.string(), r.string(), r.number("i")
        offset, size = r.number("q"), r.number("q")
        if offset < 0 or size < 0 or start + offset + size > len(data):
            raise FormatError("asset range outside package")
        if verify and hashlib.md5(data[start + offset : start + offset + size]).hexdigest() != checksum:
            raise FormatError(f"asset checksum mismatch: {name}")
        assets.append(
            {
                "name": name,
                "checksum": checksum,
                "kind": kind,
                "kind_name": ASSET_KINDS.get(kind, str(kind)),
                "offset": start + offset,
                "size": size,
            }
        )
    if r.pos != start:
        raise FormatError("package directory length mismatch")
    return header, assets


def _metadata_value(r, typename):
    if typename.endswith("[]"):
        count = r.number("i")
        if not 0 <= count <= 100000:
            raise FormatError("invalid metadata array length")
        return [_metadata_value(r, typename[:-2]) for _ in range(count)]
    if typename in ("System.String", "ColossalFramework.Packaging.Package+Asset"):
        return r.string()
    if typename == "System.DateTime":
        return r.string()
    if typename == "ModInfo":
        return {"name": r.string(), "id": r.number("Q")}
    formats = {
        "System.Boolean": "?",
        "System.Byte": "B",
        "System.Int32": "i",
        "System.UInt32": "I",
        "System.Int64": "q",
        "System.UInt64": "Q",
        "System.Single": "f",
        "System.Double": "d",
    }
    if typename not in formats:
        raise FormatError(f"unsupported metadata field type {typename}")
    return r.number(formats[typename])


def read_metadata(payload):
    """Decode a reflection-serialized metadata object (MapMetaData, SaveGameMetaData)."""
    r = LittleReader(payload)
    if r.number("B") != 0:
        raise FormatError("expected a non-null metadata object")
    typename = r.string()
    r.string()  # object name
    count = r.number("i")
    fields = {}
    for _ in range(count):
        if r.number("B"):
            continue  # null field: the stream carries no name
        field_type, name = r.string().split(",")[0], r.string()
        fields[name] = _metadata_value(r, field_type)
    if r.pos != len(payload):
        raise FormatError("metadata not completely consumed")
    return typename.split(",")[0], fields
