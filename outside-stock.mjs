// One accepted outside-stock and road-budget publication, read from archived bytes only.
//
// This module never runs the study's frozen scorer, its post-control scorer, the
// audit, a collector, the game or a browser. It re-checks the projection, its
// manifest and every carried evidence byte, re-derives the compact stock tables
// from the saved rows, and renders the one study under Road, Ship and Air. It is
// a distinct typed study: not pooled with the outside-query, rail or native
// studies, not a qualification, promise, certificate or live rule.
import { createHash } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { isDeepStrictEqual } from "node:util";

const ROOT = fileURLToPath(new URL(".", import.meta.url));
const sha = (bytes) => createHash("sha256").update(bytes).digest("hex");
const read = (file) => readFileSync(ROOT + file);

export const OUTSIDE_STOCK_STUDY = "outside-stock-budget-v1";
export const OUTSIDE_STOCK_PROJECTION = "tools/map-factory/capability-evidence/outside-stock-studies.json";
export const OUTSIDE_STOCK_PROJECTION_SHA = "b86d1fd861cff3ffe6ec821205c9f654b83f3ca524e8530d65c24118e3ea44eb";
export const OUTSIDE_STOCK_TOOL = "tools/map-factory/integrate_outside_stock.py";
export const OUTSIDE_STOCK_TOOL_SHA = "96fac4e2bdfa295ba872c8d177ca7dc047700f31ce18387da7ef8f018f3a46f0";
export const OUTSIDE_STOCK_SOURCES = "tools/map-factory/capability-evidence/outside-stock-sources.json";
export const OUTSIDE_STOCK_SOURCES_SHA = "9e8ba66a3dd4bb5d4a7f475119b2f0e056c6a80a6e1a4dd8b19fec7e8e2aef85";
export const OUTSIDE_STOCK_PREFIX = "tools/map-factory/capability-evidence/";
export const OUTSIDE_STOCK_PUBLICATION = "d745b14e3e207ee67f91033811958a2934fb38a4";
export const OUTSIDE_STOCK_REPO = "https://github.com/frontierkodiak/region-to-skylines/blob/";

const MODES = ["road", "ship", "air"];
const PRIMARY = "lane:any_lane:forbidden";
const REFERENCE = "weak_component";
const BUDGETS = [100000, 200000, 1000000];
const FROZEN_PLAN_SHA256 = "717f6c0335f4558c77d2d23b4b1181a540f70ca21779365eeae6939c8c1ef3c8";

const EXPECTED = {
  kind: "outside_stock_budget_study",
  publication_files: 142,
  copied_files: 32,
  linked_files: 110,
  integrity_members: 141,
  population: {
    installed: 105,
    excluded_packages: 13,
    excluded_hashes: 21,
    eligible: 92,
    supported: 28,
    abstaining: 64,
    decode_errors: 23,
  },
  selected: { holdout: 48, control: 12, intervention: 24 },
  requested_packages: 3,
  metadata_only_packages: 2,
  requests: 84,
  observed: 78,
  unknown: 6,
  stock: 48,
  primary: { road: [12, 0, 12, 0], ship: [8, 0, 4, 0], air: [8, 0, 4, 0] },
  primary_total: [28, 0, 20, 0],
  weak: { road: [12, 12, 0, 0], ship: [8, 0, 4, 0], air: [8, 0, 4, 0] },
  subset: 16,
  subset_primary: [8, 0, 8, 0],
  subset_reference: [8, 8, 0, 0],
  subset_not_matched: 32,
  disagreements: 12,
  height_drift: { "holdout-01": 33.029134, "holdout-02": 161.935462, "holdout-03": 8.026451 },
  roslyn_prefabs: 4,
  pre_post_changes: 3,
  reported_fingerprint_mismatches: 17,
  rederived_fingerprint_mismatches: 18,
  controls: { planned: 12, unknown: 6, completed: 6 },
  intervention: { groups: 8, rows: 24, clean: 7, drifting: 1 },
  runtime: { openings: 9, phases: 25, identities: 45, receipts: 9, windows: 9 },
  groups: 40,
  strata: 6,
  tags: 6,
};

const fail = (message) => {
  throw new Error(message);
};

const tally = (rows, rule) => {
  const counts = { tp: 0, fp: 0, tn: 0, fn: 0 };
  for (const row of rows) {
    const prediction = row[rule];
    const label = row.label;
    if (prediction === "success" && label === "success") counts.tp += 1;
    else if (prediction === "success" && label === "no_path") counts.fp += 1;
    else if (prediction === "no_path" && label === "no_path") counts.tn += 1;
    else if (prediction === "no_path" && label === "success") counts.fn += 1;
  }
  return [counts.tp, counts.fp, counts.tn, counts.fn];
};

const countsKey = (record) => [record.tp, record.fp, record.tn, record.fn];

/** Every repo-relative file the page serves for this study, plus its projection. */
export function outsideStockFiles(study) {
  const files = [OUTSIDE_STOCK_PROJECTION, OUTSIDE_STOCK_SOURCES];
  for (const record of (study ?? outsideStock().study).files) files.push(record.path);
  return [...new Set(files)];
}

/**
 * Re-check the projection, its tool and its source manifest, then every carried
 * evidence byte and every declaration it publishes. A changed byte anywhere
 * fails before the page is built.
 */
