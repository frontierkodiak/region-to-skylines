// Execute archived/current captures against the same synthetic PNG/vector providers.
// Source snapshots remain byte-identical; only import URLs are resolved for execution.
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';
import Pbf from 'pbf';
import { pngRGB } from '../terrain.js';

const root = new URL('../', import.meta.url);
const archive = 'tools/map-factory/fixtures/contracts/pl1066-optional-runways-v1/historical-inputs.js';
const sha = b => createHash('sha256').update(b).digest('hex');
const read = name => readFile(new URL(name, root));
async function moduleFrom(bytes) {
  const text = bytes.toString().replace('"./terrain.js"', JSON.stringify(new URL('terrain.js', root).href))
    .replace('"@mapbox/vector-tile"', JSON.stringify(import.meta.resolve('@mapbox/vector-tile')))
    .replace('"pbf"', JSON.stringify(import.meta.resolve('pbf')));
  return import('data:text/javascript;base64,' + Buffer.from(text).toString('base64'));
}
function vectorTile(runway = true) {
  const tile = new Pbf();
  tile.writeMessage(3, (_, layer) => {
    layer.writeVarintField(15, 2);
    layer.writeStringField(1, 'aeroway');
    layer.writeVarintField(5, 4096);
    layer.writeStringField(3, 'class');
    layer.writeStringField(3, 'ref');
    for (const value of [runway ? 'runway' : 'taxiway', '09/27'])
      layer.writeMessage(4, (v, p) => p.writeStringField(1, v), value);
    layer.writeMessage(2, (_, f) => {
      f.writeVarintField(1, 7);
      f.writePackedVarint(2, [0, 0, 1, 1]);
      f.writeVarintField(3, 2);
      f.writePackedVarint(4, [9, 2000, 4096, 10, 4000, 0]);
    });
  });
  return tile.finish();
}
const digests = result => ({
  png: sha(result.png), geometry: sha(JSON.stringify(result.geometry)),
  banks: sha(new Uint8Array(result.banks.buffer, result.banks.byteOffset, result.banks.byteLength)),
  game: sha(new Uint8Array(result.game.buffer, result.game.byteOffset, result.game.byteLength)),
});
export async function captureProof() {
  const oldBytes = await read(archive), newBytes = await read('inputs.js');
  const old = await moduleFrom(oldBytes), current = await moduleFrom(newBytes);
  const rgb = new Uint8Array(256 * 256 * 3);
  for (let i = 0; i < rgb.length; i += 3) { rgb[i] = 128; rgb[i + 1] = 100; }
  const png = new Uint8Array(await (await pngRGB(rgb, 256, 256)).arrayBuffer());
  const tile = vectorTile(), missingTile = vectorTile(false), originalFetch = globalThis.fetch;
  globalThis.fetch = async url => {
    const address = String(url);
    if (address.endsWith('/planet')) return Response.json({ tiles: ['https://capture-proof.invalid/{z}/{x}/{y}'] });
    if (address.startsWith('https://capture-proof.invalid/')) return new Response(Number(new URL(address).pathname.split('/')[2]) > 12000 ? missingTile : tile);
    if (address.includes('/terrarium/')) return new Response(png);
    throw Error('Unexpected network request in offline capture proof: ' + address);
  };
  const cases = [];
  try {
    for (const [lon, lat, rotation, scale] of [[0, 0, 0, 1], [11.4, 47.27, 27, 0.75], [-43.205, -22.94, -15, 1.25], [120, 0, 0, 1]]) {
      const sq = { lon, lat, rotation, scale, name: 'Synthetic capture', slug: 'synthetic' };
      const historical = await old.captureInputs(sq), defaultResult = await current.captureInputs(sq);
      const disabled = await current.captureInputs(sq, { includeRunways: false });
      const enabled = await current.captureInputs(sq, { includeRunways: true });
      cases.push({ sq, historical: digests(historical), current_default: digests(defaultResult),
        explicit_false: digests(disabled), enabled: digests(enabled),
        historical_keys: Object.keys(historical.geometry), default_keys: Object.keys(defaultResult.geometry),
        historical_provenance_keys: Object.keys(historical.geometry.provenance), default_provenance_keys: Object.keys(defaultResult.geometry.provenance),
        runway_pieces: enabled.geometry.runways.length, airport: enabled.geometry.airport });
    }
  } finally { globalThis.fetch = originalFetch; }
  return {
    schema: 1, status: 'default_capture_byte_compatible_not_native_qualification', native_tested: false,
    source_sha256: { historical_inputs: sha(oldBytes), current_inputs: sha(newBytes),
      terrain: sha(await read('terrain.js')), proof_driver: sha(await read('test/capture-runway-proof.mjs')) },
    providers: { elevation_png_sha256: sha(png), runway_vector_sha256: sha(tile),
      scope: 'Synthetic constant 100m Terrarium PNG and encoded OpenMapTiles aeroway lines; no live requests or historical recapture' },
    cases,
  };
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  process.stdout.write(JSON.stringify(await captureProof(), null, 2) + '\n');
