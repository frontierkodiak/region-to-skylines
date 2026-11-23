# Outside-query protocol and readiness

PL-1307 adds an isolated off-game module at exact accepted source
`d745b14e3e207ee67f91033811958a2934fb38a4`. Target: internal
`PL-1142-native-v2`. No accepted file is changed.

- `protocol.py` parses MetaBool and exact RPC envelopes into typed literal results.
- `schema.py` validates the v2 frozen-input and runtime schema before comparisons.
- `evidence.py` rehashes referenced retained bytes.
- `readiness.py` checks fresh complete controls and verified input coverage.
  Readiness means ready for independent measurement, never native qualification.
- `bridge_contract.py` separates exact object identity from consumed-field equality.
- [SCHEMA.md](SCHEMA.md) specifies the corrected byte-backed bundle.
- [CONTRACT.md](CONTRACT.md) traces actual field reads and public wire semantics.
- [NEXT-STUDY.md](NEXT-STUDY.md) proposes the next bounded independent experiment.
- `bindings.json` binds retained real-byte fixtures and the source/helper closure.
  `module.json` binds this new module, tests and documents.

The current result remains **Unknown** for pre-export qualification. The old
48 selected labels agree, only 16 road requests have strict bridge identity,
and the failed first control leaves all three modes unqualified. Parsing the
first control's `"False"` correctly does not retroactively complete its queries.

## Run offline

From the repository root, use the standard library through uv. No game packages,
mod builds, live services or old outcome/scorer functions are needed.

```sh
uv run --no-project python -m unittest discover -s tools/map-factory/capability-evidence/outside-readiness-v1 -v
ruff check tools/map-factory/capability-evidence/outside-readiness-v1
uv run --no-project python tools/map-factory/capability-evidence/outside-readiness-v1/check.py verify
uv run --no-project python tools/map-factory/capability-evidence/outside-readiness-v1/check.py retained-controls
```

`verify` exits 0 after file/source closure checks. `retained-controls` exits 2
with specific Unknown reasons, including Asanu's incomplete control opening and
missing prospective evidence in Hanami's old schema. `bundle --input FILE --evidence-root DIRECTORY`
checks a proposed v2 input/control bundle. Version 1 is rejected. Exit 0 means ready for measurement;
exit 2 means Unknown/not ready. Neither output authorizes collection or a cert.

The regressions read original gzip members and preparation zip in place, not
responses recreated by today's serializer. Tests reintroduce original truthiness,
body-only envelope checking and truthy completion to demonstrate failures. A
constructed height-only counterexample runs the unchanged pure predicate, never
historical labels or scorer functions.

## Regenerate bindings after a deliberate source-only edit

Run `uv run --no-project python tools/map-factory/capability-evidence/outside-readiness-v1/bind.py`.
It regenerates both manifests. `module.json` hashes every file in this new
prefix except itself and `__pycache__`. Do not regenerate old integrity, freezes,
predictions or outcomes. Commit the new manifests with the reviewed source.
The Git commit is the immutable review boundary; hashes alone do not prove authorship.

## Acceptance correction

The earlier `d39a31e` head is **not accepted**. Its old tests passed while five
parent regressions showed false-ready results for shared nulls and omissions.
`rejected-d39/` retains that proof unchanged. `test_acceptance.py` adapts those
regressions to byte-backed v2 inputs and checks shared omissions, malformed maps,
unknown facts, wrong runtime bindings and corrupt or missing evidence. Each
acceptance test first proves that its honest CONSTRUCTED context is ready for
measurement and still unqualified. The prior peer PASS does not extend to v2.
