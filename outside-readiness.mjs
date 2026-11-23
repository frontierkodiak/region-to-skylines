// One accepted outside-readiness stopped-study publication, read from archived bytes only.
//
// This module never runs the study's frozen collector, driver, auditor, bundle
// builder, evaluator, reporter, scorer, model or game. It re-checks the strict
// 26-file publication scope, the module member hashes, the pre-control freeze
// records, the 51 retained raw hashes and the five carried raw gzip bytes,
// re-derives the canonical 82-file study-tree digest and the versioned 30-file
// contract digest, and renders the one study under Road, Ship and Air. It is a
// distinct typed study: not pooled with the outside-query, outside-stock, rail
// or native studies, not a qualification, promise, certificate or live rule.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { gunzipSync } from "node:zlib";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const blob = (bytes) => createHash("sha1").update(Buffer.concat([Buffer.from(`blob ${bytes.length}\0`), bytes])).digest("hex");
const read = (file) => readFileSync(ROOT + file);
const parse = (file) => JSON.parse(read(file).toString("utf8"));
const canonical = (value) => JSON.stringify(Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))));

export const OUTSIDE_READINESS_STUDY = "outside-readiness-stock-v2";
export const OUTSIDE_READINESS_PROJECTION = "tools/map-factory/capability-evidence/outside-readiness-studies.json";
export const OUTSIDE_READINESS_PROJECTION_SHA = "dfeb78c733b2f0f259e4c279030fe53334b58543773c69a22fed38320713b0c9";
export const OUTSIDE_READINESS_TOOL = "tools/map-factory/integrate_outside_readiness.py";
export const OUTSIDE_READINESS_TOOL_SHA = "31e820f4c97383bcb07f184bdfffff2d0bca635c6b3febfeab518083f5316e2a";
export const OUTSIDE_READINESS_SOURCES = "tools/map-factory/capability-evidence/outside-readiness-sources.json";
export const OUTSIDE_READINESS_SOURCES_SHA = "c2af9f3b80b34dba6f6ba12a0cbd4dc18c6183c319ebfa3d770fc05eef343982";
export const OUTSIDE_READINESS_PREFIX = "tools/map-factory/capability-evidence/";
export const OUTSIDE_READINESS_PUBLICATION = "4eca4d291cc133513e8bac6484185d3a3b6e80ae";
export const OUTSIDE_READINESS_FROZEN = "bd00a4cd1719afb32a67601949103ca8ef9cf76d";
export const OUTSIDE_READINESS_SOURCE = "86fee78d9517eff3c0e715813202b7b81b7e11d1";
export const OUTSIDE_READINESS_REPO = "https://github.com/frontierkodiak/region-to-skylines/blob/";

const MODES = ["road", "ship", "air"];
const CELLS = MODES.flatMap((mode) => ["success", "no_path"].map((kind) => `${mode}:${kind}`));
const STUDY_SOURCE_SHA256 = "03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d";
const CONTRACT_SOURCE_SHA256 = "561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860";

const EXPECTED = {
  kind: "outside_readiness_stock_study",
  publication_files: 26,
  copied_files: 25,
  linked_files: 1,
  frozen_publication_files: 20,
  post_control_files: 6,
  frozen_changed_files: 2,
  module_members: 25,
  module_version: 3,
  raw_files: 51,
  raw_copied_files: 5,
  frozen_source_files: 82,
  contract_source_files: 30,
  holdout: 6,
  controls: 12,
  requests: 18,
  pool: 25,
  packages: 1,
  covered_cells: 6,
  inventory_files: 45,
  inventory_roots: 11,
  plugins: 7,
  assemblies: 23,
  processes: 10,
  tests: 59,
  old_facts: 84,
  old_publication_files: 142,
  readiness_files: 24,
};

const fail = (message) => {
  throw new Error(message);
};

const hashes = (value) => Object.fromEntries(Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)));
const tally = (rows, key) => rows.reduce((total, row) => total + (row[key] === true ? 1 : 0), 0);
const four = (record) => [record.tp ?? record.TP, record.fp ?? record.FP, record.tn ?? record.TN, record.fn ?? record.FN];
const pair = (record) => {
  const [tp, fp, tn, fn] = four(record);
  return `TP ${tp} · FP ${fp} · TN ${tn} · FN ${fn}`;
};
const short = (digest) => `${String(digest).slice(0, 12)}…`;
const yes = (value) => (value ? "yes" : "no");

/** Every repo-relative file the page serves for this study, plus its projection. */
export function outsideReadinessFiles(study) {
  const files = [OUTSIDE_READINESS_PROJECTION, OUTSIDE_READINESS_SOURCES];
  for (const record of (study ?? outsideReadiness().study).files) files.push(record.path);
  for (const record of (study ?? outsideReadiness().study).raw) files.push(record.path);
  return [...new Set(files)];
}

/**
 * Re-check the projection, its tool, its manifest, the publication's exact
 * 26-file scope, the 20 pre-control records, the 51 raw hashes and the five
 * carried raw gzip bytes, then re-derive the two source digests. A changed
 * byte anywhere fails before the page is built.
 */
