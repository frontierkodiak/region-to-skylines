"""Check that every archived preview/map and Clef score binds to the actual delivered bytes."""

import argparse
import base64
import hashlib
import json
import zipfile
from pathlib import Path


def native_audit(root, experiment):
    def digest(data):
        return hashlib.sha256(data).hexdigest()

    manifest = json.loads((root / "manifest.json").read_text())
    identity = json.loads((root / "clef-identity.json").read_text())
    scores = json.loads((root / "clef.json").read_text())
    references = json.loads(
        (Path(__file__).parent / "results/references.json").read_text()
    )
    images = 0
    for asset in manifest["assets"]:
        name = asset["name"]
        target = name.split("-", 1)[1]
        suffix = ".webp" if target == "apartment" else ".jpg"
        photo = (experiment / "references" / (target + suffix)).read_bytes()
        assert digest(photo) == references[target]["photo_sha256"], name
        for view, image in asset["images"].items():
            raw = (root / image["path"]).read_bytes()
            assert digest(raw) == image["sha256"], (name, view)
            images += 1
            if view not in ("close", "gameplay"):
                continue
            score = scores[name + "-" + view]
            assert score["image_sha256"] == image["sha256"], (name, view)
            assert score["reference_sha256"] == digest(photo), name
            assert score["response"]["images_sha256"] == [digest(raw), digest(photo)], (
                name
            )
            assert (
                score["model_id"]
                == score["response"]["model_id"]
                == identity["model_id"]
            ), name
            payload = {
                "model": "clef-flash",
                "state": score["state"],
                "questions": score["questions"],
                "images": [
                    "data:image/png;base64," + base64.b64encode(raw).decode(),
                    "data:image/"
                    + ("webp" if suffix == ".webp" else "jpeg")
                    + ";base64,"
                    + base64.b64encode(photo).decode(),
                ],
            }
            assert (
                digest(json.dumps(payload, sort_keys=True).encode())
                == score["request_sha256"]
            ), name
    packages = json.loads((root / "native-packages.json").read_text())
    crps = 0
    for filename, receipt in packages.items():
        archive = root / filename
        assert digest(archive.read_bytes()) == receipt["sha256"], filename
        with zipfile.ZipFile(archive) as bundle:
            assert {n for n in bundle.namelist() if n.endswith(".crp")} == set(
                receipt["crps"]
            ), filename
            for name, expected in receipt["crps"].items():
                actual = digest(bundle.read(name))
                assert actual == expected, name
                assert actual == next(
                    a["crp_sha256"]
                    for a in manifest["assets"]
                    if a["name"] + ".crp" == name
                ), name
                crps += 1
    assert (len(manifest["assets"]), images, len(scores), crps) == (9, 72, 18, 9)
    return {
        "assets": 9,
        "native_frames": images,
        "judged_views": 18,
        "packaged_crps": crps,
        "auditor_sha256": digest(Path(__file__).read_bytes()),
        "manifest_sha256": digest((root / "manifest.json").read_bytes()),
        "scores_sha256": digest((root / "clef.json").read_bytes()),
        "identity_sha256": digest((root / "clef-identity.json").read_bytes()),
        "packages_manifest_sha256": digest(
            (root / "native-packages.json").read_bytes()
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment", type=Path)
    parser.add_argument(
        "--native",
        type=Path,
        help="Audit the native gallery, exact judge requests and delivered CRP ZIPs too",
    )
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
    if args.native:
        checked["native"] = native_audit(args.native, args.experiment)
    (args.experiment / "artifact-audit.json").write_text(json.dumps(checked, indent=2))
    print("PASS", checked)


if __name__ == "__main__":
    main()
