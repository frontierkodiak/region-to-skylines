"""Finite constructed role processes. Only the collector owns the socket client."""

from pathlib import Path
import signal
import sys
import time

from authority import ConstructedAuthority
from loopback_fixture import identity
from runtime import Transport, collect
from wire import Deadline, Unknown, decode, encoded
from wire_supervisor import atomic, await_file


def cancelled(signum, frame):
    raise Unknown("external supervisor interrupted owned collector")


def collector(config, directory, deadline):
    import accepted_api as api
    from exercise import ConnectedFixture
    from entry import Request, enter

    signal.signal(signal.SIGTERM, cancelled)
    frozen = api.spec.read(Path(config["freeze"]))
    store = api.spec.ArtifactStore(Path(config["store"]))
    raw = config["request"]
    request = Request(
        raw["freeze_sha256"],
        encoded(raw["binding"]),
        raw["session"],
        encoded(raw["limits"]),
        "CONSTRUCTED",
    )
    trace, transport, error = [], None, None

    def snapshot(done=False):
        atomic(
            directory / "collector.json",
            dict(
                kind="CONSTRUCTED",
                records=transport.records if transport else [],
                pending=transport.pending if transport else None,
                trace=trace,
                inventories=transport.inventory_captures if transport else [],
                error=error,
                done=done,
            ),
        )

    try:
        with enter(
            frozen,
            store,
            request,
            ConstructedAuthority(request),
            ConnectedFixture(config, trace),
        ) as session:
            transport = Transport(session, session.native, store, api)
            transport.snapshot = snapshot
            collect(transport, config["births"], config["limits"])
    except BaseException as failure:
        error = f"{type(failure).__name__}: {failure}"
    finally:
        snapshot(done=True)


def driver(config, directory, deadline):
    birth = config["births"]["collector"]
    while identity(birth["pid"]) == birth:
        deadline.pause(0.01)
    value = decode(await_file(directory / "collector.json", deadline))
    payload = dict(
        kind="CONSTRUCTED",
        binding=config["binding"],
        births=config["births"],
        driver_pid=config["births"]["driver"]["pid"],
        records=value["records"],
    )
    atomic(directory / "driver.json", payload)


def auditor(config, directory, deadline):
    payload = decode(await_file(directory / "driver.json", deadline))
    if payload["binding"] != config["binding"] or payload["births"] != config["births"]:
        raise Unknown("driver changed input bindings")
    atomic(
        directory / "auditor.json",
        dict(
            driver_handoff_sha256=__import__("hashlib")
            .sha256(encoded(payload))
            .hexdigest(),
            records=len(payload["records"]),
            checked=True,
        ),
    )


def monitor(config, directory, deadline):
    birth = config["births"]["collector"]
    samples = []
    while True:
        current = identity(birth["pid"])
        samples.append(dict(at=time.monotonic(), identity=current))
        if current != birth:
            break
        deadline.pause(0.02)
    atomic(directory / "monitor.json", dict(collector=birth, samples=samples))


def main():
    role, location, end = sys.argv[1:]
    directory = Path(location)
    deadline = Deadline(float(end))

    # No role can remain blocked forever waiting for configuration or a producer.
    def expired(signum, frame):
        raise Unknown("finite role deadline expired")

    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, deadline.remaining())
    config = decode(await_file(directory / "config.json", deadline))
    try:
        {
            "collector": collector,
            "driver": driver,
            "auditor": auditor,
            "monitor": monitor,
        }[role](config, directory, deadline)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == "__main__":
    main()
