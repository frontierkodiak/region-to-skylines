# The committed CLI region

`npm run test:cli` (and `npm run gate`) runs the shipped `cli.mjs` on the asheville square at
`--scale 0.5` with the network replaced by the responses here. The point is a real run of the
entry point: the test fails if the CLI stops writing the heightmap, its water map or the JSON
with the square's water-source records.

- `requests.json` holds every URL the recorded run asked for, with the status and content type.
- `tiles/` holds the exact response bytes, named by the URL's SHA-256 prefix (so repeats of one
  tile collapse). 30 AWS Terrain Tiles (Terrarium) PNGs and 36 OpenFreeMap vector tiles plus
  its TileJSON; 5.0 MB in all.
- `region.json` holds the square, the command, where the bytes came from and the SHA-256 of the
  three files the run wrote.

The bytes are real service data: elevation from AWS Terrain Tiles (Mapzen and its sources),
rivers, lakes and coast from OpenStreetMap (ODbL) via OpenFreeMap. Credits stay as the page's.

## Re-capture

Capture when the CLI's input format or the region deliberately changes; the recorded output
hashes change with it:

```sh
RECORD_DIR=/tmp/region node --import test/support/record-region.mjs \
  cli.mjs asheville --scale 0.5 --heightmap --out /tmp/map --json
```

Copy `/tmp/region/requests.json` and `/tmp/region/*.bin` here, then write `region.json` with the
new `outputs` hashes from a clean run. `test/cli-run.test.mjs` replays these files through
`test/support/offline-region.mjs`; a URL the capture does not hold fails the run rather than
reaching the network.
