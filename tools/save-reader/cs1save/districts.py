"""Decoders for DistrictManager, EconomyManager and TransportManager blocks,
transcribed from each manager's Data.Serialize in CS1 1.21.1-f9 (format 121034).

District and line custom names live in InstanceManager's names.
"""

import numpy as np

from .managers import objects, prefab_block
from .stream import FormatError

DISTRICT_COUNT = 128  # Array8<District>(128)
PARK_COUNT = 128  # Array8<DistrictPark>(128)
DISTRICT_GRID = 512  # DISTRICTGRID_RESOLUTION
DISTRICT_CELL = 19.2  # DISTRICTGRID_CELL_SIZE, metres
LINE_COUNT = 256  # Array16<TransportLine>(256)
INVESTMENT_COUNT = 255  # Array8<Investment>(255)

# Field lists of the District*Data structs, in Serialize order.
POPULATION_DATA = [
    ("temp_count", "u24"),
    ("final_count", "u24"),
    ("delta0", "i16"),
    ("delta1", "i16"),
    ("delta2", "i16"),
    ("delta3", "i16"),
    ("delta4", "i16"),
    ("delta5", "i16"),
    ("delta6", "i16"),
    ("delta7", "i16"),
    ("delta8", "i16"),
    ("delta9", "i16"),
    ("delta10", "i16"),
    ("delta11", "i16"),
    ("delta12", "i16"),
    ("delta13", "i16"),
    ("delta14", "i16"),
    ("delta15", "i16"),
]
PRODUCTION_DATA = [
    ("temp_electricity_capacity", "u24"),
    ("temp_water_capacity", "u24"),
    ("temp_sewage_capacity", "u24"),
    ("temp_incineration_capacity", "u24"),
    ("temp_garbage_amount", "u32"),
    ("temp_garbage_capacity", "u32"),
    ("final_electricity_capacity", "u24"),
    ("final_water_capacity", "u24"),
    ("final_sewage_capacity", "u24"),
    ("final_incineration_capacity", "u24"),
    ("final_garbage_amount", "u32"),
    ("final_garbage_capacity", "u32"),
    ("temp_heal_capacity", "u24"),
    ("temp_cremate_capacity", "u24"),
    ("temp_dead_amount", "u32"),
    ("temp_dead_capacity", "u32"),
    ("final_heal_capacity", "u24"),
    ("final_cremate_capacity", "u24"),
    ("final_dead_amount", "u32"),
    ("final_dead_capacity", "u32"),
    ("temp_education1_capacity", "u24"),
    ("temp_education2_capacity", "u24"),
    ("temp_education3_capacity", "u24"),
    ("final_education1_capacity", "u24"),
    ("final_education2_capacity", "u24"),
    ("final_education3_capacity", "u24"),
    ("temp_criminal_amount", "u24"),
    ("temp_criminal_capacity", "u24"),
    ("final_criminal_amount", "u24"),
    ("final_criminal_capacity", "u24"),
    ("temp_criminal_extra", "u16"),
    ("final_criminal_extra", "u16"),
    ("average_criminal_extra", "u32"),
    ("temp_taxi_capacity", "u16"),
    ("final_taxi_capacity", "u16"),
    ("temp_snow_amount", "u32"),
    ("temp_snow_capacity", "u32"),
    ("final_snow_amount", "u32"),
    ("final_snow_capacity", "u32"),
    ("temp_heating_capacity", "u24"),
    ("final_heating_capacity", "u24"),
    ("temp_snow_cover", "u32"),
    ("final_snow_cover", "u32"),
    ("temp_water_storage_amount", "u32"),
    ("temp_water_storage_capacity", "u32"),
    ("temp_shelter_citizen_number", "u24"),
    ("temp_shelter_citizen_capacity", "u24"),
    ("final_water_storage_amount", "u32"),
    ("final_water_storage_capacity", "u32"),
    ("final_shelter_citizen_number", "u24"),
    ("final_shelter_citizen_capacity", "u24"),
    ("temp_renewable_electricity", "u24"),
    ("temp_polluting_electricity", "u24"),
    ("final_renewable_electricity", "u24"),
    ("final_polluting_electricity", "u24"),
    ("temp_library_capacity", "u24"),
    ("final_library_capacity", "u24"),
    ("temp_health_care_productivity", "u24"),
    ("final_health_care_productivity", "u24"),
    ("temp_hospital_count", "u24"),
    ("final_hospital_count", "u24"),
    ("temp_death_care_productivity", "u24"),
    ("final_death_care_productivity", "u24"),
    ("temp_cemetery_count", "u24"),
    ("final_cemetery_count", "u24"),
    ("temp_generic_industry_area", "u24"),
    ("temp_farming_industry_area", "u24"),
    ("temp_forestry_industry_area", "u24"),
    ("temp_ore_industry_area", "u24"),
    ("temp_oil_industry_area", "u24"),
    ("final_generic_industry_area", "u24"),
    ("final_farming_industry_area", "u24"),
    ("final_forestry_industry_area", "u24"),
    ("final_ore_industry_area", "u24"),
    ("final_oil_industry_area", "u24"),
    ("temp_generic_industry_count", "u24"),
    ("temp_farming_industry_count", "u24"),
    ("temp_forestry_industry_count", "u24"),
    ("temp_ore_industry_count", "u24"),
    ("temp_oil_industry_count", "u24"),
    ("final_generic_industry_count", "u24"),
    ("final_farming_industry_count", "u24"),
    ("final_forestry_industry_count", "u24"),
    ("final_ore_industry_count", "u24"),
    ("final_oil_industry_count", "u24"),
    ("temp_generic_industry_productivity", "u24"),
    ("temp_farming_industry_productivity", "u24"),
    ("temp_forestry_industry_productivity", "u24"),
    ("temp_ore_industry_productivity", "u24"),
    ("temp_oil_industry_productivity", "u24"),
    ("final_generic_industry_productivity", "u24"),
    ("final_farming_industry_productivity", "u24"),
    ("final_forestry_industry_productivity", "u24"),
    ("final_ore_industry_productivity", "u24"),
    ("final_oil_industry_productivity", "u24"),
]
GROUND_DATA = [
    ("temp_landvalue", "u32"),
    ("temp_coverage", "u32"),
    ("final_landvalue", "u16"),
    ("temp_pollution", "u32"),
    ("final_pollution", "u8"),
]
AGE_DATA = [
    ("temp_count", "u24"),
    ("final_count", "u24"),
]
EDUCATION_DATA = [
    ("temp_count", "u24"),
    ("temp_unemployed", "u24"),
    ("temp_homeless", "u24"),
    ("final_count", "u24"),
    ("final_unemployed", "u24"),
    ("final_homeless", "u24"),
    ("temp_eligible_workers", "u24"),
    ("final_eligible_workers", "u24"),
]
TOURIST_DATA = [
    ("temp_visits", "u24"),
    ("final_visits", "u24"),
    ("average_visits", "u24"),
    ("temp_count", "u24"),
    ("final_count", "u24"),
]
PRIVATE_DATA = [
    ("temp_home_or_work_count", "u24"),
    ("temp_empty_count", "u24"),
    ("temp_happiness", "u32"),
    ("temp_level", "u24"),
    ("final_home_or_work_count", "u24"),
    ("final_empty_count", "u24"),
    ("final_happiness", "u8"),
    ("final_level", "u8"),
    ("temp_level1", "u24"),
    ("temp_level2", "u24"),
    ("temp_level3", "u24"),
    ("temp_level4", "u24"),
    ("temp_level5", "u24"),
    ("final_level1", "u8"),
    ("final_level2", "u8"),
    ("final_level3", "u8"),
    ("final_level4", "u8"),
    ("final_level5", "u8"),
    ("temp_health", "u32"),
    ("final_health", "u8"),
    ("temp_building_area", "u24"),
    ("final_building_area", "u24"),
    ("temp_building_count", "u16"),
    ("temp_abandoned_count", "u16"),
    ("temp_burned_count", "u16"),
    ("final_building_count", "u16"),
    ("final_abandoned_count", "u16"),
    ("final_burned_count", "u16"),
    ("temp_alive_count", "u24"),
    ("final_alive_count", "u24"),
    ("temp_crime_rate", "u32"),
    ("final_crime_rate", "u8"),
    ("temp_collapsed_count", "u16"),
    ("final_collapsed_count", "u16"),
]
SPECIALIZATION_DATA = [
    ("temp_home_or_work_count", "u24"),
    ("temp_empty_count", "u24"),
    ("final_home_or_work_count", "u24"),
    ("final_empty_count", "u24"),
    ("temp_building_area", "u24"),
    ("final_building_area", "u24"),
    ("temp_alive_count", "u24"),
    ("final_alive_count", "u24"),
]
CONSUMPTION_DATA = [
    ("temp_electricity_consumption", "u24"),
    ("temp_water_consumption", "u24"),
    ("temp_sewage_accumulation", "u24"),
    ("temp_garbage_accumulation", "u24"),
    ("temp_income_accumulation", "u32"),
    ("temp_building_count", "u16"),
    ("temp_garbage_piles", "u24"),
    ("temp_water_pollution", "u24"),
    ("temp_dead_count", "u24"),
    ("temp_sick_count", "u24"),
    ("final_dead_count", "u24"),
    ("final_sick_count", "u24"),
    ("temp_export_amount", "u32"),
    ("temp_import_amount", "u32"),
    ("final_export_amount", "u32"),
    ("final_import_amount", "u32"),
    ("final_electricity_consumption", "u24"),
    ("final_water_consumption", "u24"),
    ("final_sewage_accumulation", "u24"),
    ("final_garbage_accumulation", "u24"),
    ("final_income_accumulation", "u32"),
    ("final_building_count", "u16"),
    ("final_garbage_piles", "u8"),
    ("final_water_pollution", "u8"),
    ("temp_heating_consumption", "u24"),
    ("final_heating_consumption", "u24"),
]
USAGE_DATA = [
    ("temp_electricity_usage", "u24"),
    ("temp_heating_usage", "u24"),
    ("temp_water_usage", "u24"),
    ("temp_sewage_usage", "u24"),
    ("final_electricity_usage", "u24"),
    ("final_heating_usage", "u24"),
    ("final_water_usage", "u24"),
    ("final_sewage_usage", "u24"),
]
RESOURCE_DATA = [
    ("temp_ore", "u32"),
    ("temp_oil", "u32"),
    ("temp_forestry", "u32"),
    ("temp_agricultural", "u32"),
    ("temp_goods", "u32"),
    ("final_ore", "u32"),
    ("final_oil", "u32"),
    ("final_forestry", "u32"),
    ("final_agricultural", "u32"),
    ("final_goods", "u32"),
    ("average_ore", "u32"),
    ("average_oil", "u32"),
    ("average_forestry", "u32"),
    ("average_agricultural", "u32"),
    ("average_goods", "u32"),
    ("temp_mail", "u32"),
    ("final_mail", "u32"),
    ("average_mail", "u32"),
    ("temp_fish", "u32"),
    ("final_fish", "u32"),
    ("average_fish", "u32"),
]
SUB_CULTURE_DATA = [
    ("temp_count", "u24"),
    ("temp_happiness", "u32"),
    ("final_count", "u24"),
    ("final_happiness", "u8"),
]
AREA_RESOURCE_DATA = [
    ("temp_consumption", "u32"),
    ("temp_production", "u32"),
    ("temp_buffer_amount", "u32"),
    ("temp_incoming_transfer", "u32"),
    ("temp_buffer_capacity", "u32"),
    ("final_consumption", "u32"),
    ("final_production", "u32"),
    ("final_buffer_amount", "u32"),
    ("final_incoming_transfer", "u32"),
    ("final_buffer_capacity", "u32"),
    ("temp_import", "u32"),
    ("temp_export", "u32"),
    ("final_import", "u32"),
    ("final_export", "u32"),
]
PARK_PRIVATE_DATA = [
    ("temp_child_count", "u24"),
    ("temp_teen_count", "u24"),
    ("temp_young_count", "u24"),
    ("temp_adult_count", "u24"),
    ("temp_senior_count", "u24"),
    ("temp_work_count", "u24"),
    ("temp_alive_work_count", "u24"),
    ("final_child_count", "u24"),
    ("final_teen_count", "u24"),
    ("final_young_count", "u24"),
    ("final_adult_count", "u24"),
    ("final_senior_count", "u24"),
    ("final_work_count", "u24"),
    ("final_alive_work_count", "u24"),
    ("zoned_squares", "u32"),
]
ACADEMIC_WORKS_DATA = [
    ("works_type1", "i32"),
    ("works_type2", "i32"),
    ("works_type3", "i32"),
    ("works_count", "i32"),
]


