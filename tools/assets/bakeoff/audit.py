"""Check that every archived preview/map and Clef score binds to the actual delivered bytes."""

import argparse
import hashlib
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    args = parser.parse_args()
    checked = {"files": 0, "judged_views": 0, "assets": 0}
    for dirname in ("outputs", "outputs-clean"):
        root = args.experiment / dirname
        for receipt in root.glob("*/receipt.json"):
            data = json.loads(receipt.read_text())
            for name, digest in data["files"].items():
                assert name != "receipt.json", (receipt, "self-referential receipt")
                actual = hashlib.sha256(
                    (receipt.parent / name).read_bytes()
                ).hexdigest()
                assert actual == digest, (receipt, name, "artifact hash mismatch")
                checked["files"] += 1
            checked["assets"] += 1
        scores = json.loads((root / "clef.json").read_text())
        for key, score in scores.items():
            method, target, view = key.split("-")
            path = root / (method + "-" + target) / (view + ".png")
            assert (
                hashlib.sha256(path.read_bytes()).hexdigest() == score["image_sha256"]
            ), (key, "stale score")
            suffix = ".webp" if target == "apartment" else ".jpg"
            photo = args.experiment / "references" / (target + suffix)
            assert (
                hashlib.sha256(photo.read_bytes()).hexdigest()
                == score["reference_sha256"]
            ), (key, "changed reference")
            assert score["response"]["model_id"] == score["model_id"], (
                key,
                "changed model",
            )
            checked["judged_views"] += 1
    assert checked["assets"] == 12 and checked["judged_views"] == 24, checked
    (args.experiment / "artifact-audit.json").write_text(json.dumps(checked, indent=2))
    print("PASS", checked)


if __name__ == "__main__":
    main()
