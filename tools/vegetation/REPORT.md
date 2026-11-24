# Vegetation supply: observations and proposed bar

This is a partial supply ledger, not a vetted recommendation set. No Workshop
asset has completed all review gates. Native results and their limitations are
recorded in the observation bundle and on the shelf.

## Installed supply

Blade’s installed game assembly has SHA-256
`c7f0e723dfe867d10aef73f14268bcf9f5ea4bab1c5ce4987897ed27f46511a1`.
The read-only scan inspected 276 root serialized `.assets` and `levelN` files,
with per-file SHA-256 receipts and no read failures. It found 85 TreeInfo
objects: **84 non-template tree prefabs**, including separate winter variants,
and the editor’s TreeTemplate. Name screening found **77 natural-prop
candidates**. No extra TreeInfo was found in the level files.

Main-mesh triangles among the 84 non-template trees range from **288 to 2,826**,
with a **929 median**. Winter variants are counted separately; this is a prefab
distribution, not an instance-weighted or taxon-weighted distribution. The data
contains unscaled mesh height and X/Z envelopes and each texture’s dimensions.
Native random-scale ranges are separate where observed.

All installed tree prefabs were inventoried, including DLC/creator-pack names
and winter variants. That is not proof that every released DLC is installed,
owned, or available in every theme. Prop screening is explicitly not proven
exhaustive. Theme masks and runtime behaviour are not inferred from file names.

## Workshop discovery

