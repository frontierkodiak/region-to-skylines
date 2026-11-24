// Default-plan potential, mirrored in tools/map-factory/place_rules.py.
export const PLACE_RULES = { land_yes_fraction: 0.57, ore_target: 0.052, oil_target: 0.027, fertile_target: 0.034 };
const rounded = x => Math.floor(x * 1e6 + 0.5) / 1e6;
export function measurePlace(ground, depth, cover=null) {
  const n=1081;
  if(ground?.length!==n*n||depth?.length!==n*n)return null;
  const screened=cover?.length===271*271;
  let count=0,dry=0,flat=0,resource=0,farm=0;
  for(let r=240;r<840;r+=4)for(let c=240;c<840;c+=4){
    const i=r*n+c;let wet=Infinity;
    for(let y=r;y<r+4;y++)for(let x=c;x<c+4;x++)wet=Math.min(wet,depth[y*n+x]);
    const slope=Math.hypot((ground[i+1]-ground[i-1])/32,(ground[i+n]-ground[i-n])/32);
    if(!Number.isFinite(wet)||wet<0||!Number.isFinite(slope))return null;
    count++;if(wet>=0.25)continue;dry++;
    if(slope<0.15)flat++;
    if(r>=480&&r<600&&c>=480&&c<600)continue;
    resource++;if(slope<=0.12&&!(screened&&cover[(r/4)*271+c/4]===50))farm++;
  }
  return {buildable_fraction:rounded(flat/count),dry_fraction:rounded(dry/count),resource_fraction:rounded(resource/count),farm_fraction:rounded(farm/count),urban_screened:screened};
}
export function placeDecisions(metrics,evidence,footprint,rules=PLACE_RULES) {
  const valid=metrics&&['buildable_fraction','dry_fraction','resource_fraction','farm_fraction'].every(k=>Number.isFinite(metrics[k])&&metrics[k]>=0&&metrics[k]<=1);
  const fraction=valid?metrics.buildable_fraction:null;
  const land={level:!valid?'maybe':fraction===0?'no':fraction>=rules.land_yes_fraction?'yes':'maybe',reason:valid?'stock_relative_buildable_land':'place_data_unavailable',fraction,stock_threshold:rules.land_yes_fraction};
  const details={};
  for(const kind of ['ore','oil','fertile']){
    const share=valid?metrics[kind==='fertile'?'farm_fraction':'resource_fraction']:null,target=rules[kind+'_target'];
    const records=kind!=='fertile'&&(evidence?.deposits?.[kind]?.central??0)>0;
    details[kind]={level:!valid?'maybe':share===0?'no':share>=target||records?'yes':'maybe',reason:records?'recorded_resource_and_dry_land':'balanced_plan_space',eligible_fraction:share,target_fraction:target};
  }
  const noLand=valid&&metrics.dry_fraction===0;
  const cover=evidence?.landcover?.status==='available'&&evidence.landcover.coverage_of_central_land>=0.5&&Number.isFinite(evidence.vegetation?.tree_suitability);
  const support=noLand?0:cover?evidence.vegetation.tree_suitability:null;
  details.forest={level:noLand?'no':!cover?'maybe':support>0?'yes':'no',reason:noLand?'no_dry_land':cover?'existing_forest_resource_support':'forest_evidence_unavailable',suitability:support};
  const values=Object.values(details).map(d=>d.level);
  const resources={level:values.includes('yes')?'yes':values.every(v=>v==='no')?'no':'maybe',reason:'default_resource_plan',details};
  const candidate=footprint?.footprint==='candidate',miss=footprint?.reason==='no_footprint_in_finite_search';
  const start={level:candidate?'yes':miss?'no':'maybe',reason:candidate?'dry_flat_384m_footprint':miss?'no_sampled_384m_footprint':'footprint_data_unavailable',footprint_m:[384,384],hookup:'unknown',search:'central_1920m_square_64m_centers'};
  return {buildable:land,resources,start_footprint:start};
}
