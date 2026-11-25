// Player-facing capability and chart copy. The PR also lists the page's
// static labels, export messages and installation instructions for copy review.
export const labels = {road:'Road',rail:'Rail',ship:'Ship',air:'Air',water:'Water',buildable:'Land',resources:'Resources',trees:'Trees'};
export const states = {yes:'Yes',no:'No',maybe:'Maybe',promised:'Yes',likely:'Maybe',not_possible_here:'No',unknown:'Unknown',loading:'Loading'};
export const pct = x => Number.isFinite(x) ? `${Math.round(x*100)}%` : '?';
const number = x => Number.isFinite(x) ? String(Number(x.toFixed(2))) : '?';
export function planDetail(result) {
  if(result?.reason==='stock_relative_buildable_land') return `${pct(result.fraction)} dry, gentle ground in the central tiles.`;
  if(result?.reason!=='default_resource_plan')return null;
  return Object.entries(result.details).map(([key,value])=>`${key==='fertile'?'Farm':key[0].toUpperCase()+key.slice(1)} ${states[value.level].toLowerCase()}`).join(' · ')+'.';
}
export function placeDetail(result) {
  const e=result?.evidence;if(!e)return null;
  if(result.reason==='vegetation_suitability_candidate')return `Tree cover on ${pct(e.vegetation.tree_cover_share_of_central_land)} of central land.`;
  if(result.reason==='tree_support_below_candidate_threshold')return `Tree support ${number(e.vegetation.tree_suitability)}, below ${number(e.vegetation.candidate_min)}.`;
  if(result.reason==='fertile_land_suitability_candidate')return `Fertile suitability ${number(e.fertility.suitability)}, cropland ${pct(e.fertility.crop_share_of_central_land)}.`;
  if(result.reason==='fertile_cover_below_candidate_threshold')return `Fertile suitability ${number(e.fertility.suitability)}, below ${number(e.fertility.candidate_min)}.`;
  return null;
}
export const waterDetail = result => result?.opportunity==='candidate'?'Mapped wet shore. Water stability is untested.':'Water stability is untested.';
export const footprintDetail = result => result?.footprint==='candidate'?'384 × 384 m dry, gentle patch.':'No sampled 384 × 384 m patch.';
export function capabilityReason(id,result) {
  if(result.reason==='mapped_water_width')return `Mapped corridor ${result.width_m} m. Needs ${result.threshold_m} m, with ${result.margin_m} m margin.`;
  if(result.reason==='mapped_edge_crossing')return id==='road'?'A motorway or trunk road crosses the edge.':'A mainline railway crosses the edge.';
  if(result.reason==='no_mapped_edge_crossing')return id==='road'?'No motorway or trunk road crosses the edge.':'No mainline railway crosses the edge.';
  if(result.reason==='near_map_edge')return 'A mapped line ends within 32 m of the edge.';
  if(result.reason==='no_edge_waterway')return 'No connected mapped water reaches the edge.';
  if(id==='air')return 'The exporter adds two plane entries.';
  if(id==='water')return waterDetail(result);
  return planDetail(result)??placeDetail(result)??'Data unavailable.';
}
export const stockLabels = {terrain_relief_m:'Relief',terrain_roughness_percent:'Roughness',central_terrain_diversity_m:'Height range'};
export const stockReason = (label,value,p25,p75)=>`${label} ${value}. Middle half of stock maps ${p25} to ${p75}.`;