Discovery starts with [MrMaison’s Nature Collection](https://steamcommunity.com/workshop/filedetails/?id=644677259)
and [pdelmo’s low-poly collection](https://steamcommunity.com/sharedfiles/filedetails/?id=963893498),
then enumerates all pages returned by the public Tree tag and named Prop/Prop
Decal searches. The captured Tree query reports **775 entries across 26 pages**.
The normalized index excludes obvious unrelated discovery items but retains
those records separately to audit screening. This is not an exhaustive census
of every untagged bush, grass, rock or decal on the Workshop.

Item facts come from Valve’s public `GetPublishedFileDetails` API. Ratings and
author names supplement them from public Steam pages; declared dependencies are
inspected separately. Missing pages and unmeasured packages are explicit.
There are **955 screened vegetation candidates** in this snapshot. Declared
dependencies were successfully inspected for **42/955**; **913** were rate-limited
and remain unknown. The full discovery set had 57 successful page inspections
out of 1,722 attempts. API metadata and public browse state were retrieved, but
that is not dependency verification. The refresher now stops on the first HTTP
429, preserves progress, resumes only unchecked items and paces bounded batches.

Subscriber counts do not influence the quality verdict. Cached packages are
read locally and never redistributed. An empty public `file_url` is recorded;
no third-party package mirror or Steam login is used by the collector.

## Coverage by RESOLVE biome

The [RESOLVE 2017 biome scheme](https://developers.google.com/earth-engine/datasets/catalog/RESOLVE_ECOREGIONS_2017)
provides fourteen bins. Assignments here are conservative **name-based screening
hypotheses**, not occurrence, climatic suitability or species-identification
results. Urban ornamental use may be far outside a plant’s natural biome.

| Biome | What the named built-ins provide | Important gap |
|---|---|---|
| Tropical moist broadleaf | Palms, a few broadleaf ornamentals | Diverse canopy hardwoods, lianas, understory, regional architecture |
| Tropical dry broadleaf | Baobab/umbrella-thorn-like forms and palms | Dry-forest canopy diversity and drought-deciduous variants |
| Tropical conifer | Generic pine forms | Tropical pine species/architecture, associates |
| Temperate broadleaf/mixed | Alder, beech, birch, maple, oak, cottonwood and planted fruit trees | Age classes, understory and regional genus proportions |
| Temperate conifer | Pine, spruce, yew and redwood forms | Fir, hemlock and cedar diversity without Workshop assets |
| Boreal/taiga | Pine, spruce, birch and static winter versions | Larch, dwarf woodland, wet-ground vegetation |
| Tropical savanna | Baobab and umbrella thorn are useful silhouettes | Grass and shrub diversity, size/age variation |
| Temperate grassland | Generic grass and shrubs | Prairie/steppe grasses and forbs; avoid tree-heavy substitution |
| Flooded grassland | Sparse generic grasses | Living reeds/sedges and wetland structure, not tied-reed decoration |
| Montane grassland | Generic low vegetation only | Alpine tussocks and dwarf shrubs |
| Tundra | No named palette established | Dwarf willow/birch, sedges, mosses and lichens; snow trees are not tundra |
| Mediterranean | Pine and evergreen-oak silhouettes | Olive/cork oak and maquis diversity |
| Desert/xeric | No named cactus/xeric-shrub palette established | Succulents and xeric shrub forms |
| Mangroves | No named built-in mangrove established | Root architecture and canopy diversity |

Temperate and conifer forest **forms** are relatively well served compared with
the other bins, not ecologically complete. Tall tropical canopy, mangrove,
xeric, alpine/tundra and grassland-understory palettes are the clearest gaps.
The Workshop contains named candidates for some gaps, including mangrove,
eucalyptus, olive, acacia and tree fern. They are candidates, not approved fills.

## Proposed independent quality bar

The [creator tree guide](https://cslmodding.info/asset/tree/) distinguishes
two-sided main geometry, vertex-colour wind, and the tree billboard path. A
building-style authored-LOD checklist alone would misjudge trees.

1. **Forest fill, 100k–250k map instances.** Start at a main-mesh target rounded
   from the installed p75: approximately **1,500 triangles**. Budget geometry as
   near-visible instances × main triangles plus far-visible instances × native
   LOD triangles. Do not multiply main triangles by all map instances and call
   that an actual frame’s workload. Inspect alpha area, empty cards and overdraw.
2. **Textures.** Start at a **1,024 px per-side target** and **128 MiB unique
   resident palette target**. These are provisional policy values, not measured
   limits. Include compression, mipmaps and sharing; texture memory is shared
   across instances, not charged in full for every tree.
3. **Native timing.** Five A/B/A repeats at two zooms, identical stock population
   and positions, 120 warm-up + 300 retained frames per arm. Proposed acceptance:
   at most **10% p95 wall-frame regression**; baseline drift above **5%** makes it
   inconclusive. Report run spread, errors and the limiter. A failure to identify
   the limiter also makes any performance verdict inconclusive.
4. **LOD/art/scale.** Multi-angle near, gameplay and transition views; coherent
   silhouette and colour; no alpha fringes or severe pop; plausible wind and
   roots. Height and crown spread, including native random scale, should match
   a sourced plant size class within **20%**. Separate winter or fall prefabs
   do not prove dynamic snow/season behaviour.
5. **Maintenance/dependencies.** Fresh-city load, save/reload and installed-game
   compatibility; resolve hard dependency closure. No embedded assemblies or
   required mods in the default vegetation-only profile. Optional aesthetic
   suggestions are not hard dependencies. Last-update age alone is not failure.
6. **Recommendation and other characteristics.** Public original author link,
   credit, provenance and terms review. Reference and recommend, never bundle
   Workshop binaries. Also review age/size variants, texture sharing, consistent
   scale and colour, repeated silhouettes, root float, deterministic prefab
   identity and missing-asset behaviour.

Above-target assets can still be reviewed for an **accent ≤5k-instance** or
**specimen ≤200-instance** role. A pack may contain both cheap and expensive
variants. The current item-level failure exposes an over-target member; it does
not mean every member is unusable. Nothing is auto-approved for an exported map.

## Native reference result

The accepted timing run used the exact stock Grand River package, 139,362 tree
instances, a paused fresh city, fixed noon lighting, 1920×1080 and an interior
dry forest patch at (-1350, -1350). It compared `Conifer2` against cached
`2262443894.Lodgepole Pine 03 19m_Data`. All thirty arms retained that count:
five A/B/A repeats at each zoom, 120 warm-up and 300 retained frames per arm.
Dry-terrain ray checks and rendered-frame PNGs establish actual forest framing.

| Camera size | Baseline p95 median | Candidate p95 median | Paired p95 difference median | Maximum A/A drift |
|---|---:|---:|---:|---:|
| 350 | 36.24 ms | 38.32 ms | +4.84% | 1.13% |
| 1400 | 21.02 ms | 21.27 ms | +1.91% | 4.03% |

The ratio column is the median of within-repeat paired ratios, not the ratio of
the displayed overall medians. Candidate p95 ranges were 33.76–38.89 ms near
and 20.51–21.93 ms far. These are **inconclusive performance evidence**, not a
pass: the limiter is not isolated, the two trees have different silhouettes,
and the host is shared. None of the twenty candidates is fully approved.

The renderer was blade's RTX 2080 Ti at PCI 05:00.0. Across 121 read-only
samples (00:45:46–00:56:35 UTC), board peaks were 10,821 MiB, 148.18 W and 65°C;
the sampled game-only VRAM peak was 2,673 MiB. The observed card limit was
200 W, unchanged by this work. Other workloads occupied substantial VRAM.
CPU data is `ps` lifetime-average utilization, not instantaneous attribution.
The driver window was approximately 18m04s including the FIFO queue and load.
Three existing serialization errors were present before and after, with no
new errors. The session receipt and cleanup check report no surviving game,
Steam instance, transient unit, state file or installed package copy.

An earlier outer-world camera run was rejected as sky-only; none of its timing
samples enters these results. Native GPU-only meshes are marked unreadable,
not zero triangles. Their offline serialized counts remain authoritative.
The observation manifest records the driver/build hashes and rejected attempts.

The twenty-pair sheet was recaptured in a second owned disposable session with
genus/form-first built-in neighbours and closer views. Its initial clipped
fixture was replaced through a guarded existing-session adapter; the owning
driver was then explicitly interrupted for context teardown. Its receipt has
empty cleanup and no offline-account error. The three serialization errors
remained unchanged. The 98 resource samples peaked at 10,821 MiB total,
2,673 MiB game, 130.75 W and 62°C; controller window28m12s includes the queue.

**The sheet remains exploratory.** Some tall built-in crowns still clip because
their native instance scale reaches2×. Wide gameplay originals are included.
The driver now sizes both maximum-scale envelopes by perspective-frustum
constraints; a forward-projection check covers all twenty observed pairs.
That last scale-aware correction has **not** been recaptured natively. These
images cannot support a completed scale/billboard review or best-twenty claim.

## What still blocks acceptance

The cached-pool sheet is not the globally best twenty Workshop trees. Uncached
shortlisted packages still need an approved acquisition path and native QA.
Theme availability, dynamic wind/snow behaviour, sourced scale and multi-angle
billboard reviews are not complete. The index and browse page are usable now;
the original issue must not be called finished or its unknown assets relabelled
as passes. See `download-shortlist.json` for a bounded next acquisition proposal.
