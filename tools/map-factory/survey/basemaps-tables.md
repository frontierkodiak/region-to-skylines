Corpus: 104 maps (CO.crp is the system package of blank editor terrains, excluded). Values are p25 / median / p75 across maps unless noted. 'Central' = the 25 tiles a vanilla city can buy (9×9 tile grid, tiles 2..6); 1 resource cell = 33.75 m = 0.00114 km²; central area = 92.16 km².

### Coverage and New Game bars

| | ore | oil | fertile | forest |
|:--|--:|--:|--:|--:|
| maps with none in the 25 tiles | 2 | 4 | 2 | 0 |
| share of central land covered (>0) | 0.07 / 0.15 / 0.24 | 0.03 / 0.07 / 0.12 | 0.05 / 0.12 / 0.18 | 0.30 / 0.39 / 0.51 |
| central km² covered | 5.7 / 10.8 / 18.8 | 3.1 / 7.3 / 12.5 | 4.5 / 9.3 / 13.6 | 23.5 / 29.7 / 37.7 |
| share of the map's cells inside the 25 tiles | 0.41 / 0.74 / 0.98 | 0.44 / 0.78 / 0.99 | 0.56 / 0.83 / 1.00 | 0.33 / 0.40 / 0.49 |
| of 25 tiles, tiles with any | 11 / 15 / 22 | 8 / 13 / 19 | 12 / 17 / 22 | 25 / 25 / 25 |
| of 25 tiles, tiles ≥ 5 % of a tile's max | 5 / 8 / 13 | 2 / 6 / 11 | 4 / 8 / 12 | 20 / 22 / 24 |
| metadata amount ÷ maxResourceAmount (bar fill at exponent 1), p10/p50/p90 | 0.017 / 0.060 / 0.184 | 0.005 / 0.039 / 0.124 | 0.007 / 0.048 / 0.134 | 0.080 / 0.167 / 0.278 |
| start tile has some (maps) | 60 | 52 | 91 | 104 |
| start tile km² | 0.00 / 0.06 / 0.42 | 0.00 / 0.00 / 0.42 | 0.14 / 0.55 / 1.05 | 0.87 / 1.20 / 1.50 |

Water: metadata waterAmount ÷ max, p10/p50/p90 = 0.051 / 0.171 / 0.389; wet share of the 25 tiles = 0.08 / 0.16 / 0.27.
buildableArea (New Game %): p10/p25/p50/p75/p90 = 47 / 57 / 68 / 76 / 83.
Sand (unused by vanilla industries, editor-paintable): none in the 25 tiles on 15 maps; central km² 0.1 / 1.8 / 7.8.

### Patch shape

Blobs = 8-connected components after a 2-cell closing (fertile: painted area including the forest cells that zero it), inside the 25 tiles, ≥ 0.05 km².

| | ore | oil | fertile |
|:--|--:|--:|--:|
| blobs per map | 5 / 8 / 13 | 3 / 6 / 11 | 5 / 7 / 9 |
| median blob km² | 0.33 / 0.71 / 1.28 | 0.21 / 0.50 / 1.29 | 0.33 / 0.71 / 1.74 |
| p90 blob km² | 1.15 / 2.39 / 4.18 | 0.66 / 1.55 / 3.10 | 1.37 / 3.41 / 6.86 |
| largest blob km² | 2.17 / 3.55 / 7.53 | 1.34 / 2.45 / 5.71 | 2.24 / 5.82 / 11.29 |
| share of area in the 3 largest blobs | 0.57 / 0.76 / 0.95 | 0.59 / 0.82 / 0.95 | 0.64 / 0.78 / 0.93 |
| mean value 1 cell(s) in from the edge | 12 / 25 / 43 | 14 / 35 / 62 | 70 / 91 / 123 |
| mean value 2 cell(s) in from the edge | 40 / 85 / 138 | 49 / 107 / 168 | 85 / 121 / 157 |
| mean value 3 cell(s) in from the edge | 68 / 127 / 189 | 76 / 149 / 205 | 93 / 139 / 189 |
| mean value 4 cell(s) in from the edge | 83 / 143 / 210 | 93 / 164 / 222 | 107 / 158 / 204 |
| mean value 6 cell(s) in from the edge | 123 / 178 / 243 | 139 / 205 / 240 | 124 / 185 / 239 |
| cells at 255 / ≥192 / <64 (of cells >0) | 0.24 / 0.37 / 0.33 | 0.26 / 0.40 / 0.33 | 0.17 / 0.28 / 0.33 |

