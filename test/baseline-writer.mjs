// Old native receipts describe this retained writer, not the playable-water rewrite.
import { readFile } from "node:fs/promises";

const snapshots = {
  "mapgen.js": "mapgen.js",
  "tools/map-factory/region.py": "region.py",
  "tools/map-factory/prepare.py": "prepare.py",
  "package.json": "package.json",
  ".gitattributes": "gitattributes",
};

export const baselineSource = name => readFile(new URL(snapshots[name]
  ? "../tools/map-factory/fixtures/baseline-writer/" + snapshots[name]
  : "../" + name, import.meta.url));