def read_struct(s, spec):
    out = {}
    for name, code in spec:
        out[name] = READ[code](s)
    return out


READ = {
    "u8": lambda s: s.u8(),
    "i8": lambda s: s.i8(),
    "bool": lambda s: s.bool(),
    "u16": lambda s: s.u16(),
    "i16": lambda s: s.i16(),
    "u24": lambda s: s.u24(),
    "i24": lambda s: s.i24(),
    "u32": lambda s: s.u32(),
    "i32": lambda s: s.i32(),
    "u64": lambda s: s.u64(),
    "i64": lambda s: s.i64(),
    "f32": lambda s: s.f32(),
}

# Bit positions of DistrictPolicies enums.
SPECIALIZATION = [
    "Forest",
    "Farming",
    "Oil",
    "Ore",
    "Leisure",
    "Tourist",
    "Organic",
    "Selfsufficient",
    "Hightech",
    "ResidentialWallToWall",
    "CommercialWallToWall",
    "OfficeWallToWall",
    "Financial",
]
SERVICES = [
    "PowerSaving",
    "WaterSaving",
    "SmokeDetectors",
    "RecreationBoost",
    "PetBan",
    "Recycling",
    "SmokingBan",
    "EducationBoost",
    "RecreationalUse",
    "FreeTransport",
    "SchoolsOut",
    "DoubleSentences",
    "ExtraInsulation",
    "NoElectricity",
    "OnlyElectricity",
    "HelicopterPriority",
    "PreferFerries",
    "HighTicketPrices",
    "EducationalBlimps",
    "RecyclePlastic",
    "PreferParks",
    "ParkMaintenanceBoost",
    "AutomatedSorting",
    "FreeWifi",
    "ForProfitEducation",
    "BookFair",
    "FishingLicense",
    "TouristTravelCard",
    "AlgaeBasedWaterFiltering",
]
TAXATION = [
    "TaxRaiseResLow",
    "TaxRaiseResHigh",
    "TaxRaiseComLow",
    "TaxRaiseComHigh",
    "TaxRaiseOffice",
    "TaxLowerResLow",
    "TaxLowerResHigh",
    "TaxLowerComLow",
    "TaxLowerComHigh",
    "TaxLowerOffice",
    "DontTaxLeisure",
]
CITY_PLANNING = [
    "SmallBusiness",
    "BigBusiness",
    "IndustrySpace",
    "HighTechHousing",
    "HighriseBan",
    "HeavyTrafficBan",
    "EncourageBiking",
    "BikeBan",
    "NoLoudNoises",
    "OldTown",
    "StuddedTires",
    "AntiSlip",
    "LightningRods",
    "FastRecovery",
    "NoRebuild",
    "VIPArea",
    "CombustionEngineBan",
    "ElectricCars",
    "FilterIndustrialWaste",
    "BoostConnections",
    "WorkersUnion",
    "AutomatedToll",
    "Industry4point0",
    "SustainableFishing",
    "DolphinSafeTuna",
    "AirplaneTours",
    "FitnessIncentive",
]
SPECIAL = ["Reserved"]
EVENT = [
    "SubsidizedYouth",
    "ComeOneComeAll",
    "MatchSecurity",
    "BandAdvertisement",
    "PremiumStudio",
    "CityParkAd",
    "AmusementParkAd",
    "NatureReserveAd",
    "ZooAd",
    "Team01Ad",
    "Team02Ad",
    "Team03Ad",
    "Team04Ad",
    "Team05Ad",
    "Team06Ad",
    "Team07Ad",
    "SponsorAd",
    "NoNeedForEarplugs",
    "ZeroWasteParade",
    "RaceAdvertisement",
]
PARK_POLICY = [
    "AnimalEthics",
    "ParkAdvertisement",
    "MainPark",
    "FireworksBan",
    "FireworksBoost",
    "NightTours",
    "EvenMoreFun",
    "NatureRecycle",
    "ImprovedLogistics",
    "WorkSafety",
    "AdvancedAutomation",
    "StudentHealthcare",
    "FreeLunch",
    "VisitingScholars",
    "UniversalEducation",
    "FreeFanMerchandise",
    "VarsitySportsAds",
    "SponsorshipDeal",
    "HotelDiscounts",
    "GreatMaintenance",
    "CarRentals",
    "SlowDriving",
    "SugarBan",
    "StreetMusic",
    "ForceServicePoint",
]

