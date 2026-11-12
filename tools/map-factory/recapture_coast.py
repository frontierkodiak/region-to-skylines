"""Own temporary HTTP server + named headless Playwright CLI; always close both.

Recaptures with frozen non-sea vectors and fresh DEM/ocean evidence. This is an
experimental capture helper, not the live application's sea policy.
"""

import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(frozen, output, slugs):
    output.mkdir(parents=True, exist_ok=True)
    sources = {slug: frozen / f"{slug}-geometry.json" for slug in slugs}
    for path in sources.values():
        if not path.is_file():
            raise FileNotFoundError(path)

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/__capture/blank":
                data = b"<!doctype html><title>Isolated map capture</title>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(data)
            elif self.path.startswith("/__capture/frozen/"):
                slug = self.path.removeprefix("/__capture/frozen/")
                if slug not in sources:
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(sources[slug].read_bytes())
            else:
                super().do_GET()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=ROOT)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_port}"
    session = f"pl857-coast-{os.getpid()}"
    logs = output / "browser-logs"
    logs.mkdir(exist_ok=True)

    def cli(*args, timeout=240):
        result = subprocess.run(
            ["playwright-cli", f"-s={session}", *args],
            cwd=logs,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log = result.stdout + result.stderr
        with (logs / "commands.log").open("a") as handle:
            handle.write(f"{args[0]} exit={result.returncode}\n{log}\n")
        if result.returncode or "### Error" in log or "TimeoutError" in log:
            raise RuntimeError(log)
        return log

    try:
        cli("open", f"{url}/__capture/blank")
        cli(
            "run-code",
            "async page => { await page.addScriptTag({url:'/tools/map-factory/capture-ocean.test.js'}); "
            "const r=await page.evaluate(()=>testOceanCapture()); if(!r.passed) throw Error('tests failed'); return r; }",
        )
        for slug in slugs:
            folder = output / slug
            folder.mkdir(exist_ok=True)
            if any(folder.iterdir()):
                raise ValueError(f"Use a fresh capture folder: {folder}")
            code = (
                """async page => {
              const downloads = [];
              page.on('download', async d => {
                const save = d.saveAs(DEST + '/' + d.suggestedFilename());
                downloads.push(save); await save;
              });
              await page.addScriptTag({url:'/tools/map-factory/capture.js'});
              const result = await page.evaluate(async ({slug, originalHash}) => {
                const frozen = await (await fetch('/__capture/frozen/' + slug)).json();
                return captureRegion(frozen.sq, {frozenGeometry:frozen, frozenGeometrySha256:originalHash});
              }, {slug:SLUG, originalHash:ORIGINAL_HASH});
              for(let i=0;i<100 && downloads.length<6;i++) await page.waitForTimeout(100);
              if(downloads.length!==6) throw Error('expected all six capture downloads');
              await Promise.all(downloads);
              return result;
            }""".replace("DEST", json.dumps(str(folder)))
                .replace("SLUG", json.dumps(slug))
                .replace("ORIGINAL_HASH", json.dumps(sha(sources[slug])))
            )
            # Dedicated script file avoids command-line size and shell quoting.
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".js", dir=logs
            ) as script:
                script.write(code)
                script.flush()
                result = cli("run-code", "--filename", script.name)
            before = json.loads(sources[slug].read_text())
            after = json.loads((folder / f"{slug}-geometry.json").read_text())
            for key in ["sq", "rivers", "lakes", "riverAreas", "roads", "streams"]:
                if before[key] != after[key]:
                    raise ValueError(
                        f"Controlled capture changed non-sea geometry: {slug}/{key}"
                    )
            receipt = {
                "source_geometry": str(sources[slug]),
                "source_geometry_sha256": sha(sources[slug]),
                "non_sea_geometry_preserved": True,
                "in_game_verified": False,
                "source_revision": subprocess.check_output(
                    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
                ).strip(),
                "files_sha256": {p.name: sha(p) for p in sorted(folder.iterdir())},
                "browser_result": result,
            }
            (folder / "capture.json").write_text(json.dumps(receipt, indent=2) + "\n")
            print(
                f"{slug}: explicit ocean capture complete; frozen non-sea geometry preserved",
                flush=True,
            )
            # Remove download listeners before the next case; captured page is ours only.
            cli("run-code", "async page => { page.removeAllListeners('download'); }")
    finally:
        browser_closed = False
        try:
            cli("close", timeout=30)
            browser_closed = True
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            if thread.is_alive():
                raise RuntimeError("capture HTTP server did not stop")
            (logs / "cleanup.json").write_text(
                json.dumps(
                    {
                        "browser_session_closed": browser_closed,
                        "server_closed": True,
                        "session": session,
                        "server_url": url,
                    },
                    indent=2,
                )
                + "\n"
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("frozen", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--only", nargs="+", default=["rio", "charleston"])
    args = parser.parse_args()
    run(args.frozen.resolve(), args.output.resolve(), args.only)