export function outsideReadiness(load = read) {
  if (sha(load(OUTSIDE_READINESS_TOOL)) !== OUTSIDE_READINESS_TOOL_SHA) fail("Outside-readiness projection tool changed");
  if (sha(load(OUTSIDE_READINESS_SOURCES)) !== OUTSIDE_READINESS_SOURCES_SHA) fail("Outside-readiness source manifest changed");
  const bytes = load(OUTSIDE_READINESS_PROJECTION);
  const projectionSha = sha(bytes);
  if (projectionSha !== OUTSIDE_READINESS_PROJECTION_SHA) fail("Outside-readiness projection changed");
  const projection = JSON.parse(bytes.toString("utf8"));
  if (projection.schema !== 1) fail("Outside-readiness projection header changed");
  if (JSON.stringify(Object.keys(projection.studies)) !== JSON.stringify([OUTSIDE_READINESS_STUDY]))
    fail("Outside-readiness projection is not the one accepted publication");
  const study = projection.studies[OUTSIDE_READINESS_STUDY];
  const manifest = JSON.parse(load(OUTSIDE_READINESS_SOURCES).toString("utf8"));
  const publication = manifest.publications?.[OUTSIDE_READINESS_STUDY];
  if (!publication) fail("Outside-readiness source manifest lost its publication");
  if (projection.source_manifest.file !== OUTSIDE_READINESS_SOURCES ||
      projection.source_manifest.sha256 !== OUTSIDE_READINESS_SOURCES_SHA ||
      projection.source_manifest.commit !== OUTSIDE_READINESS_PUBLICATION ||
      projection.source_manifest.frozen_commit !== OUTSIDE_READINESS_FROZEN)
    fail("Outside-readiness projection does not bind the carried source manifest");
  if (publication.commit !== OUTSIDE_READINESS_PUBLICATION ||
      publication.base !== OUTSIDE_READINESS_SOURCE ||
      publication.frozen_commit !== OUTSIDE_READINESS_FROZEN)
    fail("Outside-readiness source manifest names another publication");

  // Study identity and the Unknown outcome.
  if (study.study !== OUTSIDE_READINESS_STUDY || study.kind !== EXPECTED.kind) fail("Outside-readiness study identity changed");
  if (study.evidence_only !== true || study.certificates !== "none") fail("Outside-readiness study is not evidence only");
  if (study.result !== "unknown") fail("Outside-readiness study claims another outcome");
  const source = study.source;
  if (source.publication_commit !== OUTSIDE_READINESS_PUBLICATION ||
      source.publication_base !== OUTSIDE_READINESS_SOURCE ||
      source.frozen_commit !== OUTSIDE_READINESS_FROZEN ||
      source.internal_merge !== "10be1b73598d7080afae44010c9de8b99d295316" ||
      source.target !== "PL-1142-native-v2" || source.pull_request !== 93 ||
      source.branch !== "PL-1313-stock-v2" ||
      source.source_issue !== "01a2097f-7ea5-7803-ad5b-21f13dc72289")
    fail("Outside-readiness source identity changed");
  if (!isDeepStrictEqual(source.review, {
    pass: "01a2099e-0d6c-7a16-8749-a3544357356a",
    acceptance: "01a209a4-8c98-7e83-b6e3-0fbcb257f550",
  })) fail("Outside-readiness review record changed");
  if (source.module.version !== EXPECTED.module_version || source.module.members !== EXPECTED.module_members ||
      source.module.source !== OUTSIDE_READINESS_SOURCE || source.module.target !== "PL-1142-native-v2")
    fail("Outside-readiness module identity changed");

  const holdout = study.holdout;
  if (holdout.planned !== EXPECTED.holdout || holdout.observed !== 0 || holdout.unknown !== EXPECTED.holdout)
    fail("Outside-readiness holdout accounting changed");
  if (holdout.accuracy !== null || holdout.precision !== null || holdout.recall !== null)
    fail("Outside-readiness study invents a holdout metric");
  if (holdout.records.length !== EXPECTED.holdout || holdout.records.some((row) => row.status !== "unobserved_unknown"))
    fail("Outside-readiness planned holdout cell is no longer Unknown");

  // The strict publication scope: 26 files, 25 carried, one linked bulk member.
  const closure = study.closure;
  if (closure.publication_files !== EXPECTED.publication_files || closure.copied_files !== EXPECTED.copied_files ||
      closure.linked_files !== EXPECTED.linked_files || closure.frozen_publication_files !== EXPECTED.frozen_publication_files ||
      closure.module_members !== EXPECTED.module_members || closure.prefix !== `${OUTSIDE_READINESS_PREFIX}${OUTSIDE_READINESS_STUDY}`)
    fail("Outside-readiness publication file scope changed");
  const publicationFiles = Object.keys(publication.files);
  const copiedRelative = study.files.map((record) => record.path.slice(closure.prefix.length + 1)).sort();
  const linkedRelative = study.linked.map((record) => record.path.slice(closure.prefix.length + 1)).sort();
  if (publicationFiles.length !== EXPECTED.publication_files ||
      publication.copied.length !== EXPECTED.copied_files || publication.linked.length !== EXPECTED.linked_files ||
      JSON.stringify([...publication.copied].sort()) !== JSON.stringify(copiedRelative) ||
      JSON.stringify([...publication.linked].sort()) !== JSON.stringify(linkedRelative) ||
      publication.publication_files !== EXPECTED.publication_files)
    fail("Outside-readiness source manifest file split changed");
  if (publication.post_control.length !== EXPECTED.post_control_files || publication.frozen_changed.length !== EXPECTED.frozen_changed_files)
    fail("Outside-readiness post-control file set changed");

  for (const record of study.files) {
    if (!record.path.startsWith(`${closure.prefix}/`)) fail("Outside-readiness carried evidence outside the study prefix");
    if (!/^[a-f0-9]{64}$/.test(record.sha256 ?? "") || !/^[a-f0-9]{40}$/.test(record.git_blob ?? ""))
      fail(`${record.path}: carried evidence lacks a hash`);
    const raw = load(record.path);
    if (raw.length !== record.bytes || sha(raw) !== record.sha256)
      fail(`Outside-readiness carried evidence changed: ${record.path}`);
    if (blob(raw) !== record.git_blob) fail(`${record.path}: carried Git blob id does not follow its bytes`);
    const published = publication.files[record.path.slice(closure.prefix.length + 1)];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob || published.bytes !== record.bytes)
      fail(`${record.path}: carried evidence does not match the source manifest`);
  }
  if (!Array.isArray(study.linked) || study.linked.length !== EXPECTED.linked_files) fail("Outside-readiness linked source count changed");
  for (const record of study.linked) {
    const relative = record.path.slice(closure.prefix.length + 1);
    const published = publication.files[relative];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob || published.bytes !== record.bytes)
      fail(`${record.path}: linked source does not match the source manifest`);
    if (existsSync(ROOT + record.path)) fail(`${record.path}: a linked file is duplicated in the repository`);
  }

  // module.json's 25 member hashes must match the 25 non-module publication files.
  const module = parse(`${closure.prefix}/module.json`);
  const members = Object.keys(module.files).sort();
  const nonModule = publicationFiles.filter((name) => name !== "module.json").sort();
  if (members.length !== EXPECTED.module_members || JSON.stringify(members) !== JSON.stringify(nonModule))
    fail("Outside-readiness module member set changed");
  for (const [name, digest] of Object.entries(module.files)) {
    if (publication.files[name]?.sha256 !== digest) fail(`${name}: module hash disagrees with the publication manifest`);
  }

  // The pre-control freeze records: six files did not exist, two changed, the
  // other eighteen publication bytes are the frozen bytes.
  let absent = 0, changed = 0;
  for (const record of [...study.files, ...study.linked]) {
    const relative = record.path.slice(closure.prefix.length + 1);
    const postControl = publication.post_control.includes(relative);
    if (postControl) {
      if (record.frozen !== null) fail(`${relative}: a post-control file claims a pre-control record`);
      absent += 1;
      continue;
    }
    if (!record.frozen || !/^[a-f0-9]{64}$/.test(record.frozen.sha256 ?? "") || !/^[a-f0-9]{40}$/.test(record.frozen.git_blob ?? ""))
      fail(`${relative}: a pre-control file lost its frozen record`);
    if (publication.files[relative].frozen?.sha256 !== record.frozen.sha256) fail(`${relative}: frozen record disagrees with the manifest`);
    if (publication.frozen_changed.includes(relative)) {
      if (record.frozen.sha256 === record.sha256) fail(`${relative}: a changed file records its publication bytes as frozen`);
      changed += 1;
    } else if (record.frozen.sha256 !== record.sha256) {
      fail(`${relative}: an unchanged file records two different frozen and published hashes`);
    }
  }
  if (absent !== EXPECTED.post_control_files || changed !== EXPECTED.frozen_changed_files)
    fail("Outside-readiness frozen record split changed");

  // The 51 retained raw hashes and the five carried gzip files.
  const evaluation = parse(`${closure.prefix}/evaluation.json`);
  if (Object.keys(evaluation.raw_files).length !== EXPECTED.raw_files) fail("Outside-readiness retained raw count changed");
  if (study.raw_manifest.length !== EXPECTED.raw_files) fail("Outside-readiness projection raw count changed");
  if (JSON.stringify(hashes(Object.fromEntries(study.raw_manifest.map((row) => [row.path, row.sha256])))) !==
      JSON.stringify(hashes(evaluation.raw_files))) fail("Outside-readiness raw manifest disagrees with the evaluation");
  if (study.raw.length !== EXPECTED.raw_copied_files) fail("Outside-readiness carried raw count changed");
  for (const record of study.raw) {
    const raw = load(record.path);
    if (raw.length !== record.bytes || sha(raw) !== record.sha256) fail(`${record.path}: carried raw gzip changed`);
    const original = gunzipSync(raw);
    if (original.length !== record.raw_bytes || sha(original) !== record.raw_sha256)
      fail(`${record.path}: decompressed raw bytes changed`);
    if (evaluation.raw_files[record.raw_path] !== record.raw_sha256)
      fail(`${record.path}: carried raw bytes are not one of the recorded 51 raw files`);
  }

  // The frozen plan and its two source digests.
  const freeze = parse(`${closure.prefix}/freeze.json`);
  if (freeze.source !== OUTSIDE_READINESS_SOURCE || freeze.target !== "PL-1142-native-v2") fail("Outside-readiness freeze source changed");
  const sources = freeze.source_files;
  if (Object.keys(sources).length !== EXPECTED.frozen_source_files) fail("Outside-readiness frozen source manifest changed");
  if (sha(Buffer.from(canonical(sources))) !== STUDY_SOURCE_SHA256) fail("Outside-readiness study-tree digest is not re-derivable");
  if (study.freeze.source_files !== EXPECTED.frozen_source_files || study.freeze.source_sha256 !== STUDY_SOURCE_SHA256)
    fail("Outside-readiness projection study digest changed");
  const contract = study.freeze.contract_source_files;
  if (contract.length !== EXPECTED.contract_source_files ||
      new Set(contract).size !== EXPECTED.contract_source_files ||
      JSON.stringify(contract) !== JSON.stringify([...contract].sort()))
    fail("Outside-readiness contract closure changed");
  for (const name of contract) if (sources[name] === undefined) fail(`${name}: contract closure file missing from the freeze`);
  const subset = Object.fromEntries(contract.map((name) => [name, sources[name]]));
  if (sha(Buffer.from(canonical(subset))) !== CONTRACT_SOURCE_SHA256) fail("Outside-readiness contract digest is not re-derivable");
  if (study.freeze.contract_source_sha256 !== CONTRACT_SOURCE_SHA256 ||
      study.freeze.non_contract_source_files !== EXPECTED.frozen_source_files - EXPECTED.contract_source_files)
    fail("Outside-readiness projection contract count changed");
  if (freeze.protocol.entry !== "NewGameFromMap" || freeze.protocol.seed !== 857 ||
      freeze.protocol.max_length !== 100000 || freeze.protocol.version !== 2 || freeze.protocol.invert_traffic !== false)
    fail("Outside-readiness frozen protocol changed");
  if (freeze.old_fact_count !== EXPECTED.old_facts || freeze.old_publication_files !== EXPECTED.old_publication_files ||
      freeze.readiness_files !== EXPECTED.readiness_files) fail("Outside-readiness immutable sibling counts changed");
  if (freeze.build.dll.sha256 !== "7b15fba2e424954e51120a9fdbe79e7d43606e5922f2fdd6389a3044a6944d75" ||
      freeze.build.dll.mvid !== "65019b31-a6bb-4e72-a75d-ca664806ef23" ||
      freeze.build.game_executable_sha256 !== "a18607b230f20b5653379a8debb6d5fe69e3ccd45863798f2e2a5ec403b8a9ca")
    fail("Outside-readiness frozen build identity changed");

  // The refusal: the runtime policy records the 82-file digest, not the
  // required 30-file closure, and both digests stay recorded.
  const bundle = parse(`${closure.prefix}/bundle.json`);
  const policy = bundle.policy;
  if (bundle.version !== 2 || policy.source_sha256 !== STUDY_SOURCE_SHA256 || policy.source_sha256 === CONTRACT_SOURCE_SHA256)
    fail("Outside-readiness bundle policy binding changed");
  if (policy.dll_sha256 !== freeze.build.dll.sha256) fail("Outside-readiness bundle DLL changed");
  if (Object.keys(policy.files).length !== EXPECTED.inventory_files ||
      Object.keys(policy.roots).length !== 11 || Object.keys(policy.plugins).length !== EXPECTED.plugins ||
      Object.keys(policy.assemblies).length !== EXPECTED.assemblies)
    fail("Outside-readiness bundle runtime inventory changed");
  const readiness = study.readiness;
  const evaluationReadiness = evaluation.readiness;
  if (readiness.ready_for_measurement !== false || evaluationReadiness.ready_for_measurement !== false)
    fail("Outside-readiness study claims readiness");
  if (readiness.contract_source_files !== EXPECTED.contract_source_files ||
      readiness.contract_source_sha256 !== CONTRACT_SOURCE_SHA256 ||
      readiness.study_source_files !== EXPECTED.frozen_source_files ||
      readiness.study_source_sha256 !== STUDY_SOURCE_SHA256)
    fail("Outside-readiness readiness bindings changed");
  if (!isDeepStrictEqual(readiness.reasons, evaluationReadiness.reasons) || readiness.reasons.length !== 2 ||
      readiness.reasons.some((reason) => !reason.endsWith("runtime policy differs from freeze")))
    fail("Outside-readiness refusal reasons changed");
  if (readiness.bundle_sha256 !== "767de08aeb6df62a5e81dcc5d4ec98f03d282f6685347e39a07796e0df38018b" ||
      readiness.assembler_sha256 !== "d8c41863b6ed62b02d3e6f9dfa3d0f55283d978850b9b6243183e163956a7961")
    fail("Outside-readiness refusal record changed");

  // Population, selection, requests and the control arithmetic.
  const inventory = parse(`${closure.prefix}/inventory.json`);
  const exclusions = parse(`${closure.prefix}/exclusions.json`);
  const selection = parse(`${closure.prefix}/selection.json`);
  const requests = parse(`${closure.prefix}/requests.json`);
  const predictions = parse(`${closure.prefix}/predictions.json`);
  if (inventory.length !== 105) fail("Outside-readiness installed package count changed");
  if (inventory.filter((row) => row.cells).length !== 25) fail("Outside-readiness eligible package count changed");
  if (Object.keys(exclusions.table).length !== 26) fail("Outside-readiness exclusion hash set changed");
  if (study.population.packages !== 105 || study.population.eligible !== 25 || study.population.excluded_hashes !== 26)
    fail("Outside-readiness population summary changed");
  if (selection.rule !== study.selection.rule || selection.missing_cells.length !== 0 ||
      selection.covered_cells.length !== EXPECTED.covered_cells ||
      JSON.stringify([...selection.covered_cells].sort()) !== JSON.stringify([...CELLS].sort()))
    fail("Outside-readiness selection cells changed");
  if (selection.ordered_pool.length !== EXPECTED.pool || selection.selected.length !== EXPECTED.packages ||
      selection.selected[0].file !== "PL Cavern Coast.crp" ||
      selection.selected[0].sha256 !== "8888d2e4cff59babd69afa0a11417e97f4c8486bcffde6891e9dd8afb29245ac")
    fail("Outside-readiness selected package changed");
  if (study.selection.pool !== EXPECTED.pool || study.selection.covered_cells.length !== EXPECTED.covered_cells ||
      study.selection.missing_cells.length !== 0 || study.selection.selected.length !== EXPECTED.packages)
    fail("Outside-readiness selection summary changed");
  if (Object.keys(predictions).length !== EXPECTED.requests || requests.query_ids.length !== EXPECTED.requests ||
      study.requests.planned !== EXPECTED.requests || study.requests.controls !== EXPECTED.controls ||
      study.requests.holdout !== EXPECTED.holdout)
    fail("Outside-readiness request accounting changed");
  if (study.control_rows.length !== EXPECTED.controls) fail("Outside-readiness control row count changed");
  if (study.control_rows.some((row) => row.complete !== true || row.released !== true ||
      row.pre_build_index !== row.effective_build_index)) fail("Outside-readiness control arithmetic changed");
  if (tally(study.control_rows, "complete") !== EXPECTED.controls || tally(study.control_rows, "released") !== EXPECTED.controls)
    fail("Outside-readiness control completion changed");
  if (study.controls.openings !== 2 || study.controls.requests !== EXPECTED.controls ||
      study.controls.successes !== 6 || study.controls.failures !== 6 ||
      study.controls.pre_equals_effective !== EXPECTED.controls ||
      study.controls.owned_processes !== EXPECTED.processes ||
      study.controls.owned_processes_gone !== EXPECTED.processes ||
      study.controls.inventories_per_opening !== 3 || study.controls.inventory.files !== EXPECTED.inventory_files)
    fail("Outside-readiness control summary changed");
  for (const case_ of evaluation.controls) {
    if (case_.inventory_files !== EXPECTED.inventory_files || case_.inventory_roots !== EXPECTED.inventory_roots ||
        case_.plugins.length !== EXPECTED.plugins || case_.assemblies !== EXPECTED.assemblies ||
        case_.opening_graph_sha256 !== case_.post_graph_sha256)
      fail(`${case_.case_id}: control opening context changed`);
    if (Object.values(case_.cleanup).some((record) => record.gone !== true))
      fail(`${case_.case_id}: an owned process is not gone`);
  }
  if (study.observation_windows.length !== 2) fail("Outside-readiness observation windows changed");
  for (const window of study.observation_windows) {
    if (!window.started_at || !window.finished_at || window.started_at >= window.finished_at)
      fail("Outside-readiness observation window changed");
  }
  if (study.verification.tests !== EXPECTED.tests || study.verification.retained_byte_replay !== true)
    fail("Outside-readiness verification summary changed");
  if (!study.limits.includes("Unknown") || !study.limits.includes("not estimable") ||
      !study.limits.includes("never 0%") || !study.limits.includes("not a qualification"))
    fail("Outside-readiness limits lost a bound");

  const summary = {
    kind: study.kind,
    study: study.study,
    source_commit: source.publication_commit,
    source_base: source.publication_base,
    frozen_commit: source.frozen_commit,
    internal_merge: source.internal_merge,
    source_issue: source.source_issue,
    pull_request: source.pull_request,
    publication_files: closure.publication_files,
    copied_files: closure.copied_files,
    linked_files: closure.linked_files,
    raw_files: study.raw_manifest.length,
    raw_copied_files: study.raw.length,
    module_version: source.module.version,
    module_members: source.module.members,
    projection_file: OUTSIDE_READINESS_PROJECTION,
    projection_sha256: projectionSha,
    projection_tool_file: OUTSIDE_READINESS_TOOL,
    source_manifest_file: OUTSIDE_READINESS_SOURCES,
    source_manifest_sha256: OUTSIDE_READINESS_SOURCES_SHA,
    result: study.result,
    holdout: { planned: holdout.planned, observed: holdout.observed, unknown: holdout.unknown },
    controls: {
      openings: study.controls.openings,
      requests: study.controls.requests,
      successes: study.controls.successes,
      failures: study.controls.failures,
      pre_equals_effective: study.controls.pre_equals_effective,
      owned_processes_gone: study.controls.owned_processes_gone,
      inventories_per_opening: study.controls.inventories_per_opening,
      inventory_files: study.controls.inventory.files,
    },
    freeze: {
      source_files: study.freeze.source_files,
      source_sha256: study.freeze.source_sha256,
      contract_source_files: study.freeze.contract_source_files.length,
      contract_source_sha256: study.freeze.contract_source_sha256,
      git_commit_at_freeze: study.freeze.git_commit_at_freeze,
      old_fact_count: study.freeze.old_fact_count,
      old_publication_files: study.freeze.old_publication_files,
      readiness_files: study.freeze.readiness_files,
    },
    readiness: {
      ready_for_measurement: readiness.ready_for_measurement,
      reasons: readiness.reasons,
      missing_native_fact: readiness.missing_native_fact,
    },
    selection: {
      packages: study.selection.selected.length,
      pool: study.selection.pool,
      covered_cells: study.selection.covered_cells.length,
      missing_cells: study.selection.missing_cells.length,
      file: study.selection.selected[0].file,
    },
    verification: {
      tests: study.verification.tests,
      check_study_verify: study.verification.check_study_verify,
      fresh_clone_limit: study.verification.fresh_clone_limit,
      retained_byte_replay: study.verification.retained_byte_replay,
    },
    observation_windows: study.observation_windows,
    evidence_files_sha256: study.evidence_sha256,
    linked_files_sha256: study.linked_sha256,
    raw_manifest_sha256: study.raw_manifest_sha256,
    raw_evidence_sha256: study.raw_evidence_sha256,
    certificates: "none",
  };
  summary.projection_tool_sha256 = OUTSIDE_READINESS_TOOL_SHA;
  return { projection, study, summary, sha: projectionSha };
}

