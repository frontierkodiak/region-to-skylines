# CS1 map conventions: what players notice, and what this tool does

A ledger of the conventions a longtime Cities: Skylines 1 map-maker follows.
They're ranked by how much players notice them, each with what our
region-to-map tool does today. Evidence and sources:

- [`survey/community.md`](survey/community.md): 113 top Workshop maps and
  11,393 of their comments, the wiki, CO's map-editor dev diary, the top
  map-making guides and BonBonB's reviews.
- [`survey/tools.md`](survey/tools.md): heightmap generators and map-editor
  mods, from their source.
- [`survey/basemaps.md`](survey/basemaps.md): resources and trees decoded from
  the 104 shipped maps.
- Durable game facts are in knowledge:
  [natural resources and trees](https://github.com/polli-labs/knowledge/blob/main/games/cities-skylines-natural-resources.md)
  and [playable map files](https://github.com/polli-labs/knowledge/blob/main/games/cities-skylines-map-files.md).

Status as of 2026-11-10. **Done** means in the writer and checked offline.
**In game** means also seen in CS1. Owner issues: PL-857 writes terrain,
water, connections and metadata; PL-902 writes resources and trees.

| # | Convention | Players notice | Today | Owner |
|--:|:--|:--|:--|:--|
| 1 | The start tile works from minute one: flowing water, a highway ramp into it, flat land, on the real town. | High: reviewers check it first. | The start tile is picked for water. A starter reservoir is added if a region has none. The highway path to the start tile is checked natively. | PL-857 |
| 2 | Water behaves: flows downhill and off the map, no floods, no droughts. | High: the angriest complaints, and the top real-terrain failure. | Rivers are prefilled with sources along long reaches. A 60-minute soak drained the older Asheville map; sustained flow is still open. | PL-857 |
| 3 | Plenty of gently sloped land in the 25 tiles, smooth where you build, drama at the edges. | High: buildable % is the first panel stat. Official median 68 %. | Real terrain at 1:1. The panel still shows the template's 74 %. The game's figure covers a shifted 5×5 block and scores a 25 % slope as 0.8 flat. | PL-857 |
| 4 | All four connection types, reachable in the 25 tiles, simple, correctly wired. | High: the most-discussed topic. | Highway and rail come from the template. Ship and air are missing; 103 of 104 shipped maps have air. | PL-857 |
| 5 | Every resource is present and usable inside the 25 tiles. | Medium-high: "is this a bug?" comments, and reviews dock a star. | **Done.** `balanced` (the default) tops ore, oil and fertile land up to the official medians. Forest comes from trees at about 17–20 %. `real` uses evidence only. | PL-902 |
| 6 | Resources sit where geology says, on land you can build on: fertile on river flats, ore at the foot of hills, oil on lowlands and coast. Never on peaks, under water or under roads. | Medium-high: specific complaints. | **Done.** Ore comes from USGS MRDS deposits and MSHA mines, coal included; plants and mills are skipped. Oil comes from NETL WELLS: the density of drilled oil and gas wells becomes oil fields, held under a 7 % New Game share. All three sources are US-only and keyless. Invented patches follow the shipped-map terrain pattern. Resources are cleared from water, slopes over 40 % and the outside-connection roads. | PL-902 |
| 7 | Several district-sized patches spread over the tiles. Renewables in or next to the start tile, ore and oil a tile out. | Medium. | **Done.** Patches are soft-edged blobs of 0.5–2 km², spread at least 1.6 km apart. Fertile land is placed nearest the start first. Invented ore and oil stay out of the start tile and off fields. | PL-902 |
| 8 | Resource ground tint is a visual choice: no painting resources just for colour. | Medium, and split. | Resources are placed only as resources. | PL-902 |
| 9 | Tree budget under the 250k editor cap, with headroom stated. | Medium: popular maps median 215k, official 143k. | **Done.** Default 180k, which leaves about 70k to plant. `--trees` sets it. Stating it on a download page belongs to the web app. | PL-902 |
| 10 | Natural forests: varied density, real edges, along water and valleys, a biome-fit species mix. No trees on cliffs, in water, or clipping roads. | Medium. | **Done.** Trees follow ESA WorldCover tree cover. By default (`--forest dense`) they form close-packed stands on summits, steep ridges, slopes and stream corridors, leaving buildable flats open; it beat the evenly spread `open` layout in two blind in-game judgings. Stands are at least ~100 m wide with feathered edges, and trees clump inside them. Each stand has a dominant species, and alders line water. Trees stay off water, roads and fields, and off rock faces: none where the game's own tree brush refuses (steeper axis gradient ≥ 50 %, from `TreeTool`) or steeper than 60 % overall. Slots are shuffled so size and brightness vary. With 180k trees, many real forested ridges stay bare. | PL-902 |
| 11 | Forestry needs density: a thin "look" forest yields little. | Low-medium. | **Done.** Stands hold 3–5 trees per cell, so their forest resource sits near the cap. Five forestry woods of ~0.4 km² go on buildable, tree-covered land nearest the start, so forestry industry has somewhere to build. | PL-902 |
| 12 | Vanilla: no DLC, mods or Workshop assets. | Medium-high: "vanilla" is in 29 % of top descriptions. | **Done.** Only original-release tree prefabs the map's theme loads. No mods are referenced. | PL-857, PL-902 |
| 13 | The theme fits the place, and European is opt-in. | Medium. | Every map uses the template's Temperate ("Sunny") theme. Boreal and tropical regions need their own template. | PL-857 |
| 14 | An honest preview: a daylight top-down plus resource, water and height overlays, connection counts, tree headroom and tile mode. | Medium. | No preview image yet. `paint.py` writes a resource overlay PNG and a JSON summary a page could show. | PL-857 (preview), web app |
| 15 | Ready for 9, 25 or 81 tiles. | Medium: about 2M players run the 25- and 81-tile mods. | Real resources and trees cover all 81 tiles. Invented patches go only inside the 25, and the outer ring gets 0.6× tree density. | PL-902 |

## What real-terrain maps get wrong

These are ranked by how often reviews raise them; details are in
`survey/community.md`.

1. Water that won't drain or flows backwards: PL-857.
2. Flood-prone shores, with too little freeboard above sea level: PL-857.
3. Relief that is too smooth or too exaggerated: the web app's height choice.
4. Horizontal scale: real roads swamp a 1:1 downtown. The web app has a scale
   setting.
5. Real roads that aren't playable highways: PL-857's templates take only real
   motorways.
6. A start tile away from the real town: PL-857.
7. Missing resources: fixed here (item 5).

## Knobs

Each default should need no touching. The CLI flags are on `paint.py` and
`generate.py`.

| Knob | Default | Flag |
|:--|:--|:--|
| Tree count | 180,000 | `--trees` |
| Resource mode | `balanced`: real evidence, topped up to the targets | `--resources balanced\|real` |
| Ore, oil and fertile land targets (New Game share) | official medians: 5.2 %, 2.7 %, 3.4 % | `--ore-share`, `--oil-share`, `--fertile-share` |
| Fertile land from real crop and pasture | ×1.0 | `--fertile` |
| Forest layout | `dense`: packed stands on unbuildable land, plus forestry woods | `--forest dense\|open` |
| Trees outside the 25 tiles | ×0.6 | `--outer-trees` |
| Random seed | 0 | `--seed` |

The community also asks for a theme choice, a height scale, a start-tile
override and per-connection toggles. Those belong to the writer and the web
app, not this stage.
