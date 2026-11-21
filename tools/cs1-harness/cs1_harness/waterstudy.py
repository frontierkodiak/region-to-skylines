"""Optional full-floor snapshots, with unique sequence IDs and explicit missed slots."""

from __future__ import annotations

import math

from .client import HarnessError


class WaterStudy:
    def __init__(self, client, stage, points, every, record):
        if not math.isfinite(every) or not 0 < every <= 5:
            raise ValueError("water-study-every must be finite and in (0, 5] game-minutes")
        self.client, self.stage, self.points = client, stage, points
        self.every, self.record = every, record
        self.next_slot = 0
        self.sequence = 0

    def capture(self, actual_minute, *, final=False):
        if not math.isfinite(actual_minute) or actual_minute < 0:
            raise ValueError("Invalid observed study minute")
        due = math.floor((actual_minute + 1e-9) / self.every)
        if not final and due < self.next_slot:
            return None
        missed = list(range(self.next_slot, due)) if due >= self.next_slot else []
        prefix = f"ws{self.sequence:06d}"
        result = self.client.call(
            "water_study_snapshot",
            dir=str(self.stage / "grids"),
            prefix=prefix,
            points=[[p["x"], p["z"]] for p in self.points],
        )
        if result.get("schema") != "polli.water-study-snapshot/1" or result.get("prefix") != prefix:
            raise HarnessError("Water study snapshot identity mismatch")
        if len(result.get("samples", [])) != len(self.points):
            raise HarnessError("Water study snapshot omitted authored probes")
        for point, sample in zip(self.points, result["samples"]):
            if abs(sample["x"] - point["x"]) > 0.001 or abs(sample["z"] - point["z"]) > 0.001:
                raise HarnessError("Water study snapshot changed authored probe positions")
            sample["name"] = point["name"]
        result.update(
            sequence=self.sequence,
            trigger_game_minute=actual_minute,
            scheduled_slot=due,
            scheduled_minute=due * self.every,
            missed_slots=missed,
            final=final,
        )
        self.record("water_study_snapshot", result)
        self.sequence += 1
        self.next_slot = max(self.next_slot, due + 1)
        return result
