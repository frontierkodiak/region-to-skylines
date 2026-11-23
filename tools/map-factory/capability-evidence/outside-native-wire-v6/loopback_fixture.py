"""Finite owned loopback process; scripted native-shaped replies, never native evidence."""

from contextlib import contextmanager
from pathlib import Path
import select
import socket
import subprocess
import sys
import time

from wire import decode, encoded, Unknown


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return dict(pid=pid, start_ticks=int(fields[19]))
    except FileNotFoundError:
        return None


@contextmanager
def server(script, directory, mode="script", delay=1.5):
    """Parent binds the only port a fixture client may use; no service discovery."""
    directory.mkdir(parents=True, exist_ok=False)
    plan = directory / "plan.json"
    plan.write_bytes(encoded(dict(script=script, mode=mode, delay=delay)))
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)
    process = subprocess.Popen(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            str(listener.fileno()),
            str(plan),
        ],
        pass_fds=(listener.fileno(),),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
    )
    birth = identity(process.pid)
    evidence = dict(birth=birth, port=listener.getsockname()[1], kind="CONSTRUCTED")
    try:
        ready, _, _ = select.select([process.stdout], [], [], 3)
        if not ready or process.stdout.readline() != b"ready\n":
            raise Unknown("fixture failed readiness")
        yield evidence
    finally:
        process.stdin.close()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            if identity(process.pid) != birth:
                raise Unknown("refuse kill: fixture PID/start changed")
            process.kill()
            process.wait(timeout=3)
        listener.close()
        process.stdout.close()
        evidence.update(exit_code=process.returncode, after=identity(process.pid))
        if evidence["after"] == birth:
            raise Unknown("fixture still present")
        (directory / "lifecycle.json").write_bytes(encoded(evidence))


def serve(fd, plan):
    listener = socket.socket(fileno=fd)
    config = decode(plan.read_bytes())
    script = iter(config["script"])
    calls = []

    def save():
        (plan.parent / "calls.json").write_bytes(encoded(calls))

    print("ready", flush=True)
    end = time.monotonic() + 20
    while time.monotonic() < end:
        ready, _, _ = select.select([listener, sys.stdin], [], [], 0.05)
        if sys.stdin in ready and not sys.stdin.buffer.read(1):
            break
        if listener not in ready:
            continue
        conn, _ = listener.accept()
        conn.settimeout(0.5)
        with conn:
            buf = bytearray()
            while b"\n" not in buf and len(buf) <= 1 << 20:
                data = conn.recv(4096)
                if not data:
                    break
                buf.extend(data)
            if not buf:
                continue
            request = decode(bytes(buf))
            calls.append(dict(request=request, accepted=time.monotonic()))
            save()  # A stall cannot be asserted solely from the client's timeout.
            row = next(
                script,
                {
                    "op": request["op"],
                    "reply": {"ok": False, "error": "script exhausted"},
                },
            )
            if row["op"] != request["op"] or (
                "args" in row
                and row["args"] != {k: v for k, v in request.items() if k != "op"}
            ):
                payload = (
                    encoded({"ok": False, "error": "fixture request differs"}) + b"\n"
                )
            else:
                payload = (
                    row.get("raw", "").encode()
                    if "raw" in row
                    else encoded(row["reply"]) + b"\n"
                )
            mode = row.get("mode", config["mode"])
            try:
                if mode == "blocked":
                    calls[-1]["blocked_until"] = time.monotonic() + config["delay"]
                    save()
                    select.select([sys.stdin], [], [], config["delay"])
                elif mode == "drip":
                    for byte in payload:
                        conn.sendall(bytes([byte]))
                        time.sleep(0.02)
                elif mode == "no-newline":
                    conn.sendall(payload.rstrip(b"\n"))
                    select.select([sys.stdin], [], [], config["delay"])
                else:
                    conn.sendall(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass
            calls[-1]["finished"] = time.monotonic()
            save()
    listener.close()
    save()


if __name__ == "__main__":
    serve(int(sys.argv[1]), Path(sys.argv[2]))
