// Capture the deterministic PL-1066 cohort, without a CLI export or risk override.
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadPyodide } from 'pyodide';
import { fromUrl } from 'geotiff';
import { PRESETS, DEFAULTS } from '../../terrain.js';
import { captureInputs } from '../../inputs.js';
import { startFactory, landCover, deposits, clearWork, WORLDCOVER_S3, worldCoverFile, FACTORY_FILES } from '../../mapgen.js';

const [output, mode = '--plan'] = process.argv.slice(2);
if (!output || !['--plan', '--capture'].includes(mode)) throw Error('Usage: capture-connections.mjs OUTPUT [--plan|--capture]');
const root = fileURLToPath(new URL('../../', import.meta.url));
const fixtures = ['asheville', 'innsbruck', 'rio', 'pittsburgh', 'charleston'];
const fresh = PRESETS.filter(p => !fixtures.includes(p.slug)).sort((a, b) => a.slug.localeCompare(b.slug, 'en'));
if (fresh.length < 3) throw Error('The selection rule must supply at least three fresh squares');
const plan = {
  schema: 1, issue: 'PL-1066',
  selection_rule: 'All PRESETS excluding the five fixtures, sorted by slug; default square, no substitutions, no outcome-based retries.',
  fixtures,
  fresh: fresh.map(p => ({ ...DEFAULTS, lon: p.lon, lat: p.lat, rotation: 0, scale: 1, vscale: 'auto', rivers: true, name: p.name, slug: p.slug })),
};
await mkdir(output, { recursive: true });
const planPath = resolve(output, 'cohort.json');
try {
  const prior = JSON.parse(await readFile(planPath, 'utf8'));
  if (JSON.stringify(prior) !== JSON.stringify(plan)) throw Error('Frozen cohort differs; use a new output directory');
} catch (error) { if (error.code !== 'ENOENT') throw error; }
await writeFile(planPath, JSON.stringify(plan, null, 2) + '\n');
if (mode === '--plan') { console.log(planPath); process.exit(0); }
const sha = b => createHash('sha256').update(b).digest('hex');
const sourceFiles = {};
for (const f of ['inputs.js', 'terrain.js', 'mapgen.js', ...FACTORY_FILES.map(f => 'tools/map-factory/' + f)]) sourceFiles[f] = sha(await readFile(join(root, f)));
const factory = await startFactory({ loadPyodide, read: async f => new Uint8Array(await readFile(join(root, 'tools/map-factory', f))) });
for (const sq of plan.fresh) {
  const folder = resolve(output, 'inputs', sq.slug);
  try { await readFile(join(folder, 'capture.json')); console.error(`${sq.slug}: cached capture retained`); continue; }
  catch (error) { if (error.code !== 'ENOENT') throw error; }
  await mkdir(folder, { recursive: true });
  const status = s => console.error(`${sq.slug}: ${s}`);
  clearWork(factory);
  try {
    const inputs = await captureInputs(sq, { status, includeRunways: true });
    await writeFile(join(folder, 'input.png'), inputs.png);
    await writeFile(join(folder, 'geometry.json'), JSON.stringify(inputs.geometry) + '\n');
    await writeFile(join(folder, 'banks.f32'), new Uint8Array(inputs.banks.buffer));
    const cover = await landCover(factory, sq, { fromUrl, tileUrl: t => WORLDCOVER_S3 + worldCoverFile(t), status });
    const evidence = await deposits(factory, sq, { status });
    await writeFile(join(folder, 'landcover.u8.gz'), factory.py.FS.readFile(cover.path));
    if (evidence) await writeFile(join(folder, 'evidence.json'), factory.py.FS.readFile(evidence.path));
    const files = {};
    for (const f of ['input.png', 'geometry.json', 'banks.f32', 'landcover.u8.gz', ...(evidence ? ['evidence.json'] : [])]) files[f] = sha(await readFile(join(folder, f)));
    await writeFile(join(folder, 'capture.json'), JSON.stringify({
      source_commit: execFileSync('git', ['rev-parse', 'HEAD'], { cwd: root, encoding: 'utf8' }).trim(),
      source_files_sha256: sourceFiles, capture_options: { includeRunways: true }, sq, files_sha256: files, evidence_available: !!evidence,
      landcover: { tiles: cover.tiles, classes: cover.classes },
    }, null, 2) + '\n');
  } catch (error) {
    await writeFile(join(folder, 'capture-error.json'), JSON.stringify({ error: String(error), sq }, null, 2) + '\n');
    console.error(`${sq.slug}: capture failed: ${error}`);
  }
}
process.exit(0);