# The policy Bool array: 32 bits x 128 items per mask, bit-major, in this order.
DISTRICT_MASKS = [
    ("specialization", SPECIALIZATION),
    ("services", SERVICES),
    ("taxation", TAXATION),
    ("city_planning", CITY_PLANNING),
    ("special", SPECIAL),
    ("specialization_effect", SPECIALIZATION),
    ("services_effect", SERVICES),
    ("taxation_effect", TAXATION),
    ("city_planning_effect", CITY_PLANNING),
    ("special_effect", SPECIAL),
    ("event", EVENT),
    ("event_effect", EVENT),
]
PARK_MASKS = [
    ("event", EVENT),
    ("park", PARK_POLICY),
    ("park_effect", PARK_POLICY),
    ("specialization", SPECIALIZATION),
]

PARK_TYPES = [
    "None",
    "Generic",
    "AmusementPark",
    "Zoo",
    "NatureReserve",
    "Industry",
    "Farming",
    "Forestry",
    "Ore",
    "Oil",
    "GenericCampus",
    "TradeSchool",
    "LiberalArts",
    "University",
    "Airport",
    "PedestrianZone",
]
INDUSTRY_PARKS = {5, 6, 7, 8, 9}
CAMPUS_PARKS = {10, 11, 12, 13}
AIRPORT_PARK = 14
PEDESTRIAN_PARK = 15