export function outsideStock(load = read) {
  if (sha(load(OUTSIDE_STOCK_TOOL)) !== OUTSIDE_STOCK_TOOL_SHA) fail("Outside-stock projection tool changed");
  if (sha(load(OUTSIDE_STOCK_SOURCES)) !== OUTSIDE_STOCK_SOURCES_SHA) fail("Outside-stock source manifest changed");
  const bytes = load(OUTSIDE_STOCK_PROJECTION);
  const projectionSha = sha(bytes);
  if (projectionSha !== OUTSIDE_STOCK_PROJECTION_SHA) fail("Outside-stock projection changed");
  const projection = JSON.parse(bytes.toString("utf8"));
  if (projection.schema !== 1) fail("Outside-stock projection header changed");
  if (JSON.stringify(Object.keys(projection.studies)) !== JSON.stringify([OUTSIDE_STOCK_STUDY]))
    fail("Outside-stock projection is not the one accepted publication");
  const study = projection.studies[OUTSIDE_STOCK_STUDY];
  const manifest = JSON.parse(load(OUTSIDE_STOCK_SOURCES).toString("utf8"));
  const publication = manifest.publications?.[OUTSIDE_STOCK_STUDY];
  if (!publication) fail("Outside-stock source manifest lost its publication");
  if (projection.source_manifest.file !== OUTSIDE_STOCK_SOURCES ||
      projection.source_manifest.sha256 !== OUTSIDE_STOCK_SOURCES_SHA ||
      projection.source_manifest.commit !== OUTSIDE_STOCK_PUBLICATION)
    fail("Outside-stock projection does not bind the carried source manifest");
  if (publication.commit !== OUTSIDE_STOCK_PUBLICATION) fail("Outside-stock source manifest names another publication");

  if (study.study !== OUTSIDE_STOCK_STUDY || study.kind !== EXPECTED.kind) fail("Outside-stock study identity changed");
  if (study.evidence_only !== true || study.certificates !== "none") fail("Outside-stock study is not evidence only");
  const source = study.source;
  if (source.publication_commit !== OUTSIDE_STOCK_PUBLICATION ||
      source.publication_base !== "030db86ce470b972b6ef3462a2698744dff40ebb" ||
      source.accepted_base !== "030db86ce470b972b6ef3462a2698744dff40ebb" ||
      source.internal_merge !== "62b48a01a195f7632747fe52c72b348539dc7f8a" ||
      source.pull_request !== 89 || source.branch !== "PL-1294-stock-budget" ||
      source.source_issue !== "01a20799-865c-75cc-bdc1-05a81193aff4")
    fail("Outside-stock source identity changed");
  if (!isDeepStrictEqual(source.review, {
    pass: "01a2086c-06d0-7461-9bf1-65fbd1b478d2",
    engineering_note: "01a2086a-f275-7104-87a9-8215b81a07e9",
    parent_acceptance: "01a20870-8dad-7705-8ab8-c81868a3e7d1",
  })) fail("Outside-stock review record changed");
  if (source.history?.superseded_head !== "7b5b4ab4214cd6027844dd7ed7f13cd414ab69e0")
    fail("Outside-stock study lost its rejected earlier head");
  if (!isDeepStrictEqual(source.native_sources, {
    outside_query_model: "030db86ce470b972b6ef3462a2698744dff40ebb",
    stock_holdout_catalog: "914c153687106197e5f3a745d3ff7e181181ea8a",
  })) fail("Outside-stock native sources changed");

  const closure = study.closure;
  if (closure.publication_files !== EXPECTED.publication_files ||
      closure.copied_files !== EXPECTED.copied_files ||
      closure.linked_files !== EXPECTED.linked_files ||
      closure.integrity_members !== EXPECTED.integrity_members ||
      closure.commit !== OUTSIDE_STOCK_PUBLICATION ||
      closure.prefix !== `${OUTSIDE_STOCK_PREFIX}${OUTSIDE_STOCK_STUDY}`)
    fail("Outside-stock publication file scope changed");
  const publicationFiles = Object.keys(publication.files);
  const copiedRelative = study.files.map((record) => record.path.slice(closure.prefix.length + 1)).sort();
  const linkedRelative = study.linked.map((record) => record.path.slice(closure.prefix.length + 1)).sort();
  if (publicationFiles.length !== EXPECTED.publication_files ||
      publication.copied.length !== EXPECTED.copied_files ||
      publication.linked.length !== EXPECTED.linked_files ||
      JSON.stringify([...publication.copied].sort()) !== JSON.stringify(copiedRelative) ||
      JSON.stringify([...publication.linked].sort()) !== JSON.stringify(linkedRelative) ||
      publication.integrity_file !== "integrity.json")
    fail("Outside-stock source manifest file split changed");

  // Carried bytes: exactly the publication's present files, hashed in place.
  if (!Array.isArray(study.files) || study.files.length !== EXPECTED.copied_files)
    fail("Outside-stock carried evidence count changed");
  for (const record of study.files) {
    if (!record.path.startsWith(`${OUTSIDE_STOCK_PREFIX}${OUTSIDE_STOCK_STUDY}/`))
      fail("Outside-stock carried evidence outside the study prefix");
    if (!/^[a-f0-9]{64}$/.test(record.sha256 ?? "") || !/^[a-f0-9]{40}$/.test(record.git_blob ?? ""))
      fail(`${record.path}: carried evidence lacks a hash`);
    const raw = load(record.path);
    if (raw.length !== record.bytes || sha(raw) !== record.sha256)
      fail(`Outside-stock carried evidence changed: ${record.path}`);
    const published = publication.files[record.path.slice(closure.prefix.length + 1)];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob ||
        published.bytes !== record.bytes)
      fail(`${record.path}: carried evidence does not match the source manifest`);
  }
  const present = new Set(study.files.map((record) => record.path));
  for (const path of study.documents) {
    if (!present.has(`${closure.prefix}/${path}`)) fail("Outside-stock study lost a carried document");
  }

  // Linked bulk members: pinned, corroborated where a carried record exists, and never served.
  if (!Array.isArray(study.linked) || study.linked.length !== EXPECTED.linked_files)
    fail("Outside-stock linked source count changed");
  for (const record of study.linked) {
    const relative = record.path.slice(closure.prefix.length + 1);
    const published = publication.files[relative];
    if (!published || published.sha256 !== record.sha256 || published.git_blob !== record.git_blob ||
        published.bytes !== record.bytes)
      fail(`${record.path}: linked source does not match the source manifest`);
    if (!Array.isArray(record.declared_by) || record.declared_by.length < 1)
      fail(`${record.path}: linked source is not declared by a carried document`);
    if (record.corroborated !== (record.declared_by.length >= 2))
      fail(`${record.path}: linked corroboration flag disagrees with its declarations`);
    if (existsSync(ROOT + record.path)) fail(`${record.path}: a linked file is duplicated in the repository`);
  }
  if (study.linked.filter((record) => !record.corroborated).length !== 4)
    fail("Outside-stock linked single-declaration set changed");

  // Population, requests and the qualified status.
  if (!isDeepStrictEqual(study.population.counts, EXPECTED.population))
    fail("Outside-stock population changed");
  if (Object.keys(study.population.excluded_hashes).length !== EXPECTED.population.excluded_hashes)
    fail("Outside-stock exclusion hash set changed");
  if (study.population.selection.requested_packages !== EXPECTED.requested_packages ||
      study.population.selection.metadata_only_packages !== EXPECTED.metadata_only_packages)
    fail("Outside-stock package selection changed");
  for (const [case_, record] of Object.entries(study.population.selection.cases)) {
    if (record.supported && record.requests === 0) fail(`${case_}: supported package lost its requests`);
    if (!record.supported && record.requests !== 0) fail(`${case_}: unsupported package gained requests`);
  }
  const requests = study.requests;
  if (requests.planned !== EXPECTED.requests || requests.observed !== EXPECTED.observed ||
      requests.unknown !== EXPECTED.unknown ||
      !isDeepStrictEqual(requests.by_kind, EXPECTED.selected) ||
      requests.records.length !== EXPECTED.requests)
    fail("Outside-stock request accounting changed");
  const unknown = requests.records.filter((record) => !record.observed);
  if (unknown.length !== EXPECTED.unknown || unknown.some((record) => record.kind !== "control" || record.case_id !== "stock-1"))
    fail("Outside-stock Unknown controls changed");
  if (requests.records.some((record) => !["success", "no_path", "unknown"].includes(record.label)))
    fail("Outside-stock request label set changed");
  if (requests.records.some((record) => !record.observed && record.label !== "unknown"))
    fail("Outside-stock unobserved request is not Unknown");
  const ids = new Set(requests.records.map((record) => record.id));
  if (ids.size !== EXPECTED.requests) fail("Outside-stock planned request IDs are not unique");

  // Re-derive the stock tables from the saved rows.
  const rows = study.stock.rows;
  if (!Array.isArray(rows) || rows.length !== EXPECTED.stock) fail("Outside-stock saved row count changed");
  if (new Set(rows.map((row) => row.id)).size !== EXPECTED.stock) fail("Outside-stock saved rows are not unique");
  for (const row of rows) {
    if (!MODES.includes(row.mode)) fail(`${row.id}: unknown mode`);
    if (!["success", "no_path"].includes(row.primary) || !["success", "no_path"].includes(row.reference))
      fail(`${row.id}: a saved prediction is not a label`);
    if (!["success", "no_path"].includes(row.label)) fail(`${row.id}: a saved label is not a label`);
    if (!Array.isArray(row.tags) || !row.tags.length) fail(`${row.id}: a saved row lost its selection tags`);
  }
  for (const mode of MODES) {
    const selected = rows.filter((row) => row.mode === mode);
    if (JSON.stringify(tally(selected, "primary")) !== JSON.stringify(EXPECTED.primary[mode]))
      fail(`Outside-stock ${mode} primary confusion changed`);
    if (JSON.stringify(tally(selected, "reference")) !== JSON.stringify(EXPECTED.weak[mode]))
      fail(`Outside-stock ${mode} reference confusion changed`);
    if (JSON.stringify(countsKey(study.stock.primary[mode])) !== JSON.stringify(EXPECTED.primary[mode]))
      fail(`Outside-stock ${mode} projection table disagrees with its rows`);
    if (JSON.stringify(countsKey(study.stock.reference[mode])) !== JSON.stringify(EXPECTED.weak[mode]))
      fail(`Outside-stock ${mode} reference table disagrees with its rows`);
  }
  if (JSON.stringify(tally(rows, "primary")) !== JSON.stringify(EXPECTED.primary_total))
    fail("Outside-stock primary total changed");
  const subset = rows.filter((row) => row.snapshot_matched);
  if (subset.length !== EXPECTED.subset ||
      JSON.stringify(tally(subset, "primary")) !== JSON.stringify(EXPECTED.subset_primary) ||
      JSON.stringify(tally(subset, "reference")) !== JSON.stringify(EXPECTED.subset_reference))
    fail("Outside-stock strict bridge subset changed");
  if (study.bridge.subset.requests !== EXPECTED.subset ||
      study.bridge.subset.not_matched !== EXPECTED.subset_not_matched ||
      JSON.stringify(countsKey(study.bridge.subset.primary)) !== JSON.stringify(EXPECTED.subset_primary) ||
      JSON.stringify(countsKey(study.bridge.subset.reference)) !== JSON.stringify(EXPECTED.subset_reference))
    fail("Outside-stock bridge subset summary changed");
  const disagreements = rows.filter((row) => row.label !== "unknown" && row.primary !== row.label);
  if (disagreements.length !== 0) fail("Outside-stock primary now disagrees with a stock label");
  const referenceDisagreements = rows.filter((row) => row.label !== "unknown" && row.reference !== row.label);
  if (referenceDisagreements.length !== EXPECTED.disagreements ||
      referenceDisagreements.some((row) => row.mode !== "road"))
    fail("Outside-stock reference disagreements changed");
  for (const [key, record] of Object.entries(study.stock.package_mode)) {
    const selected = rows.filter((row) => `${row.case_id}/${row.mode}` === key);
    if (record.n !== selected.length ||
        JSON.stringify([record.TP, record.FP, record.TN, record.FN]) !== JSON.stringify(tally(selected, "primary")))
      fail(`Outside-stock package-mode table disagrees with its rows: ${key}`);
  }
  for (const mode of MODES) {
    const one = study.stock.one_class[mode].packages.slice().sort();
    const expected = Object.entries(study.stock.package_mode)
      .filter(([key, record]) => key.endsWith(`/${mode}`) && record.absent_class_power)
      .map(([key]) => key.split("/")[0]).sort();
    if (JSON.stringify(one) !== JSON.stringify(expected)) fail(`Outside-stock ${mode} one-class packages changed`);
  }
  if (Object.values(study.stock.qualified_modes).some((value) => value !== false))
    fail("Outside-stock study claims a qualified mode");
  if (Object.keys(study.stock.package_mode).length !== 9) fail("Outside-stock package-mode group set changed");
  if (Object.keys(study.stock.groups).length !== EXPECTED.groups) fail("Outside-stock metric group set changed");
  if (Object.keys(study.stock.selection_strata).length !== EXPECTED.strata) fail("Outside-stock stratum set changed");
  if (Object.keys(study.stock.selection_tags).length !== EXPECTED.tags) fail("Outside-stock selection tag set changed");
  const tagTotal = Object.values(study.stock.selection_tags).reduce((total, value) => total + value, 0);
  if (tagTotal <= EXPECTED.stock) fail("Outside-stock selection tags no longer overlap");

  // Controls, intervention, drift, bridge and runtime.
  if (study.controls.all_controls_complete !== false || study.controls.hanami_complete !== true)
    fail("Outside-stock control completion changed");
  if (study.controls.cases["stock-1"].planned + study.controls.cases["stock-2"].planned !== EXPECTED.controls.planned ||
      study.controls.cases["stock-1"].observed !== 0 ||
      study.controls.cases["stock-2"].observed !== EXPECTED.controls.completed)
    fail("Outside-stock control rows changed");
  for (const mode of MODES) {
    if (study.controls.modes[mode].qualified !== false) fail(`Outside-stock ${mode} control is qualified`);
  }
  if (study.intervention.groups.length !== EXPECTED.intervention.groups ||
      study.intervention.groups.reduce((total, group) => total + group.rows.length, 0) !== EXPECTED.intervention.rows ||
      study.intervention.cohort.clean_single_variable_trials !== EXPECTED.intervention.clean ||
      study.intervention.cohort.drifting_groups !== EXPECTED.intervention.drifting ||
      study.intervention.error_mechanisms !== "unknown")
    fail("Outside-stock intervention changed");
  for (const group of study.intervention.groups) {
    if (JSON.stringify(group.rows.map((row) => row.budget)) !== JSON.stringify(BUDGETS))
      fail(`${group.old_query_id}: intervention budgets changed`);
    if (group.old_label === "failure" && group.rows.some((row) => row.label !== "no_path"))
      fail(`${group.old_query_id}: a retained error now resolves`);
    if (group.non_budget_effective_arguments_equal !== true || group.entry_context_unchanged !== true)
      fail(`${group.old_query_id}: a non-budget argument changed`);
    for (const row of group.rows) {
      if (row.budget !== row.effective_max_length) fail(`${group.old_query_id}: the budget was clamped`);
      if (row.label === "no_path" && (row.flags !== 8 || row.returned_length !== row.budget))
        fail(`${group.old_query_id}: the retained sentinel changed`);
    }
  }
  const measured = study.intervention.groups.filter((group) => group.sensitive);
  if (measured.length !== 1 ||
      measured[0].old_query_id !== "hong-kong/native-v2-5/road/167" ||
      JSON.stringify(measured[0].labels) !== JSON.stringify(["no_path", "success", "success"]))
    fail("Outside-stock measured budget response changed");
  const drifted = study.intervention.groups.filter((group) => !group.all_mode_graph_constant);
  if (drifted.length !== 1 || drifted[0].old_query_id !== "pittsburgh/native-v2-6/road/093")
    fail("Outside-stock drifting intervention group changed");
  const million = drifted[0].rows.find((row) => row.budget === 1000000);
  if (!million || million.snapshot_matched !== false) fail("Outside-stock drifting million-budget row claims a per-query snapshot");

  if (JSON.stringify(study.bridge.height_drift) !== JSON.stringify(EXPECTED.height_drift))
    fail("Outside-stock bridge height drift changed");
  if (study.bridge.roslyn_prefabs.length !== EXPECTED.roslyn_prefabs ||
      study.bridge.roslyn_prefabs.some((change) => change.export !== "Highway" || change.native !== "Highway Connection"))
    fail("Outside-stock Roslyn prefab change changed");
  if (study.bridge.horizontal_unchanged !== true ||
      study.bridge.lane_connectivity_invert_outside_mismatches !== 0)
    fail("Outside-stock bridge now reports a horizontal or connection mismatch");
  for (const package_ of ["holdout-01", "holdout-02", "holdout-03"]) {
    const record = study.bridge.packages[package_];
    for (const mode of MODES) {
      const modeRecord = record.modes[mode];
      if (modeRecord.horizontal_equal !== true) fail(`${package_}/${mode}: horizontal coordinates changed`);
      if (["lanes", "invert", "outside", "start", "end"].some((field) => field in modeRecord.fields))
        fail(`${package_}/${mode}: a connection field mismatch appeared`);
    }
  }
  if (study.drift.pre_post_query_changes.length !== EXPECTED.pre_post_changes ||
      study.drift.reported_opening_fingerprint_mismatches !== EXPECTED.reported_fingerprint_mismatches ||
      study.drift.pre_query_opening_fingerprint_mismatches !== EXPECTED.rederived_fingerprint_mismatches)
    fail("Outside-stock opening drift changed");
  if (study.runtime.openings !== EXPECTED.runtime.openings ||
      study.runtime.phase_inventories !== EXPECTED.runtime.phases ||
      study.runtime.process_identities !== EXPECTED.runtime.identities ||
      Object.keys(study.runtime.installed_crp_receipts).length !== EXPECTED.runtime.receipts ||
      study.runtime.observation_windows.length !== EXPECTED.runtime.windows)
    fail("Outside-stock runtime accounting changed");
  if (study.runtime.launch_caption_used_as_evidence !== false) fail("Outside-stock used a stale launch caption");
  if (study.runtime.process_kinds["stock-1"].length !== 5) fail("Outside-stock first-opening auditor chain changed");
  for (const window of study.runtime.observation_windows) {
    if (!window.started_at || window.case_id === undefined || window.started_at === window.finished_at)
      fail("Outside-stock observation window changed");
  }
  if (study.integrity_reconstruction.integrity_members !== EXPECTED.integrity_members ||
      study.integrity_reconstruction.raw_members !== 105)
    fail("Outside-stock integrity reconstruction changed");
  const protocol = study.protocol;
  if (protocol.seed !== 857 || protocol.api !== "PathManager.CreatePath" || protocol.entry !== "NewGameFromMap" ||
      protocol.default_max_length !== 100000 || JSON.stringify(protocol.budgets) !== JSON.stringify(BUDGETS))
    fail("Outside-stock protocol frame changed");
  if (!isDeepStrictEqual(protocol.mode_vehicle, { road: "Car", ship: "Ship", air: "Plane" }) ||
      !isDeepStrictEqual(protocol.category_by_mode, { road: "PassengerCar", ship: "All", air: "All" }) ||
      !isDeepStrictEqual(protocol.lane_types, {
        road: ["Vehicle"],
        ship: ["CargoVehicle", "TransportVehicle", "Vehicle"],
        air: ["CargoVehicle", "TransportVehicle", "Vehicle"],
      }) || protocol.invert_traffic !== false)
    fail("Outside-stock protocol domain changed");
  if (study.runtime.cleanup_note.indexOf("not a description of blade's current") < 0)
    fail("Outside-stock cleanup note claims current host state");
  if (study.schema_repair.repair.body_effective_keys[0] !== "id" ||
      !isDeepStrictEqual(study.schema_repair.repair.transport_required, { ok: true }))
    fail("Outside-stock schema repair changed");
  if (!study.limits.includes("UNQUALIFIED") || !study.limits.includes("Unknown") ||
      !study.limits.includes("not qualification"))
    fail("Outside-stock limits lost a bound");

  const summary = {
    kind: study.kind,
    study: study.study,
    source_commit: source.publication_commit,
    source_base: source.publication_base,
    internal_merge: source.internal_merge,
    source_issue: source.source_issue,
    pull_request: source.pull_request,
    publication_files: closure.publication_files,
    copied_files: closure.copied_files,
    linked_files: closure.linked_files,
    integrity_members: closure.integrity_members,
    projection_file: OUTSIDE_STOCK_PROJECTION,
    projection_sha256: projectionSha,
    projection_tool_file: OUTSIDE_STOCK_TOOL,
    source_manifest_file: OUTSIDE_STOCK_SOURCES,
    source_manifest_sha256: OUTSIDE_STOCK_SOURCES_SHA,
    population: {
      installed: study.population.counts.installed,
      eligible: study.population.counts.eligible,
      supported: study.population.counts.supported,
      abstaining: study.population.counts.abstaining,
      decode_errors: study.population.counts.decode_errors,
      excluded_hashes: study.population.counts.excluded_hashes,
    },
    selected_packages: Object.keys(study.population.selection.cases).length,
    planned_requests: requests.planned,
    observed_requests: requests.observed,
    unknown_requests: requests.unknown,
    stock_requests: study.stock.requests,
    stock_primary: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.stock.total[key]])),
    stock_reference_road: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.stock.reference.road[key]])),
    stock_modes: Object.fromEntries(MODES.map((mode) => [mode, {
      primary: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.stock.primary[mode][key]])),
      reference: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.stock.reference[mode][key]])),
      discrimination_estimable: study.stock.modes[mode].discrimination_estimable,
    }])),
    qualified_modes: { road: false, ship: false, air: false },
    bridge_subset_requests: study.bridge.subset.requests,
    bridge_subset_primary: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.bridge.subset.primary[key]])),
    bridge_subset_reference: Object.fromEntries(["tp", "fp", "tn", "fn"].map((key) => [key, study.bridge.subset.reference[key]])),
    bridge_height_drift: study.bridge.height_drift,
    roslyn_prefab_changes: study.bridge.roslyn_prefabs.length,
    opening_pre_post_changes: study.drift.pre_post_query_changes.length,
    opening_fingerprint_mismatches_reported: study.drift.reported_opening_fingerprint_mismatches,
    controls: {
      planned: study.controls.cases["stock-1"].planned + study.controls.cases["stock-2"].planned,
      unknown: study.controls.cases["stock-1"].planned,
      completed: study.controls.cases["stock-2"].planned,
      all_controls_complete: false,
    },
    intervention: {
      groups: study.intervention.groups.length,
      rows: study.intervention.groups.reduce((total, group) => total + group.rows.length, 0),
      false_positives: study.intervention.cohort.old_false_positives,
      matched_successes: study.intervention.cohort.matched_old_successes,
      clean_single_variable_trials: study.intervention.cohort.clean_single_variable_trials,
      drifting_groups: study.intervention.cohort.drifting_groups,
      measured_response: study.intervention.measured_response.labels,
      error_mechanisms: "unknown",
    },
    runtime: {
      openings: study.runtime.openings,
      phase_inventories: study.runtime.phase_inventories,
      process_identities: study.runtime.process_identities,
      installed_crp_receipts: Object.keys(study.runtime.installed_crp_receipts).length,
    },
    observation_windows: study.runtime.observation_windows,
    evidence_files_sha256: sha(JSON.stringify(study.files.map((record) => [record.path, record.sha256]))),
    linked_files_sha256: sha(JSON.stringify(study.linked.map((record) => [record.path, record.sha256]))),
    certificates: "none",
  };
  summary.projection_tool_sha256 = OUTSIDE_STOCK_TOOL_SHA;
  return { projection, study, summary, sha: projectionSha };
}

