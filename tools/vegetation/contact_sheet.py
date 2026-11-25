"""Labeled contact pages made only from unchanged native screenshots."""

import argparse
import json
from pathlib import Path
import textwrap

from PIL import Image, ImageDraw, ImageFont


def build(source, out):
    out.mkdir(parents=True, exist_ok=True)
    font_path = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), 15) if font_path.exists() else ImageFont.load_default()
    index = []
    for kind, folder in [("tree", "overview"), ("prop", "props")]:
        listing = source / folder / "specimens.json"
        if not listing.exists():
            continue
        entries = json.loads(listing.read_text())
        for start in range(0, len(entries), 24):
            page = Image.new("RGB", (1440, 8 * 326), "#f6f4ec")
            draw = ImageDraw.Draw(page)
            name = f"{kind}-{start // 24 + 1:03d}.jpg"
            for offset, entry in enumerate(entries[start : start + 24]):
                x, y = (offset % 3) * 480, (offset // 3) * 326
                frame = entry.get("views", {}).get("close")
                if frame:
                    with Image.open(source / folder / frame) as original:
                        image = original.convert("RGB")
                        image.thumbnail((480, 270))
                        page.paste(image, (x, y))
                label = f"{start + offset + 1}  {entry['candidate']}"
                for line, text in enumerate(textwrap.wrap(label, width=54)[:3]):
                    draw.text((x + 6, y + 271 + line * 17), text, font=font, fill="#24342b")
                index.append({"kind": kind, "ordinal": start + offset + 1, "page": name, **entry})
            page.save(out / name, quality=90)
    (out / "index.json").write_text(json.dumps(index, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.out)
