"""Stage an additive metadata build without editing an accepted harness file."""

from pathlib import Path
import shutil

import study
from cs1_harness import build
from cs1_harness.config import Config


def main():
    cfg = Config.for_host()
    stage = cfg.build_dir / "rail-metadata-sources"
    stage.mkdir(parents=True, exist_ok=False)
    for path in sorted((study.HARNESS / "mod").glob("*.cs")):
        shutil.copyfile(path, stage / path.name)
    path = stage / "Harness.cs"
    text = path.read_text()
    anchor = "            NetworkOps.Register();"
    if text.count(anchor) != 1:
        raise ValueError("unrecognised exact harness registration")
    path.write_text(
        text.replace(anchor, anchor + "\n            RailMetadata.Register();")
    )
    shutil.copyfile(study.HERE / "RailMetadata.cs", stage / "RailMetadata.cs")
    build.MOD_SOURCES = stage
    receipt = build.build(cfg)
    study.freeze(
        study.HERE / "metadata-build.json",
        {
            "frozen_at": study.now(),
            "generator_sha256": study.sha(Path(__file__)),
            "original_sources": {
                p.name: study.sha(p)
                for p in sorted((study.HARNESS / "mod").glob("*.cs"))
            },
            "generated_sources": receipt["sources"],
            "build_receipt": receipt,
            "registration": "one additive RailMetadata.Register call in staged Harness.cs only",
        },
    )
    print(receipt["dll_sha256"])


if __name__ == "__main__":
    main()