# Per-district struct sequence after the random seed (District loop of Serialize).
DISTRICT_LAYOUT = (
    [("population", POPULATION_DATA), ("final_happiness", "u8"), ("final_crime_rate", "u8")]
    + [
        (n, AGE_DATA)
        for n in (
            "child",
            "teen",
            "young",
            "adult",
            "senior",
            "child_health",
            "child_sick",
            "senior_health",
            "senior_sick",
            "age_at_death",
            "dead_seniors",
        )
    ]
    + [("last_average_lifespan", "i8")]
    + [(n, AGE_DATA) for n in ("elementary_eligible", "highschool_eligible", "university_eligible")]
    + [(n, PRIVATE_DATA) for n in ("residential", "commercial", "visitor", "industrial", "office", "player")]
    + [
        (n, SPECIALIZATION_DATA)
        for n in ("farming", "forestry", "ore", "oil", "leisure", "tourist", "organic", "selfsufficient", "hightech")
    ]
    + [(n, AGE_DATA) for n in ("birth", "death")]
    + [(n, EDUCATION_DATA) for n in ("educated0", "educated1", "educated2", "educated3")]
    + [(n, AGE_DATA) for n in ("education1", "education2", "education3", "student1", "student2", "student3")]
    + [("production", PRODUCTION_DATA)]
    + [
        (n, CONSUMPTION_DATA)
        for n in (
            "player_consumption",
            "residential_consumption",
            "commercial_consumption",
            "industrial_consumption",
            "office_consumption",
        )
    ]
    + [("usage", USAGE_DATA), ("ground", GROUND_DATA), ("import", RESOURCE_DATA), ("export", RESOURCE_DATA)]
    + [(n, TOURIST_DATA) for n in ("tourist1", "tourist2", "tourist3")]
    + [(n, SUB_CULTURE_DATA) for n in ("hippie", "hipster", "redneck", "gangsta")]
)

