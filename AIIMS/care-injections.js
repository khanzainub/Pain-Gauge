/* Injection note and checked joints use the shared daily save/carry-forward flow. */
(()=>{'use strict';
const node=id=>document.getElementById(id);
const joints=node('careInjectionJoints');
for(const p of POINTS){const label=document.createElement('label');label.className='check';const input=document.createElement('input');input.type='checkbox';input.value=p.id;const text=document.createElement('span');text.textContent=p.label;label.append(input,text);joints.appendChild(label);}
function set(profile={}){node('careInjectionNotes').value=profile.injectionNotes||'';const selected=new Set((profile.injectionJoints||[]).map(j=>j.id));joints.querySelectorAll('input').forEach(input=>input.checked=selected.has(input.value));node('careInjectionStatus').textContent='';}
function save(){if(node('careInjectionNotes').value.trim()&&!joints.querySelector('input:checked')){node('careInjectionStatus').textContent='Select at least one joint for the injection note.';return false;}const ok=window.savePainGaugeDailySection?.();node('careInjectionStatus').textContent=ok?'Saved on this phone':'Could not save. Please try again.';return ok;}
node('careSaveInjection').onclick=()=>{if(save())node('careInjectionSection').open=false;};
node('careClearInjection').onclick=()=>{if(!window.PainGaugeCare?.identity())return;if(!confirm('Clear this section? Your saved pain entries will stay.'))return;const before={injectionNotes:node('careInjectionNotes').value,injectionJoints:[...joints.querySelectorAll('input:checked')].map(i=>({id:i.value}))};set({});if(!save())set(before);};
node('careInjectionNotes').addEventListener('change',save);joints.addEventListener('change',save);
// Small outlined, pastel illustrations echo the existing mood characters.
const paths={profile:'<circle cx="16" cy="12" r="5"/><path d="M7 27v-3c0-7 18-7 18 0v3"/>',food:'<path d="M10 8v9m-3-9v5q3 5 6 0V8m-3 9v10M23 8c-5 5-5 10 0 10m0-10v19"/>',medicine:'<path d="M11 9a6 6 0 0 1 9 0l5 6a6 6 0 0 1-9 8l-5-6a6 6 0 0 1 0-8Zm2 2 9 10"/>',sleep:'<path d="M23 23A11 11 0 0 1 12 6a11 11 0 1 0 11 17Z"/><path d="M23 7v4m-2-2h4"/>',mood:'<circle cx="16" cy="16" r="10"/><path d="M11 14h1m8 0h1m-10 5q5 6 10 0"/>',period:'<path d="M16 6C13 12 8 16 8 21a8 8 0 0 0 16 0c0-5-5-9-8-15Z"/>',injection:'<path d="m11 10 11 11m-8-14 11 11M12 11l-6 6 9 9 6-6M6 26l-3 3m16-22 3-3 6 6-3 3M9 20l3-3"/>'};
const kinds={profileSection:'profile',careFoodSection:'food',careMedicationSection:'medicine',careSleepSection:'sleep',careMoodSection:'mood',carePeriodFields:'period',careInjectionSection:'injection'};
for(const [id,kind] of Object.entries(kinds)){const summary=node(id)?.querySelector('summary');if(!summary)continue;const icon=document.createElement('span');icon.className='care-section-icon';icon.setAttribute('aria-hidden','true');icon.innerHTML='<svg viewBox="0 0 32 32" focusable="false"><circle cx="16" cy="16" r="15" fill="'+({food:'#e0eee6',medicine:'#e7e2f4',sleep:'#e1eafa',injection:'#e5e1f4',period:'#f8dbe8'}[kind]||'#e5ecf6')+'"/><g fill="none" stroke="#36536d" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">'+paths[kind]+'</g></svg>';summary.prepend(icon);}
window.PainGaugeInjections={set};
let profile={};try{profile=JSON.parse(localStorage.getItem(PROFILE)||'{}');}catch{}set({...profile,...window.PainGaugeDaily.forDate($('entryDate').value||today())});
})();
