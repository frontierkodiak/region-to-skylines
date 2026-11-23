"""Read-only content-addressed retained bytes, not a caller-supplied hash oracle."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from protocol import ProtocolError, decode


def sha256(value: object, where: str) -> str:
    if type(value) is not str or re.fullmatch("[0-9a-f]{64}", value) is None:
        raise ProtocolError(f"{where}: require nonempty lowercase SHA-256")
    return value


@dataclass(frozen=True)
class ArtifactStore:
    """Files are named by SHA-256 under root; no game/runtime files are opened."""

    root: Path

    def read(self, expected: object, where: str) -> bytes:
        key = sha256(expected, where)
        path = self.root / key
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ProtocolError(f"{where}: missing retained artifact {key}") from error
        if not data or hashlib.sha256(data).hexdigest() != key:
            raise ProtocolError(f"{where}: empty or corrupt retained artifact {key}")
        return data

    def json(self, expected: object, where: str) -> dict:
        try:
            return decode(self.read(expected, where))
        except ProtocolError as error:
            raise ProtocolError(f"{where}: {error}") from error