PARK_HEADER = [
    ("random_seed", "u64"),
    ("main_gate", "u16"),
    ("condition", "u16"),
    ("temp_entertainment", "u16"),
    ("final_entertainment", "u16"),
    ("temp_happiness", "u32"),
    ("final_happiness", "u32"),
    ("temp_max_happiness", "u32"),
    ("final_max_happiness", "u32"),
    ("last_visitor_count", "u32"),
    ("total_visitor_count", "u32"),
    ("temp_ticket_income", "u32"),
    ("final_ticket_income", "u32"),
    ("ticket_price", "u16"),
    ("temp_resident_count", "u16"),
    ("final_resident_count", "u16"),
    ("temp_tourist_count", "u16"),
    ("final_tourist_count", "u16"),
    ("park_type", "u8"),
    ("park_level", "u8"),
    ("random_gate", "u16"),
    ("temp_gate_count", "u8"),
    ("final_gate_count", "u8"),
    ("temp_visitor_capacity", "u16"),
    ("final_visitor_capacity", "u16"),
    ("temp_main_capacity", "u16"),
    ("final_main_capacity", "u16"),
    ("day_night_count", "u8"),
    ("temp_attractiveness", "u16"),
    ("final_attractiveness", "u16"),
    ("area_factor", "u8"),
    ("temp_work_efficiency_delta", "u8"),
    ("temp_storage_delta", "u8"),
    ("final_work_efficiency_delta", "u8"),
    ("final_storage_delta", "u8"),
    ("total_production_amount", "u64"),
    ("temp_worker_count", "u16"),
    ("final_worker_count", "u16"),
]
INDUSTRY_RESOURCES = [
    "grain",
    "logs",
    "ore",
    "oil",
    "animal_products",
    "flours",
    "paper",
    "planed_timber",
    "petroleum",
    "plastics",
    "glass",
    "metals",
    "luxury_products",
]


def read_layout(s, layout):
    out = {}
    for name, spec in layout:
        out[name] = READ[spec](s) if isinstance(spec, str) else read_struct(s, spec)
    return out


def hotel_data(s):
    out = read_struct(
        s, [("temp_visitors", "u24"), ("final_visitors", "u24"), ("temp_profit", "u24"), ("final_profit", "u24")]
    )
    out["color"] = tuple(s.u8() for _ in range(4))
    out.update(
        read_struct(
            s, [("temp_popularity_sum", "u24"), ("temp_hotel_count", "u24"), ("final_average_popularity", "u24")]
        )
    )
    out["chain_name"] = s.unique_string()
    out["chain"] = s.i8()
    out.update(read_struct(s, [("temp_bonus", "u24"), ("final_bonus", "u24")]))
    return out


def year_report(s):
    """DistrictYearReportData.Serialize."""
    read_struct(
        s,
        [
            ("student_count", "i32"),
            ("campus_attractiveness", "i32"),
            ("reputation_level", "i8"),
            ("grant_type", "i8"),
            ("grant_work_index", "i16"),
        ],
    )
    read_struct(s, ACADEMIC_WORKS_DATA)
    s.u64()  # total prize money
    s.encoded("u64", 5)  # tickets income
    s.encoded("u64", 5)  # winnings income
    s.encoded("u8", 5)  # matches won
    s.encoded("u8", 5)  # matches lost
    s.encoded("u8", 5)  # matches cancelled
    s.encoded_bool(5)  # trophies
    s.i8()  # toga party count
    s.i64(), s.i64(), s.i64()  # toga party seeds
    s.unique_string()  # milestone unlocked
    s.i16()  # total works


def park(s, index):
    out = read_struct(s, PARK_HEADER)
    kind = out["park_type"]
    out["park_type_name"] = PARK_TYPES[kind] if kind < len(PARK_TYPES) else str(kind)
    if kind in INDUSTRY_PARKS:
        out["resources"] = {n: read_struct(s, AREA_RESOURCE_DATA) for n in INDUSTRY_RESOURCES}
    if kind in CAMPUS_PARKS or index == 0:
        out["student_count"] = s.u16()
        out["student_capacity"] = s.u16()
        out["campus_attractiveness"] = s.u16()
        read_struct(s, ACADEMIC_WORKS_DATA)
        for _ in range(3 + 10):  # current, last, second-last year reports; 10-report ledger
            year_report(s)
        s.bool(), s.u8(), s.u8(), s.i16(), s.u8(), s.f32()
        s.encoded("i64", 25)  # coach hire times (DateTime ticks)
        s.u8(), s.i16()
        s.encoded("u8", 3)  # varsity colour
        s.i16(), s.i16(), s.i16(), s.u16()
        s.encoded_bool(5)  # away matches done
        out["campus_building_count"] = s.i16()
    if kind == AIRPORT_PARK:
        s.f32()
        out["total_incoming_passengers"] = s.u32()
        out["total_outgoing_passengers"] = s.u32()
        s.bool(), s.bool(), s.bool()
        s.u32(), s.u32(), s.u32(), s.u32()
    if kind == PEDESTRIAN_PARK:
        reasons = s.i32()
        if not 0 <= reasons <= 64:
            raise FormatError(f"implausible pedestrian reason count {reasons}")
        for _ in range(2):  # material requests, then suggestions
            for _ in range(reasons):
                s.u8()
                count = s.i32()
                if count < 0:
                    raise FormatError("negative pedestrian material list")
                s.encoded("u16", count)
        s.encoded("u16", out["final_gate_count"])
        s.encoded("u16", out["temp_gate_count"])
        for _ in range(s.i8()):
            s.i64(), s.u16()
        for _ in range(4):  # residential, commercial, industrial, office
            read_struct(s, PARK_PRIVATE_DATA)
        s.i8(), s.bool(), s.u32(), s.u32()
        for _ in range(reasons):
            s.u8(), s.u32(), s.u32(), s.u32(), s.u32()
        s.bool(), s.bool()
    return out


