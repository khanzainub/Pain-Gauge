/* One dated routine shared by every pain location; carried forward until changed. */
(()=>{
'use strict';
const keys=['foodHabit','dietPatterns','dietNotes','medicationCategories','medication','medicationsTaken','medicationsSkipped','sleepHours','sleepQuality','mood','wellbeingNotes','periodStatus','periodStart','periodNotes','injectionNotes','injectionJoints'];
const pick=p=>Object.fromEntries(keys.map(k=>[k,p[k]??(['dietPatterns','medicationCategories','injectionJoints'].includes(k)?[]:'')]));
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
 const dated={};for(const row of [...rows].sort((a,b)=>String(a.updatedAt||a.createdAt||'').localeCompare(String(b.updatedAt||b.createdAt||''))))if(row.date)dated[row.date]=row;
 Object.assign(dated,profile.dailyConditions||{});
 return Object.entries(dated).flatMap(([date,p])=>(Array.isArray(p.injectionJoints)?p.injectionJoints:[]).filter(j=>j&&typeof j.id==='string'&&typeof j.label==='string').map(j=>({id:date+':'+j.id,date,anatomicalId:j.id,anatomicalLocation:j.label,notes:p.injectionNotes||''})));
}
window.PainGaugeDaily={forDate,load,commit,ensureToday,injections};
$('entryDate').addEventListener('change',()=>{if($('entryDate').value&&$('entryDate').value<=today())load($('entryDate').value);});
})();
