# Native-evidence admission · PL-912 · short-run residual blocks promotion

The lead's November 15 decision is explicit: **a genuinely wet stream may keep
CS1's native sandy shore.** Dry beds reading as broken water are the defect;
grass with no stream and sand-free rendering are out of scope. Every existing
observation, required flag, mask and acceptance threshold remains unchanged.

Neither rejected arm is revived. The held-DEM arm made the water narrower,
lowered some existing floors and lost Pittsburgh support. The broad gravity
omission arm failed native wetness. Both remain quarantined.

## One bounded next candidate

`native_admission.py` consumes an exact prepared package and its existing native
records. It plans removal only for a **complete mapped minor-water source
piece** that has neither water nor native water within 64 m at five minutes,
and no such support in any later recorded epoch. This uses dense source-line
vertices from both the writer and browser rasterizers, not the qualification
probe list or camera bounds. The 64 m / seven-unit test is the existing harness
near-water definition, not a new qualification threshold. It does **not** claim
that nearby water alone makes a visibly dry carved channel acceptable.

The same selector runs on all five maps. It covers bank-limited river
components and feasible modeled streams. Unforced streams already left uncarved
by the current writer are not reactivated. Disconnected components with the
same name are separate; major rivers are not selected merely because an
individual map-tile fragment is dry. Feature indices refer to `rivers` followed
by `streams` **after `surface_geometry()` filtering**, not raw `geometry.json`
array indices.

For eligible pieces, the planner replays removal of their inherited combined
line/polygon excavation, respecting retained lines and independent lake cuts.
It also restores the old Python incision in their own three-cell territory.
It never re-routes the surviving network, changes a water head, adds a supply
or deepens any existing terrain vertex. Selected startup films are removed.

These protections win over omission:

- Every recorded native wet cell, even below the wetness threshold, and the
  neighboring vertices supporting its interpolation patches.
- Retained startup water and its continuous interpolation support, resolved to
  a finite fixed point after clearing the omitted film.
- All source-control footprints, with an extra two-cell margin; all controls
  remain exactly unchanged, including withdrawals and output rates.
- Actual network-node/segment corridors, source lakes and ocean polygons.
- Independently retained browser-cut contributions at shared endpoints.

A source piece whose line cannot reach its remaining independently supported
terrain is **deferred**, not partially declared uncarved. Deferred dry pieces
remain genuine residuals: a visible residual in the opening/Areas gate blocks
the sweep. This is a conservative first unit, not proof that every possible
dry branch has been resolved.

## Evidence and delivery boundary

The code requires a committed planner snapshot; it hashes source files before
and after planning. It binds the exact original package, initial grids,
geometry, held DEM, native epochs, frozen observation file and candidate grids.
The packager checks these bindings and the complete five-map preflight before
replaying the original resource plan. It decodes actual CRP grids/networks.
Neither helper writes an accepted fixture or changes the default generator.

This is currently a **prepared-map experiment**, not a shipped browser/Python
admission API. Before promotion, the generic evidence contract must be wired
through both writers and prove the same exact grids/packages under Python and
shipping JS/Pyodide. Input-hash-bound native evidence must fail closed on stale
or different inputs. The unchanged current fixture contract is not acceptance
of these new packages.

The CPU audit compares saved native states under the proposed floors. It is
not a new water simulation and cannot establish supply, flooding, visible
continuity or 60-minute sustainment. No prior qualification transfers to a
changed package.

## Execution order

Committed planner snapshot `7786d4f` produced this **CPU-only** preflight. The
same rule also handles already-uncarved dry stream pieces; piece counts are not
counts of newly repaired channels. Detailed residuals and package hashes are in
`fixtures/native-admission-preflight.json`.

| Map | Raised terrain vertices | Startup-water cells cleared | Required points with initial nearby water, CPU replay |
| --- | ---: | ---: | ---: |
| Asheville | 14 | 3 | 1,261 / 1,261 |
| Innsbruck | 0 | 1 | 694 / 694 |
| Rio | 192 | 37 | 1,556 / 1,556 |
| Pittsburgh | 1 | 0 | 1,799 / 1,799 |
| Charleston | 1 | 33 | 2,214 / 2,214 |

No existing floor is lowered. All encoded source controls, original resource
plans and hydrology/layout records remain exact. The independent saved-state
audit preserves all recorded five-through-sixty-minute wet interpolation
patches and all retained startup patches. This still does **not** predict a
fresh native run. In Rio, two river pieces are restored and three candidates
remain deferred; the original wet opening connector is retained.

The November 15 reservation was respected; the fresh native attempts below
queued after its end and behind existing holders. Every future launch must
recheck `cs1-harness queue`, `holder.json` and Steam, then use the normal silent
private `:57` lifecycle. A timer is never proof the account or slot is free.

1. Fresh Rio zero/five-minute native opening **and Areas** views, retaining all
   4,256 frozen observations and the unchanged 1,556-member required cohort.
   Inspect visible water, not sand alone or inferred wetness. Also capture
   Asheville's actual zero/five opening and Areas under the same rule.
2. Stop on a short gate regression or visibly broken residual. Do not launch
   a full sweep to discover a failure already established by the short gate.
3. Complete generic writer/JS/Pyodide integration and the new fixture contract
   with exact candidate parity; do not relabel old packages or omit probes.