def bits_to_names(mask, names):
    return [names[b] if b < len(names) else f"bit{b}" for b in range(32) if mask >> b & 1]


def unpack_masks(bools, count, masks):
    """Bool array laid out [mask][bit][item] -> {mask name: uint32 per item}."""
    cube = bools.reshape(len(masks), 32, count).astype(np.uint64)
    weights = (np.uint64(1) << np.arange(32, dtype=np.uint64))[None, :, None]
    values = (cube * weights).sum(axis=1).astype(np.uint32)
    return {name: values[i] for i, (name, _) in enumerate(masks)}


def district(s):
    out = {"airline_name": s.unique_string(), "auto_opened_airport_panel": s.bool()}
    flags = s.encoded("u32", DISTRICT_COUNT)
    park_flags = s.encoded("u32", PARK_COUNT)
    n_bools = 32 * (len(DISTRICT_MASKS) * DISTRICT_COUNT + len(PARK_MASKS) * PARK_COUNT)
    bools = s.encoded_bool(n_bools)
    split = 32 * len(DISTRICT_MASKS) * DISTRICT_COUNT
    d_masks = unpack_masks(bools[:split], DISTRICT_COUNT, DISTRICT_MASKS)
    p_masks = unpack_masks(bools[split:], PARK_COUNT, PARK_MASKS)
    mask_names = dict(DISTRICT_MASKS)
    park_mask_names = dict(PARK_MASKS)

    districts = []
    for i in range(DISTRICT_COUNT):
        if flags[i] == 0:
            continue
        d = {"index": i, "flags": int(flags[i]), "random_seed": s.u64()}
        d.update(read_layout(s, DISTRICT_LAYOUT))
        if i == 0:
            d["hotel"] = hotel_data(s)
        d["style"] = s.unique_string() if s.bool() else None
        d["library_visitors"] = read_struct(s, AGE_DATA)
        d["airline"] = s.i8()
        d["population_count"] = d["population"]["final_count"]
        d["policies"] = {name: bits_to_names(int(d_masks[name][i]), mask_names[name]) for name, _ in DISTRICT_MASKS}
        districts.append(d)

    parks = []
    for i in range(PARK_COUNT):
        if park_flags[i] == 0:
            continue
        p = {"index": i, "flags": int(park_flags[i])}
        p.update(park(s, i))
        p["policies"] = {name: bits_to_names(int(p_masks[name][i]), park_mask_names[name]) for name, _ in PARK_MASKS}
        parks.append(p)

    cells = DISTRICT_GRID * DISTRICT_GRID
    grid = s.encoded("u8", 8 * cells).reshape(8, DISTRICT_GRID, DISTRICT_GRID)
    park_grid = s.encoded("u8", 8 * cells).reshape(8, DISTRICT_GRID, DISTRICT_GRID)
    objects(s, 19)
    out["next_policy_message_frames"] = (s.u32(), s.u32())
    out["district_policies_set"] = s.u32()
    out.update(
        districts=districts,
        parks=parks,
        # [z, x]: up to four districts per cell, sorted so district1 has the
        # largest alpha; DistrictManager.GetDistrict reads district1.
        grid_districts=grid[:4],
        grid_alpha=grid[4:],
        park_grid_districts=park_grid[:4],
        park_grid_alpha=park_grid[4:],
        city=city_headline(districts[0]) if districts and districts[0]["index"] == 0 else None,
    )
    return out


def cell_centre(x, z):
    """World X/Z (metres) of district-grid cell (x, z); GetDistrict maps world
    position p to cell floor(p / 19.2 + 256) on each axis."""
    return ((x - 256 + 0.5) * DISTRICT_CELL, (z - 256 + 0.5) * DISTRICT_CELL)