### Placement against terrain (cells inside the 25 tiles, on land)

Per map: the median over resource cells; table shows p25 / median / p75 of those across maps. Height percentile is against the 25 tiles' land (50 = typical). 'Above water' = height over the surface of the nearest wet (>0.5 m) water cell. Ratios divide by the same map's all-land median.

| | all central land | ore | oil | fertile | forest |
|:--|--:|--:|--:|--:|--:|
| slope % | 4.6 / 7.3 / 12.0 | 7.8 / 13.6 / 19.0 | 3.8 / 6.5 / 10.4 | 1.9 / 3.6 / 5.6 | 4.1 / 5.8 / 9.8 |
| height percentile | 50 / 50 / 50 | 53 / 65 / 77 | 22 / 35 / 49 | 26 / 35 / 48 | 42 / 48 / 53 |
| m above nearest water | 24 / 34 / 60 | 35 / 54 / 98 | 13 / 21 / 48 | 14 / 21 / 41 | 22 / 33 / 53 |
| m to water | 562 / 824 / 1164 | 657 / 1095 / 1458 | 215 / 457 / 1115 | 542 / 716 / 1024 | 462 / 794 / 1073 |
| slope ÷ map median | 1 | 1.11 / 1.50 / 2.23 | 0.66 / 0.90 / 1.31 | 0.33 / 0.55 / 0.75 | 0.73 / 0.91 / 1.05 |
| m to water ÷ map median | 1 | 1.03 / 1.30 / 1.61 | 0.38 / 0.55 / 1.08 | 0.72 / 1.00 / 1.35 | 0.81 / 0.96 / 1.06 |
| m above water ÷ map median | 1 | 1.14 / 1.42 / 2.12 | 0.49 / 0.72 / 1.00 | 0.52 / 0.75 / 0.97 | 0.85 / 0.99 / 1.12 |
| share of cells under water | – | 0.00 / 0.01 / 0.04 | 0.01 / 0.13 / 0.32 | 0.00 / 0.01 / 0.07 | 0.00 / 0.00 / 0.00 |

### Trees

Total trees p10/p25/p50/p75/p90: 59845 / 102567 / 142956 / 199472 / 233902; max 250000 (MAX_MAP_TREES = 250,000; 7 maps ≥ 245k). Inside the 25 tiles: 42492 / 58663 / 86597. Trees per km² of forest-resource area: 1531 / 1788 / 2184.
Forest cell values across all maps: 60: 44%, 120: 25%, 180: 14%, 240: 8%, 255: 8% (60 per tree, capped at 255).
Grow state: [(('0', '1', '15'), 94), (('0', '15'), 9), (('1', '15'), 1)] — almost every tree is saved at 15 (grown); a few at 0/1 (overlapping a network or building).

Original-release tree prefabs (the only ones in the 2015/Snowfall maps, data versions 244–316): `Tree2variant`, `Tree3variant`, `Conifer`, `Conifer2`, `treeForest`, `Pine01low`, `Beech01low`, `Alder01`, `Bush01`, `Bush02`, `palm01`, `palmplant01`; winter theme: `WintertreeForest`, `Coniferwinter`, `Conifer2Winter`, `Pine01Winter`, `Bush01Winter`.

| environment | maps | share of trees by prefab (maps using it), original-release prefabs only |
|:--|--:|:--|
| Sunny | 25 | Beech01low 26% (14), Alder01 12% (13), Tree3variant 10% (12), Tree2variant 6% (11), Bush02 2% (13), Bush01 2% (13) |
| North | 26 | treeForest 31% (21), Conifer2 21% (22), Conifer 13% (21), Pine01low 7% (17), Beech01low 3% (10), Bush01 2% (15), Alder01 2% (9), Tree3variant 2% (13), Tree2variant 1% (13) |
| Europe | 25 | Pine01low 8% (7), Tree3variant 6% (13), Conifer2 5% (12), Beech01low 5% (11), Conifer 5% (10), Tree2variant 5% (12), Bush01 4% (18), treeForest 4% (11), Alder01 2% (12) |
| Tropical | 23 | palm01 23% (18), Beech01low 12% (10), palmplant01 8% (21), Tree2variant 6% (8), Bush01 5% (12), Tree3variant 4% (8), Bush02 3% (17), Alder01 1% (7) |
| Winter | 5 | WintertreeForest 61% (4), Coniferwinter 33% (5), Conifer2Winter 4% (5), Bush01Winter 2% (4), Pine01Winter 0% (2) |

