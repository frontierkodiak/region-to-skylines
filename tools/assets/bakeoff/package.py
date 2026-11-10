"""Package nine uniquely named A/B1/C import inputs; keep the raw-photo B0 control separate."""

import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    sources = Path(__file__).parent
    manifest = {
        "stage": "pre-bridge authoring inputs, NOT tested CRP assets",
        "assets": [],
    }
    with zipfile.ZipFile(
        args.archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6
    ) as archive:
        for method in ("A", "B", "C"):
            root = args.experiment / ("outputs-clean" if method == "B" else "outputs")
            checks = json.loads((root / "verification.json").read_text())
            for target in ("bungalow", "storefront", "apartment"):
                name = method + "-" + target
                assert (
                    sum(
                        c["passed"]
                        for c in checks
                        if c["asset"] in (name, name + "_lod")
                    )
                    == 2
                ), name
                folder = root / name
                files = []
                for path in sorted(folder.iterdir()):
                    if (
                        path.suffix not in (".fbx", ".png")
                        and path.name != "receipt.json"
                    ):
                        continue
                    if path.name in (
                        "close.png",
                        "gameplay.png",
                        "lod.png",
                        "night.png",
                    ):
                        continue
                    destination = name + "/" + path.name
                    archive.write(path, destination)
                    files.append(
                        {
                            "path": destination,
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        }
                    )
                assert len(files) == 13, (
                    name,
                    "expected two FBXs, ten maps and a receipt",
                    len(files),
                )
                manifest["assets"].append(
                    {
                        "name": name,
                        "method": "B1 clean concept" if method == "B" else method,
                        "files": files,
                    }
                )
        archive.writestr("manifest.json", json.dumps(manifest, indent=2))
        archive.writestr(
            "IMPORT.md",
            """# Asheville A/B1/C authoring inputs

Nine main meshes, nine custom LODs, and all five maps at each level.
Names are unique across the pack; do not mix in the separate B0 photo control.
Each folder holds one asset. Preserve suffix names when copying into CS1's
Addons/Import directory or passing files to the PL-880 authoring bridge.
Lots (8-m cells): bungalow 2x3, storefront 2x3, apartment 4x3.

These are FBX authoring inputs, not CRP assets or a game-tested pack. Models
were judged in Blender only. B's zero illumination/color masks deliberately
disable semantic night windows/variation, rather than inventing their locations.
Metre sizes are study assumptions and bounded inferred geometry, not surveys.
Blender preview scenes are reproduced by the scripts, not included here.

Code: https://github.com/frontierkodiak/region-to-skylines (PL-881-assets branch)
""",
        )
        for name in ("README.md", "PROMPTS.md"):
            archive.write(sources / name, "study/" + name)
    with zipfile.ZipFile(args.archive) as archive:
        assert archive.testzip() is None
        for asset in manifest["assets"]:
            for item in asset["files"]:
                assert (
                    hashlib.sha256(archive.read(item["path"])).hexdigest()
                    == item["sha256"]
                )
    print(
        "PASS: 9 import candidates, 117 hashed input files;",
        args.archive.stat().st_size,
        "archive bytes",
    )


if __name__ == "__main__":
    main()