def city_headline(d):
    """City-wide final counts from district 0."""

    def pick(name, field="final_count"):
        return d[name][field]

    educated = [d[f"educated{k}"] for k in range(4)]
    return {
        "population": pick("population"),
        "households": d["residential"]["final_home_or_work_count"],
        "empty_households": d["residential"]["final_empty_count"],
        "jobs": sum(d[n]["final_home_or_work_count"] for n in ("commercial", "industrial", "office", "player")),
        # Every resident counted once by education level (sums to population).
        "residents_by_education": [e["final_count"] for e in educated],
        "unemployed": sum(e["final_unemployed"] for e in educated),
        "eligible_workers": sum(e["final_eligible_workers"] for e in educated),
        "tourists": sum(d[f"tourist{k}"]["final_count"] for k in (1, 2, 3)),
        "children": pick("child"),
        "teens": pick("teen"),
        "young_adults": pick("young"),
        "adults": pick("adult"),
        "seniors": pick("senior"),
        "students": {k: d[f"student{k}"]["final_count"] for k in (1, 2, 3)},
        "happiness": d["final_happiness"],
        "crime_rate": d["final_crime_rate"],
        "land_value": d["ground"]["final_landvalue"],
        "building_counts": {
            n: d[n]["final_building_count"] for n in ("residential", "commercial", "industrial", "office", "player")
        },
        "abandoned": {n: d[n]["final_abandoned_count"] for n in ("residential", "commercial", "industrial", "office")},
        "electricity": {
            "capacity": d["production"]["final_electricity_capacity"],
            "consumption": sum(d[c]["final_electricity_consumption"] for c in CONSUMERS),
        },
        "water": {
            "capacity": d["production"]["final_water_capacity"],
            "consumption": sum(d[c]["final_water_consumption"] for c in CONSUMERS),
        },
        "sewage": {
            "capacity": d["production"]["final_sewage_capacity"],
            "accumulation": sum(d[c]["final_sewage_accumulation"] for c in CONSUMERS),
        },
    }


CONSUMERS = (
    "player_consumption",
    "residential_consumption",
    "commercial_consumption",
    "industrial_consumption",
    "office_consumption",
)


# EconomyManager -------------------------------------------------------------------

PUBLIC_SERVICES = [
    "Road",
    "Electricity",
    "Water",
    "Beautification",
    "Garbage",
    "HealthCare",
    "PoliceDepartment",
    "Education",
    "Monument",
    "FireDepartment",
    "PublicTransport",
    "Disaster",
    "PlayerIndustry",
    "PlayerEducation",
    "Museums",
    "VarsitySports",
    "Fishing",
    "ServicePoint",
    "Hotel",
    "Race",
]
PUBLIC_SUB_SERVICES = [
    "PublicTransportBus",
    "PublicTransportMetro",
    "PublicTransportTrain",
    "PublicTransportShip",
    "PublicTransportPlane",
    "PublicTransportTaxi",
    "PublicTransportTram",
    "PublicTransportMonorail",
    "PublicTransportCableCar",
    "BeautificationParks",
    "PublicTransportTours",
    "PublicTransportPost",
    "PlayerIndustryForestry",
    "PlayerIndustryFarming",
    "PlayerIndustryOil",
    "PlayerIndustryOre",
    "PlayerEducationTradeSchool",
    "PlayerEducationLiberalArts",
    "PlayerEducationUniversity",
    "PublicTransportTrolleybus",
    "PoliceDepartmentBank",
]
BUDGET_NAMES = PUBLIC_SERVICES + PUBLIC_SUB_SERVICES + ["unused41"]

# EconomyManager.PrivateClassIndex(service, subService, Level.None) = (8 + sub) * 5.
TAX_INDEX = {
    "residential_low": 40,
    "residential_high": 45,
    "commercial_low": 50,
    "commercial_high": 55,
    "industrial": 60,
    "office": 95,
}


def economy(s):
    tax = s.encoded("u8", 140)
    budgets = s.encoded("u8", 2 * 42).reshape(42, 2)
    income = s.encoded("i64", 3094 + 20)
    expenses = s.encoded("i64", 3094 + 20 + 20 + 20)
    loans = []
    for _ in range(3):
        loan = read_struct(
            s,
            [
                ("amount_taken", "i32"),
                ("amount_left", "i32"),
                ("interest_rate", "i16"),
                ("length", "i16"),
                ("interest_paid", "i32"),
            ],
        )
        if loan["amount_taken"]:
            loans.append(loan)
    out = read_struct(
        s,
        [
            ("start_money", "i64"),
            ("cash_amount", "i64"),
            ("cash_delta", "i64"),
            ("last_cash_amount", "i64"),
            ("last_cash_delta", "i64"),
            ("tax_multiplier", "i16"),
            ("bailout_accepted", "i16"),
            ("last_bailout_frame", "u32"),
        ],
    )
    objects(s, 2)
    out["investments"] = investments(s)
    total_income = income[3094:]
    total_expenses = expenses[3094 + 40 :]
    out.update(
        tax_rates_raw=tax,
        tax_rates={k: int(tax[i]) for k, i in TAX_INDEX.items()},
        budgets={BUDGET_NAMES[i]: (int(budgets[i, 0]), int(budgets[i, 1])) for i in range(42)},
        loans=loans,
        # Money is stored in 1/100 units; the in-game display divides by 100.
        # Under the built-in Unlimited Money mod, cash runs negative and
        # m_lastCashAmount is Int64.MaxValue; the panel then shows infinity.
        cash=out["cash_amount"] / 100,
        last_cash=out["last_cash_amount"] / 100,
        # GetIncomeAndExpenses sums the 16 finished slots of the rolling history.
        weekly_income=int(total_income[:16].sum()) / 100,
        weekly_expenses=int(total_expenses[:16].sum()) / 100,
        income_by_class=income[:3094].reshape(182, 17),
        expenses_by_class=expenses[:3094].reshape(182, 17),
        loan_expenses=expenses[3094:3114],
        policy_expenses=expenses[3114:3134],
    )
    return out


