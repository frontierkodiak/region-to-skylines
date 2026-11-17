# Asheville gameplay data sources

Public source/catalogue checks on **2026-11-17**, for PL-1019. These are source
and coverage facts, not imported or game-qualified layers. Format carriers and
writer gaps are in [GAMEPLAY_FORMATS.md](GAMEPLAY_FORMATS.md).

## Sources, reuse terms and coverage

| Layer/data | Source and actual coverage | Reuse terms observed; limits |
| --- | --- | --- |
| Dams | [USACE NID public GIS](https://nid.sec.usace.army.mil/nid/) supplies point locations, purpose, heights, length and storage; [FeatureServer layer 0](https://geospatial.sec.usace.army.mil/dls/rest/services/NID/National_Inventory_of_Dams_Public_Service/FeatureServer/0) returned the candidates below. OSM can supply wall/shore geometry. | The [federal NTAD representation of NID](https://catalog.data.gov/dataset/dams-c7ed4) lists **CC0**; use that distribution for a clearly licensed downloadable inventory. NID is not a complete inventory of every small weir and does not supply a surveyed wall, bathymetry, absolute pool stage or operating curve. Do not infer generation from purpose alone. |
| Water/sewage sites | [City water sources](https://www.ashevillenc.gov/department/water/water-quality-report/) identify North Fork, Bee Tree/William DeBruhl and Mills River; the French Broad intake is a backup. [MSD location](https://www.msdbc.org/contact.php) places its plant north of 2028 Riverside Drive in Woodfin; [MSD treatment description](https://www.msdbc.org/faq.php) confirms treated return to the French Broad. [EPA ECHO](https://echodata.epa.gov/echo/cwa_rest_services.get_facility_info?output=JSON&p_pid=NC0024911) identifies the French Broad River WRF, permit NC0024911. | Operator pages establish facts, not an open engineering/GIS licence. For redistributable site geometry use OSM (**ODbL**) or explicitly licensed federal records; no utility schematics or private pipe network were acquired. Full intakes/reservoirs extend well outside the default square; these are not three pumps on the downtown river. |
| City zoning | [Asheville Zoning Districts, layer 11](https://gis.ashevillenc.gov/server/rest/services/Districts/ZoningDistricts/FeatureServer/11): **740 features** in an unfiltered count. Fields include `districts`, `status`, `type` and overlays. | The city's [AVLGIS catalogue item](https://www.arcgis.com/sharing/rest/content/items/bf8dd741efe646a793339bbd1485c66b?f=json) explicitly links **PDDL 1.0** (the label misspells it “PPDL”). City jurisdiction only; filter status and separate overlays. Permitted zoning is not observed present-day building use. Mixed-use and conditional zoning have no exact vanilla RCI translation. |
| County zoning/parcels | [County open-data FeatureServer](https://gis.buncombecounty.org/arcgis/rest/services/opendata/FeatureServer) exposes Property (1), Street Centerline (3), Buncombe County Zoning (5); [opendata_2](https://gis.buncombecounty.org/arcgis/rest/services/opendata_2/MapServer) has yearly parcels including Property_2025 (17). County and city jurisdictions are distinct. | [County GIS terms](https://gis.buncombecounty.org/buncomap/default.aspx) call the data public-domain but also state resale/commercial-use restrictions and possible reproduction licensing. Do **not** treat anonymous access as an unrestricted public-export licence. Assessor use is a parcel label, not a verified use for every building. No owner/contact attributes are needed for gameplay. |
| Neighborhoods/districts | The city's [current registered-neighborhood layer](https://gis.ashevillenc.gov/server/rest/services/Boundaries/NeighborhoodView/FeatureServer/11) returned **87 records**: 82 Active, 3 Inactive, 2 In transition; examples include Montford and Grove Park/Sunset. The [city's 2023 web map](https://www.arcgis.com/sharing/rest/content/items/21cd26fea84847b8a314b7333ec5cad6/data?f=json) points at this service. | Current layer copyright is blank and its advertised service item was inaccessible; no explicit layer licence was found. The separate older [hosted Neighborhoods item](https://www.arcgis.com/sharing/rest/content/items/a45d4ed6e51043ea97b5bfbdf657c7cc?f=json) has an incomplete licensing link and metadata saying “OLD Don't use”. Do not silently substitute it or assume the zoning item's PDDL covers this layer. Registered groups do not tessellate the whole city. Export names/boundaries only, not contacts. |
| Rail and local roads | [OSM](https://www.openstreetmap.org/copyright) covers the river-valley tracks, yards, branches and streets. Existing [PL-982 import](REAL_ROADS.md) already supports main-line rail but expressly filters `service` tracks and prunes short spurs. | **ODbL**, with OSM attribution and applicable database obligations. A complete yard needs retained topology/parallel tracks rather than the main-line simplification. Track presence does not prove current service or traffic. A raw yard geometry query was not successfully acquired in this pass; no new completeness claim is made. |
| ART transit | [Producer's static GTFS ZIP](https://data.trilliumtransit.com/gtfs/asheville-nc-us/asheville-nc-us.zip) was downloaded and inspected: **18 routes, 677 stops, 13,480 shape rows**, one Asheville Rides Transit agency. Feed version `UTC: 28-Aug-2026 23:04`; advertised dates 2026-08-28 through 2026-12-31. | `feed_info.txt`'s **`feed_license` is blank** and no licence file was in the ZIP. Public fetchability is established, explicit reuse terms are not. 599 stop points fall in the full default square, 463 in the central-25 envelope, before road-access checks. A route leaving the square cannot be imported as a disconnected stub and called an operational line. Vanilla line budgets/day-night behavior do not reproduce a GTFS timetable. |
| Power plants/corridors | [EIA plant locations](https://www.eia.gov/tools/faqs/faq.php?id=567&t=1) cover generation of at least 1 MW via EIA-860/860M. The [HIFLD transmission catalogue](https://catalog.data.gov/dataset/electric-power-transmission-lines) describes a national transmission layer; OSM supplies a directly reusable alignment alternative. [Duke's plant description](https://news.duke-energy.com/releases/duke-energy-progress-customers-receiving-560-megawatts-of-cleaner-energy-from-new-natural-gas-power-plant-in-north-carolina) identifies Asheville's combined-cycle station in Arden and the 2020 coal retirement. | EIA data is [public-domain with source/date acknowledgment](https://www.eia.gov/about/copyrights_reuse.php); HIFLD's catalogue links government-works terms but has old metadata, and its live line extract was **not** qualified here. OSM is **ODbL**. Do not recreate a current coal plant from an old map or claim real voltage/load-flow simulation from vanilla power lines. The Arden generating site is outside the default downtown square. |
| Floodplains | [FEMA NFHL](https://catalog.data.gov/dataset/national-flood-hazard-layer), with a live [Flood Hazard Zones layer](https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28). A bounding-envelope count around the default square returned **400 features**, not a full coverage/accuracy audit. | Federal catalogue links **government-works/public-domain** terms. Effective regulatory flood zones are not ordinary river extents or a Helene inundation reconstruction. Base-flood elevations need their vertical units/datum transformed into the exporter's offset/scaled game heights. No NFHL polygon-to-CS1 hydraulic validation was run. |
| Real starting city | Combine OSM networks, explicitly licensed footprints, city zoning, building-use evidence and service sites above; add game state rather than just geographic geometry. | Retain each source's terms; there is no single “Asheville” licence. County parcel-use and neighborhood terms above remain unresolved for public redistribution. Zones alone do not identify existing homes, shops, workplaces or their occupants. |

Counts above are dated whole-source/query observations, not a claim that all
features fit, are active, or can be played. The ART ZIP SHA-256 was
`e26ad1ae421bdf541fa132213c223dfc2d6ad2103da4906b601a31cae5050a7e`.

## Dam candidates in the default square

The [preset](../../terrain.js) and committed
`fixtures/asheville/geometry.json.gz` specify **35.58 N, 82.555 W**, rotation 0,
scale 1. The terrain half-width is 8,640 m; the vanilla central-25 envelope has
half-width 4,800 m (not all purchased at game start). The following are NID
**point** locations projected with [the exporter's WGS84 frame](prepare.py),
rounded to 0.01 km. This tests location, not whether an entire reservoir fits.

| Candidate / NID ID | East, north from centre (km) | Full terrain / central 25 | Interpretation |
| --- | --- | --- | --- |
| Craggy / NC06522 | -4.00, +6.87 | Inside / outside | Only named candidate inside this preset. Inventory lists 13 ft hydraulic height, 706 ft length, hydroelectric purpose and normal operations. |
| Lake Julian / NC05712 | +0.73, -11.48 | Outside / outside | Inventory purpose is labelled hydroelectric/recreation; that label alone does not establish the plant technology or a suitable CS1 powerhouse. |
| North Fork / NC00288 | +19.05, +9.04 | Outside / outside | Water-supply reservoir, not a hydroelectric inference. |
| Bee Tree / NC00289 | +13.96, +6.79 | Outside / outside | Water-supply reservoir. |
| Lake Lure / NC00100 | +33.63, -17.09 | Outside / outside | Separate region. |
| Fontana / NC00298 | -113.28, -14.14 | Outside / outside | Separate region, not a modest extension of this preset. |
| Lake James: Catawba / NC00374; Paddy Creek / NC00375; Linville / NC00141 | +60.38 to +65.01, +16.98 to +18.22 | Outside / outside | Multiple dam structures, not a single Lake James point/powerhouse. |

Craggy can affect the French Broad upstream even though its site is outside
vanilla's purchasable envelope. Being in the full terrain does not make the
dam a player-editable starting-tile asset. Moving the square, expanding its
real-world span, or relying on an 81 Tiles mod changes the product/qualification
contract; none was done here.

NID's `DAM_HEIGHT`, `HYDRAULIC_HEIGHT`, `DAM_LENGTH` and storage fields are not
an absolute reservoir-level survey. Derive any initial stage from independent
elevation/shore evidence in a known datum, then apply the same height offset
and vertical compression as the terrain. Do not insert new target regulators
merely to make a reservoir look stable.

Reproduce the dam lookup against layer 0 with `returnGeometry=false`,
`outFields=NIDID,NAME,LATITUDE,LONGITUDE,DAM_HEIGHT,HYDRAULIC_HEIGHT,DAM_LENGTH,PRIMARY_PURPOSE,OPERATIONAL_STATUS`
and this SQL filter:

```sql
NIDID IN ('NC06522','NC05712','NC00288','NC00289','NC00100',
         'NC00298','NC00374','NC00375','NC00141')
```

The [NID GIS/API entry points](https://nid.sec.usace.army.mil/api/developer)
document public access. A null operational-status field is **unknown**, not
evidence that a dam was removed, closed or generating electricity today.
