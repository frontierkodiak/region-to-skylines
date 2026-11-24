// Species-level leaf habits, checked against NC State Extension on 2026-11-23.
// These classify the named taxon, not its abundance or the habit of its genus.
const DECIDUOUS = ["Acer campestre", "Acer platanoides", "Acer rubrum", "Fraxinus pennsylvanica",
  "Gleditsia triacanthos", "Liquidambar styraciflua", "Pyrus calleryana", "Quercus bicolor",
  "Quercus palustris", "Quercus rubra", "Syringa reticulata", "Tilia cordata", "Zelkova serrata"];
export const SPECIES_TRAITS = Object.fromEntries([
  ...DECIDUOUS.map((name) => [name, "broadleaf_deciduous"]),
  ["Magnolia grandiflora", "broadleaf_evergreen"],
]);
export const TRAIT_SOURCES = Object.keys(SPECIES_TRAITS).map((species) => ({ species,
  growth_form: SPECIES_TRAITS[species], source: `https://plants.ces.ncsu.edu/plants/${species.toLowerCase().replaceAll(" ", "-")}/`, checked: "2026-11-23" }));
export function speciesGrowthForm(name) {
  const binomial = String(name ?? "").trim().split(/\s+/).slice(0, 2).join(" ");
  return SPECIES_TRAITS[binomial] ?? null;
}
