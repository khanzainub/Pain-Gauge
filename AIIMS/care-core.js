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
function validBackup(b){if(!b||b.app!=='Pain Gauge'||b.schemaVersion!==1||!Array.isArray(b.entries)||b.entries.length>50000||!b.profile||typeof b.profile!=='object'||Array.isArray(b.profile))throw Error('Not a valid Pain Gauge backup.');for(const e of b.entries){if(!e||typeof e!=='object'||Array.isArray(e)||typeof e.id!=='string'||typeof e.date!=='string'||typeof e.anatomicalId!=='string'||typeof e.anatomicalLocation!=='string'||!Number.isFinite(Number(e.painScore))||Number(e.painScore)<0||Number(e.painScore)>10)throw Error('A pain entry has an invalid location, date or score.');}return b;}
function contentOf(b){return JSON.stringify({profile:b.profile||{},entries:b.entries||[]});}
async function patientId(sub){const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode('pain-gauge-aiims:'+sub));return 'PG-'+Array.from(new Uint8Array(hash)).slice(0,10).map(x=>x.toString(16).padStart(2,'0')).join('').toUpperCase();}
const api={configureTeam,teamDoctors,teamEmails,ADMIN_EMAIL,normalizeEmail,isAdmin,latestLocations,validBackup,contentOf,patientId};root.PainGaugeCareCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