Original-release maps by environment and their prefab mix:

- Cliffside Bay (Europe, 54,518 trees): Bush01 49%, Pine01low 20%, Tree3variant 17%, Tree2variant 11%, Alder01 1%, Beech01low 1%
- Foggy Hills (Europe, 165,966 trees): Pine01low 76%, Tree3variant 10%, Bush01 8%, Tree2variant 4%, Alder01 2%, treeForest 0%
- Grand River (Europe, 139,362 trees): Pine01low 49%, Tree3variant 21%, Tree2variant 17%, Bush01 7%, Beech01low 3%, Alder01 3%
- Regal Hills (Europe, 50,435 trees): Tree2variant 65%, Tree3variant 33%, Bush01 2%
- Black Woods (North, 249,976 trees): treeForest 85%, Pine01low 12%, Tree3variant 1%, Tree2variant 1%, Conifer 0%, Conifer2 0%
- By The Dam (North, 211,839 trees): Conifer2 93%, Pine01low 7%
- Green Plains (North, 226,289 trees): treeForest 43%, Conifer 32%, Pine01low 20%, Tree3variant 3%, Bush01 0%, Conifer2 0%
- Lavender Lake (North, 200,254 trees): treeForest 64%, Bush01 15%, Tree3variant 7%, Tree2variant 4%, Conifer 4%, Pine01low 3%
- Prussian Peaks (North, 246,703 trees): Conifer2 92%, Pine01low 5%, treeForest 1%, Bush01 1%, Conifer 1%, Tree2variant 0%
- Riverrun (North, 220,379 trees): treeForest 76%, Pine01low 18%, Bush01 3%, Tree3variant 1%, Tree2variant 1%, Conifer 1%
- Seven Lakes (North, 192,893 trees): treeForest 69%, Conifer 28%, Conifer2 2%, Bush01 1%
- Arid Plains (Sunny, 41,779 trees): Tree2variant 40%, Beech01low 30%, Tree3variant 26%, Bush01 4%
- Eden Valley (Sunny, 125,705 trees): Alder01 24%, Tree2variant 18%, Bush02 17%, Beech01low 14%, Tree3variant 14%, Bush01 13%
- Floodland (Sunny, 250,000 trees): Tree3variant 45%, Tree2variant 44%, Beech01low 10%
- Islands (Sunny, 249,730 trees): Beech01low 87%, Alder01 11%, Bush01 1%, Bush02 1%
- Shady Strands (Sunny, 228,970 trees): Beech01low 60%, Alder01 34%, Bush01 5%, Bush02 1%
- The Dust Bowl (Sunny, 176,961 trees): Beech01low 47%, Tree3variant 41%, Alder01 8%, Bush02 3%, Tree2variant 0%
- Two Rivers (Sunny, 249,939 trees): Beech01low 84%, Alder01 15%, Bush02 0%, Bush01 0%
- Diamond Coast (Tropical, 182,684 trees): Beech01low 41%, palm01 25%, Bush01 20%, palmplant01 10%, Bush02 2%, Tree3variant 0%
- Garden Rivers (Tropical, 198,104 trees): Tree2variant 61%, palmplant01 15%, Bush01 11%, Tree3variant 6%, palm01 6%, Alder01 1%
- Lagoon Shore (Tropical, 236,016 trees): Beech01low 25%, palm01 22%, Bush01 17%, Tree3variant 16%, palmplant01 11%, Tree2variant 7%
- Sandy Beach (Tropical, 246,534 trees): palm01 23%, Beech01low 21%, Tree2variant 20%, Tree3variant 18%, Bush02 8%, Bush01 7%
- The Archipelago (Tropical, 226,993 trees): palm01 76%, palmplant01 24%
- Frosty Rivers (Winter, 186,470 trees): WintertreeForest 86%, Coniferwinter 14%, Conifer2Winter 0%
- Icy Islands (Winter, 166,081 trees): WintertreeForest 82%, Coniferwinter 18%, Conifer2Winter 0%, Bush01Winter 0%
- Snowy Coast (Winter, 188,434 trees): WintertreeForest 75%, Coniferwinter 20%, Bush01Winter 2%, Pine01Winter 2%, Conifer2Winter 1%

### Forest resource versus trees

Exact cell match with min(60 × trees in cell, 255): p0/p10/p50 = 0.872 / 0.967 / 0.992. Forest cells with no tree: p50/p90/max = 382 / 3332 / 26018. Worst: CCP Map 8 26018, Black Woods 22478, Riverrun 18307, CCP Map 1 16262, CCP Map 5 10020. Fertility on forest cells: 0 cells in the whole corpus; ore and oil in the same cell: 0.