def investments(s):
    out = read_struct(
        s,
        [
            ("last_updated_day", "i16"),
            ("money_earned", "i32"),
            ("last_updated_month", "i16"),
            ("temp_monthly_earned", "i32"),
            ("final_monthly_earned", "i32"),
            ("temp_cash_collecting", "i32"),
            ("final_cash_collecting", "i32"),
            ("temp_spend", "i32"),
            ("final_spend", "i32"),
            ("last_buy_ticks", "i64"),
            ("last_sell_ticks", "i64"),
            ("all_in", "bool"),
        ],
    )
    objects(s, 3)
    flags = s.encoded("u16", INVESTMENT_COUNT - 1)
    live = int(np.count_nonzero(flags))
    for _ in range(live):
        count = s.i16()
        if count < 0:
            raise FormatError("negative investment history length")
        s.encoded("f32", count)
    owned = [read_struct(s, [("player_spent", "i32"), ("shares", "u32"), ("base_value", "f32")]) for _ in range(live)]
    s.take(8 * live)  # requirement-missing dates
    s.take(6 * live)  # state (i16), random influence (f32)
    info, names = prefab_block(s, live)
    out["held"] = [dict(o, prefab=names[i]) for o, i in zip(owned, info)]
    return out


# TransportManager -------------------------------------------------------------------

LINE_FLAGS = {
    1: "Created",
    2: "Deleted",
    4: "Complete",
    8: "Temporary",
    0x10: "Hidden",
    0x20: "Selected",
    0x40: "Invalid",
    0x80: "CompleteSet",
    0x100: "CustomColor",
    0x200: "CustomName",
    0x1000: "DisabledDay",
    0x2000: "DisabledNight",
    0x10000: "Highlighted",
}
PASSENGER_GROUPS = ["resident", "tourist", "child", "teen", "young", "adult", "senior", "car_owning"]
LINE_RECORD = np.dtype(
    [
        ("line_number", ">u2"),
        ("stops", ">u2"),
        ("color", "u1", 3),
        ("building", ">u2"),
        ("budget", ">u2"),
        ("total_length", ">f4"),
        ("average_interval", "u1"),
        ("ticket_price", ">u2"),
        ("passengers", ">u1", 72),
    ]
)
LINE_NUMBER_SLOTS = 17


def passengers(raw):
    """TransportPassengerData: 8 groups of (temp, final, average) UInt24."""
    values = raw.reshape(8, 3, 3).astype(np.int64)
    counts = (values[..., 0] << 16) | (values[..., 1] << 8) | values[..., 2]
    return {g: {"temp": int(c[0]), "final": int(c[1]), "average": int(c[2])} for g, c in zip(PASSENGER_GROUPS, counts)}


def transport(s):
    flags = s.encoded("u32", LINE_COUNT - 1)
    ids = np.flatnonzero(flags) + 1
    milestones = s.u16()
    info, names = prefab_block(s, len(ids) + milestones)
    objects(s, milestones)
    line_numbers = [s.u16() for _ in range(LINE_NUMBER_SLOTS)]
    raw = np.frombuffer(s.take(LINE_RECORD.itemsize * len(ids)), dtype=LINE_RECORD)
    totals = np.frombuffer(s.take(72 * LINE_NUMBER_SLOTS), dtype=np.uint8).reshape(LINE_NUMBER_SLOTS, 72)
    objects(s, 7)
    vehicle_selection = [(s.i16(), s.shared_string()) for _ in range(s.i16())]
    lines = []
    for k, line_id in enumerate(ids):
        rec = raw[k]
        f = int(flags[line_id - 1])
        lines.append(
            {
                "index": int(line_id),
                "flags": f,
                "flag_names": [n for b, n in LINE_FLAGS.items() if f & b],
                "prefab": names[info[k]],
                "line_number": int(rec["line_number"]),
                "first_stop": int(rec["stops"]),
                "color": tuple(int(c) for c in rec["color"]),
                "building": int(rec["building"]),
                "budget": int(rec["budget"]),
                "total_length": float(rec["total_length"]),
                "average_interval": int(rec["average_interval"]),
                "ticket_price": int(rec["ticket_price"]),
                "passengers": passengers(rec["passengers"]),
            }
        )
    return {
        "lines": lines,
        "next_line_numbers": line_numbers,
        "passengers_by_type": [passengers(row) for row in totals],
        "vehicle_selection": vehicle_selection,
    }


def line_stops(line, net):
    """Stop node ids of a transport line, following TransportLine.GetNextStop
    over the decoded NetManager: the segment leaving a stop (m_startNode == stop)
    leads to the next stop."""
    index = {int(n): i for i, n in enumerate(net["node_ids"])}
    seg_index = {int(g): i for i, g in enumerate(net["segment_ids"])}
    stops, stop = [], line["first_stop"]
    while stop and stop in index and len(stops) <= 4096:
        stops.append(stop)
        nxt = 0
        for seg in net["node_segments"][index[stop]]:
            j = seg_index.get(seg)
            if j is not None and int(net["segment_start_node"][j]) == stop:
                nxt = int(net["segment_end_node"][j])
                break
        if nxt == line["first_stop"]:
            break
        stop = nxt
    return stops


PARSERS = {
    "DistrictManager": district,
    "EconomyManager": economy,
    "TransportManager": transport,
}
