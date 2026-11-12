"""Verify pinned tiles in one own foreground browser; close browser/server in finally."""

import argparse
import functools
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[2]


def run(frozen, provenance, output, capture=False, first_observed=False, control=False):
    if control and not capture:
        raise ValueError("control requires explicit capture")
    output.mkdir(parents=True, exist_ok=False)
    if first_observed and str(provenance) != "-":
        raise ValueError(
            "first-observed input must explicitly use '-' instead of recorded provenance"
        )
    config = {
        "frozen": json.loads(frozen.read_text()),
        "tiles": []
        if first_observed
        else json.loads(provenance.read_text())["ocean"]["tiles"],
        "firstObserved": first_observed,
        "control": control,
    }

    class Handler(SimpleHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/__surface/config.json":
                data = json.dumps(config).encode()
                kind = "application/json"
            elif self.path == "/__surface/terrain.js":
                data = (
                    ROOT / "terrain.js"
                ).read_bytes() + b"\nexport {clipLine,bbox,tileRange};\n"
                kind = "text/javascript"
            elif self.path == "/__surface/blank":
                data = b"<!doctype html><title>Own surface evidence</title>"
                kind = "text/html"
            else:
                return super().do_GET()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(
        ("127.0.0.1", 0), functools.partial(Handler, directory=ROOT)
    )
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    session = f"pl857-surface-{os.getpid()}"
    logs = output / "browser.log"

    def cli(*args, timeout=240):
        r = subprocess.run(
            ["playwright-cli", f"-s={session}", *args],
            cwd=output,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        log = r.stdout + r.stderr
        with logs.open("a") as h:
            h.write(log + "\n")
        if r.returncode or "### Error" in log or "TimeoutError" in log:
            raise RuntimeError(log)
        return log

    closed = False
    try:
        cli("open", f"http://127.0.0.1:{server.server_port}/__surface/blank")
        cli(
            "run-code",
            "async page => { await page.addScriptTag({url:'/tools/map-factory/capture-ocean.test.js'}); const r=await page.evaluate(()=>testOceanCapture()); if(!r.passed) throw Error('ocean tests failed'); return r; }",
        )
        script = output / "inspect.js"
        script.write_text(
            """async page => {
          const result=await page.evaluate(async()=>{
            const t=await import('/__surface/terrain.js');
            const {inspectWaterways,matchFrozen,snapshotTiles}=await import('/tools/map-factory/waterway-evidence.js');
            const config=await(await fetch('/__surface/config.json')).json();
            const tiles=snapshotTiles(config.frozen,config.tiles,t);
            const decoded=await inspectWaterways(tiles,t.clipLine,{firstObserved:true});
            return {...decoded,...matchFrozen(config.frozen,decoded.pieces)};
          });
          const [download] = await Promise.all([page.waitForEvent('download'),page.evaluate(data=>{
            const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)]));
            a.download='waterway-evidence.json';a.click();
          },result)]);
          await download.saveAs(DEST);
          return {tiles:result.tiles.length,pieces:result.pieces.length,matched:result.matched.length,
                  unknown:result.unknown.length,ambiguous:result.ambiguous.length};
        }""".replace("DEST", json.dumps(str(output / "waterway-evidence.json")))
        )
        print(cli("run-code", "--filename", str(script)), flush=True)
        if capture:
            config["inspection"] = json.loads(
                (output / "waterway-evidence.json").read_text()
            )
            config["inspectionSha256"] = hashlib.sha256(
                (output / "waterway-evidence.json").read_bytes()
            ).hexdigest()
            config["tiles"] = config["inspection"]["tiles"]
            config["originalGeometrySha256"] = hashlib.sha256(
                frozen.read_bytes()
            ).hexdigest()
            if config["inspection"]["unknown"] or config["inspection"]["ambiguous"]:
                raise ValueError("unknown/ambiguous frozen matches; refusing capture")
            folder = output / config["frozen"]["sq"]["slug"]
            folder.mkdir()
            capture_script = output / "capture.js"
            capture_script.write_text(
                """async page => {
              const downloads=[];
              page.on('download', d=>{downloads.push(d.saveAs(DEST+'/'+d.suggestedFilename()));});
              await page.addScriptTag({url:'/tools/map-factory/capture.js'});
              const result=await page.evaluate(async()=>{
                const config=await(await fetch('/__surface/config.json')).json();
                const {surfaceGeometry}=await import('/tools/map-factory/waterway-evidence.js');
                const selected=config.control ? config.frozen : surfaceGeometry(config.frozen,config.inspection,config.originalGeometrySha256,config.inspectionSha256);
                const bytes=new TextEncoder().encode(JSON.stringify(selected));
                const sha=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),b=>b.toString(16).padStart(2,'0')).join('');
                return captureRegion(selected.sq,{frozenGeometry:selected,frozenGeometrySha256:sha,pinnedVectorTiles:config.tiles});
              });
              for(let i=0;i<100 && downloads.length<6;i++) await page.waitForTimeout(100);
              if(downloads.length!==6) throw Error('expected six capture downloads');
              await Promise.all(downloads);return result;
            }""".replace("DEST", json.dumps(str(folder)))
            )
            print(cli("run-code", "--filename", str(capture_script)), flush=True)
            after = json.loads(
                (folder / f"{config['frozen']['sq']['slug']}-geometry.json").read_text()
            )
            before = config["frozen"]
            for key in ["sq", "roads", "lakes", "riverAreas"]:
                if before[key] != after[key]:
                    raise ValueError(f"controlled capture changed {key}")
            for field in ["rivers", "streams"]:
                kept = after[field]
                originals = (
                    before[field]
                    if control
                    else [
                        m["original"]
                        for m in config["inspection"]["matched"]
                        if m["field"] == field
                        and m["evidence"]["properties"].get("brunnel") != "tunnel"
                    ]
                )
                if len(kept) != len(originals) or any(
                    {k: f[k] for k in orig} != orig for f, orig in zip(kept, originals)
                ):
                    raise ValueError(f"retained points/ordering changed {field}")
            (folder / "capture.json").write_text(
                json.dumps(
                    {
                        "original_geometry_sha256": config["originalGeometrySha256"],
                        "files_sha256": {
                            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in folder.iterdir()
                        },
                        "surface_water_policy": after.get("surfaceWaterPolicy"),
                        "control_capture": control,
                        "in_game_verified": False,
                        "default_adopted": False,
                    },
                    indent=2,
                )
                + "\n"
            )
        (output / "source.json").write_text(
            json.dumps(
                {
                    "frozen_sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
                    "provenance_sha256": None
                    if first_observed
                    else hashlib.sha256(provenance.read_bytes()).hexdigest(),
                    "recorded_provenance": not first_observed,
                    "terrain_sha256": hashlib.sha256(
                        (ROOT / "terrain.js").read_bytes()
                    ).hexdigest(),
                    "helper_sha256": hashlib.sha256(
                        (ROOT / "tools/map-factory/waterway-evidence.js").read_bytes()
                    ).hexdigest(),
                    "capture_sha256": hashlib.sha256(
                        (ROOT / "tools/map-factory/capture.js").read_bytes()
                    ).hexdigest(),
                    "runner_sha256": hashlib.sha256(
                        Path(__file__).read_bytes()
                    ).hexdigest(),
                    "evidence_sha256": hashlib.sha256(
                        (output / "waterway-evidence.json").read_bytes()
                    ).hexdigest(),
                },
                indent=2,
            )
            + "\n"
        )
    finally:
        try:
            cli("close", timeout=30)
            closed = True
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
            (output / "cleanup.json").write_text(
                json.dumps(
                    {
                        "browser_closed": closed,
                        "server_closed": not thread.is_alive(),
                        "session": session,
                    }
                )
                + "\n"
            )
            if thread.is_alive():
                raise RuntimeError("own HTTP server did not stop")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for k in ["frozen", "provenance", "output"]:
        p.add_argument(k, type=Path)
    p.add_argument("--capture", action="store_true")
    p.add_argument(
        "--control",
        action="store_true",
        help="capture original full geometry without exclusions, as a recapture-drift control",
    )
    p.add_argument(
        "--first-observed",
        action="store_true",
        help="use provenance '-' and fixed snapshot only; no historical tile hash claim",
    )
    run(**vars(p.parse_args()))
