"""The harness over MCP: the same operations as the CLI, for any agent harness.

Every tool runs the CLI (`python -m cs1_harness.cli …`) in a subprocess, so the
CLI stays the one contract: same arguments, same slot rules, same outputs.
Long work (a map soak) goes through `submit`, which returns at once and posts
the verdict on the issue when the run ends.

Register it with a client as a stdio server, e.g. for Claude Code:
    claude mcp add cs1-harness -- uv run --directory <checkout>/tools/cs1-harness cs1-harness mcp
"""

from __future__ import annotations

import json
import signal
import subprocess
import sys

from mcp.server import MCPServer

mcp = MCPServer("cs1-harness")


def cli(*args: str, timeout: float = 600) -> dict:
    """Run one CLI command. On timeout it gets SIGTERM, so a session it holds tears down as on any
    other exit (the CLI turns SIGTERM into SystemExit); SIGKILL only if teardown takes 5 more minutes."""
    p = subprocess.Popen(
        [sys.executable, "-m", "cs1_harness.cli", *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.send_signal(signal.SIGTERM)
        try:
            stdout, stderr = p.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            p.kill()
            stdout, stderr = p.communicate()
        stderr = f"timed out after {timeout:.0f} s; stopped with SIGTERM\n" + (stderr or "")
    out = (stdout or "").strip()
    try:
        data = json.loads(out) if out else None
    except ValueError:
        data = out
    return {"exit_code": p.returncode, "result": data, "log": (stderr or "").strip()[-4000:]}


@mcp.tool()
def queue() -> dict:
    """Who holds this host's harness slot (command, issue, label, ETA) and who is waiting."""
    return cli("queue", "--json")


@mcp.tool()
def contention(hours: float = 24) -> dict:
    """How contended the slot was over the last `hours`: waits, longest wait, share of time held."""
    return cli("queue", "--stats", "--hours", str(hours))


@mcp.tool()
def runs(
    issue: str | None = None,
    verdict: str | None = None,
    check_type: str | None = None,
    map_sha: str | None = None,
    commit: str | None = None,
) -> dict:
    """Registered runs, filtered (all filters AND together): verdict, map hash, harness commit, metrics."""
    args = ["runs", "--json"]
    for flag, value in (
        ("--issue", issue),
        ("--verdict", verdict),
        ("--check-type", check_type),
        ("--map-sha", map_sha),
        ("--commit", commit),
    ):
        if value:
            args += [flag, value]
    return cli(*args)


@mcp.tool()
def verdict(run_dir: str) -> dict:
    """Judge a finished run directory: verdict.json with each check's value and threshold, plus triage."""
    return cli("verdict", "--json", run_dir)


@mcp.tool()
def compare(run_refs: list[str], out_dir: str) -> dict:
    """Overlay water volume, wet probes and population over time for runs (paths or registry ids).
    Writes compare.png and compare.json in out_dir."""
    r = cli("compare", *run_refs, "--out", out_dir)
    try:
        r["result"] = json.loads(open(f"{out_dir}/compare.json").read())
    except OSError:
        pass
    return r


@mcp.tool()
def submit(
    issue: str,
    map_path: str,
    out_dir: str,
    probes: str | None = None,
    game_minutes: float = 60,
    wake: bool = False,
    extra_run_args: list[str] | None = None,
) -> dict:
    """Queue a map soak detached. It waits for the slot, runs, and comments the verdict, frames and
    timelapse on `issue`, which wakes an agent assignee; `wake` adds an @mention for other cases. Returns at once."""
    args = ["submit", "--issue", issue] + (["--wake"] if wake else [])
    args += ["--", "run", "--map", map_path, "--out", out_dir, "--game-minutes", str(game_minutes)]
    if probes:
        args += ["--probes", probes]
    return cli(*args, *(extra_run_args or []))


@mcp.tool()
def notify(run_dir: str, issue: str, dry_run: bool = True) -> dict:
    """Comment a finished run's verdict on an issue (dry_run shows the comment without posting)."""
    return cli("notify", run_dir, "--issue", issue, *(["--dry-run"] if dry_run else []))


@mcp.tool()
def up(map_path: str | None = None, label: str | None = None, wait_minutes: float = 0) -> dict:
    """Start a session: the game at the main menu, left running for `call` until `down`. Waits up to
    wait_minutes for the slot; never takes over another session."""
    args = ["up"]
    if map_path:
        args += ["--map", map_path]
    if label:
        args += ["--label", label]
    return cli(*args, "--wait-minutes", str(wait_minutes), timeout=wait_minutes * 60 + 900)


@mcp.tool()
def call(op: str, args: dict | None = None) -> dict:
    """Send one op to the running game (`ops` lists them with their arguments)."""
    return cli("call", op, json.dumps(args or {}))


@mcp.tool()
def down(out_dir: str | None = None) -> dict:
    """Quit the game and stop everything `up` started; move its files to out_dir."""
    return cli("down", *(["--out", out_dir] if out_dir else []))


def main():
    mcp.run()


if __name__ == "__main__":
    main()
