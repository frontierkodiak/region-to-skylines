// Vercel build: the static page as is, plus the command-line tool packed from the same commit,
// so the command the page hands an agent runs exactly the code the page runs (and needs no git).
import { execFileSync } from "node:child_process";
import { mkdirSync, rmSync, copyFileSync, readFileSync, writeFileSync, renameSync } from "node:fs";

const SITE = "https://region-to-skylines.vercel.app";
const PAGE = ["index.html", "app.js", "terrain.js", "style.css", "agents.md", "llms.txt"];
const sha = (process.env.VERCEL_GIT_COMMIT_SHA ||
  (() => { try { return execFileSync("git", ["rev-parse", "HEAD"], { encoding: "utf8" }).trim(); } catch { return "dev"; } })()).slice(0, 7);
const { version } = JSON.parse(readFileSync("package.json", "utf8"));

rmSync("dist", { recursive: true, force: true });
mkdirSync("dist");
const [{ filename }] = JSON.parse(execFileSync("npm", ["pack", "--json", "--pack-destination", "dist"], { encoding: "utf8" }));
// a new file name per commit: npx caches by URL, so a fixed name would keep running an old tool
const tgz = `region-to-skylines-${version}-${sha}.tgz`;
renameSync(`dist/${filename}`, `dist/${tgz}`);
copyFileSync(`dist/${tgz}`, "dist/cli.tgz"); // a stable alias for the README; the page and agents.md use the pinned name
for (const f of PAGE) {
  const text = readFileSync(f, "utf8");
  writeFileSync(`dist/${f}`, f.endsWith(".css") ? text : text.replaceAll("__CLI_TGZ__", `${SITE}/${tgz}`));
}
console.log(`built dist/ with ${tgz}`);