/** The ledger keeps only this derived summary, never the rows themselves. */
export function validateOutsideStock(ledger, load = read) {
  const { study, summary } = outsideStock(load);
  if (!isDeepStrictEqual(ledger.outside_stock_studies, summary))
    fail("Outside-stock projection is stale or unbound in the ledger");
  for (const id of MODES) {
    const capability = ledger.capabilities.find((entry) => entry.id === id);
    if (!isDeepStrictEqual(capability?.outside_stock_studies, [OUTSIDE_STOCK_STUDY]))
      fail(`${id} does not reference the outside-stock study`);
    if (!isDeepStrictEqual(capability?.outside_research_studies, ["outside-query-model-v1"]))
      fail(`${id} lost its sibling outside-query reference`);
  }
  for (const other of ledger.capabilities.filter((entry) => !MODES.includes(entry.id))) {
    if (other.outside_stock_studies) fail(`${other.id} references outside-stock evidence it does not own`);
  }
  if ((ledger.native_path_certificates ?? []).some((certificate) => certificate.study === OUTSIDE_STOCK_STUDY))
    fail("An outside-stock native certificate exists; this study is evidence only");
  if (ledger.evidence_studies?.[OUTSIDE_STOCK_STUDY]) fail("The study was registered as a native study");
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
const four = (confusion) => [
  confusion.tp ?? confusion.TP,
  confusion.fp ?? confusion.FP,
  confusion.tn ?? confusion.TN,
  confusion.fn ?? confusion.FN,
];
const pair = (confusion) => {
  const [tp, fp, tn, fn] = four(confusion);
  return `TP ${tp} · FP ${fp} · TN ${tn} · FN ${fn}`;
};
const short = (digest) => `${digest.slice(0, 12)}…`;
const requestText = (record) =>
  record.from && record.to ? `${record.from.join(",")}→${record.to.join(",")}` : "no recorded request";

function evidenceList(escape, study) {
  return `<ul>${study.files.map((record) => {
    const relative = record.path.slice(OUTSIDE_STOCK_PREFIX.length);
    return `<li><a data-evidence href="./${escape(record.path)}" data-sha256="${escape(record.sha256)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · ${escape(record.role)}</li>`;
  }).join("")}</ul>`;
}

function linkedList(escape, study) {
  return `<ul>${study.linked.map((record) => {
    const relative = record.path.slice(OUTSIDE_STOCK_PREFIX.length);
    return `<li><a data-linked-evidence href="${escape(OUTSIDE_STOCK_REPO + OUTSIDE_STOCK_PUBLICATION + "/" + record.path)}" data-blob="${escape(record.git_blob)}">${escape(relative)}</a> · <code>${escape(record.sha256)}</code> · Git blob <code>${escape(record.git_blob)}</code> · ${escape(num(record.bytes))} bytes · ${escape(record.role)}<br>Declared by ${record.declared_by.map((where) => `<code>${escape(where)}</code>`).join(", ")}${record.corroborated ? "" : " (one carried declaration only; the manifest and integrity record pin it, and the page does not claim a second)"}.</li>`;
  }).join("")}</ul>`;
}

function sourceBlock(escape, study) {
  const source = study.source;
  return `<dl>
    <dt>Publication</dt><dd><code>${escape(source.publication_commit)}</code> on base <code>${escape(source.publication_base)}</code>, PR #${escape(String(source.pull_request))}; internal merge <code>${escape(source.internal_merge)}</code>. The source is the publication commit, not that merge.</dd>
    <dt>Earlier report</dt><dd>${escape(source.history.note)} The rejected review is <code>${escape(source.history.superseded_review)}</code> on head <code>${escape(source.history.superseded_head)}</code>.</dd>
    <dt>Native sources</dt><dd>Outside-query model <code>${escape(source.native_sources.outside_query_model)}</code>; accepted eleven-package stock freeze <code>${escape(source.native_sources.stock_holdout_catalog)}</code>. The budget repeats reopen the old pittsburgh and hong-kong packages by their exact old CRP bytes.</dd>
    <dt>Source issue</dt><dd>${escape(source.source_issue)}</dd>
    <dt>Review</dt><dd>Independent PASS ${escape(source.review.pass)}; engineering note ${escape(source.review.engineering_note)}; parent acceptance ${escape(source.review.parent_acceptance)}.</dd>
    <dt>Freeze</dt><dd>Requests, predictions and controls were frozen before the new native requests; the budget intervention and its old labels were frozen before any budget run. The frozen plan's own hash is <code>${escape(FROZEN_PLAN_SHA256)}</code> and is corroborated by the integrity, source-fix and evaluation records. Observation windows are the recorded driver start/finish times below, never this freeze time.</dd>
    <dt>File scope</dt><dd>${escape(String(study.closure.publication_files))} publication files: ${escape(String(study.closure.copied_files))} present here byte for byte (31 evidence files and the integrity record), ${escape(String(study.closure.linked_files))} linked as immutable Git blobs with SHA-256 and blob ids in <a href="./${escape(OUTSIDE_STOCK_SOURCES)}">the strict source manifest</a>. The integrity record pins its other ${escape(String(study.closure.integrity_members))} members.</dd>
    <dt>Stock exclusion source</dt><dd>Copied byte for byte from <code>${escape(study.stock_exclusion_source.path)}</code> at <code>${escape(study.stock_exclusion_source.publication_commit)}</code> (SHA-256 <code>${escape(study.stock_exclusion_source.carried_sha256)}</code>), whose own source is <code>${escape(study.stock_exclusion_source.source_commit)}</code>.</dd>
  </dl>`;
}

function populationRows(study) {
  const counts = study.population.counts;
  return [
    ["Installed builtin packages", String(counts.installed)],
    ["Excluded by declared inventory and package hashes", `${counts.excluded_packages} packages · ${counts.excluded_hashes} hashes (blank CO, the two controls and the ten PL-1239 cases)`],
    ["Eligible after exclusion", String(counts.eligible)],
    ["Supported (model inputs resolved)", String(counts.supported)],
    ["Abstaining", `${counts.abstaining}, including ${counts.decode_errors} retained NetManager decode errors`],
  ];
}

function packageRows(study) {
  return Object.entries(study.population.selection.cases).map(([case_, record]) => [
    case_, record.file, record.supported ? "supported" : "metadata only",
    String(record.requests), short(record.sha256), record.reason,
  ]);
}

function modeRows(study) {
  return MODES.map((mode) => {
    const primary = study.stock.primary[mode];
    const reference = study.stock.reference[mode];
    const record = study.stock.modes[mode];
    return [
      mode,
      String(record.requests),
      String(record.successes),
      String(record.failures),
      pair(primary),
      pair(reference),
      record.discrimination_estimable ? "two classes" : "one class only",
      study.stock.qualified_modes[mode] ? "qualified" : "UNQUALIFIED",
    ];
  }).concat([[
    "total",
    String(study.stock.requests),
    String(study.stock.modes.road.successes + study.stock.modes.ship.successes + study.stock.modes.air.successes),
    String(study.stock.modes.road.failures + study.stock.modes.ship.failures + study.stock.modes.air.failures),
    pair({ tp: study.stock.total.tp, fp: study.stock.total.fp, tn: study.stock.total.tn, fn: study.stock.total.fn }),
    pair({ tp: study.stock.total.tp, fp: study.stock.total.fp, tn: 0, fn: study.stock.total.fn }),
    "descriptive only",
    "UNQUALIFIED",
  ]]);
}

function packageModeRows(study) {
  return Object.entries(study.stock.package_mode).map(([key, record]) => [
    key.split("/")[0], key.split("/")[1], String(record.n), pair(record),
    record.absent_class_power ? "absent class" : "two classes",
  ]);
}

function stratumRows(study) {
  return study.stock.selection_strata.map((record) => [
    record.stratum, String(record.available), String(study.stock.selection_tags[record.stratum] ?? 0),
    short(record.selected_sha256),
  ]);
}

function tagRows(study) {
  return Object.entries(study.stock.selection_tags).map(([tag, count]) => [tag, String(count)]);
}

function groupRows(study) {
  return Object.entries(study.stock.groups).map(([key, record]) => [
    key, String(record.n), String(record.TP), String(record.FP), String(record.TN), String(record.FN),
    record.precision === null ? "null" : Number(record.precision).toFixed(3),
    record.recall === null ? "null" : Number(record.recall).toFixed(3),
    record.prediction_coverage === null ? "null" : Number(record.prediction_coverage).toFixed(3),
    record.absent_class_power ? "absent" : "two classes",
  ]);
}

function disagreementRows(study) {
  return study.stock.disagreements.map((row) => [
    row.query_id, row.mode, row.rule, row.prediction, row.label,
  ]);
}

function requestRows(study) {
  return study.requests.records.map((record) => [
    record.id, record.kind, record.case_id ?? "", label(record.mode), requestText(record),
    label(record.label), record.observed ? "observed" : "not observed",
  ]);
}

function controlRows(study) {
  return study.requests.records.filter((record) => record.kind === "control").map((record) => [
    record.case_id, label(record.mode), label(record.request_kind), requestText(record),
    label(record.label), record.observed ? "observed" : "Unknown",
    record.reason ?? "",
  ]);
}

function interventionRows(study) {
  return study.intervention.groups.map((group) => [
    group.old_query_id, group.old_label, group.selection,
    ...group.rows.map((row) => `${row.budget}: ${row.label}${row.snapshot_matched ? "" : " (no snapshot)"}`),
    group.all_mode_graph_constant ? "stable" : "graph changed",
  ]);
}

function bridgeRows(study) {
  const rows = [];
  for (const [package_, record] of Object.entries(study.bridge.packages)) {
    if (!record.supported) {
      rows.push([package_, "unsupported", "0", record.missing.length, "n/a", "null predictions", "retained"]);
      continue;
    }
    for (const mode of MODES) {
      const modeRecord = record.modes[mode];
      rows.push([
        package_, mode, modeRecord.exact_equal ? "exact" : "differs",
        String(modeRecord.mismatches),
        Object.entries(modeRecord.fields).map(([field, count]) => `${field}:${count}`).join(", ") || "none",
        `${modeRecord.max_vertical}`,
        modeRecord.horizontal_equal ? "unchanged" : "changed",
      ]);
    }
  }
  return rows;
}

function driftRows(study) {
  return Object.entries(study.drift.opening_changes).filter(([, modes]) =>
    MODES.some((mode) => modes[mode].changed)).map(([case_, modes]) => [
    case_,
    modes.air.changed ? modes.air.changed_segments.join(", ") : "none",
    modes.ship.changed ? modes.ship.changed_segments.join(", ") : "none",
    modes.road.changed ? modes.road.changed_segments.join(", ") : "none",
  ]);
}

function windowRows(study) {
  return study.runtime.observation_windows.map((window) => [
    window.case_id, window.started_at, window.finished_at, window.host,
    `${window.power_peak_watts} W`, `${window.temperature_peak_c} °C`,
    String(window.total_gpu_memory_peak_mib),
  ]);
}

/** The one study, rendered in one place, referenced from Road, Ship and Air. */
export function outsideStockPage({ study }, escape) {
  const counts = study.population.counts;
  return `<article id="outside-stock-study" data-outside-stock>
    <div class="ledger-title"><h2>Outside-stock validation and budget limits</h2><span>research only · evidence</span></div>
    <p class=note>One prospective stock validation and one separate retained-road budget intervention, referenced from Road, Ship and Air. It is evidence only: not the current runtime estimate above, not a qualification, not pooled with the outside-query, rail or native studies, not a vote, not a fitted place-level promise and not activation. A selected failure labels that exact request, never a place.</p>
    <p>${escape(study.scope)}</p>
    ${sourceBlock(escape, study)}
    <p>${escape(study.method)}</p>

    <h3>Population and the five fixed selections</h3>
    ${table(escape, ["Population", "Count"], populationRows(study), "data-outside-stock-population")}
    <p>${escape(String(counts.installed))} installed builtin packages; ${escape(String(counts.eligible))} eligible after the declared exclusions, ${escape(String(counts.supported))} supported, ${escape(String(counts.abstaining))} abstaining including ${escape(String(counts.decode_errors))} retained NetManager decode errors. The ${escape(String(counts.excluded_hashes))} excluded hashes and every package hash stay pinned; no package is repaired or replaced after an outcome.</p>
    ${table(escape, ["Case", "Package", "Inputs", "Requests", "Package SHA-256", "Selection reason"], packageRows(study), "data-outside-stock-packages")}
    <p>Three queried packages carry all ${escape(String(study.stock.requests))} stock requests; two unsupported packages carry null predictions for all three modes, which is ${escape(String(study.stock.package_mode ? 6 : 6))} null package-mode records, not invented requests or native negatives. Selection tags overlap: ${escape(String(Object.values(study.stock.selection_tags).reduce((total, value) => total + value, 0)))} tag memberships cover ${escape(String(study.stock.requests))} requests and must never be summed as independent samples.</p>

    <h3>New stock labels · descriptive intent-to-test</h3>
    ${table(escape, ["Mode", "Requests", "Successes", "Failures", "Primary TP/FP/TN/FN", "Reference TP/FP/TN/FN", "Discrimination", "Status"], modeRows(study), "data-outside-stock-modes")}
    <p>The primary rule matches all ${escape(String(study.stock.requests))} labels: ${pair({ tp: study.stock.total.tp, fp: study.stock.total.fp, tn: study.stock.total.tn, fn: study.stock.total.fn })}. That is descriptive agreement on correlated requests, <strong>not</strong> qualification, global accuracy, a geographic "no", a service, spawning, sustained navigation or a promise. <strong>All three modes remain UNQUALIFIED</strong> because the retained all-controls completion requirement fails on the first Asanu opening. The weak reference's road result is ${pair(study.stock.reference.road)}: weak connectivity cannot represent lane-direction restrictions, so those are descriptive disagreements, never local absences.</p>
    ${table(escape, ["Package", "Mode", "n", "Primary TP/FP/TN/FN", "Classes"], packageModeRows(study), "data-outside-stock-package-mode")}
    <p>One-class package-modes (${MODES.map((mode) => `${escape(mode)}: ${study.stock.one_class[mode].packages.map((item) => escape(item)).join(", ") || "none"}`).join("; ")}) are kept visible rather than scored as discrimination. Empty strata and absent classes are not estimable.</p>

    <h3>Selection strata</h3>
    ${table(escape, ["Stratum", "Available candidates", "Tagged requests", "Selected set SHA-256"], stratumRows(study), "data-outside-stock-strata")}
    ${table(escape, ["Selection tag", "Requests carrying it"], tagRows(study), "data-outside-stock-tags")}
    <p>Package tags apply to every request of that package in every mode, so the tag counts overlap and are not samples. Every tagged first-four/fill request and the reciprocal pair stay in the carried frozen plan.</p>

    <h3>Strict bridge subset</h3>
    ${table(escape, ["Subset", "Requests", "Primary", "Reference", "Not exact matches"],
      [["road · holdout-01 + holdout-02", String(study.bridge.subset.requests), pair(study.bridge.subset.primary), pair(study.bridge.subset.reference), String(study.bridge.subset.not_matched)]],
      "data-outside-stock-subset")}
    <p>Only these ${escape(String(study.bridge.subset.requests))} road requests have exact export/native field identity. The other ${escape(String(study.bridge.subset.not_matched))} requests fail exact bridge identity and are <strong>not</strong> admitted to this subset. Applying the unchanged rule to opening-native fields is a post-outcome diagnostic, never a replacement pre-export prediction.</p>

    <h3>Bridge · every retained mismatch, by package and mode</h3>
    ${table(escape, ["Package", "Mode", "Identity", "Mismatches", "Fields", "Largest vertical difference", "Horizontal"], bridgeRows(study), "data-outside-stock-bridge")}
    <p>Ship and air endpoint heights change at opening, by at most ${escape(String(study.bridge.height_drift["holdout-01"]))}, ${escape(String(study.bridge.height_drift["holdout-02"]))} and ${escape(String(study.bridge.height_drift["holdout-03"]))} in the three selected packages. Horizontal coordinates do not change. CL Roslyn Peninsula also changes ${escape(String(study.bridge.roslyn_prefabs.length))} road prefabs from <code>Highway</code> to <code>Highway Connection</code>${study.bridge.roslyn_prefabs.length ? ` (segments ${study.bridge.roslyn_prefabs.map((change) => escape(String(change.segment))).join(", ")})` : ""}. No lane, connectivity, Invert or Outside-role mismatch is observed.</p>

    <h3>Opening-to-post drift</h3>
    ${table(escape, ["Opening", "Air segments", "Ship segments", "Road segments"], driftRows(study), "data-outside-stock-drift")}
    <p>CL Roslyn Peninsula changes seven air and two ship endpoint heights; ${escape(String(study.drift.pre_post_query_changes.length))} pre/post-query fingerprints change (${study.drift.pre_post_query_changes.map((id) => escape(id)).join(", ")}). The publication reports ${escape(String(study.drift.reported_opening_fingerprint_mismatches))} of 18 opening-fingerprint mismatches against the query-freeze opening graph. This ledger does not re-run that comparison because the freeze is linked, but it does re-derive that ${escape(String(study.drift.pre_query_opening_fingerprint_mismatches))} pre-query model-field fingerprints differ from the recorded opening snapshot. All 18 Roslyn requests stay outside the strict subset and the descriptive label counts are unchanged.</p>

    <h3>Controls</h3>
    ${table(escape, ["Case", "Mode", "Kind", "Request", "Label", "State", "Reason"], controlRows(study), "data-outside-stock-controls")}
    <p>The first Asanu opening fails before any path request because the collector read the native MetaBool string "False" as a Python boolean. It and its six Unknown controls are retained without retry. Hanami completes all six controls (one exact positive and one invalid-vehicle rejection per mode), but the frozen all-controls completion requirement still fails for every mode, so no mode is qualified and no control is a replacement vote.</p>

    <h3>Retained-road budget intervention</h3>
    ${table(escape, ["Old request", "Old label", "Selection", "100000", "200000", "1000000", "All-mode graph"], interventionRows(study), "data-outside-stock-intervention")}
    <p>All ${escape(String(study.intervention.cohort.old_false_positives))} retained road errors fail at 100000, 200000 and 1000000; one matched old-success request (<code>${escape(study.intervention.measured_response.old_query_id)}</code>) fails at 100000 and succeeds at both larger budgets. That is a measured response, not an identified search-budget mechanism, native cost or metre conversion; all four error mechanisms remain <strong>Unknown</strong>. Old labels are immutable and never rerun or replaced. Seven groups keep the all-mode fingerprint unchanged; <code>${escape(study.intervention.drift.old_query_id)}</code> does not (${escape(String(study.intervention.drift.air_segments.length))} air endpoint heights change, segments ${study.intervention.drift.air_segments.map((segment) => escape(String(segment))).join(", ")}), and no separate per-query road-only snapshot was retained, so it is not a clean single-variable trial.</p>
    <p>The requested maxLength is a float handed to the public API; the returned <code>flags=8</code> and <code>length</code> sentinel are not proof of native exhaustion, cost, metres or an SI conversion.</p>

    <h3>Schema repair</h3>
    <p>The original frozen scorer failed on the transport's missing <code>ok=true</code>; its retained failure is <a href="./${escape(study.closure.prefix)}/analysis/frozen-scorer-failure.log">preserved</a> (SHA-256 <code>${escape(study.schema_repair.retained_failure.sha256)}</code>). The separate post-control scorer requires exactly the frozen body keys plus <code>ok=true</code>; the diff is <a href="./${escape(study.closure.prefix)}/analysis/schema-fix.diff.gz">retained</a> and bound by <a href="./${escape(study.closure.prefix)}/analysis/source-fix.json">source-fix.json</a>. This is a schema correction, not a hidden re-freeze: no rule, request, native row, label, threshold or qualification gate changed.</p>

    <h3>Runtime, file identity and cleanup</h3>
    ${table(escape, ["Opening", "Recorded start", "Recorded finish", "Host", "GPU peak power", "GPU peak temp", "Total GPU peak MiB"], windowRows(study), "data-outside-stock-windows")}
    <p>${escape(String(study.runtime.openings))} openings are retained (eight complete, one pre-query control failure). ${escape(String(study.runtime.phase_inventories))} phase inventories bind the executable, assemblies, DLL, declared file trees and plugin state; each records the excluded anonymous dynamic-method assembly and has no unresolved loaded-assembly entry. The DLL is <code>${escape(study.runtime.build.dll_sha256)}</code>. ${escape(String(study.runtime.process_identities))} observed game/collector/driver/auditor/GPU-monitor PID/start identities are gone, including the supplemental first-opening auditor chain. The old launch receipt's "no monitor" caption is stale after the auditor addition; auditor-launch/completion records, not that caption, establish coverage.</p>
    <p>This is file identity, not memory attestation or a strict no-mods claim; dynamic exclusions, plugin state and three retained DLL errors remain limitations. The cleanup statement is historical about named PID/start identities and says nothing about blade's current slot or process state.</p>

    <details><summary>All ${escape(String(study.requests.records.length))} planned requests · 48 stock, 12 controls, 24 intervention</summary>
      ${table(escape, ["Query", "Kind", "Case", "Mode", "Request", "Label", "State"], requestRows(study), "data-outside-stock-requests")}
      <p>The six Unknown controls stay Unknown, and no unobserved request becomes a negative.</p></details>
    <details><summary>Every recorded metric group · ${escape(String(Object.keys(study.stock.groups).length))} mode, package, stratum and snapshot groups</summary>
      ${table(escape, ["Group", "n", "TP", "FP", "TN", "FN", "Precision", "Recall", "Coverage", "Classes"], groupRows(study), "data-outside-stock-groups")}
      <p>Precision and recall are arithmetic on this correlated cohort; a null denominator stays null.</p></details>
    <details><summary>Reference disagreements · ${escape(String(study.stock.disagreements.length))} road false positives</summary>
      ${table(escape, ["Query", "Mode", "Rule", "Prediction", "Label"], disagreementRows(study), "data-outside-stock-disagreements")}
      <p>Every reference disagreement is a road false positive on one of the three selected packages; the primary rejects those requests using lane-direction grants. They are never a length rule, a place exception or a post-hoc refit.</p></details>
    <details><summary>Protocol, budgets and freeze rules</summary>${detail(escape, "Recorded protocol as data", study.protocol)}</details>
    <details><summary>Carried evidence · ${escape(String(study.files.length))} files served byte for byte</summary>${evidenceList(escape, study)}</details>
    <details><summary>Linked source documents · ${escape(String(study.linked.length))} immutable blobs at the publication commit</summary>${linkedList(escape, study)}</details>
    <details><summary>Integrity reconstruction, exclusion hashes and stock source</summary>${detail(escape, "Reconstructed integrity", {
      reconstruction: study.integrity_reconstruction,
      excluded_hashes: study.population.excluded_hashes,
      stock_source: study.stock_exclusion_source,
    })}</details>
    <p class=note>${escape(study.limits)}</p></article>`;
}

/** A compact reference from one capability to the single shared study. */
export function outsideStockReference(capability, { study }, escape) {
  const record = study.stock.modes[capability];
  const primary = study.stock.primary[capability];
  const head = `${capability[0].toUpperCase()}${capability.slice(1)}`;
  const line = record.discrimination_estimable
    ? `${escape(head)} has ${escape(String(record.requests))} new stock requests: primary TP ${primary.tp} · FP ${primary.fp} · TN ${primary.tn} · FN ${primary.fn}, ${escape(String(record.successes))} observed successes and ${escape(String(record.failures))} observed failures.`
    : `${escape(head)} has ${escape(String(record.requests))} new stock requests and only one class on some packages; that is positive consistency, not discrimination.`;
  return `<h3>Outside-stock validation and budget limits</h3>
    <p>Prospective stock validation and a separate correlated budget intervention on unchanged packages. ${line}
    All three modes remain unqualified after the retained first-control failure.
    <a href="#outside-stock-study">The one study, its population, controls, drift, budget table and limits</a>.
    It is evidence only: not qualification, not the current runtime estimate, not a geographic "no" and not a promise.</p>`;
}
