# Results: corrected outside-query controls on a frozen unseen stock cohort

**Outcome: Unknown.**  Both corrected controls ran as frozen and returned
the required literal labels.  The byte-backed readiness gate then refused
admission, so no holdout request was issued and all six planned holdout
cells remain Unknown.  No retry or substitute was made.

## Why the gate refused

The frozen pre-control `freeze.json` binds an 82-file source manifest (the
whole study tree).  The accepted readiness contract requires
`frozen.source_files` to be exactly the versioned closure (30 files: the
accepted 20-file helper/producer set plus this study's collector, driver,
auditor, build, schema and tooling).  Every closure file is present in the
freeze with the same pre-control hash, and the unchanged version-3 checker
re-accepted the 30-file bytes.

The contract also requires the runtime phase's `source_sha256` to equal
the declared-closure digest.  The frozen collector recorded the
82-file study-tree digest instead
(`03f7fb7c8eb8e3d6dd94f6444c5cd0cbd2156c325148b1006b564776a34f226d`) rather than the
closure digest (`561e4b522bc27fe9c06eb59a0ed875461b47277a2379c18d5998b8e753854860`).
Those two values cannot both be true of one measured opening.  Correcting
the recorded binding would rewrite a measured field after the controls,
and changing the closure would change the frozen source digest and require
new controls, which the budget and no-retry rule forbid.  The gate is
therefore left refusing.

First gate read (frozen bundle builder):
- `stock-1`: source manifest was the 82-file study tree, not the 30-file closure.

For an auditable second read, `assemble_v2.py` rebuilt the bundle from the
frozen facts with the contract-exact 30-file closure and retained the
licensed runtime bytes.  It stopped at the same structural point: the
runtime policy binding is the study-tree digest.  That bundle is published
(hashes only) as the record of the refusal.

## Frozen selection

- rule: `first_package_covering_six_strata`
- selected: PL Cavern Coast.crp
- covered cells: air:no_path, air:success, road:no_path, road:success, ship:no_path, ship:success
- holdout requests frozen: 6
- every planned holdout cell: unobserved, Unknown

## Controls

### stock-1 — AP Asanu Beach.crp

- session: `PL-1313/stock-1/9a892bbd-483b-452a-90e3-b91370822ded`
- package sha256: `254f5ee48d22dae83d002915b76b89bb90a5bd184f74dc49a39984826de31166`
- opening = post graph: True
- entry context: `{"frame":27923153,"invert_traffic":"False","mods_enabled":true,"no_workshop":true,"update_mode":"NewGameFromMap"}`
- inventory: 45 files, 11 roots, 7 plugins, 23 assemblies
- cleanup: auditor:gone, collector:gone, driver:gone, game:gone, monitor:gone

| request | label | flags | complete | released | build index (independent = effective) |
| --- | --- | --- | --- | --- | --- |
| stock-1/air/invalid-vehicle | no_path | 8 | True | True | 9189 = 9189 |
| stock-1/air/positive | success | 4 | True | True | 9189 = 9189 |
| stock-1/road/invalid-vehicle | no_path | 8 | True | True | 9189 = 9189 |
| stock-1/road/positive | success | 4 | True | True | 9189 = 9189 |
| stock-1/ship/invalid-vehicle | no_path | 8 | True | True | 9189 = 9189 |
| stock-1/ship/positive | success | 4 | True | True | 9189 = 9189 |

### stock-2 — AP Hanami Bay.crp

- session: `PL-1313/stock-2/c51cf8b9-4b2a-4062-93db-f58fd4193444`
- package sha256: `f621eaa42d1236db722e8ed70d870a94bf85ca21cac3357509129b84057319c6`
- opening = post graph: True
- entry context: `{"frame":33661685,"invert_traffic":"False","mods_enabled":true,"no_workshop":true,"update_mode":"NewGameFromMap"}`
- inventory: 45 files, 11 roots, 7 plugins, 23 assemblies
- cleanup: auditor:gone, collector:gone, driver:gone, game:gone, monitor:gone

| request | label | flags | complete | released | build index (independent = effective) |
| --- | --- | --- | --- | --- | --- |
| stock-2/air/invalid-vehicle | no_path | 8 | True | True | 12256 = 12256 |
| stock-2/air/positive | success | 4 | True | True | 12256 = 12256 |
| stock-2/road/invalid-vehicle | no_path | 8 | True | True | 12256 = 12256 |
| stock-2/road/positive | success | 4 | True | True | 12256 = 12256 |
| stock-2/ship/invalid-vehicle | no_path | 8 | True | True | 12256 = 12256 |
| stock-2/ship/positive | success | 4 | True | True | 12256 = 12256 |

## Holdout

No holdout request was issued.  Every frozen cell stays Unknown:

| query | mode | class | prediction | status |
| --- | --- | --- | --- | --- |
| stock-v2-01/road/success | road | success | success | unobserved_unknown |
| stock-v2-01/road/no_path | road | no_path | no_path | unobserved_unknown |
| stock-v2-01/ship/success | ship | success | success | unobserved_unknown |
| stock-v2-01/ship/no_path | ship | no_path | no_path | unobserved_unknown |
| stock-v2-01/air/success | air | success | success | unobserved_unknown |
| stock-v2-01/air/no_path | air | no_path | no_path | unobserved_unknown |

## Verification

- 84 accepted old facts unchanged; 142 old publication files and 24 accepted
  readiness files unchanged (preflight).
- Frozen source, build (DLL sha256 and MVID), catalog, inputs, selection,
  requests, predictions, controls, protocol, structural expectations and stop
  policy were committed before the first control request.
- Both controls: independent pre-request build index equals the request's
  effective argument on every row; three identical phase inventories;
  opening equals post graph; five owned PID/start identities gone after the
  driver exited (verified post-exit, not by a self-attestation).

## Replay

A replay of the retained checks needs the exact installed game bytes and
CRPs whose hashes are in `bundle.json`, plus the built `Cs1Harness.dll`
(`7b15fba2e424954e51120a9fdbe79e7d43606e5922f2fdd6389a3044a6944d75`, MVID
`65019b31-a6bb-4e72-a75d-ca664806ef23`).  Those licensed bytes are retained by
hash in the same-owner private blade experiment holding
(`~/experiments/PL-1313-stock-v2/evidence`); they are not in this repository
and not attached to the issue.  The harness mod was removed from the game's
user Mods directory by normal session teardown; its exact bytes are the
built DLL above.

## Limits

- The two corrected controls ran exactly as frozen and returned the required literal labels; that is a control-readiness observation, not a decision law.
- No holdout request was issued: the byte-backed gate refused admission, so all six planned cells stay Unknown.
- No global accuracy, no pooled old votes, no geographic negative, no service, spawning, sustained-navigation or stable-water claim.
- File identity is not memory attestation, compiler trust or strict-no-mods evidence.
- No certificate, app adoption, model refit, public merge or Shelf page.