/** The ledger keeps only this derived summary, never the rows themselves. */
export function validateOutsideReadiness(ledger, load = read) {
  const { study, summary } = outsideReadiness(load);
  if (!isDeepStrictEqual(ledger.outside_readiness_studies, summary))
    fail("Outside-readiness projection is stale or unbound in the ledger");
  for (const id of MODES) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    if (!isDeepStrictEqual(capability?.outside_readiness_studies, [OUTSIDE_READINESS_STUDY]))
      fail(`${id} does not reference the outside-readiness study`);
    if (!isDeepStrictEqual(capability?.outside_stock_studies, ["outside-stock-budget-v1"]))
      fail(`${id} lost its sibling outside-stock reference`);
    if (!isDeepStrictEqual(capability?.outside_research_studies, ["outside-query-model-v1"]))
      fail(`${id} lost its sibling outside-query reference`);
  }
  for (const other of ledger.capabilities.filter((entry) => !MODES.includes(entry.id))) {
    if (other.outside_readiness_studies) fail(`${other.id} references outside-readiness evidence it does not own`);
  }
  if ((ledger.native_path_certificates ?? []).some((certificate) => certificate.study === OUTSIDE_READINESS_STUDY))
    fail("An outside-readiness native certificate exists; this study is evidence only");
  if (ledger.evidence_studies?.[OUTSIDE_READINESS_STUDY]) fail("The study was registered as a native study");
  if ((ledger.native_path_certificates ?? []).length !== 4) fail("The retained native certificate set changed");
  if (study.evidence_only !== true) fail("The study is not evidence only");
  return summary;
}

