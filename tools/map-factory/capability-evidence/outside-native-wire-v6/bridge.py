"""Read-only imports of the exact accepted adapter and measurement definitions."""

from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V5 = HERE.parent / "outside-native-adapter-v5"
sys.path.insert(0, str(V5))
