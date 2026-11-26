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
  if(result.reason==='vegetation_suitability_candidate')return `Trees on ${pct(e.vegetation.tree_cover_share_of_central_land)} of the central land.`;
  if(result.reason==='tree_support_below_candidate_threshold')return `Tree score ${number(e.vegetation.tree_suitability)}; needs ${number(e.vegetation.candidate_min)}.`;
  if(result.reason==='fertile_land_suitability_candidate')return `Farmland score ${number(e.fertility.suitability)}; cropland ${pct(e.fertility.crop_share_of_central_land)} today.`;
  if(result.reason==='fertile_cover_below_candidate_threshold')return `Farmland score ${number(e.fertility.suitability)}; needs ${number(e.fertility.candidate_min)}.`;
  return null;
}
export const waterDetail = result => result?.opportunity==='candidate'?'Mapped shoreline. Not tested in game.':'Not tested in game.';
export const footprintDetail = result => result?.footprint==='candidate'?'A dry, gentle 384 × 384 m patch.':'No dry, gentle 384 × 384 m patch.';
export function capabilityReason(id,result) {
  if(result.reason==='mapped_water_width')return `Mapped channel ${result.width_m} m wide; ships need ${result.threshold_m} m.`;
  if(result.reason==='mapped_edge_crossing')return id==='road'?'A motorway or trunk road crosses the edge.':'A mainline railway crosses the edge.';
  if(result.reason==='no_mapped_edge_crossing')return id==='road'?'No motorway or trunk road crosses the edge.':'No mainline railway crosses the edge.';
  if(result.reason==='near_map_edge')return 'A mapped line stops just short of the edge.';
  if(result.reason==='no_edge_waterway')return 'No connected mapped water reaches the edge.';
  if(id==='air')return 'Planes arrive from two map edges.';
  if(id==='water')return waterDetail(result);
  return planDetail(result)??placeDetail(result)??'Data unavailable.';
}
export const stockLabels = {terrain_relief_m:'Relief',terrain_roughness_percent:'Roughness',central_terrain_diversity_m:'Height range'};
export const stockReason = (label,value,p25,p75)=>`${label} ${value}. Most stock maps: ${p25} to ${p75}.`;
