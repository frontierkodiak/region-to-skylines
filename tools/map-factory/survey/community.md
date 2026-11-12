# How the CS1 map-making community judges maps

Research notes for the real-region-to-`.crp` map tool (PL-902). Written 2026-11-10.

## What this rests on

- **Official map metadata (77 maps, base game + DLC + CCP).** Paradox's wiki has no table of buildable area and resources per map. The third-party site skylines.country (the wiki links it) holds one; I read its public data store directly (the same read the site's own frontend makes). Fields come from each map's `MapMetaData`: buildable %, oil/ore/fertile/forest/water amounts, `maxResourceAmount`, connection counts. Five Hotels & Retreats maps carry a hand-entered `maxResourceAmount = 100`; I excluded them from resource statistics. Saved as `official_maps_metadata.csv` next to this file.
- **Steam Workshop corpus.** The 113 most-subscribed and all-time top-rated CS1 maps (Steam's public `GetPublishedFileDetails`), their descriptions, and **11,393 comments across 106 of them** (Steam's public comment endpoint). I tagged comments by topic with regexes and read the hits; topic shares below are crude but comparable with each other.
- **Whose voice this is.** Two makers recur. MrMiyagi authored 7 of the 113 top maps (Vanilla Coast, Vanilla Lake, Steeltown, Newbie Harbor, Paradise Reef, Wolfgangsee, Sunset Harbor) and the most-favourited map-making guide. Zakerias (`-Z-`) authored 10 of them. Their stated conventions carry extra weight below.
- **Map-maker guides.** Paradox wiki (Map Editor, Natural resources, Maps, Industry Areas, Trees), CO's own dev diary #6 on the map editor (Dec 2014), and the top-rated Steam guides on map making: Mr Miyagi's guide, the Pre-publishing Checklist, Basic Map Creation, Creating a "Real World" map, Making Maps With Height Maps, the natural-resources encoding guide, Game Limits, and two player-written "best maps" lists.
- **A reviewer's rubric.** BonBonB's "What Map?" series (1,400+ reviews; makers cite it as the community's review standard). I read three transcripts: Kerrisdale Bay (#549), Coastal Atlantic USA (#274, a real-place map), Carrack Roads (#976, a real-place map).
- **Reddit** via the Arctic Shift archive (reddit.com blocks scripted reads): threads on trees, resources and heightmaps, 2015–2025.
- **Game code** where a mechanic decides a convention: decompiled-and-rehosted CS1 logic in open mod repos (mabako/cities-skylines-unlimiter, Quistar-LAB/TreeAnarchy, algernon-A/TreeControl), plus constants quoted by several repos.

Throughout, "**Inference:**" marks my reasoning as opposed to what a source says.

## The numbers that matter most

| Quantity | Value | Source |
|---|---|---|
| Buildable area, official maps | median 68%, IQR 57–77.5%, range 21–90% (base game median 69%) | official metadata |
| Oil, share of 25-tile area at full saturation | median 2.7% (≈2.5 km²), IQR 1.1–5.9%; 10 of 77 maps <0.5% | official metadata |
| Ore | median 5.2% (≈4.8 km²), IQR 2.8–8.7%; 2 of 77 <0.5% | official metadata |
| Fertile land | median 3.4% (≈3.1 km²), IQR 1.7–6.4%; 9 of 77 <0.5% | official metadata |
| Forest | median 17.1% (≈15.7 km²), IQR 11.5–20.9%; min 5.4%; no map lacks it | official metadata |
| Maps with all four ground/forest resources ≥1% | 52 of 77 | official metadata |
| Tree limits | map editor 250,000; in game 262,144 (usable ≈262,139) | `TreeManager.MAX_MAP_TREES`, `MAX_TREE_COUNT` |
| Trees on popular vanilla-limit maps | median 215k of 24 stated counts, IQR 175–239k, range 58–247k; 16 of 24 at ≥200k | workshop descriptions |
| Trees on official maps (inner 25 tiles) | at least ~59k median (lower bound derived from forest amount) | metadata + forest formula |
| Trees that saturate one forest cell | ~4–5 trees per 33.75 m cell (≈1 tree per 270 m²) | TreesModified logic |
| Highway connections, official maps | in-count 1: 3 maps, 2: 21, 3: 29, 4: 24 | official metadata |
| Air connections, official maps | 4 in: 51 maps, 2 in: 25, 0: 1 | official metadata |

How the resource percentages are defined. `maxResourceAmount` is 20,631,704 on every regular official map. That is exactly 25 tiles × (3,686,400 m² ÷ 1,139.0625 m²) × 255: the natural-resource grid is 512×512 cells of 33.75 m, each storing 0–255 per resource. The game's own buildable-area code uses those same constants (`3686400f`, `1139.0625f`) in `GameAreaManager.CalculateBuildableArea` ([unlimiter rehost](https://github.com/mabako/cities-skylines-unlimiter/blob/master/Areas/FakeGameAreaManager.cs)). So a map's oil % is "fraction of the 25-tile area that would be fully saturated oil". **Inference:** the amounts are summed over the inner 25 tiles only, so resources on the outer 56 tiles never show in the New Game panel.

## Ranked conventions

Ranked by how much players notice them: how often the topic appears in comments, and how badly they react when it fails. Topic shares of the 11,393 comments, for scale: rail/ship/air 6.9%, highways and connections 6.6%, theme/LUT 5.1%, hills/terrain 3.8%, water flow 3.7%, trees 3.1%, "vanilla" 2.8%, missing assets 2.4%, tile mods 2.1%, resources 2.1%, flat/buildable 1.9%, scale/realism 1.8%, start tile 1.3%, performance 0.6%. Most comments are praise, so the share of a topic among complaints is higher than these numbers suggest.

### 1. The start tile works from minute one

**(a)** The start tile has moving water you can pump from and dump sewage into, a highway exit (ramp) into it, and plenty of flat land. Reviewers look at it first.

**(b) Notice: high.** It is a hard requirement in the editor's checklist, and players complain in plain terms when any part is missing. BonBonB opens every review by checking the start square and the water flow at the start square.

**(c)**
- Dev diary #6 (CO, Dec 2014): "the starting tile has to have at least a highway connection to be playable since the player has only access to road building in the beginning … it is the map maker's responsibility to offer all the connections a city might need which means at least one highway connection in the starting tile." [forum](http://web.archive.org/web/20210511121112/https://forum.paradoxplaza.com/forum/threads/cities-skylines-dev-diary-6-map-editor.822199/)
- Wiki, Map Editor checklist requirements: "Water stream in the starting area", one incoming and one outgoing highway. The editor's own hint: "Use highway ramps to provide an exit from the highway as a starting point for the city's road network." [wiki](https://skylines.paradoxwikis.com/Map_Editor), [locale strings](https://gist.github.com/5e1c215bb07f248a913e)
- Mr Miyagi's guide: "Make sure the starting square has lots of flat space to allow the players to get a good start … I usually put a generous amount of this type of land in the start square and the surrounding squares." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=482232215)
- Pre-publishing Checklist: "The water's current in the starting square is accessible and strong enough to process water without contamination. There is ample building space and access to highways within the starting square." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2690418515)
- Cologne Köln (203k subscribers), 2015-03-17: "good map, but no freeway ramp on starting plot... >(" (posted twice by different players). Celtic Shores, 2020-09-20: "There are no road or rail connections in the starting map square." [Cologne](https://steamcommunity.com/sharedfiles/filedetails/?id=406363944), [Celtic Shores](https://steamcommunity.com/sharedfiles/filedetails/?id=1801766788)
- Carrack Roads review (#976): the reviewer objects that the start square sits at a hamlet rather than at Falmouth, the real town: "this is where I'd be doing my start square right here if I was building the map from scratch." [video](https://www.youtube.com/watch?v=CfGv-0i3Ri8)

**(d)** The checklist needs at least one incoming and one outgoing highway touching the start tile. Official maps commonly give the start tile two highway accesses (guidestrats map guides, e.g. Crater Falls). The start tile can be any of the 25; Lagoon Shore's is off-centre.

### 2. Water behaves: downhill, off the map, no floods, no droughts

**(a)** Rivers flow from a source down to the sea or off the map edge. Coastal currents carry sewage out of the map rather than pooling it. Shores don't flood and rivers don't run dry as the city grows.

**(b) Notice: high, and the most damaging failure.** A water fault can force a restart, so these comments are angrier than any others. They show up on the biggest maps.

**(c)**
- Copper Creek (the most-subscribed CS1 map, 804k), the author's 2018 note: "There is not enough water flow through the rivers to provide a city beyond about 50k population." [map](https://steamcommunity.com/sharedfiles/filedetails/?id=431174019)
- Kerrisdale Bay, 2019-02-12: "The main river and all of the minor rivers that feed into it are all at sea level, so there's no gravity pushing the water to flow out to sea." [map](https://steamcommunity.com/sharedfiles/filedetails/?id=1649656525)
- Boulder Cove, 2019-06-16: "the water flow goes inland, meaning over time you will end up with some real ♥♥♥♥ water that wont go anywhere." Midpoint Bay, 2020-08-18: coastal water should follow "a directional current which … flows right off the map's edge so as to dispose sewage … Otherwise you end up with a massive, huge pool of poop". [Boulder Cove](https://steamcommunity.com/sharedfiles/filedetails/?id=1767287078), [Midpoint Bay](https://steamcommunity.com/sharedfiles/filedetails/?id=2194947357)
- Real-place maps: Istanbul, 2015-03-11, "Water flows from sea to inland in this map". Rotterdam, 2015-05-02, "the current actually changed direction on me and started flowing inland". Hong Kong, 2015-03-12, "the river water is not actually moving … theres no down stream to dump sewage into". Taipei, 2015-03-22, "The map keep flooding by the river at the first plot of land". Uranouchi Bay, 2026-05-05: "Thanks for making a map that floods for no reason". [Istanbul](https://steamcommunity.com/sharedfiles/filedetails/?id=405821071), [Rotterdam](https://steamcommunity.com/sharedfiles/filedetails/?id=428345723), [Hong Kong](https://steamcommunity.com/sharedfiles/filedetails/?id=406270234), [Taipei](https://steamcommunity.com/sharedfiles/filedetails/?id=406722276), [Uranouchi](https://steamcommunity.com/sharedfiles/filedetails/?id=1550860466)
- Basic Map Creation: "Make sure your rivers start from the edge of the map … add [a source] at [each tributary] otherwise water will flow the wrong way … check that water doesn't flow both downstream and upstream in your river … polluted water move[s] upstream back to your water pumps." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=598419805)
- Pre-publishing Checklist: no unintended dry gaps; stream origins logical; "Water spawn points are hidden and unnoticeable"; "There is no unintentional flooding of land, roads or railways." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2690418515)
- Mr Miyagi on Vanilla Coast, 2017-11-13, after flood reports: "80m is the build area elevation still, but sea elevation lowered to 62m. That gives enough space (18m) to dig down". On Paradise Reef he places "toilet flush" sources set just below sea level that "always draw water in. Place your sewage near one and the sewage will be sucked away!" [Vanilla Coast](https://steamcommunity.com/sharedfiles/filedetails/?id=1130118928), [Paradise Reef](https://steamcommunity.com/sharedfiles/filedetails/?id=576316410)
- Creating a "Real World" map (San Francisco): the author ringed the map border with "a tiny strip of land … just a bit above sea level" so the bay drained through the Golden Gate. [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=774855825)

**(d)** About 18 m of freeboard between buildable land and sea is one maker's fix for flooding. Wiki: a water source's default column is 50 units; sea level is settable 0–500 m. Natural Disasters tsunamis flood low highways (Newbie Harbor, 2021-02-17).

### 3. Plenty of gently sloped land, smooth where you build, drama at the edges

**(a)** Most of the 25 tiles should be buildable, smooth with no fine bumps. Mountains, cliffs and open water mostly sit at the edges of the playable area or outside it. Players are split on dead-flat versus rolling, but agree on smooth where you build and no steep shorelines.

**(b) Notice: high.** Buildable % is the first stat in the New Game panel and in every map guide. Two of the ten most-subscribed maps are pitched as flat (The Great Plan 712k, Flatlands 508k). "Too flat" and "too steep" are both common complaints.

**(c)**
- Dev diary #6: "keep most of the area within the boundaries relatively smooth … The areas outside the boundaries are mostly for eye candy." Use the height infoview to catch "annoying, unnecessary bumps … While lots of erosion and other small things might in theory look good, they can present quite the challenge when laying roads."
- Mr Miyagi: "you need as much playable (flat, mostly flat and gently sloped) land within the playable squares as possible … Plan most every square so that it has playable area (sometimes I leave just one or two unbuildable)."
- Player list "The Only Maps You Will Ever Need": "usually 50% of buildable area is the absolute minimum." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2815508233). A Sunset Harbor commenter (2020-05-24) asks for "over 80% build area". [map](https://steamcommunity.com/sharedfiles/filedetails/?id=2034806081)
- r/CitiesSkylines, "When you are looking for a new custom map, what…" (2024; CS2-era, but CS1 taste carries over): "where the area is buildable, I like it to be actually flat, but then broken up by the unbuildable space"; "Not those ridiculously steep slopes, especially towards the rivers/oceans"; "So many maps are too flat"; "I need enough flat space for my downtown, then I want something natural to build around."
- r/CitiesSkylines (2015): "uneven terrain is fantastic to build on. On flat maps there's so much incentive to just make boring squares."
- Hong Kong, 2015-03-18: the mountains look "so extremely smooth and soft. Just a little little bit of erosion … some ridges / drainage grooves coming down the sides of the hills."

**(d)** Official buildable median 68%, with the IQR of 57–77.5% as the normal band. Below 50% reads as a challenge map; Gondola Islands (34%) and The Archipelago (21%) are sold that way. Buildable % = tile flatness × (1 − water fraction), averaged over tiles (`CalculateBuildableArea`). The flatness threshold itself lives in `TerrainManager` code I could not read.

### 4. Outside connections: all four types, reachable, simple, wired correctly

**(a)** Highway, rail, ship and air connections all exist and can be reached inside the 25 tiles, ideally from several sides. Highways are few, follow the terrain, and their ramps work. Interchanges aren't overbuilt and don't eat the start tile. Connections on opposite edges aren't joined straight through the middle of the playable area.

**(b) Notice: high.** This is the most-discussed topic in comments. Failures are concrete: trains never spawn, traffic jams, no ramp into the start tile.

**(c)**
- Players can't edit networks outside owned tiles (dev diary #6), so the maker must supply every connection.
- Mr Miyagi: "Any connections that are opposite one another will start sending their traffic through the center of your map … Make a ring connection." Grand River's guide makes the same point: linking the two highways turns your town into a through-route for trucks. [guidestrats](https://guidestrats.com/cities-skylines-grand-river-map-guide/)
- Overbuilt infrastructure: Newbie Harbor, 2019-11-11, "the highway intersections on the start square are ridiculous and I really don't need three train lines going into my start square ever"; 2023-08-05, "not sure I enjoy you forcing a particular style of city". Vanilla Coast, 2026-03-22: "barely any space after i build an intersection for the insane amount of highways … two rail roads running right through where the only plausable suburban neighbour hoods could go." Reddit 2024: "I'm fine with a highway on the map, or even two crossing at some point. But I'd rather not have multiple elaborate interchange[s]."
- Rail spawn bug: Riverlands, 2021-12-20, "The problem with trains is that their first nodes are too close to the border, which makes the outgoing trains pile up … then no inbound train will spawn." The same diagnosis comes up on Two Brothers Islands (2021-07-04), River Deported (2021-11-26) and Midpoint Bay (2022-05-29).
- Too few: in the Coastal Atlantic USA review (#274), the one 2-lane highway on a big flat map "is just going to die and there's only one rail link"; gameplay score 2/5. [video](https://www.youtube.com/watch?v=frp43ODDgsM)
- Pre-publishing Checklist: "multiple modes of transportation within the game's 25 purchasable squares, with at least one or more outside connections on each side of the map"; "Flight paths are drawn to avoid potential airport locations." Wiki: "Ship paths are required to be close enough to the playable area so that the harbors can connect to them."
- Grades: New Caledonia, 2016-01-13, "the grade/incline of some of the highways/railways were quite steep." Checklist: "1% for railways".
- Handedness: Sam's map list docks Eden Falls because "the highway system near the starting square flips sides … from a typical right hand highway … to left handed, and then back." [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2525363026)

**(d)** Editor caps: 4 incoming + 4 outgoing highways, 4 rail, 4 ship, 4 air (wiki). Official maps: median 3 highway pairs; rail 2–4 (5 maps have none); ship 0–4 (15 maps have none); air 4 on 51 of 77 maps. In vanilla without Mass Transit, only 1- and 3-lane highways exist (Newbie Harbor author, 2022-07-31).

### 5. Every resource is present and usable inside the 25 tiles

**(a)** A good map has all four resources (oil, ore, fertile land, forest) somewhere in the 25 tiles, on land you can build an industry on. Leaving one out is a deliberate challenge and should be stated.

**(b) Notice: medium-high.** Since the Industries DLC (2018) players plan whole cities around resources. A missing or unusable resource draws "is this a bug?" comments and costs a star in reviews. Two things soften it. Most-subscribed descriptions advertise "all resources" as a feature. And PC players can paint resources in-game with Extra Landscaping Tools (3.78M lifetime subscribers), which commenters routinely suggest. Console players can't.

**(c)**
- The editor checklist lists all four as "Recommended": "Have oil areas … forest areas … ore areas … fertile areas in the map." Dev diary #6: they "are there to make the city building more strategic … resources should stay within the playable area to be accessible."
- Absence: Powatan Valley, 2015-10-02, "very few resources other than trees make me sad :(". Cleyra, 2021-02-11, "Am I bugged or was a design choice not to add any ore areas and farm lands?". Owl's Colossal Hillside, 2019-09-22, "According to the description it has all resources … but when playing, it turns out there is no ore or oil." Boulder Rapids (2015-03-17, early days): "I was looking for maps with resources, it seems the others don't have any?"
- Outside the 25: the Kerrisdale Bay review gives gameplay potential four stars instead of five because "there['s] only oil offshore … without the twenty five tiles which means it can't be played that has vanilla for the oil." [video](https://www.youtube.com/watch?v=GUtn842Zq5s)
- Too much is a minority complaint: Tenasi River, 2015-04-09, "too easy. It has everything." Copper Creek, 2015-04-29, "too much ore fertile land forest and oil in every square". Catan XL's author makes scarcity the design ("having to buy new tiles to get specific resources").

**(d)** Official maps: 52 of 77 have all four at ≥1% of the 25-tile area. Forest is never absent (min 5.4%). Oil is the one most often near-absent (10 maps <0.5%, e.g. Grand River 0.0%, Woodgarden 0.0%), then fertile land (9; Desert Pass 0.0%, Prussian Peaks 0.2%), then ore (2).

### 6. Resources sit where the geology says, but on land you can build on

**(a)** The house convention: fertile land on river flats and valley floors; ore at the foot of hills and mountains and in foothill forests; oil in lowlands, along coasts and offshore. Players punish placement that is "logical" but unusable: ore or oil on peaks, underwater, or under pre-built roads.

**(b) Notice: medium-high.** These are specific complaints, often the only complaint about an otherwise loved map.

**(c)**
- Boreal Bay (101k): "All resources are represented on the map in pretty logical locations. Fertile land along the rivers, ore in the hills, oil along the coast." [map](https://steamcommunity.com/sharedfiles/filedetails/?id=469417355). Official maps follow the same pattern per guidestrats' guides: "Ore is most abundant near the mountains, while you'll find most of the oil near the water"; Prussian Peaks' ore "mostly … located on the mountains"; Green Peaks' and Roslyn Peninsula's oil is mostly undersea.
- Zakerias (10 `-Z-` maps in the top 113, five above 100k subscribers) writes "The ore is within the forests. There is plenty of farmland in the outer tiles" (Kruyswick), "Along the rivers you'll find farmland" (Baardmans Bay), "some in the hills, some along the river" (Mallemoer).
- Unusable placement: 7th Island Enhanced, 2018-05-03, "oil (or i think ore, not sure) was on a mountain, idk how i'm supposed to put industry up there and using landscpaing feels cheety". The author replied that they would "update the map with a few flat Ore locations". Revelstoke, 2019-04-07: "The oil is in the lake … I cant use that stuff if its in the lake." Two Brothers Islands, 2019-11-12: "I wish the oil was on the land so I could drill it." Boulder Cove, 2019-12-25: "the ore all seems to be underwater, and oil all seems to be under existing infrastructure". King's Bay, 2023-03-26: "Why does all the ore in this map spawn along the highways and rivers?"
- The geology argument cuts both ways. Wolfgangsee, 2017-06-09: "Disappointed that you have used Oil resource as snow, think Ore would have been better, as it is logical to find in mountains." The author: "you can't put ore mines on the peaks of mountains, and there isn't any oil in the Alps."
- Offshore is legitimate with Industries, which has an Offshore Oil Drilling Platform and a Seabed Mining Vessel ([wiki](https://skylines.paradoxwikis.com/Industry_Areas)). New Caledonia's author, 2019-02-08: "I forgot to add oil offshore. I always do now." A commenter there notes offshore ore "is not as effective as land based mining".

**(d)** No numbers. **Inference:** "ore at the foot of the slope" is the rule that satisfies both camps. Put ore on the buildable margin where hills meet flats, not on the slopes the buildable-area calculation discards.

### 7. Resources are spread across tiles in several district-sized patches

**(a)** Resources come in several distinct patches spread over the 25 tiles, so any 9-tile choice gets some of each. Patches are big enough to zone an industry district on, but there isn't one giant clump. The official pattern puts renewables (forest, fertile) in or next to the start tile and oil and ore one tile or more away.

**(b) Notice: medium.** Players rarely raise it unprompted, but praise for it is specific when they do. It matters more with the 25- and 81-tile mods, which most PC players run.

**(c)**
- Powatan Valley author, 2015-03-28: "Resources are spread throughout all 25 tiles. I mean, even with only 9 tiles I could never guess which combination of tiles people would choose."
- Steeltown, 2021-12-30: "lots of small resource areas. So many maps have resources all clumped together." Delta Range Enhanced, 2021-05-29: "The resources fit nicely within the square tiles, you aren't cutting a buildable area in half when you buy a new tile." Revelstoke, 2022-09-30: "it actually feels like it was designed with tiles and resources in mind, which some other maps on the workshop and in vanilla kinda don't."
- Too thin: Boulder Rapids, 2021-08-19, "lack of density for certain resources … farming industry, just not really enough to provide an efficient zone for extractors". Industry Areas wiki: "Extractors create raw products at a rate dependent on resource abundance."
- Zakerias' layouts: "four oil and four ore fields" (Kruyswick, Baardmans Bay, Great Flutland). Spykerbrook's four and four are "all … at some distance from the starting area". Den Drommel has "six ore and seven oil fields, mainly located along the border, but there is a oil/ore combo next to the starting tile" and "five big farmland regions in the corners".
- Start tile: 7th Island Enhanced's author put "all 4 types of resources on your start square" for one-tile challenge players. guidestrats on official maps: Grand River has "some amount of fertile land" in the start tile and all four first-expansion tiles but "none [ore] in the tiles immediately surrounding your starting tile". Crater Falls has fertile and forest in the start tile and a little oil in its corner. Woodgarden: "Oil is available immediately north of the starting tile, while ore can be found in the east and west."

**(d)** Official totals at full saturation: oil ~2.5 km², ore ~4.8 km², fertile ~3.1 km², forest ~15.7 km² (medians over the 92 km² inner area; one tile is 3.69 km²). The house pattern is 4 oil and 4 ore fields plus 3–5 farmland regions. Resource cells are 33.75 m, so painting is coarse. Wiki milestones: forestry and farming at Worthy Village, oil at Busy Town, ore at Boom Town. **Inference:** the official placement mirrors that unlock order, so a tool can too. Put renewables in the start tile and oil and ore one ring out. Make patches roughly 0.3–1 km² each (several 200–600 m blobs), not one 5 km² field and not 100 m slivers. I found no source giving a minimum patch size.

### 8. Resource ground tint is a visual decision

**(a)** In CS1, painted ground resources recolour the terrain: fertile shows as field texture, ore as rock or dirt, oil as a dark or mustard stain, depending on the theme. Makers exploit this to paint farm fields, dirt verges and snow. The community is split on whether that is clever or a bug.

**(b) Notice: medium, polarizing.** It produces the "why is the oil on the peaks" and "why is the ore along the highways" comments in item 6, and a named backlash: River Deported, 2022-12-14, "Great map but this resource painting trend needs to go."

**(c)**
- Copper Creek's description: "The agricultural and oil resources were used to change the ground color … the resources aren't laid out in a natural way, but instead conform to the contours of the farm plots." A commenter, 2015-04-26: "when you start to cover them with your city the various terrain colors remain visible … the result is a bit weird."
- Mr Miyagi, Steeltown, 2018-10-28: "The vanilla resource textures look awful IMO, which is why I use resource textures in my map themes that are able to blend." Many players hide them with No Radioactive Desert (773k subscribers).
- Riverlands, 2020-05-03: "Why all the fake fields? … they look great from an areal shot but it just looks unrealistic in game … Is there anyone that doesn't have to sit and delete all those rows of trees over and over?" A 2024 Reddit thread has several "no predetermined farmland" votes and one "brings some life to the map".
- Mechanics (natural-resources encoding guide, [guide](https://steamcommunity.com/sharedfiles/filedetails/?id=2927949381)): one 512×512 RGB texture stores everything. Red is oil (down) or ore (up), so the two are mutually exclusive per cell. Green is fertile (down) or sand (up), also exclusive. Blue is forest. Trees zero out fertility in their cell (item 11).

**(d)** **Inference:** a tool painting resources from real land cover (all farmland → fertile) will tint large areas with the vanilla field texture. Default to fewer, purposeful patches, and make "paint for realism" a knob.

### 9. Tree budget: stay under the editor cap, leave room, say the number

**(a)** Vanilla-limit maps stop below the 250,000-tree editor cap, and good makers say how many they used and how many the player can still plant. Players who decorate want headroom. Players who want lush maps accept 200k+. Past 250k a map needs a tree-limit mod and says so prominently.

**(b) Notice: medium.** About a quarter of top map descriptions state a tree count. The headroom figure is part of the sales pitch, and players ask for "a version with less trees" when they can't place their own.

**(c)**
- Limits: `TreeManager.MAX_TREE_COUNT = 262144`, `MAX_MAP_TREES = 250000`. Tree mods patch both 250000 and 262139 ([TreeControl](https://github.com/algernon-A/TreeControl/blob/master/Code/Patches/TreeManagerPatches.cs); constants shown in [KSPLoader TreeManager stub](https://github.com/AlexanderDzhoganov/KSPLoader/blob/master/PatchLib/TreeManager.cs)). Unlimited Trees: "This mod unlocks the games limitation of 262,144 trees". The editor counter reads "{0} / {1} trees used".
- Headroom as a feature: Copper Creek, "Approx. 35,000 more trees can be placed", plus a recommendation to use a tree brush mod "to remove many of the trees I've placed". Kerrisdale Bay: "I plopped around 200k trees, so there is some left for you to plopp and no Unlimited trees necessary." Lönnebay Universal: "only 130,000 trees built to leave headroom to the limit … to keep the map performant even on slower machines." Sea Turtle Falls: "I set a limit for myself at 150k trees … The majority of trees are on the inside 25 tiles leaving you with 100k room." Delvin Bay: "You can plant up to 75.000 additional trees". Yangtze: "Trees: I plopped 230,000 You can plop 20,000". Palm Beach: "Only 58K trees. Hardly any!"
- At the cap: Revelstoke, "Trees: I plopped 247,000. Yikes … My biggest enemy here was the tree count. You cannot take 7 steps without walking into a tree in the Pacific Northwest." Costa Azzurra: "About 246 761 … rather close the the vanilla tree limit. This could affect performance."
- Over the cap: Midwest America went from 260–270k down to 230k in an update. Two Brothers Islands has "~500k … Unlimited trees mod is listed as dependency". 2025 maps run 560k–896k with Tree Control. Players then hit "why all the trees disappear when i load the map" when the mod is missing (Cleyra, 2025-03-25).
- Midpoint Bay, 2021-02-23: "I cant detail how I want to without tree snapping. Is it possible to make a version with less trees?" (Unlimited Trees is incompatible with Tree Snapping.)

**(d)** Stated counts on 24 vanilla-limit top maps: median 215k, IQR 175–239k, range 58–247k. The in-game cap gives everyone an extra ~12,144 trees beyond a full editor map. Tree mods are mainstream: Unlimited Trees 1.23M lifetime subscribers, Tree Anarchy 0.53M, Tree Control 0.48M, Forest Brush 1.14M.

### 10. Forests look natural: varied, edged, following water and valleys, mixed

**(a)** Forest density varies. Edges are deliberate: hard curvilinear edges, soft gradients, or scattered pockets. Trees concentrate in valleys, along water and below the treeline, in a species mix that fits the biome. No trees on cliffs, in water, or clipping roads.

**(b) Notice: medium.** Reviewers grade it under detailing ("reasonable density for the game and a nice mix of trees"; "drowned trees … I think they're errors … lose another star"). Players praise tree-lined fields (Baardmans Bay, 2015-05-09: "seeing tree-lined fields in the distance feels so 'realistic'!").

**(c)**
- Pre-publishing Checklist, Trees: "The density of trees varies and is not noticeably consistent or repetitive. Tree placement reflects a logical growth pattern such near water, in valleys, and below a mountain's natural tree line. The mix of trees used is appropriate for the chosen biome." Details: "Trees/props clipping through roads and railways … have been removed."
- r/CitiesSkylines (2016-09-12), on tree-placement schools: "*Defined* tree areas have a hard border that is pleasing to the eye if used in curvi-linear, natural shapes … *Gradient* … you soften the transition by reducing tree density as you get further from the heart of the forest … for long straight edges, or when the landscape begins to change … like mountains or beaches … *Scattered* … 'threads,' 'pockets,' or simply single trees that create the illusion of forested areas with meadows."
- Creating a "Real World" map: "add a good sprinkling of the various types so as to make your map look natural and with some areas more densely forested if you intend to make forest industry possible."
- Cliffs: Paradise Reef Revisited, 2023-05-20, "the default game (without mods) does not allow trees to be painted on any area that shows rock face." No Tree Brush Slope Limit (200k subscribers) exists to override this.
- Water: vanilla trees touching water turn dead and orange; No Radioactive Desert's option is "No orange/dead trees at shoreline". BonBonB marks drowned trees as errors in both real-place reviews.
- Hidden trees: Riverlands' description: "Whenever you build on trees they are not removed just hidden. I strongly suggest bulldozing/deleting in the area you want to build". Hidden trees still count against the limit.
- Species: in vanilla, Boreal and European get conifers and pine, Tropical gets palms, Temperate gets beech and alder, plus shared species (wiki, Trees). Spykerbrook commenters single out the 'Pine' as "by far the biggest tree in the game". 7th Island Enhanced: "I specifically chose to use the ugly vanilla trees so that vanilla players don't have a naked map".

**(d)** Wiki: the editor tree brush runs from size 50 ("will place single trees") to 2000, strength 0.01–1.0. Basic Map Creation: "don't use the full round brush … it plants an incredibly dense forest and you will run out of trees". King's Bay's published Forest Brush settings: Redwood size 27 at 20%, Generic Pine size 74 at 11%, auto density.

### 11. Forestry needs density; a "look" forest is not a resource

**(a)** The forest resource comes only from tree density in each 33.75 m cell. A thin forest spread out to save tree budget looks wooded but yields little forestry. Trees also erase fertile land in their cell.

**(b) Notice: low-medium**, but a real trap for a generator. It produced a whole thread on Powatan Valley.

**(c)**
- Powatan Valley, 2015-03-24, a player: "I can see lots of trees but nothing that's 'designated' as forestry resources (dark green)". The author: "Forestry resources automatically generate where there are trees. There may be fewer dense forestry regions on this map, despite all the trees, because … there is a limit on total number of trees … I tried to keep the tree count low while still providing a forested look."
- The logic, from TreeAnarchy's reimplementation of `NaturalResourceManager.TreesModified` (it mirrors vanilla when forestry lock is off): per cell, `forest = min(4 × 15 × treeCount, 255)`, and if `forest > 0` then `fertility = 0`. [TreeAnarchy](https://github.com/Quistar-LAB/TreeAnarchy/blob/master/Patches/TreeLimit.cs)
- Wiki: "planting trees will replace fertile land with forestry, and the fertile land will be removed permanently."

**(d)** Each tree adds 60 to its cell, so a cell saturates at 5 trees (4 trees = 240), about one tree per 270 m² or ~37 per hectare. Official maps' forest amounts therefore imply at least `forestAmount / 60` trees in the inner 25 tiles: median ~59k, IQR 40–72k, max ~115k (Honu Island). A forest that is both lush and a full resource across 17% of the 25 tiles needs ~60k trees at saturation, well inside budget. **Inference:** concentrate forestry-grade density (4–5 trees per cell) in a few forests the tool marks as resource. Use sparser, edge-and-pocket planting for the look elsewhere and outside the 25 tiles. Keep tree rows out of fields that are meant to stay fertile.

### 12. Vanilla and light on dependencies, and kind to slow PCs

**(a)** A map that needs no DLC, mods or workshop assets reaches the most players and gets labelled for it. Visuals that depend on a custom theme, LUT or trees are listed as optional. Tree count and dense clumps are a known FPS cost.

**(b) Notice: medium-high.** "Vanilla" is in 12% of top map titles and 29% of descriptions, and appears in 316 comments. Missing-asset complaints are 2.4% of comments.

**(c)**
- Kerrisdale Bay's description: "NO MAP COLLECTION OR REQUIRED ITEMS, THIS! IS! VANILLA!" Titles carry it: "Vanilla Lake", "Redwood River - Vanilla map", "Sunset Harbor - Vanilla No DLC", "Vanilla Valley - No DLCs, No Subs, Just plain vanilla".
- Performance: Owl's Anahita Pass, 2017-11-26, "the sheer number of trees. It really heavily impacts the game's performance even with the Unlimited Trees mod at the lowest setting, especially since there's a lot of places … where there are 5 or more trees in extremely close contact." Den Drommel, 2016-02-19: "My 140k city on vanilla map has like 2x more fps than 25k city on this map." Forest fires: Cleyra, 2020-11-05, "everything is always on fire, maybe because of the tree density"; Anahita Pass, 2017-10-21, lightning "cause[s] MASSIVE forest fires … significant drop in performance."
- Dependencies: "The Only Maps You Will Ever Need" grades maps on how many dependencies they have: "I once subscribed a map with nearly 150 assets … when I removed both [map and LUT], my FPS jumped from 23fps idle to nearly double". Pre-publishing Checklist: separate the required items from the look-only items, and provide a collection when more than 10 are needed.

**(d)** **Inference:** our `.crp` output should be vanilla by default (vanilla trees, vanilla networks, no DLC-only roads), with a tree count well under 250k.

### 13. The environment theme fits the place, and European is opt-in

**(a)** Pick the base environment (Temperate, Boreal, Tropical, European, Winter) for the climate. Avoid European unless asked: it swaps in Central-European zoned buildings and service buildings, which many players dislike. Most custom map themes are built on Temperate.

**(b) Notice: medium.** "Need a version with no european building theme" recurs on several of the biggest maps.

**(c)**
- Kerrisdale Bay comments (2019–2020): "I only wish there was a version without the European theme"; "I'd love to make a North American style city without having to fight the European architecture style"; the author repeatedly points people to the Environment Changer mod. Valhalla, 2022-12-13: "is there a way i can change the default theme of european i just hate the european city services". Celtic Shores, 2024-08-24: "The European theme buildings are Central Europe (Germany) rather than anything close to Irish style."
- Two Brothers Islands, 2019-06-24: "all great themes has to be set in temperate"; a tropical-base map wouldn't accept a temperate-base theme.
- The wiki: the terrain type sets textures, trees and lighting. Winter maps need Snowfall.
- Real-place orientation: Mr Miyagi notes the default sun "rotates West to East", so a real map reads mirrored unless rotated 180° or paired with a theme that fixes the sun path.

**(d)** Official environments are spread across all five. **Inference:** for Asheville, Temperate is the natural default.

### 14. The Workshop page shows the map honestly and completely

**(a)** Images include a daylight top-down of the whole map plus infoview shots: resources, water flow, wind, topography, and the start tile. Previews shouldn't depend on hidden LUTs. The description lists connection counts, resources and where they are, tree count and headroom, intended tile mode, water notes (dam spots, where to put sewage), and required versus optional items.

**(b) Notice: medium.** Players ask for these explicitly, and the request repeats across maps and years.

**(c)**
- Requests: Owl's Anahita Pass, 2018-02-12, "If you could put a single picture of the entire map without the DoF and during the day, you'd probably have a lot more subs." Flatlands, 2019-05-02, "Could we get a screenshot of resources and a birds eye view of the tiles?" Istanbul, 2015-03-23, "can you add a water flow map snapshot". Aurora Borealis, 2016-09-12, asks for "the infoview overlay images … wind, terrain, transport, natural resources". Boulder Cove, 2022-10-08, "Does anyone have a screenshot of the resources map for this map?" Owl's Merchants Bay, 2017-01-15, "I only wish there was a resource map of it".
- Praise: Tenasi River, 2015-04-05, "I love the fully coherent description & screenshots of the resource map." Same page, 2015-04-03: "Thanks for posting all relevant pics so we have a good overview of the map."
- Mismatch: Copper Creek, 2015-04-29, "Why does the map look completely different in-game? … The colour isn't the same as the preview pictures". The Coastal Atlantic review complains of links to visual mods "but … they haven't included the settings for each of those".
- Description contents across the 113 top maps (my count): connections 74%, water notes 64%, theme/LUT 55%, resources 45%, tile mode (9/25/81) 39%, real-place basis 35%, vanilla 29%, tree count 26%, buildable % only 3% (the New Game panel already shows it).

**(d)** In-game, the publish dialog takes a map name and one snapshot from the Snapshot tool as the New Game preview (wiki). Workshop tags: 112 of 113 top maps carry only "Map", which the game sets. Tags are not a lever. Titles are short (median 17 characters). Common suffixes: "- Vanilla", "No DLC", "(81 Tiles)", "1:1", the maker's mark (`-Z-`, "Owl's").

### 15. Tile-mode readiness: 9, 25 or 81

**(a)** Most PC players unlock beyond 9 tiles, so a map should be good at 25 and at least presentable at 81. The outer ring can be scenery, but makers say which they designed for.

**(b) Notice: medium.** 39% of top descriptions name a tile mode. Comments ask whether the outer area is usable.

**(c)**
- Mods: "All 25 Areas purchasable" has 2.83M lifetime subscribers, BigCity 25-tiles 0.58M, 81 Tiles 2 2.15M (the older 81 Tiles mod is delisted). The wiki links the 25- and 81-tile mods from its Maps page.
- Elena Falls, 2018-07-01: "I used almost all of the 250.000 trees (default limit) for the inner 25 tiles (because mostly you cannot see the valleys of the outer area anyway)". Kerrisdale Bay: "Optimized for 9 tiles, 25 tiles or 81 tiles gameplay. You decide." Kerrisdale, 2019-06-22: "you cannot play it without 81 tiles mod cause otherwise you have no access to the port and 81 tiles mod hampers performance a lot".
- 7th Island Enhanced and Delta Range Enhanced both say "I have taken a lot of time to ensure this map is suitable for the 81 Tiles mod".

**(d)** **Inference:** essentials (connections, resources, water infrastructure) go inside the 25. The outer ring gets terrain, water and lighter trees, and never carries the only copy of anything.

## What real-terrain maps get wrong in reviews

Ranked by how often it shows up on real-place maps (Cologne, Istanbul, Hong Kong, Taipei, Rotterdam, Shanghai, London, Wolfgangsee, Shimanto, Monaco, Dubai and two BonBonB real-place reviews), plus the heightmap guides.

1. **Water that doesn't drain or flows backwards (high).** See convention 2. Real coastal and estuarine sites at sea level have no gradient, so their rivers stagnate or reverse. Sources treat water surfaces as ground: "terrain.party does not recognize the depth of water … the surface of the water will just appear as flat terrain. You'll probably have to make your own river channels" (Reddit, 2019-12-19). Portland mapper (2019-09-08): "any terrain data reads its water surface as ground level … unrealistic unless you manually change the height map." Fixes in guides: carve channels from OSM water ("Making Maps With Height Maps": fill water with a dark grey and subtract), add an artificial gradient, add drains, ring the border.
2. **Flood-prone shores (high).** Rotterdam, 2015-10-04: "the shoreline is very fragile and parts of the map are below sealevel." Taipei, Uranouchi and Kerrisdale's sunken roads all flood. Freeboard fixes as in convention 2.
3. **Wrong-scale or fake-looking relief (medium-high).** Two failure directions. Too smooth or too low: Hong Kong's hills are "extremely smooth and soft … a little bit of erosion" wanted; Shimanto's "mountains a bit small (low height)"; a Toronto mapper found every source "super flat" and discovered the data was a surface model including buildings (2022-07-10). Too steep from auto-exaggeration: skydark's generator auto-sets height scale to fill the 1024 m range, capped at 250% in current code; its README example gives San Francisco 300%. Meanwhile players complain about "ridiculously steep slopes … towards the rivers/oceans." Mr Miyagi's guide runs non-US terrain.party data through Wilbur erosion and blur because "Maps in terrain party that are outside the US and Denmark really need some Wilbur, since the quality can be lower." The wiki: 8-bit heightmaps "create noticeable steps in slopes"; use 16-bit (1/64 m per step).
4. **Horizontal scale and fit (medium).** 1:1 (17.28 km) is "a pretty fair 1:1 scale" but "Cities:Skylines roads are already overscaled at 1:1" ("Real World" map guide). Makers compromise: Skye's London at 60%, Portland at 42% ("At 50% you get a tonne of fun terrain but I-5 and I-405 take up all of downtown"). Replica builders still complain: London, 2015-10-31, "it isn't to scale. The Canary Wharf peninsula should take up a 2km square grid in itself." "The Only Maps…" guide: "the water canals surrounding it [weren't] designed to the 1:1 scale … dealbreaking." Shanghai, 2018-12-15: "True shanghai won't fit in 18x18 km". skydark shows a "reference height scale" of 17.28 / map size × 100%, so vertical scale shrinks with horizontal.
5. **Infrastructure that is real but not playable (medium).** Cologne has no ramp into the start plot. Carrack Roads turns real national roads into highways ("this is not a highway in real life"), and its rail "doesn't follow anything like the real-life route". Taipei, 2015-03-16: "Why is the railroad not going to the edge of the map in one end?" Cologne, 2020-03-03: "the highway makes an almost 90 degree turn".
6. **Start tile in the wrong place (medium).** Carrack Roads puts the start at Mylor Bridge rather than Falmouth; Hong Kong, 2015-03-15: "Make one more starting on central and wanchai? it makes more sense."
7. **Too little buildable land where the real city is (low-medium).** Istanbul, 2015-05-29: "people commenting about not having level ground; nothing to do really, Istanbul has no big patches of level ground." Monaco is sold as a challenge. Real-place players tolerate this more than fictional-map players.
8. **Orientation and the sun (low).** Default themes' sun path makes a north-up real map look odd; Mr Miyagi rotates heightmap and overlay 180°.
9. **Missing resources (low on real maps).** Real-place makers often skip resources or use them as texture (Wolfgangsee: oil painted as snow). Taipei's description jokes the basin "lacks natural resources in real life … Nevertheless, even oil is miraculously present." I found no complaint pattern specific to real maps here beyond convention 5.

## Knobs

What the evidence says a veteran would tweak, and what should just be right.

**Should just be right (no knob, or a knob that defaults correctly and warns):**
- Water: every river drains to the sea or off the map edge with downhill flow; coastal current carries off-map; no inland flow at the start tile; drains near the start tile's outfall. Validate in a sim pass if we can.
- Freeboard: buildable shoreline sits well above sea level (≈10–20 m; one maker uses 18 m). Carve and lower river channels below the banks.
- Start tile: water with current, an incoming and outgoing highway with a working ramp, and the largest flat area among candidates. When the region has a named city, the start tile is on it.
- Connections: correct direction and handedness, a first rail segment long enough to spawn trains, ship and air paths near buildable shore and clear of the likely airport flat, all four types reachable inside the 25 tiles.
- No resources under water (unless the offshore option is on), on slopes the game counts unbuildable, or under pre-built networks. Oil and ore never share a cell; fertile and sand never share a cell.
- Trees: under the 250k editor cap; none in water cells, on cliff texture, or on roads and rails; vanilla species from the chosen environment.
- Heightmap precision: 16-bit, smoothing where you build, no stair steps.

**Knobs a veteran would want, with suggested defaults from the evidence:**

| Knob | Default | Range | Why |
|---|---|---|---|
| Map scale (km across) | 17.28 (1:1) | ~17–40 | Community compromise for big cities is 42–60% scale; replica builders want 1:1. |
| Height scale | Auto, not maxed: 100% at 1:1, capped so the buildable core stays gentle | 50–250% | skydark's auto-max is the community's default and the source of "too steep" maps; tie it to map scale as skydark's reference value does. |
| Sea level / freeboard | Real coastline, with ≥10 m freeboard on built-up shores | — | Flood complaints. |
| Terrain smoothing in the buildable core | Medium | Off–strong | "Unnecessary bumps" versus "too smooth, no erosion"; keep relief outside the core. |
| Start tile | Auto (named place with water and highway) | Any of 25 | Reviewers check it first. |
| Tile target | 25 tiles detailed, 81 presentable | 9 / 25 / 81 | Most PC players run 25- or 81-tile mods. |
| Resource abundance per type (oil, ore, fertile, forest) | Official median | None … official p90 | Official medians: oil 2.7%, ore 5.2%, fertile 3.4%, forest 17% of the 25 tiles. Expose as four sliders labelled with the New Game panel's names. |
| Resource placement style | Gameplay (geology-guided, buildable, spread) | Gameplay / realistic land cover / painted texture | Items 6–8. "Realistic" paints from land cover; "texture" uses resources for ground colour. |
| Patch layout | 3–5 patches per ground resource, renewables near start, non-renewables one ring out | — | House convention; official unlock order. |
| Offshore oil/ore | Off (on if coastal and Industries is assumed) | — | Usable only with Industries; complained about otherwise. |
| Tree budget | ~180–200k | 50k–250k (more only with a "needs Tree Control" flag) | Median of popular maps 215k; headroom is a selling point; perf complaints above that. |
| Forest density / edge style | Real land cover; forestry-grade density in designated forests; gradient edges | Defined / gradient / scattered | Item 10 schools; item 11 density rule. |
| Outer-ring trees | Light | None / light / full | Makers spend the budget inside the 25. |
| Highway set | Real motorways only, connected by a ring outside the core | Real / minimal / none | Players dislike overbuilt interchanges; real trunk roads aren't highways. |
| Rail / ship / air | All present | Toggle each | Checklist recommends all; reviewers dock maps with one link. |
| Environment | From latitude and climate; never European unless chosen | 5 options | Item 13. |
| Orientation | North-up, with a flip-for-sun option | — | Miyagi's 180° trick. |

**Output extras that cost little and buy trust:** generate the Workshop image set (daylight top-down; resource, water-flow, wind and height overlays; the start tile) and a description template with connection counts, resource locations by tile, tree count and headroom, tile mode, water notes, and "100% vanilla".

## What I couldn't establish

- **How the New Game panel scales its resource bars.** The tile-purchase panel draws `Mathf.Pow(amount / tileMax, m_OilExponent)` (and ore, forestry, farming exponents), with values set in the UI prefab that I couldn't read. It shows a "none" sprite when a tile's amount is exactly zero. I assume the New Game panel uses the same exponents on whole-map metadata, but didn't verify it. I found no player discussion of how people read the bars; players instead ask for the resource overlay image or use skylines.country.
- **The flatness threshold behind buildable %** (`TerrainManager` tile flatness): not readable from the sources I had.
- **A sourced minimum patch size** for a viable Industries district. My 0.3–1 km² suggestion is inference.
- **Tree counts on official maps.** Only the derived lower bound (~59k median in the inner 25).
- **Reddit coverage is thin.** reddit.com blocks scripted reads; the archive's title search is coarse. The 2024 "what do you look for" thread is CS2-era. Paradox forum threads on map taste had no archived replies.
- **Comment topic shares are regex counts**, not hand-coded; treat them as relative, not exact.
- **The forest formula** comes from a mod's reimplementation of `TreesModified`, not decompiled vanilla code. It agrees with the wiki's fertile-land behaviour and the Powatan thread.

## Data files

- `official_maps_metadata.csv`: 82 official maps with buildable %, resource % of the 25-tile area, a derived minimum tree count, and connection counts.
- `pages/`: raw pages, workshop details and descriptions (`ws_descriptions.txt`), comment threads (`pages/comments/comments_<id>.txt`), guide markdown (`pages/guides/`), Reddit threads (`pages/reddit/`), review transcripts (`pages/yt/`).
