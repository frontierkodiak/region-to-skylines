// Vercel build: the static page, with the command it hands agents pinned to this commit, so the
// tool runs exactly the code the page runs (and needs no git).
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, readFileSync, writeFileSync, renameSync, copyFileSync, readdirSync } from "node:fs";
import { dirname } from "node:path";
import { FACTORY_FILES } from "./mapgen.js";
import { ledgerPage, validateLedger } from "./capability-ledger.mjs";
import { railStudyFiles } from "./rail-study.mjs";
import { railResearch, railResearchFiles } from "./rail-research.mjs";
import { outsideResearch, outsideResearchFiles } from "./outside-research.mjs";
import { outsideStock, outsideStockFiles } from "./outside-stock.mjs";
import { outsideReadiness, outsideReadinessFiles } from "./outside-readiness.mjs";

const SITE = "https://region-to-skylines.vercel.app";
const PAGE = ["index.html", "app.js", "terrain.js", "inputs.js", "mapgen.js", "mapgen-worker.js", "water-risk.js", "style.css", "agents.md", "llms.txt", "capabilities.json", "capability-model.js", "connection-rules.js", "start-model.js", "water-model.js", "capability-inputs.js", "capability-ui.js", "capability-evidence.js", "capability-evidence-worker.js"];
const sha = process.env.VERCEL_GIT_COMMIT_SHA ||
  (() => { try { return execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(); } catch { return ""; } })();
// The prompt and agents.md name GitHub's tarball of this exact commit: it never changes or goes
// away when the site redeploys (a file of this deploy would), and npx needs no git to fetch it.
const cli = /^[0-9a-f]{40}$/.test(sha) ? `https://codeload.github.com/frontierkodiak/region-to-skylines/tar.gz/${sha}` : `${SITE}/cli.tgz`;

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");
// /cli.tgz: the latest tool, packed from this deploy, for the README
const [{ filename }] = JSON.parse(execFileSync("npm", ["pack", "--json", "--pack-destination", "dist"], { encoding: "utf8" }));
renameSync(`dist/${filename}`, "dist/cli.tgz");
for (const f of PAGE) {
  const text = readFileSync(f, "utf8");
  writeFileSync(`dist/${f}`, f.endsWith(".css") ? text : text.replaceAll("__CLI_TGZ__", cli));
}
const ledger = JSON.parse(readFileSync("capabilities.json", "utf8"));
validateLedger(ledger);
// Serve the exact staged/active receipt bytes alongside the single ledger.
for (const certificate of [...(ledger.native_path_certificates ?? []), ...(ledger.evidence_studies?.["outside-targeted-v2"]?.qualification_candidates ?? [])]) {
  const file = certificate.runtime_identity_evidence.file;
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// Serve the directed-rail study's own bytes: raw receipts, closure and projection.
for (const file of railStudyFiles()) {
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// Serve the three accepted rail research publications' carried evidence, the
// strict file-scope manifest and the projection the page renders from.
for (const file of railResearchFiles(Object.values(railResearch().studies))) {
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// Serve the accepted outside-connection study's carried evidence and the
// projection the page renders from. Its bulk source documents stay at the
// publication commit and are linked, not copied.
for (const file of outsideResearchFiles()) {
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// Serve the accepted outside-stock publication's present evidence and the
// projection the page renders from. Its bulky frozen plan, feature dump,
// preparation archives and raw gzip stay at the publication commit and are
// linked, not copied.
for (const file of outsideStockFiles()) {
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// Serve the accepted outside-readiness stopped study's carried evidence and the
// projection, plus its small retained raw context. Its bulk frozen feature dump
// stays at the publication commit and is linked, not copied.
for (const file of outsideReadinessFiles()) {
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
for (const study of Object.values(ledger.witness_studies ?? {})) {
  for (const {file} of [...study.provenance.files, study.provenance.manifest]) {
    mkdirSync(dirname(`dist/${file}`), {recursive: true});
    copyFileSync(file, `dist/${file}`);
  }
}
for (const study of Object.values(ledger.capabilities.find((c) => c.id === "water_risk").calibration_studies)) {
  for (const { file } of study.provenance.files) {
    mkdirSync(dirname(`dist/${file}`), { recursive: true });
    copyFileSync(file, `dist/${file}`);
  }
}
writeFileSync("dist/capabilities.html", ledgerPage(ledger, sha));
const waterEvidence = "tools/map-factory/capability-evidence/pl1191-playable-water";
for (const name of readdirSync(waterEvidence).sort()) {
  const file = `${waterEvidence}/${name}`;
  mkdirSync(dirname(`dist/${file}`), { recursive: true });
  copyFileSync(file, `dist/${file}`);
}
// The terrain-shape survey the stock reference cites, byte for byte.
mkdirSync("dist/tools/map-factory/survey", { recursive: true });
copyFileSync("tools/map-factory/survey/terrain-interest.json", "dist/tools/map-factory/survey/terrain-interest.json");
// the map writer the worker runs (tools/map-factory), byte for byte
for (const f of FACTORY_FILES) {
  mkdirSync(dirname(`dist/tools/map-factory/${f}`), { recursive: true });
  copyFileSync(`tools/map-factory/${f}`, `dist/tools/map-factory/${f}`);
}
console.log(`built dist/; the tool is ${cli}`);