const table = (escape, heads, rows, attrs = "") =>
  `<div class="ledger-table"><table ${attrs}><thead><tr>${heads.map((head) => `<th scope="col">${escape(head)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((row) => `<tr>${row.map((value, index) => `<${index ? "td" : "th"}${index ? "" : ' scope="row"'}>${escape(value)}</${index ? "td" : "th"}>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;

const detail = (escape, title, value) =>
  `<details><summary>${escape(title)}</summary><pre>${escape(JSON.stringify(value, null, 2))}</pre></details>`;

const num = (value) => Number(value).toLocaleString("en-US");
const label = (value) => (value === null || value === undefined ? "Unknown" : value);

function sourceBlock(escape, study) {
  const source = study.source;
  return `<dl>
    <dt>Publication</dt><dd><code>${escape(source.publication_commit)}</code> on base <code>${escape(source.publication_base)}</code>, PR #${escape(String(source.pull_request))}; internal merge <code>${escape(source.internal_merge)}</code>. The source is the publication commit, not that merge.</dd>
    <dt>Freeze</dt><dd>The pre-control freeze is <code>${escape(source.frozen_commit)}</code>; the frozen plan records commit <code>${escape(study.freeze.git_commit_at_freeze)}</code> at <code>${escape(study.freeze.frozen_at)}</code>. Observation dates below come from the dated raw context, never from this freeze time.</dd>
    <dt>Target</dt><dd>Internal <code>${escape(source.target)}</code>; module <code>${escape(study.study)}</code> version ${escape(String(source.module.version))} with ${escape(String(source.module.members))} members.</dd>
    <dt>Source issue</dt><dd>${escape(source.source_issue)}</dd>
    <dt>Review</dt><dd>Independent peer PASS ${escape(source.review.pass)}; parent acceptance ${escape(source.review.acceptance)}. Both record a stopped study, not a validated model.</dd>
    <dt>Native sources</dt><dd>Primary rule <code>lane:any_lane:forbidden</code> and reference <code>weak_component</code> come unchanged from outside-query model <code>${escape(source.native_sources.outside_query_model)}</code>; the exclusion source is <code>${escape(source.native_sources.stock_exclusion_source)}</code>.</dd>
    <dt>File scope</dt><dd>${escape(String(study.closure.publication_files))} publication files: ${escape(String(study.closure.copied_files))} present here byte for byte, ${escape(String(study.closure.linked_files))} linked as an immutable Git blob with its SHA-256 and blob id in <a href="./${escape(OUTSIDE_READINESS_SOURCES)}">the strict source manifest</a>. ${escape(String(study.closure.post_control_files))} files were written after the controls and ${escape(String(study.closure.frozen_changed_files))} changed after the freeze; both sets are named, and the other ${escape(String(study.closure.frozen_publication_files - study.closure.frozen_changed_files))} files are the frozen bytes.</dd>
    <dt>Raw scope</dt><dd>All ${escape(String(study.raw_manifest.length))} retained raw hashes are pinned; ${escape(String(study.raw.length))} small raw files are carried gzip-compressed and decompress to their original bytes. The byte-backed licensed game and CRP evidence stays in the same-owner private blade holding and is not copied here.</dd>
  </dl>`;
}

function holdoutRows(study) {
  return study.holdout.records.map((row) => [
    row.query_id, row.mode, row.class, row.prediction, label(row.status),
  ]);
}

function controlRows(study) {
  return study.control_rows.map((row) => [
    row.case_id, row.mode, row.kind, row.query_id, row.label,
    String(row.flags), yes(row.complete), yes(row.released),
    `${row.pre_build_index} = ${row.effective_build_index}`,
  ]);
}

function windowRows(study) {
  return study.observation_windows.map((window) => [
    window.case_id, window.started_at, window.finished_at, window.source.join(", "),
  ]);
}

function untouchedRows(study) {
  return [
    ["Old accepted facts", String(study.freeze.old_fact_count), "unchanged"],
    ["Old publication files", String(study.freeze.old_publication_files), "unchanged"],
    ["Accepted readiness files", String(study.freeze.readiness_files), "unchanged"],
    ["Retained native path certificates", "4", "unchanged"],
  ];
}

function evidenceList(escape, study) {
  return `<ul>${study.files.map((record) => {
    const relative = record.path.slice(OUTSIDE_READINESS_PREFIX.length);
    const frozen = record.frozen
      ? ` · frozen <code>${escape(record.frozen.sha256)}</code>`
      : " · written after the controls";
    return `<li><a data-evidence href="./${escape(record.path)}" data-sha256="${escape(record.sha256)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · ${escape(record.role)}${frozen}${record.frozen && record.frozen.sha256 !== record.sha256 ? " (changed after the freeze)" : ""}</li>`;
  }).join("")}</ul>`;
}

function linkedList(escape, study) {
  return `<ul>${study.linked.map((record) => {
    const relative = record.path.slice(OUTSIDE_READINESS_PREFIX.length);
    return `<li><a data-linked-evidence href="${escape(OUTSIDE_READINESS_REPO + OUTSIDE_READINESS_PUBLICATION + "/" + record.path)}" data-blob="${escape(record.git_blob)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · Git blob <code>${escape(record.git_blob)}</code> · ${escape(num(record.bytes))} bytes · ${escape(record.role)}. Frozen record pinned, bulk bytes served at the publication commit.</li>`;
  }).join("")}</ul>`;
}

function rawList(escape, study) {
  return `<ul>${study.raw.map((record) => {
    const relative = record.path.slice(OUTSIDE_READINESS_PREFIX.length);
    return `<li><a data-raw-evidence href="./${escape(record.path)}" data-sha256="${escape(record.sha256)}" data-raw-sha256="${escape(record.raw_sha256)}">${escape(relative)}</a> · gzip <code>${escape(record.sha256)}</code> · decompresses to <code>${escape(record.raw_sha256)}</code> · ${escape(record.role)}</li>`;
  }).join("")}</ul>`;
}

/** The one study, rendered in one place, referenced from Road, Ship and Air. */
export function outsideReadinessPage({ study }, escape) {
  const stopped = study.readiness.reasons;
  return `<article id="outside-readiness-study" data-outside-readiness>
    <div class="ledger-title"><h2>Outside-query controls on a frozen unseen cohort — Unknown</h2><span>research only · evidence</span></div>
    <p class=note>One stopped control-readiness study, referenced from Road, Ship and Air. It is evidence only: not the current runtime estimate above, not a qualification, not pooled with the outside-query, outside-stock, rail or native studies, not a holdout vote, not an admission repair, not a new calibration score and not activation. Controls are known controls; they do not become capability votes.</p>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study)}
    <p>${escape(study.method)}</p>

    <h3>Outcome · Unknown</h3>
    <div class="ledger-table"><table data-outside-readiness-outcome><thead><tr><th scope="col">Planned holdout cells</th><th scope="col">Observed</th><th scope="col">Unknown</th><th scope="col">Accuracy</th><th scope="col">Precision</th><th scope="col">Recall</th></tr></thead><tbody><tr><th scope="row">PL Cavern Coast.crp</th><td>0 of 6</td><td>6 of 6</td><td>not estimable</td><td>not estimable</td><td>not estimable</td></tr></tbody></table></div>
    <p><strong>Zero of six planned holdout requests were issued.</strong> No holdout accuracy, precision or recall exists; those denominators stay null and <strong>not estimable</strong>, never 0%. Predictions of success or no_path are input hypotheses, not native labels.</p>
    ${table(escape, ["Planned cell", "Mode", "Class", "Prediction", "Status"], holdoutRows(study), "data-outside-readiness-holdout")}
    <p>${escape(study.stopped)}</p>
    <div class="ledger-table"><table data-outside-readiness-digests><thead><tr><th scope="col">Binding</th><th scope="col">Files</th><th scope="col">Digest</th><th scope="col">What it is</th></tr></thead><tbody>
      <tr><th scope="row">Frozen study tree</th><td>${escape(String(study.freeze.source_files))}</td><td><code>${escape(study.freeze.source_sha256)}</code></td><td>The frozen freeze.json manifest the collector actually recorded.</td></tr>
      <tr><th scope="row">Required contract closure</th><td>${escape(String(study.freeze.contract_source_files.length))}</td><td><code>${escape(study.freeze.contract_source_sha256)}</code></td><td>The versioned accepted closure; every one of its files is present in the frozen tree with the same hash.</td></tr>
      <tr><th scope="row">Runtime policy</th><td>82</td><td><code>${escape(study.bundle.policy_source_sha256)}</code></td><td>The measured opening recorded the study-tree digest, so it cannot equal the contract closure.</td></tr>
    </tbody></table></div>
    <p>The first frozen bundle read named the 82-file tree, not the 30-file closure. A post-control assembler then rebuilt the bundle from the frozen facts with the contract-exact closure and stopped at the same structural point. Both digests and both reads stay recorded; the projection is not a new freeze and not an admission repair.</p>

    <h3>What did survive · the corrected controls</h3>
    ${table(escape, ["Opening", "Mode", "Kind", "Query", "Label", "Flags", "Complete", "Released", "Build index pre = effective"], controlRows(study), "data-outside-readiness-controls")}
    <p>${escape(study.survives)}</p>
    <p>Each opening's phase inventory records ${escape(String(study.controls.inventory.files))} files, ${escape(String(study.controls.inventory.roots))} roots, ${escape(String(study.controls.inventory.plugins))} plugins and ${escape(String(study.controls.inventory.assemblies))} assemblies; three identical inventories per opening. The ${escape(String(study.controls.owned_processes))} owned game/driver/collector/auditor/monitor PID/start identities are gone after the driver exited, verified by a post-exit audit. The frozen driver could not attest its own absence; that post-exit audit closes cleanup only, not source binding.</p>

    <h3>Frozen selection</h3>
    <p>Rule <code>${escape(study.selection.rule)}</code> over ${escape(String(study.selection.pool))} previously unqueried eligible packages, capped at three. One package covered all ${escape(String(study.selection.covered_cells.length))} mode/class cells with none missing, so selection stopped there.</p>
    ${table(escape, ["Selected package", "SHA-256", "Pool", "Covered cells", "Missing cells"], study.selection.selected.map((row) => [row.file, row.sha256, String(study.selection.pool), String(study.selection.covered_cells.length), String(study.selection.missing_cells)]), "data-outside-readiness-selection")}
    <p>Predicted cells: ${escape(study.selection.covered_cells.join(", "))}. All remain Unknown; no substitute package, retry or budget sweep was made.</p>

    <h3>Observation windows</h3>
    ${table(escape, ["Opening", "Recorded start", "Recorded finish", "Dated raw context"], windowRows(study), "data-outside-readiness-windows")}
    <p>These are the recorded driver start and post-exit auditor finish times from the retained raw context. They are separate from the freeze time and the publication time.</p>

    <h3>Verification and what it does not prove</h3>
    <p>The accepted head ran ${escape(String(study.verification.tests))} retained tests green under peer review and acceptance. <code>check_study.py verify</code> passes in the original producer build context only: a fresh clone expects the untracked <code>.build/Cs1Harness.dll</code> and the original absolute staged-source path, so a fresh clone cannot reproduce the full verify. The retained-byte acceptance replay checks ${escape(String(study.raw_manifest.length))} raw hashes, the built DLL SHA-256 and MVID, and all ${escape(String(study.controls.owned_processes))} owned PID/start chains without rebuilding; the parent replayed it independently.</p>
    <p>The DLL is <code>${escape(study.freeze.dll.sha256)}</code> with MVID <code>${escape(study.freeze.dll.mvid)}</code>. File identity is not memory attestation, compiler trust, host quiescence or a strict no-mod claim; the retained plugin, dynamic-exclusion and DLC serialization facts stay limits.</p>

    <h3>Unchanged bindings</h3>
    ${table(escape, ["Binding", "Count", "State"], untouchedRows(study), "data-outside-readiness-untouched")}
    <p>The old PL-1294 study's six Unknowns stay Unknown, and the new controls do not rescue them. No old label, old fact, old publication file or accepted readiness file changed.</p>

    <h3>Limits</h3>
    <p>${escape(study.limits)}</p>

    <details><summary>Carried evidence · ${escape(String(study.files.length))} files served byte for byte</summary>${evidenceList(escape, study)}</details>
    <details><summary>Linked source · ${escape(String(study.linked.length))} immutable blob at the publication commit</summary>${linkedList(escape, study)}</details>
    <details><summary>Retained raw context · ${escape(String(study.raw.length))} small files served gzip-compressed</summary>${rawList(escape, study)}</details>
    <details><summary>All ${escape(String(study.raw_manifest.length))} retained raw hashes</summary>
      ${table(escape, ["Raw file", "SHA-256"], study.raw_manifest.map((row) => [row.path, row.sha256]), "data-outside-readiness-raw")}
      <p>The other ${escape(String(study.raw_manifest.length - study.raw.length))} raw files stay in the same-owner private blade holding. Their hashes are recorded here; the bytes are not copied into this repository or attached to the issue.</p></details>
    <details><summary>Frozen protocol, stop policy and both source digests</summary>${detail(escape, "Recorded freeze as data", {
      publication: study.source.publication_commit,
      publication_base: study.source.publication_base,
      frozen_commit: study.source.frozen_commit,
      git_commit_at_freeze: study.freeze.git_commit_at_freeze,
      frozen_at: study.freeze.frozen_at,
      protocol: study.freeze.protocol,
      stop_policy: study.freeze.stop_policy,
      source_sha256: study.freeze.source_sha256,
      contract_source_sha256: study.freeze.contract_source_sha256,
      runtime_policy_source_sha256: study.bundle.policy_source_sha256,
      readiness: study.readiness,
    })}</details>
    <p class=note>${escape(study.limits)}</p></article>`;
}

/** A compact reference from one capability to the single shared study. */
export function outsideReadinessReference(capability, { study }, escape) {
  const head = `${capability[0].toUpperCase()}${capability.slice(1)}`;
  const cells = CELLS.filter((cell) => cell.startsWith(`${capability}:`));
  const controlMode = study.control_rows.filter((row) => row.mode === capability);
  const successes = controlMode.filter((row) => row.label === "success").length;
  const failures = controlMode.filter((row) => row.label === "no_path").length;
  return `<h3>Outside-query controls on a frozen unseen cohort — Unknown</h3>
    <p>${escape(head)} has ${escape(String(cells.length))} planned holdout cells (${escape(cells.join(", "))}), and <strong>zero</strong> were issued. Both stay <strong>Unknown</strong>. The ${escape(String(controlMode.length))} ${escape(capability)} control requests returned ${escape(String(successes))} expected successes and ${escape(String(failures))} expected invalid-vehicle failures, but controls are not holdout predictions and not independent capability votes.
    <a href="#outside-readiness-study">The one study, its refusal chain, controls, raw hashes and limits</a>.
    It is evidence only: not qualification, not an accuracy figure, not a geographic "no" and not a promise.</p>`;
}
