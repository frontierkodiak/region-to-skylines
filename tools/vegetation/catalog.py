"""Anonymous CS1 Workshop discovery and metadata; never downloads asset packages.

Discovery uses public browse pages and creator collections. Item metadata comes
from Valve's public GetPublishedFileDetails API; ratings and public creator names
supplement it from browse-page state. Every source response has a digest.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html.parser import HTMLParser
import html
import json
from pathlib import Path
import re
import time
import urllib.parse
import urllib.request
from urllib.error import HTTPError

API = "https://api.steampowered.com/ISteamRemoteStorage/"
COLLECTIONS = {"644677259": "MrMaison's Nature Collection", "963893498": "pdelmos Low poly collection"}


def request(url, form=None):
    body = urllib.parse.urlencode(form).encode() if form is not None else None
    req = urllib.request.Request(url, body, headers={"User-Agent": "CS1-vegetation-catalog/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                return response.read()
        except HTTPError as error:
            # A server refusal is not a transient transport failure. In
            # particular, never retry or work around a rate limit here.
            if error.code < 500 or attempt == 2:
                raise
            time.sleep(1 + attempt)
        except (OSError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1 + attempt)


def walk_state(value):
    """Steam's SSR state contains JSON strings within JSON strings."""
    if isinstance(value, str) and value[:1] in ("{", "["):
        try:
            yield from walk_state(json.loads(value))
        except ValueError:
            return
    elif isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_state(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_state(child)


class StateParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.states = []

    def handle_data(self, data):
        if data.startswith('{"route"'):
            self.states.extend(walk_state(json.loads(data)))


def browse(query, page):
    params = {
        "appid": "255710",
        "browsesort": "totaluniquesubscribers",
        "numperpage": 30,
        "p": page,
        "l": "english",
        **query,
    }
    url = "https://steamcommunity.com/workshop/browse/?" + urllib.parse.urlencode(params)
    raw = request(url)
    parser = StateParser()
    parser.feed(raw.decode())
    result = next((s for s in parser.states if "total_count" in s and "results" in s), None)
    if result is None:
        raise ValueError(f"No browse result state in {url}")
    authors = {}
    for s in parser.states:
        if "public_data" in s and "steamid" in s["public_data"]:
            d = s["public_data"]
            authors[d["steamid"]] = d.get("persona_name") or d.get("personaname")
    return (
        result,
        authors,
        {"url": url, "sha256": hashlib.sha256(raw).hexdigest(), "total": result["total_count"], "page": page},
    )


def api(method, ids, count_name):
    form = {count_name: len(ids), **{f"publishedfileids[{i}]": value for i, value in enumerate(ids)}}
    raw = request(f"{API}{method}/v1/", form)
    return json.loads(raw)["response"], hashlib.sha256(raw).hexdigest()


def collect(out, installed_ids):
    items, authors, receipts, collections = {}, {}, [], {}
    # Full Tree tag census; text searches supplement bushes/grass/rocks that are
    # tagged Prop or Decal rather than Tree. Those searches are explicitly scoped.
    queries = [{"requiredtags[0]": "Tree"}] + [
        {"requiredtags[0]": tag, "searchtext": word}
        for tag, word in [
            ("Prop", "grass"),
            ("Prop", "bush"),
            ("Prop", "rock"),
            ("Prop", "moss"),
            ("Prop", "leaves"),
            ("Prop Decal", "grass"),
            ("Prop Decal", "rock"),
            ("Prop Decal", "leaves"),
        ]
    ]
    for query in queries:
        first, names, receipt = browse(query, 1)
        pages = [first]
        authors.update(names)
        receipts.append(receipt)
        with ThreadPoolExecutor(max_workers=3) as pool:
            for result, names, receipt in pool.map(
                lambda p: browse(query, p), range(2, first["total_pages"] + 1)
            ):
                pages.append(result)
                authors.update(names)
                receipts.append(receipt)
        for page in pages:
            for item in page["results"]:
                items[item["publishedfileid"]] = item
        print(f"{query}: {first['total_count']} results, {first['total_pages']} pages", flush=True)
    for cid, title in COLLECTIONS.items():
        response, digest = api("GetCollectionDetails", [cid], "collectioncount")
        detail = response["collectiondetails"][0]
        if detail["result"] != 1:
            raise ValueError(f"Collection unavailable: {cid}: {detail['result']}")
        members = [c["publishedfileid"] for c in detail["children"] if c["filetype"] == 0]
        collections[cid] = {"title": title, "members": members, "sha256": digest}
        for iid in members:
            items.setdefault(iid, {})
    for iid in installed_ids:
        items.setdefault(iid, {})
    ids = sorted(items, key=int)
    result = []
    for start in range(0, len(ids), 100):
        batch = ids[start : start + 100]
        response, digest = api("GetPublishedFileDetails", batch, "itemcount")
        receipts.append({"api": "GetPublishedFileDetails", "ids": batch, "sha256": digest})
        for d in response["publishedfiledetails"]:
            iid = d["publishedfileid"]
            if d["result"] != 1:
                result.append({"id": iid, "availability": "unavailable", "api_result": d["result"]})
                continue
            if d.get("consumer_app_id") != 255710:
                continue
            extra = items[iid]
            description = d.get("description", "")
            claims = re.findall(r"\b(\d[\d,]*)\s*(?:triangles|tris|tri)\b", description, re.I)
            result.append(
                {
                    "id": iid,
                    "title": d["title"],
                    "author_id": d["creator"],
                    "author": authors.get(d["creator"]),
                    "url": f"https://steamcommunity.com/sharedfiles/filedetails/?id={iid}",
                    "subscribers": d.get("subscriptions"),
                    "favourites": d.get("favorited"),
                    "rating_stars": extra.get("star_rating"),
                    "rating_votes": extra.get("total_votes"),
                    "updated_unix": d.get("time_updated"),
                    "created_unix": d.get("time_created"),
                    "file_bytes": int(d.get("file_size", 0)),
                    "tags": [t["tag"] for t in d.get("tags", [])],
                    "preview_url": d.get("preview_url"),
                    "visibility": d.get("visibility"),
                    "banned": bool(d.get("banned")),
                    "collections": [cid for cid, c in collections.items() if iid in c["members"]],
                    "dependencies": None,
                    "required_mods": None,
                    "dependency_status": "not_yet_inspected",
                    "package_available_locally": iid in installed_ids,
                    "anonymous_file_url_available": bool(d.get("file_url")),
                    "author_reported_triangle_counts": [int(v.replace(",", "")) for v in claims],
                    "description_sha256": hashlib.sha256(description.encode()).hexdigest(),
                    "availability": "public"
                    if d.get("visibility") == 0 and not d.get("banned")
                    else "restricted",
                }
            )
        print(f"metadata {min(start + 100, len(ids))}/{len(ids)}", flush=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "retrieved_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "scope": "Tree tag census plus Prop grass/bush/rock and Decal grass/rock/leaves searches, two creator collections, installed packages",
                "complete_workshop_census": False,
                "collections": collections,
                "receipts": receipts,
                "items": result,
            },
            indent=2,
        )
        + "\n"
    )


class DependencyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.required_depth = None
        self.ids = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "div":
            self.depth += 1
            if attrs.get("id") == "RequiredItems":
                self.required_depth = self.depth
        if tag == "a" and self.required_depth is not None:
            match = re.search(r"filedetails/\?id=(\d+)", attrs.get("href", ""))
            if match:
                self.ids.append(match[1])

    def handle_endtag(self, tag):
        if tag == "div":
            if self.required_depth == self.depth:
                self.required_depth = None
            self.depth -= 1


def inspect_page(item):
    url = item["url"] + "&l=english"
    try:
        raw = request(url)
        text = raw.decode()
        if 'class="workshopItemTitle"' not in text:
            raise ValueError("Not a rendered public item page")
        parser = DependencyParser()
        parser.feed(text)
        item["dependencies"] = sorted(set(parser.ids), key=int)
        item["dependency_status"] = "public_page_checked"
        item.pop("page_error", None)
        item.pop("retry_after", None)
        item["page_sha256"] = hashlib.sha256(raw).hexdigest()
        rating = re.search(r"/(\d)-star_large.png", text)
        votes = re.search(r'class="numRatings">([\d,]+) ratings', text)
        item["rating_stars"] = int(rating[1]) if rating else None
        item["rating_votes"] = int(votes[1].replace(",", "")) if votes else None
        if not item.get("author"):
            author = re.search(r'class="friendBlockContent">\s*(.*?)<br', text, re.S)
            item["author"] = html.unescape(author[1].strip()) if author else None
    except HTTPError as error:
        item["dependency_status"] = "rate_limited" if error.code == 429 else "page_failed"
        item["page_error"] = str(error)
        item["retry_after"] = error.headers.get("Retry-After") if error.headers else None
    except (OSError, ValueError) as error:
        item["dependency_status"] = "page_failed"
        item["page_error"] = str(error)
    return item


def enrich(path, page_limit=50):
    data = json.loads(path.read_text())
    items = data["items"]
    attempted, limited = 0, False
    for item in items:
        if item.get("dependency_status") == "public_page_checked" or not item.get("url"):
            continue
        if attempted >= page_limit:
            break
        inspect_page(item)
        attempted += 1
        print(f"public item page {attempted}/{page_limit}: {item['dependency_status']}", flush=True)
        if item["dependency_status"] == "rate_limited":
            limited = True
            break
        if attempted < page_limit:
            time.sleep(3)
    data["dependency_page_refresh"] = {
        "attempted": attempted,
        "rate_limited": limited,
        "completed_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    # Checkpoint before another service call, including on a rate-limit stop.
    path.write_text(json.dumps(data, indent=2) + "\n")
    dependencies = data.get("dependency_items", {})
    missing = sorted(
        {d for item in items for d in item.get("dependencies") or []}
        - {i["id"] for i in items}
        - {iid for iid, cached in dependencies.items() if cached.get("result") == 1},
        key=int,
    )
    for start in [] if limited else range(0, len(missing), 100):
        response, digest = api("GetPublishedFileDetails", missing[start : start + 100], "itemcount")
        for d in response["publishedfiledetails"]:
            dependencies[d["publishedfileid"]] = {
                "title": d.get("title"),
                "tags": [t["tag"] for t in d.get("tags", [])],
                "result": d["result"],
            }
    by_id = {i["id"]: i for i in items}
    for item in items:
        if item.get("dependencies") is not None:
            item["required_mods"] = [
                d
                for d in item["dependencies"]
                if "Mod" in by_id.get(d, dependencies.get(d, {})).get("tags", [])
            ]
            item["unresolved_dependencies"] = [
                d
                for d in item["dependencies"]
                if d not in by_id and dependencies.get(d, {}).get("result") != 1
            ]
    data["dependency_items"] = dependencies
    path.write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--installed-ids", type=Path)
    parser.add_argument(
        "--enrich", action="store_true", help="Inspect each existing item's public dependency/rating page"
    )
    parser.add_argument(
        "--page-limit",
        type=int,
        default=50,
        help="Maximum dependency pages per invocation; stop immediately on HTTP 429",
    )
    args = parser.parse_args()
    if args.enrich:
        if args.page_limit < 1:
            parser.error("--page-limit must be positive")
        enrich(args.out, args.page_limit)
    else:
        collect(args.out, set(json.loads(args.installed_ids.read_text())) if args.installed_ids else set())
