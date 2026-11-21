# Reproduce the rail study

From the repository root:

```sh
uv run --directory tools/cs1-harness python \
  ../map-factory/capability-evidence/rail-v1/verify.py
uv run --project tools/map-factory python \
  tools/map-factory/capability-evidence/outside-v1/verify.py --require-nine-attempts
uv run --directory tools/cs1-harness python -m unittest discover -s tests
```

The first command checks compressed and original raw hashes, current frozen
source hashes, the original cohort, package bindings, frozen request inventory,
dates, exact returned endpoints, native context and cleanup. It replays evidence
interpretation, not the game. `integrity.json` names every retained raw file.
No proprietary package binaries, assemblies or decompiled code are included.

Earlier failed/calibration revisions reproduce with their exact sources, not
the current planner. For example, in an empty task-local path:

```sh
git worktree add --detach REPRO aac994054f6024043225297eb0af41bec6b0287b
PYTHONPATH=REPRO/tools/cs1-harness uv run --directory tools/cs1-harness python \
  ABSOLUTE_REPRO/tools/map-factory/capability-evidence/rail-v1/verify.py
```

Use the v1 SHA above for the first revision. Because `uv --directory` changes
the working directory, use an absolute PYTHONPATH and script path in practice.
Both historical reproductions were run during this study. `git archive` omits
these research tools by the repository's export-ignore policy; use a worktree.

A new live study uses the original packages, not rebuilt/recaptured inputs:

```sh
uv run --directory tools/cs1-harness cs1-harness build
uv run --directory tools/cs1-harness python -m cs1_harness.rail_study prepare --study RUN
uv run --directory tools/cs1-harness python \
  ../map-factory/capability-evidence/rail-v1/run_foreground.py controls --study RUN
# Refuses to run without the validated stock-positive/invalid-pair gate.
uv run --directory tools/cs1-harness python \
  ../map-factory/capability-evidence/rail-v1/run_foreground.py cohort --study RUN
```

Use an absolute RUN path; `--only SLUG` allows one cohort opening. Every map
acquires/releases the existing fair queue with zero wait and fresh offline/
idle guards. The foreground driver joins both collector and telemetry monitor
before returning. Busy/failed attempts are retained. No account, install,
security, shared-service, map or exporter change is part of this study.
