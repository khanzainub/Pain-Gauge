/* One dated routine shared by every pain location; carried forward until changed. */
(()=>{
'use strict';
const keys=['foodHabit','dietPatterns','dietNotes','medicationCategories','medication','medicationsTaken','medicationsSkipped','sleepHours','sleepQuality','mood','wellbeingNotes','periodStatus','periodStart','periodNotes'];
const pick=p=>Object.fromEntries(keys.map(k=>[k,p[k]??(['dietPatterns','medicationCategories'].includes(k)?[]:'')]));
function saved(){try{return JSON.parse(localStorage.getItem(PROFILE)||'{}');}catch{return {};}}
function days(p=saved()){
 const result={};
 // Import older diaries once, choosing the latest saved routine for each day.
 for(const e of [...entries()].sort((a,b)=>String(a.updatedAt||a.createdAt||'').localeCompare(String(b.updatedAt||b.createdAt||''))))if(e.date)result[e.date]=pick(e);
 return {...result,...p.dailyConditions};
}
function forDate(date){const p=saved(),all=days(p),prior=Object.keys(all).filter(d=>d<=date).sort().pop();return prior?pick(all[prior]):Object.keys(all).length?pick({}):pick(p);}
function load(date){setProfile({...saved(),...forDate(date)});window.updatePainGaugeMood?.();}
function commit(profile,date){
 if(!date||date>today())return {...profile,dailyConditions:days()};
 const all=days(),routine=pick(profile);all[date]=routine;
 const latest=Object.keys(all).sort().pop();
 const result={...profile,...all[latest],dailyConditions:all};
 // Keep the entry snapshots used by charts, CSV and statistics consistent for this date.
 const rows=entries();let changed=false;
 const updated=rows.map(e=>{if(e.date!==date||JSON.stringify(pick(e))===JSON.stringify(routine))return e;changed=true;return {...e,...routine,updatedAt:new Date().toISOString()};});
 if(changed)saveEntries(updated);
 localStorage.setItem(PROFILE,JSON.stringify(result));
 // Caller needs the selected date's values, while the saved profile keeps the latest routine.
 return {...result,...routine};
}
function ensureToday(){const p=saved();if(!p.dailyConditions?.[today()])commit({...p,...forDate(today())},today());}
function injections(profile,rows=[]){
 const saved=Array.isArray(profile.injections)?profile.injections:[];
 if(profile.injectionVersion===2)return saved.filter(i=>!i.deleted);
 // Preserve older notes once, collapsing their automatic daily carry-forward.
 const dated={};for(const row of [...rows].sort((a,b)=>String(a.updatedAt||a.createdAt||'').localeCompare(String(b.updatedAt||b.createdAt||''))))if(row.date)dated[row.date]=row;
 Object.assign(dated,profile.dailyConditions||{});
 const legacy=[],seen=new Map();for(const date of Object.keys(dated).sort()){
  const p=dated[date];if(p.injectionJoints===undefined)continue;
  const active=new Set();for(const j of Array.isArray(p.injectionJoints)?p.injectionJoints:[]){if(!j||typeof j.id!=='string'||typeof j.label!=='string')continue;active.add(j.id);const name=p.injectionNotes||'Injection';if(seen.get(j.id)!==name)legacy.push({id:'legacy:'+date+':'+j.id,date,name,anatomicalId:j.id,anatomicalLocation:j.label,createdAt:date+'T00:00:00Z',updatedAt:date+'T00:00:00Z'});seen.set(j.id,name);}
  for(const id of seen.keys())if(!active.has(id))seen.delete(id);
 }
 const merged=new Map(legacy.map(i=>[i.id,i]));for(const i of saved)merged.set(i.id,i);return [...merged.values()].filter(i=>!i.deleted);
}
window.PainGaugeDaily={forDate,load,commit,ensureToday,injections};
$('entryDate').addEventListener('change',()=>{if($('entryDate').value&&$('entryDate').value<=today())load($('entryDate').value);});
})();
