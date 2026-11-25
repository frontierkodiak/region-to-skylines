"""One foreground Gemini vision request, with image hashes and provider usage."""

import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import time
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prompt", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("--image", type=Path, action="append", required=True)
    parser.add_argument("--model", default="gemini-4-neon")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("Refusing to overwrite a measured call receipt")
    parts = [{"text": args.prompt.read_text()}]
    images = []
    for path in args.image:
        data = path.read_bytes()
        images.append({"name": path.name, "sha256": hashlib.sha256(data).hexdigest()})
        parts.append(
            {
                "inlineData": {
                    "mimeType": mimetypes.guess_type(path)[0],
                    "data": base64.b64encode(data).decode(),
                }
            }
        )
    request = urllib.request.Request(
        f"https://generativelanguage.googleapis.com/v1beta/models/{args.model}:generateContent",
        headers={
            "x-goog-api-key": os.environ["GEMINI_API_KEY"],
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "contents": [{"parts": parts}],
                "generationConfig": {
                    "thinkingConfig": {"thinkingLevel": "LOW"},
                    "maxOutputTokens": 4096,
                    "responseMimeType": "application/json",
                },
            }
        ).encode(),
    )
    start = time.monotonic()
    with urllib.request.urlopen(request, timeout=180) as response:
        body = json.load(response)
    text = "".join(
        p.get("text", "")
        for p in body["candidates"][0]["content"]["parts"]
        if not p.get("thought")
    )
    result = json.loads(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(
            {
                "model": body.get("modelVersion"),
                "usage": body.get("usageMetadata"),
                "wall_seconds": time.monotonic() - start,
                "prompt": args.prompt.read_text(),
                "images": images,
                "result": result,
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"out": str(args.out), "usage": body.get("usageMetadata"), "result": result}
        )
    )


if __name__ == "__main__":
    main()