4. One fresh 60-minute evaluation per map, preserving all old passing gates.
   Keep the original Rio flood subset and Charleston ground-truth failures
   explicit. Charleston remains diagnosis-only; no mask/check changes.
5. Phone-readable actual before/after sheets, steward and Opus review, then
   landing through a PR. No self-merge or agent acceptance.

## Actual November 15 Rio result: not a visible completion

The prepared Rio package `1745bab2356ea8c654eaeb3c2578cea23c8ded99ed7d1daf7e19f53ca729158b`
ran for **5.109722 game minutes**, with diagnostic source `82701e8`.
All 4,256 frozen observations remained. Required wet-or-near coverage was
**1,556/1,556 at zero and 1,545/1,556 at five (99.2931%, unchanged 95% gate)**.
The eleven dry required positions at five are exactly the old reference's
eleven: zero new-only or old-only misses. This is two sampled epochs, not a
wet-throughout qualification.

Initial terrain/water match the candidate exactly; final terrain is unchanged.
All 290 controls' positions, targets, intake/output rates match at both epochs.
Actual opening and Areas cameras match the reference in all ten compared
position/render fields. Actual before/after sheets retain the genuinely wet
opening stream and its native shore. **The central Areas result is effectively
unchanged and does not earn promotion.** Three dry candidates remain carved,
but PL-990 corrects their attribution: two are at the far western tile edge;
the third is the intake's own bed. They are not the cause of the central image.
No Asheville short, other candidate
native map or 60-minute evaluation followed this failed visible checkpoint.

The whole-piece guard restores surface-filtered pieces 21 (Rio Faria) and 33
(Rio Méier), raising 192 vertices and clearing 37 startup cells. It defers
pieces 35/36 (Rio Méier) and 151 (Rio Trapicheiros). This is not a complete
dry-reach implementation. The numerical record is
`fixtures/native-admission-short-rejected.json`; actual raw frames, grids,
receipts and phone sheets are attached to PL-912.

## Native hydraulic-floor counterexample

A second, **read-only reference** diagnostic ran for 5.100278 game minutes at
`b3fa6fe`, on original package
`4bc5628e6af29f6c2beb62629bf350fe6a8324e5f5a67bb5f267a8381dd6b7a7`.
It is not another candidate or an attempt to qualify the first one. The harness
now dumps actual hydraulic `BlockHeights` and `BlockHeightTargets` alongside
the existing raw terrain and water, and reads each source's `buffered_water`.
These are additive observations, not field writes.

- The native hydraulic floor differs from raw terrain at **54 vertices**, by
  up to **19.46875 m**. The cause of these differences is not established.
  Floor equals target everywhere, and is byte-identical between zero and five.
- `native_support.sample_water()` using that floor exactly reproduces native
  ground, surface and wetness for all **4,256 original + 81 supplementary
  observations at each paused epoch** (8,674 observations total; zero mismatch).
  Raw terrain alone does not. The supplemental positions use native float32
  coordinates; the frozen original observations are unchanged.
- Supplementary source-line sampling every 4 m finds **zero wet and zero
  within-64-m readings on all five disputed pieces at five minutes**. At zero,
  most have startup water. This diagnoses drainage, not sustained wetness.
- The measured floor also matches all 25,536 historical Rio ground samples.
  Old t005/t045 grid/timeline pairs still disagree in water/surface (22/24 wet
  mismatches); do not call these exact co-timed water replays or waive them.

The precise interpolation-support helper is **diagnostic only**, not wired
into admission. It conservatively retains every patch that can report the
existing seven/eight-unit water thresholds, including water inferred over an
empty lower corner and clamped boundary patches. Tests exercise those cases.

The crucial intake is hydrology source 91 (native ID 92), the downstream
Trapicheiros surface/tunnel inlet at (-2160, 2112). Target 93.671875 m,
intake 52,428, output zero remain unchanged. Its physical radius is about
101.589 m; nearest qualifying depth vertex at five is 112 m away. **Native
buffered water is 10 at five despite zero output flow. It is not proven
inactive.** Native intake availability depends on ground as well as water and
target, including dry cells below target. Merely preserving control-table
bytes does not prove withdrawal unchanged when the underlying floor is raised.

A CPU falsification probe—not a package or proposed default—replaced the
blanket positive-water stencil with precise support and omitted that intake's
guard. It could restore piece 36, but still stranded four vertices on piece 35
and one on 151. Its intake omission is **not admissible evidence of safety**.
The remaining cut ownership/startup interactions need source-grounded review;
do not narrow a selector or call these vertices exempt.

PL-990 independently reproduced the sampler and intake constraint. It found
that the 64 m whole-piece selector also misses genuinely dry line vertices near
water, and that the slow-decaying initial shore stamp can outlive startup film
which never returns. A new generic dry-subreach/startup-film unit is documented
in [DRY_SUBREACHES.md](DRY_SUBREACHES.md). It is not a shipped or qualified rule.
All old gates and fixture bytes remain unchanged. The accepted default on main
is unchanged; the proposed branch now has an input-bound shipping integration
under verification, described in `DRY_SUBREACHES.md`. It is not acceptance.
PL-979 owns reservoir/new-supply research; this baseline does not wait for or
absorb it.

Both native attempts completed foreground with empty owned cleanup receipts.
Normal quit required exact-owned-game termination after its grace period;
neither was a spontaneous crash. The member waits and slot timer are consumed.
