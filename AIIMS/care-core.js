/* Pure helpers shared by the AIIMS patient and admin views. No credentials. */
(function(root){
'use strict';
const ADMIN_EMAIL='khanzainub@gmail.com';
function normalizeEmail(v){return String(v||'').trim().toLowerCase();}
let doctors=[{email:ADMIN_EMAIL,name:'Zainab Khan'}];
function configureTeam(config){if(!config||!Array.isArray(config.doctors)||!config.doctors.length)throw Error('Care-team configuration is missing.');const unique=new Map();for(const d of config.doctors){const email=normalizeEmail(d.email);if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw Error('Invalid care-team email.');unique.set(email,{email,name:String(d.name||email).slice(0,120)});}doctors=[...unique.values()];return teamEmails();}
function teamDoctors(){return doctors.map(d=>({...d}));}
function teamEmails(){return doctors.map(d=>d.email);}
function isAdmin(user){return !!user&&user.email_verified===true&&teamEmails().includes(normalizeEmail(user.email));}
function timestamp(e){return [String(e.date||''),String(e.updatedAt||e.createdAt||'')].join('|');}
function latestLocations(list){const map=new Map();for(const e of list||[]){const key=e.anatomicalId||e.anatomicalLocation;if(!key)continue;const old=map.get(key);if(!old||timestamp(e)>timestamp(old))map.set(key,e);}return [...map.values()].sort((a,b)=>Number(b.painScore)-Number(a.painScore));}
function latestDayPain(list){const records=(list||[]).filter(e=>e&&typeof e.date==='string'&&Number.isFinite(Number(e.painScore)));if(!records.length)return null;const date=records.reduce((latest,e)=>e.date>latest?e.date:latest,'');const sameDay=records.filter(e=>e.date===date);const highest=[...sameDay].sort((a,b)=>Number(b.painScore)-Number(a.painScore)||timestamp(b).localeCompare(timestamp(a)))[0];return {date,highest};}
function validBackup(b){if(!b||b.app!=='Pain Gauge'||b.schemaVersion!==1||!Array.isArray(b.entries)||b.entries.length>50000||!b.profile||typeof b.profile!=='object'||Array.isArray(b.profile))throw Error('Not a valid Pain Gauge backup.');if(b.profile.injections!==undefined){if(!Array.isArray(b.profile.injections)||b.profile.injections.length>10000)throw Error('Invalid injection records.');for(const i of b.profile.injections)if(!i||typeof i.id!=='string'||typeof i.date!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(i.date)||typeof i.name!=='string'||typeof i.anatomicalId!=='string'||typeof i.anatomicalLocation!=='string')throw Error('Invalid injection record.');}for(const e of b.entries){if(!e||typeof e!=='object'||Array.isArray(e)||typeof e.id!=='string'||typeof e.date!=='string'||typeof e.anatomicalId!=='string'||typeof e.anatomicalLocation!=='string'||!Number.isFinite(Number(e.painScore))||Number(e.painScore)<0||Number(e.painScore)>10)throw Error('A pain entry has an invalid location, date or score.');}return b;}
function normalized(v){if(Array.isArray(v))return v.map(normalized);if(v&&typeof v==='object')return Object.fromEntries(Object.keys(v).sort().filter(k=>v[k]!==undefined&&v[k]!==null&&v[k]!==''&&!(Array.isArray(v[k])&&!v[k].length)).map(k=>[k,normalized(v[k])]));return v;}
function same(a,b){return JSON.stringify(normalized(a))===JSON.stringify(normalized(b));}
function contentOf(b){return JSON.stringify(normalized({profile:b.profile||{},entries:[...(b.entries||[])].sort((a,b)=>String(a.id).localeCompare(String(b.id)))}));}
function mergeBackups(local,remote,base=null){
 validBackup(local);validBackup(remote);const profile={},lp=local.profile,rp=remote.profile,bp=base?.profile||{};
 for(const key of new Set([...Object.keys(lp),...Object.keys(rp),...Object.keys(bp)])){const l=lp[key],r=rp[key];if(l===undefined)profile[key]=r;else if(r===undefined)profile[key]=l;else if(same(l,r))profile[key]=l;else if(base&&same(l,bp[key]))profile[key]=r;else if(base&&same(r,bp[key]))profile[key]=l;else if(String(local.profileUpdatedAt||'')>String(remote.profileUpdatedAt||''))profile[key]=l;else if(l===undefined||l===''||l===null||Array.isArray(l)&&!l.length)profile[key]=r;else if(r===undefined||r===''||r===null||Array.isArray(r)&&!r.length)profile[key]=l;else profile[key]=r;}
 // Merge injection events by ID, retaining deletion tombstones across devices.
 if(Array.isArray(lp.injections)||Array.isArray(rp.injections)){const events=new Map();for(const i of [...(rp.injections||[]),...(lp.injections||[])]){if(!i||!i.id)continue;const old=events.get(i.id);if(!old||String(i.updatedAt||i.createdAt||'')>=String(old.updatedAt||old.createdAt||''))events.set(i.id,i);}profile.injections=[...events.values()];}
 const lm=new Map(local.entries.map(e=>[e.id,e])),rm=new Map(remote.entries.map(e=>[e.id,e])),bm=new Map((base?.entries||[]).map(e=>[e.id,e])),entries=[];
 for(const id of new Set([...lm.keys(),...rm.keys(),...bm.keys()])){const l=lm.get(id),r=rm.get(id),b=bm.get(id);if(base&&b&&(!l&&same(r,b)||!r&&same(l,b)))continue;let chosen;if(!l)chosen=r;else if(!r)chosen=l;else if(same(l,r))chosen=l;else if(base&&same(l,b))chosen=r;else if(base&&same(r,b))chosen=l;else chosen=String(l.updatedAt||l.createdAt||'')>String(r.updatedAt||r.createdAt||'')?l:r;if(chosen)entries.push(chosen);}
 return {...remote,...local,profile,entries,profileUpdatedAt:[local.profileUpdatedAt||'',remote.profileUpdatedAt||''].sort().pop()};
}
function languageKey(account,doctor=false){return doctor?null:account?.patientId?'painGaugeAIIMS:'+account.patientId+':language':'painGaugeAIIMS:landing:language';}
async function patientId(sub){const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode('pain-gauge-aiims:'+sub));return 'PG-'+Array.from(new Uint8Array(hash)).slice(0,10).map(x=>x.toString(16).padStart(2,'0')).join('').toUpperCase();}
const api={configureTeam,teamDoctors,teamEmails,ADMIN_EMAIL,normalizeEmail,isAdmin,latestLocations,latestDayPain,validBackup,contentOf,mergeBackups,languageKey,patientId};root.PainGaugeCareCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
