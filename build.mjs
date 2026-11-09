// Vercel build: the static page, with the command it hands agents pinned to this commit, so the
// tool runs exactly the code the page runs (and needs no git).
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, readFileSync, writeFileSync, renameSync } from "node:fs";

const SITE = "https://region-to-skylines.vercel.app";
const PAGE = ["index.html", "app.js", "terrain.js", "style.css", "agents.md", "llms.txt"];
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
console.log(`built dist/; the tool is ${cli}`);
