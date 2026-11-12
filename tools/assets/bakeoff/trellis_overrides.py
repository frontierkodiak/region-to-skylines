"""Bind upstream's unpinned git dependencies to the adjacent verified clones."""

from pathlib import Path
import tomllib

root = Path.cwd()
path = root / "pyproject.toml"
text = path.read_text()
config = tomllib.loads(text)
if "override-dependencies" not in config.get("tool", {}).get("uv", {}):
    text += "\n[tool.uv]\noverride-dependencies = [\n"
    for name, folder in (("cumesh", "CuMesh"), ("flex-gemm", "FlexGEMM")):
        text += f'  "{name} @ {(root.parent / folder).resolve().as_uri()}",\n'
    text += "]\n"
    path.write_text(text)
