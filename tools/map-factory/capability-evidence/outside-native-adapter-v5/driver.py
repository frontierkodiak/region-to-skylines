"""Harmless offline driver: writes a retained observation handoff, then exits."""

import json
from pathlib import Path
import sys

if __name__ == "__main__":
    payload = json.loads(sys.stdin.readline())
    Path(sys.argv[1]).write_text(json.dumps(payload, sort_keys=True))
