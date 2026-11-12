"""Advisory, method-blind Clef-Flash scores with exact view/source/model provenance."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.request


DESCRIPTIONS = {
    "bungalow": "Asheville 1920s Craftsman bungalow: broad porch, pale horizontal siding, pitched roof, dormer and chimney",
    "storefront": "Lexington Avenue Asheville brick storefront: three stories, flat roof/parapet, tall sash windows and glazed shopfront",
    "apartment": "Hillcrest Asheville brick townhome/apartment row: long two-story red-brick mass, pitched cross-gable roof, cream panels and porch entries",
}


def request(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    for attempt in range(3):
        try:
            req = urllib.request.Request(
                url, data=data, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("references", type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:9120/v1/systemone")
    parser.add_argument("--methods", nargs="+", default=["A", "B", "C"])
    args = parser.parse_args()
    identity = request(args.endpoint)
    (args.output / "clef-identity.json").write_text(json.dumps(identity, indent=2))
    results_path = args.output / "clef.json"
    records = json.loads(results_path.read_text()) if results_path.exists() else {}
    for name, description in DESCRIPTIONS.items():
        suffix = ".webp" if name == "apartment" else ".jpg"
        reference = (args.references / (name + suffix)).read_bytes()
        for method in args.methods:
            for view in ("close", "gameplay"):
                image = (
                    args.output / (method + "-" + name) / (view + ".png")
                ).read_bytes()
                payload = {
                    "model": "clef-flash",
                    "state": (
                        f"The first image is a game-asset preview, the second a real reference. "
                        f"Desired building: {description}. Judge architectural form and materials, "
                        "not the photograph versus render medium. Do not infer a generation method."
                    ),
                    "questions": {
                        "reads_as_target": {
                            "type": "noul",
                            "criteria": {
                                "true": "The first image is a recognizable, plausible example of the described building type.",
                                "false": "Wrong type, malformed building, or unrecognizable architectural form.",
                            },
                        },
                        "reference_fidelity": {
                            "type": "score",
                            "criteria": [
                                "Not a coherent building",
                                "Building but wrong architectural type",
                                "Recognizable type, major form or material errors",
                                "Plausible local type, some reference details differ",
                                "Close architectural match to the photo in massing, roof, openings and materials",
                            ],
                        },
                    },
                    "images": [
                        "data:image/png;base64," + base64.b64encode(image).decode(),
                        "data:image/"
                        + ("webp" if suffix == ".webp" else "jpeg")
                        + ";base64,"
                        + base64.b64encode(reference).decode(),
                    ],
                }
                digest = hashlib.sha256(
                    json.dumps(payload, sort_keys=True).encode()
                ).hexdigest()
                key = method + "-" + name + "-" + view
                if records.get(key, {}).get("request_sha256") == digest and (
                    records[key]["model_id"] == identity["model_id"]
                ):
                    continue
                start = time.monotonic()
                response = request(args.endpoint, payload)
                records[key] = {
                    "request_sha256": digest,
                    "image_sha256": hashlib.sha256(image).hexdigest(),
                    "reference_sha256": hashlib.sha256(reference).hexdigest(),
                    "model_id": identity["model_id"],
                    "questions": payload["questions"],
                    "state": payload["state"],
                    "response": response,
                    "seconds": time.monotonic() - start,
                    "advisory_only": True,
                }
                results_path.write_text(json.dumps(records, indent=2))
                print(key, json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