### Connections and start tile

Start tile index (5×5, 12 = centre): 12: 72, 7: 7, 17: 5, 18: 5, 13: 5, 6: 3, 11: 3, 8: 3, 16: 1.
- incomingRoads: 1×3, 2×24, 3×31, 4×46
- incomingTrainTracks: 0×6, 1×5, 2×37, 3×23, 4×33
- incomingShipPath: 0×23, 1×9, 2×35, 3×10, 4×27
- incomingPlanePath: 0×1, 2×27, 3×1, 4×75

### Per map

| map (file) | env | ver | build % | trees | ore | oil | fert | forest | water | start | ore/oil/fert blobs |
|:--|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--|
| Arid Plains (MT Trains) | Sunny | 320 | 79 | 41,779 | 0.017 | 0.004 | 0.015 | 0.079 | 0.046 | 12 | 5/4/9 |
| Asanu Beach (AP Asanu Beach) | Tropical | 114007 | 75 | 164,593 | 0.120 | 0.029 | 0.051 | 0.146 | 0.127 | 12 | 11/5/3 |
| Azure Gulf (DN Azure Gulf) | Sunny | 113007 | 65 | 140,025 | 0.021 | 0.018 | 0.030 | 0.141 | 0.235 | 12 | 11/6/13 |
| Black Woods (NorthEurope3FINAL) | North | 293 | 69 | 249,976 | 0.059 | 0.057 | 0.033 | 0.185 | 0.217 | 12 | 9/6/10 |
| By The Dam (ND By The Dam) | North | 312 | 65 | 211,839 | 0.043 | 0.009 | 0.013 | 0.303 | 0.241 | 16 | 5/2/6 |
| CCMP2 Boreal Map 1 (CCMP2 Boreal Map 1) | North | 116019 | 70 | 133,174 | 0.088 | 0.016 | 0.030 | 0.175 | 0.068 | 7 | 26/13/17 |
| CCMP2 Boreal Map 2 (CCMP2 Boreal Map 2) | North | 116019 | 26 | 135,965 | 0.053 | 0.048 | 0.034 | 0.115 | 0.373 | 6 | 17/18/16 |
| CCMP2 Desert Map 1 (CCMP2 Desert Map 1) | Europe | 116020 | 89 | 45,598 | 0.185 | 0.195 | 0.005 | 0.062 | 0.012 | 17 | 12/16/8 |
| CCMP2 Desert Map 2 (CCMP2 Desert Map 2) | Europe | 116019 | 79 | 108,756 | 0.136 | 0.153 | 0.010 | 0.104 | 0.048 | 11 | 17/7/13 |
| CCMP2 Euro Map 1 (CCMP2 Euro Map 1) | Europe | 116019 | 77 | 211,461 | 0.054 | 0.008 | 0.031 | 0.223 | 0.076 | 7 | 50/18/48 |
| CCMP2 Euro Map 2 (CCMP2 Euro Map 2) | Europe | 116019 | 81 | 208,424 | 0.038 | 0.004 | 0.028 | 0.175 | 0.081 | 12 | 36/6/26 |
| CCMP2 Temperate Map 1 (CCMP2 Temperate Map 1) | Sunny | 116019 | 48 | 140,810 | 0.097 | 0.208 | 0.030 | 0.172 | 0.374 | 12 | 20/28/12 |
| CCMP2 Temperate Map 2 (CCMP2 Temperate Map 2) | Sunny | 116020 | 48 | 206,386 | 0.128 | 0.073 | 0.049 | 0.205 | 0.210 | 17 | 19/32/23 |
| CCMP2 Tropical Map 1 (CCMP2 Tropical Map 1) | Tropical | 116019 | 46 | 75,448 | 0.097 | 0.088 | 0.030 | 0.105 | 0.359 | 6 | 22/32/9 |
| CCMP2 Tropical Map 2 (CCMP2 Tropical Map 2) | Tropical | 116020 | 78 | 181,088 | 0.063 | 0.090 | 0.050 | 0.171 | 0.168 | 18 | 52/15/27 |
| CCP Map 1 (CCP Map 1) | Tropical | 114011 | 62 | 103,163 | 0.036 | 0.094 | 0.105 | 0.192 | 0.278 | 8 | 4/10/9 |
| CCP Map 2 (CCP Map 2) | Tropical | 114011 | 68 | 100,181 | 0.049 | 0.044 | 0.076 | 0.161 | 0.285 | 13 | 2/4/14 |
| CCP Map 3 (CCP Map 3) | North | 114011 | 83 | 97,139 | 0.107 | 0.014 | 0.198 | 0.128 | 0.047 | 12 | 2/3/5 |
| CCP Map 4 (CCP Map 4) | North | 114011 | 59 | 93,693 | 0.047 | 0.035 | 0.070 | 0.159 | 0.099 | 12 | 5/3/14 |
| CCP Map 5 (CCP Map 5) | Europe | 114011 | 89 | 86,613 | 0.250 | 0.359 | 0.000 | 0.177 | 0.040 | 12 | 1/2/0 |
| CCP Map 6 (CCP Map 6) | Sunny | 114011 | 90 | 124,933 | 0.145 | 0.111 | 0.161 | 0.175 | 0.031 | 12 | 7/4/8 |
| CCP Map 7 (CCP Map 7) | Sunny | 114011 | 78 | 107,319 | 0.078 | 0.073 | 0.115 | 0.142 | 0.175 | 12 | 3/3/6 |
| CCP Map 8 (CCP Map 8) | Europe | 114011 | 73 | 104,891 | 0.062 | 0.113 | 0.120 | 0.224 | 0.137 | 12 | 3/6/9 |
| Cape Apple (PB Cape Apple) | Sunny | 115014 | 64 | 116,763 | 0.021 | 0.012 | 0.066 | 0.126 | 0.299 | 7 | 5/4/16 |
| Cavern Coast (PL Cavern Coast) | Tropical | 110025 | 61 | 238,228 | 0.061 | 0.010 | 0.040 | 0.301 | 0.243 | 13 | 9/4/9 |
| Cliffside Bay (Cliffside Bay) | Europe | 244 | 53 | 54,518 | 0.087 | 0.015 | 0.048 | 0.100 | 0.225 | 8 | 5/2/4 |
| Coastal Flatland (MM Coastal Flatland) | Sunny | 117005 | 57 | 134,676 | 0.021 | 0.039 | 0.065 | 0.116 | 0.414 | 12 | 3/6/5 |
| Coastal Gem (PB Coastal Gem) | Tropical | 115014 | 57 | 74,407 | 0.027 | 0.008 | 0.019 | 0.060 | 0.391 | 12 | 10/6/9 |
| Crater Falls (DN Crater Falls) | North | 113010 | 46 | 126,917 | 0.120 | 0.021 | 0.077 | 0.199 | 0.182 | 11 | 16/3/9 |
| Desert Oasis (DN Desert Oasis) | Tropical | 113010 | 76 | 57,988 | 0.078 | 0.096 | 0.002 | 0.089 | 0.016 | 7 | 3/7/5 |
| Diamond Coast (Tropical2FINAL) | Tropical | 244 | 69 | 182,684 | 0.079 | 0.026 | 0.022 | 0.282 | 0.189 | 12 | 2/1/17 |
| Eden Valley (Eden Valley2) | Sunny | 109011 | 79 | 125,705 | 0.045 | 0.063 | 0.061 | 0.245 | 0.075 | 12 | 9/1/9 |
| Emerald Cliffs (MM Emerald Cliffs) | Europe | 117004 | 72 | 72,970 | 0.040 | 0.058 | 0.058 | 0.085 | 0.217 | 18 | 12/8/6 |
| Fisher Enclave (DN Fisher Enclave) | Europe | 113010 | 45 | 110,270 | 0.005 | 0.062 | 0.019 | 0.146 | 0.498 | 12 | 2/17/9 |
| Floodland (ND Floodland) | Sunny | 312 | 76 | 250,000 | 0.000 | 0.000 | 0.000 | 0.152 | 0.059 | 17 | 0/0/0 |
| Foggy Hills (Foggy Hills) | Europe | 244 | 74 | 165,966 | 0.091 | 0.031 | 0.051 | 0.101 | 0.087 | 12 | 2/2/7 |
| Frosty Rivers (Winter3Final) | Winter | 244 | 56 | 186,470 | 0.048 | 0.034 | 0.046 | 0.150 | 0.303 | 12 | 5/4/5 |
| Frozenshire (Winter4Final) | Winter | 111015 | 51 | 165,975 | 0.110 | 0.039 | 0.015 | 0.258 | 0.109 | 12 | 13/5/6 |
| Garden Rivers (Garden Rivers2) | Tropical | 109006 | 80 | 198,104 | 0.035 | 0.024 | 0.025 | 0.244 | 0.147 | 12 | 2/4/8 |
| Gondola Islands (PB Gondola Islands) | Europe | 115014 | 34 | 29,134 | 0.016 | 0.011 | 0.056 | 0.056 | 0.645 | 12 | 6/5/7 |
| Grand River (Grand River) | Europe | 244 | 84 | 139,362 | 0.098 | 0.000 | 0.063 | 0.124 | 0.078 | 12 | 4/0/7 |
| Gray Waters (PU Gray Waters) | North | 116010 | 56 | 71,722 | 0.044 | 0.023 | 0.033 | 0.102 | 0.298 | 12 | 12/8/14 |
| Green Peaks (IN Green Peaks) | Europe | 111013 | 54 | 76,365 | 0.024 | 0.013 | 0.081 | 0.079 | 0.321 | 12 | 7/5/7 |
| Green Plains (NorthEurope1FINAL) | North | 244 | 74 | 226,289 | 0.061 | 0.048 | 0.029 | 0.189 | 0.119 | 12 | 6/4/6 |
| Hanami Bay (AP Hanami Bay) | Sunny | 114009 | 70 | 101,017 | 0.056 | 0.033 | 0.080 | 0.133 | 0.190 | 12 | 9/7/4 |
| Honu Island (PL Honu Island) | Tropical | 110025 | 45 | 247,917 | 0.024 | 0.107 | 0.002 | 0.333 | 0.485 | 17 | 7/4/6 |
| Icy Islands (Winter2Final) | Winter | 244 | 59 | 166,081 | 0.062 | 0.061 | 0.025 | 0.138 | 0.305 | 12 | 6/4/4 |
| Islands (SouthEurope1FINAL) | Sunny | 244 | 60 | 249,730 | 0.035 | 0.046 | 0.034 | 0.240 | 0.330 | 12 | 7/6/6 |
| Lagoon Shore (Tropical3FINAL) | Tropical | 112031 | 56 | 236,016 | 0.083 | 0.021 | 0.048 | 0.292 | 0.339 | 18 | 7/2/8 |
| Lavender Lake (Lavender Lake2) | North | 109006 | 75 | 200,254 | 0.054 | 0.038 | 0.039 | 0.177 | 0.076 | 12 | 4/5/2 |
| MP23_Map01 (MP23_Map01) | Europe | 117013 | 60 | 147,247 | 0.214 | 0.031 | 0.115 | 0.145 | 0.216 | 12 | 23/24/6 |
| MP23_Map02 (MP23_Map02) | Sunny | 117013 | 83 | 61,740 | 0.047 | 0.575 | 0.290 | 0.094 | 0.055 | 12 | 12/1/5 |
| MP23_Map03 (MP23_Map03) | North | 117013 | 47 | 174,732 | 0.180 | 0.046 | 0.056 | 0.176 | 0.335 | 7 | 25/15/6 |
| MP23_Map04 (MP23_Map04) | Tropical | 117013 | 68 | 239,647 | 0.083 | 0.040 | 0.217 | 0.295 | 0.051 | 12 | 37/22/4 |
| MP23_Map05 (MP23_Map05) | Europe | 117013 | 64 | 37,003 | 0.388 | 0.337 | 0.087 | 0.071 | 0.179 | 12 | 14/5/1 |
| MP23_Map06 (MP23_Map06) | Sunny | 117013 | 83 | 135,888 | 0.270 | 0.532 | 0.160 | 0.161 | 0.023 | 12 | 8/1/5 |
| MP23_Map07 (MP23_Map07) | North | 117013 | 62 | 240,167 | 0.276 | 0.077 | 0.089 | 0.269 | 0.190 | 12 | 13/11/4 |
| MP23_Map08 (MP23_Map08) | Tropical | 117013 | 46 | 191,637 | 0.186 | 0.073 | 0.027 | 0.265 | 0.415 | 13 | 17/30/13 |
| MP23_Map09 (MP23_Map09) | Europe | 117013 | 39 | 130,548 | 0.083 | 0.115 | 0.087 | 0.132 | 0.362 | 11 | 15/12/4 |
| MP23_Map10 (MP23_Map10) | Sunny | 117013 | 44 | 186,443 | 0.097 | 0.270 | 0.089 | 0.207 | 0.412 | 13 | 38/21/8 |
| MP27_Map01 (MP27_Map01) | Sunny | 118011 | 73 | 222,273 | 0.064 | 0.182 | 0.245 | 0.154 | 0.235 | 18 | 10/9/11 |
| MP27_Map02 (MP27_Map02) | Tropical | 118011 | 75 | 228,024 | 0.044 | 0.061 | 0.075 | 0.352 | 0.128 | 8 | 14/32/13 |
| MP27_Map03 (MP27_Map03) | Europe | 118011 | 83 | 198,998 | 0.070 | 0.080 | 0.230 | 0.231 | 0.119 | 13 | 8/12/37 |
| MP27_Map04 (MP27_Map04) | Tropical | 118011 | 49 | 143,964 | 0.088 | 0.126 | 0.067 | 0.164 | 0.499 | 7 | 10/17/9 |
| MP27_Map05 (MP27_Map05) | Europe | 118011 | 89 | 128,842 | 0.309 | 0.083 | 0.038 | 0.156 | 0.019 | 12 | 10/12/4 |
| MP27_Map06 (MP27_Map06) | North | 118011 | 63 | 198,198 | 0.151 | 0.101 | 0.143 | 0.248 | 0.121 | 17 | 14/34/6 |
| MP27_Map07 (MP27_Map07) | Sunny | 118011 | 57 | 218,678 | 0.201 | 0.077 | 0.116 | 0.326 | 0.150 | 12 | 9/11/6 |
| MP27_Map08 (MP27_Map08) | Europe | 118011 | 57 | 220,102 | 0.179 | 0.083 | 0.137 | 0.200 | 0.216 | 12 | 7/6/8 |
| MP27_Map09 (MP27_Map09) | North | 118011 | 72 | 218,677 | 0.192 | 0.073 | 0.118 | 0.295 | 0.079 | 6 | 19/24/14 |
| MP27_Map10 (MP27_Map10) | Sunny | 118011 | 96 | 177,171 | 0.217 | 0.164 | 0.307 | 0.118 | 0.013 | 12 | 50/51/20 |
| Marble Canyon (IN Marble Canyon) | Sunny | 111013 | 69 | 103,084 | 0.173 | 0.054 | 0.057 | 0.183 | 0.195 | 12 | 4/3/4 |
| Marin Bay (CL Marin Bay) | Sunny | 112004 | 61 | 171,135 | 0.055 | 0.042 | 0.041 | 0.193 | 0.275 | 12 | 7/5/14 |
| Maze Valley (MM Maze Valley) | Europe | 117005 | 74 | 151,001 | 0.039 | 0.031 | 0.054 | 0.134 | 0.095 | 18 | 7/9/5 |
| Mountain Meadows (PL Mountain Meadows) | Europe | 110025 | 69 | 91,141 | 0.015 | 0.006 | 0.162 | 0.173 | 0.069 | 12 | 8/4/3 |
| Murky Coast (CL Murky Coast) | North | 112004 | 71 | 172,778 | 0.024 | 0.002 | 0.071 | 0.154 | 0.157 | 12 | 5/2/7 |
| Narrow Passage (PU Narrow Passage) | Sunny | 116010 | 49 | 70,898 | 0.043 | 0.033 | 0.087 | 0.081 | 0.471 | 12 | 6/11/4 |
| Northwood Hills (CL Northwood Hills) | Europe | 112004 | 72 | 123,668 | 0.078 | 0.017 | 0.128 | 0.171 | 0.078 | 12 | 9/2/5 |
| Noyou Port (AP Noyou Port) | North | 114008 | 80 | 138,363 | 0.039 | 0.027 | 0.038 | 0.173 | 0.058 | 7 | 11/15/9 |
| Oracle Lake (PB Oracle Lake) | North | 115014 | 78 | 195,947 | 0.063 | 0.009 | 0.009 | 0.195 | 0.116 | 12 | 13/4/7 |
| Pearl Bay (IN Pearl Bay) | Tropical | 111013 | 58 | 154,719 | 0.108 | 0.088 | 0.080 | 0.230 | 0.288 | 12 | 5/5/5 |
| Pine Rivers (PL Pine Rivers) | North | 110025 | 84 | 36,677 | 0.045 | 0.002 | 0.005 | 0.054 | 0.110 | 12 | 28/3/3 |
| Prussian Peaks (ND Alpine Villages) | North | 316 | 52 | 246,703 | 0.028 | 0.008 | 0.002 | 0.261 | 0.127 | 12 | 3/1/7 |
| Regal Hills (MT Fix The Traffic) | Europe | 316 | 72 | 50,435 | 0.013 | 0.003 | 0.007 | 0.071 | 0.118 | 12 | 5/2/4 |
| River Terrace (PU River Terrace) | North | 116010 | 64 | 141,948 | 0.040 | 0.023 | 0.071 | 0.146 | 0.243 | 12 | 11/10/7 |
| Riverrun (NorthEurope2FINAL) | North | 116011 | 76 | 220,379 | 0.043 | 0.040 | 0.047 | 0.241 | 0.077 | 12 | 7/10/5 |
| Roslyn Peninsula (CL Roslyn Peninsula) | Tropical | 112004 | 54 | 41,198 | 0.019 | 0.052 | 0.010 | 0.070 | 0.409 | 12 | 6/7/4 |
| Sandy Beach (Tropical1FINAL) | Tropical | 293 | 63 | 246,534 | 0.035 | 0.020 | 0.014 | 0.269 | 0.217 | 12 | 8/3/13 |
| Seven Lakes (MT Ferry Empire) | North | 316 | 81 | 192,893 | 0.007 | 0.001 | 0.001 | 0.293 | 0.113 | 12 | 4/1/4 |
| Shady Strands (SouthEurope2FINAL) | Sunny | 293 | 57 | 228,970 | 0.040 | 0.022 | 0.030 | 0.217 | 0.385 | 12 | 3/4/5 |
| Shifting Sands (MM Shifting Sands) | Tropical | 117005 | 72 | 59,104 | 0.075 | 0.048 | 0.031 | 0.090 | 0.141 | 12 | 11/13/6 |
| Snowy Coast (Winter1Final) | Winter | 244 | 68 | 188,434 | 0.037 | 0.023 | 0.043 | 0.185 | 0.233 | 12 | 4/4/6 |
| Splitz Tributary (PB Splitz Tributary) | Europe | 115023 | 89 | 128,199 | 0.026 | 0.013 | 0.017 | 0.117 | 0.052 | 12 | 11/8/8 |
| Swamplands (DN Swamplands) | North | 113010 | 71 | 199,211 | 0.018 | 0.009 | 0.054 | 0.147 | 0.198 | 12 | 9/3/10 |
| The Archipelago (ND Island Hopping) | Tropical | 316 | 21 | 226,993 | 0.000 | 0.000 | 0.001 | 0.219 | 0.765 | 12 | 0/0/14 |
| The Dust Bowl (ND Tornado Country) | Sunny | 316 | 82 | 176,961 | 0.006 | 0.005 | 0.021 | 0.212 | 0.154 | 12 | 1/1/5 |
| Twin Fjords (IN Twin Fjords) | North | 111013 | 69 | 98,989 | 0.104 | 0.119 | 0.017 | 0.091 | 0.114 | 12 | 13/11/8 |
| Two Rivers (SouthEurope3FINAL) | Sunny | 244 | 78 | 249,939 | 0.052 | 0.051 | 0.016 | 0.292 | 0.105 | 12 | 7/6/5 |
| Weaving Waters (MM Weaving Waters) | Europe | 117005 | 84 | 122,324 | 0.061 | 0.043 | 0.061 | 0.200 | 0.071 | 12 | 9/8/4 |
| Windblown Coast (PU Windblown Coast) | Tropical | 116010 | 66 | 39,431 | 0.033 | 0.049 | 0.012 | 0.067 | 0.239 | 12 | 3/12/8 |
| Windfield (PL Windfield) | Sunny | 110025 | 65 | 213,146 | 0.015 | 0.088 | 0.093 | 0.202 | 0.276 | 12 | 3/4/1 |
| Winter Hills (Winter5Final) | Winter | 111015 | 68 | 61,573 | 0.013 | 0.011 | 0.001 | 0.080 | 0.085 | 12 | 6/5/5 |
| Wolf Creek (CL Wolf Creek) | North | 112004 | 60 | 122,376 | 0.078 | 0.006 | 0.017 | 0.143 | 0.106 | 12 | 11/3/3 |
| Woodgarden (IN Woodgarden) | North | 111013 | 62 | 158,348 | 0.089 | 0.000 | 0.093 | 0.161 | 0.257 | 12 | 7/0/9 |
| Wyvern Pass (PU Wyvern Pass) | Tropical | 116010 | 66 | 109,024 | 0.112 | 0.021 | 0.056 | 0.116 | 0.094 | 12 | 14/11/8 |

Resource columns are New Game amounts ÷ maxResourceAmount (25 tiles).
