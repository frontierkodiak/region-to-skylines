"""Fetch the fixed PL-881 photographic and NAIP reference pack (stdlib only)."""

import argparse
import hashlib
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request


def fetch(url):
    request = urllib.request.Request(
        url, headers={"User-Agent": "Polli-PL881-reference-study/1.0"}
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2**attempt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    commons = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(
        {
            "action": "query",
            "format": "json",
            "prop": "imageinfo",
            "iiprop": "url|extmetadata",
            "titles": "File:40+36 N Lexington Ave Asheville 1.jpg",
        }
    )
    metadata = json.loads(fetch(commons))
    info = next(iter(metadata["query"]["pages"].values()))["imageinfo"][0]
    (args.output / "storefront-metadata.json").write_text(json.dumps(info, indent=2))
    photos = {
        "bungalow": (
            "https://psabc.org/wp-content/uploads/2020/02/108Norwood.jpg",
            "https://psabc.org/but-bungalows-go-on-forever/",
            "108 Norwood Avenue",
        ),
        "storefront": (
            info["url"],
            info["descriptionurl"],
            "40 North Lexington Avenue",
        ),
        "apartment": (
            "https://haca.org/wp-content/uploads/2025/12/Hillcrest-14-1024x768-1.webp",
            "https://haca.org/properties/hillcrest-apartments/",
            "100 Atkinson Street",
        ),
    }
    records = {}
    for name, (url, source, address) in photos.items():
        data = fetch(url)
        suffix = ".webp" if name == "apartment" else ".jpg"
        (args.output / (name + suffix)).write_bytes(data)
        records[name] = {
            "photo_url": url,
            "source": source,
            "address": address,
            "photo_sha256": hashlib.sha256(data).hexdigest(),
        }
        geocode = (
            "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?"
            + urllib.parse.urlencode(
                {
                    "address": address + ", Asheville, NC",
                    "benchmark": "Public_AR_Current",
                    "format": "json",
                }
            )
        )
        geo = json.loads(fetch(geocode))
        (args.output / (name + "-geocode.json")).write_text(json.dumps(geo, indent=2))
        matches = geo["result"]["addressMatches"]
        if not matches and name == "apartment":
            # Coordinates published in the property owner's embedded location map.
            center = {"x": -82.5712694, "y": 35.5944931}
            records[name]["coordinate_source"] = source + " (embedded Google map)"
        elif matches:
            center = matches[0]["coordinates"]
        else:
            raise ValueError(
                f"No geocode for {address}; do not silently substitute a location"
            )
        lon, lat = center["x"], center["y"]
        bbox = [lon - 0.0018, lat - 0.0015, lon + 0.0018, lat + 0.0015]
        endpoint = "https://imagery.nationalmap.gov/arcgis/rest/services/USGSNAIPImagery/ImageServer"
        params = {
            "bbox": ",".join(map(str, bbox)),
            "bboxSR": 4326,
            "imageSR": 3857,
            "size": "768,768",
            "format": "png",
            "bandIds": "0,1,2",
            "f": "image",
        }
        naip_url = endpoint + "/exportImage?" + urllib.parse.urlencode(params)
        naip = fetch(naip_url)
        if not naip.startswith(b"\x89PNG"):
            raise ValueError(f"NAIP returned non-PNG for {name}: {naip[:200]!r}")
        (args.output / (name + "-naip.png")).write_bytes(naip)
        identify = (
            endpoint
            + "/identify?"
            + urllib.parse.urlencode(
                {
                    "geometry": json.dumps(
                        {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}
                    ),
                    "geometryType": "esriGeometryPoint",
                    "returnCatalogItems": "true",
                    "f": "json",
                }
            )
        )
        records[name].update(
            {
                "center_wgs84": center,
                "bbox_wgs84": bbox,
                "naip_url": naip_url,
                "naip_sha256": hashlib.sha256(naip).hexdigest(),
            }
        )
        try:
            (args.output / (name + "-naip-identify.json")).write_bytes(fetch(identify))
        except (urllib.error.URLError, TimeoutError) as error:
            records[name]["naip_identify_error"] = str(error)
        (args.output / "manifest.json").write_text(json.dumps(records, indent=2))
        print(name, center, flush=True)


if __name__ == "__main__":
    main()
