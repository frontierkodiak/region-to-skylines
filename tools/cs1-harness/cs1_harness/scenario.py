"""Standard, disposable city construction on top of a normal game session."""

from __future__ import annotations

import time

from .client import HarnessError


def build(session, log=print) -> dict:
    """Build using native tools, keeping every rejection in the run's evidence."""
    log("building test-city in the start tile")
    session.client.call("scenario_build")
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        session.alive()
        status = session.client.call("scenario_status")
        if status["state"] == "failed":
            raise HarnessError(f"test-city construction failed: {status['error']}")
        if status["state"] == "done":
            return status
        time.sleep(0.5)
    raise HarnessError("test-city construction did not finish in 120 seconds")


def reachability(session) -> dict:
    """Require actual passenger-car paths, not just connected segment ids."""
    status = session.client.call("scenario_paths", start=True)
    deadline = time.monotonic() + 60
    while not status["complete"] and time.monotonic() < deadline:
        session.alive()
        time.sleep(0.5)
        status = session.client.call("scenario_paths")
    if not status["complete"]:
        raise HarnessError("test-city native car paths did not finish in 60 seconds")
    return status
