/* Doctor CSV exports use entry snapshots, with current profiles in separate columns. */
(function(root){'use strict';
const profileKeys=['patientAge','gender','diagnosis','otherDiagnosis','diagnosisStatus','diseaseDuration','symptomYear','diagnosisYear','diseaseNotes','foodHabit','dietPatterns','dietNotes','medication','medicationCategories','medicationsTaken','medicationsSkipped','sleepHours','sleepQuality','mood','wellbeingNotes','periodStatus','periodStart','periodNotes'];
const entryKeys=['id','date','anatomicalId','anatomicalLocation','bodySide','bodyView','region','painScore','notes',...profileKeys,'createdAt','updatedAt'];
const columns=['row_type','patient_id','patient_name','account_email',...entryKeys.map(k=>'entry_'+k),...profileKeys.map(k=>'profile_'+k)];
function sexOf(patient){const p=patient.data.profile||{};return p.gender||[...patient.data.entries].sort((a,b)=>String(b.updatedAt||b.createdAt||b.date).localeCompare(String(a.updatedAt||a.createdAt||a.date))).find(e=>e.gender)?.gender||'';}
function records(patients,{from='',to='',patientId='',sex=''}={}){
 if(from&&to&&from>to)throw Error('From date must be on or before To date.');
 const rows=[];
 for(const patient of patients){const p=patient.data.profile||{},account=patient.data.account||{},id=p.patientId||account.patientId||'';if(patientId&&id!==patientId)continue;if(sex&&(sex==='unrecorded'?!!sexOf(patient):sexOf(patient)!==sex))continue;
 const selected=patient.data.entries.filter(e=>(!from||e.date>=from)&&(!to||e.date<=to));if(!selected.length&&!patient.data.entries.length&&!from&&!to)selected.push(null);
 for(const e of selected){const row={row_type:e?'pain_entry':'profile_only',patient_id:id,patient_name:p.patientName||e?.patientName||'',account_email:account.email||''};for(const key of entryKeys)row['entry_'+key]=e?.[key]??'';for(const key of profileKeys)row['profile_'+key]=p[key]??'';rows.push(row);}}
 return rows.sort((a,b)=>String(a.patient_id).localeCompare(String(b.patient_id))||String(a.entry_date).localeCompare(String(b.entry_date))||String(a.entry_anatomicalLocation).localeCompare(String(b.entry_anatomicalLocation))||String(a.entry_updatedAt).localeCompare(String(b.entry_updatedAt)));
}
function cell(value){let s=Array.isArray(value)?value.join('; '):String(value??'');if(typeof value!=='number'&&/^[\s]*[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';}
function csv(rows){return '\uFEFF'+[columns.map(cell).join(','),...rows.map(row=>columns.map(key=>cell(row[key])).join(','))].join('\r\n')+'\r\n';}
const api={records,csv,columns,profileKeys,entryKeys};root.PainGaugeCareExport=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window!=='undefined'?window:globalThis);
