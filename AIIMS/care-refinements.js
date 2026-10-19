/* Shared chart presentation only. Stored records and consent remain canonical. */
(()=>{
'use strict';
const ns='http://www.w3.org/2000/svg';
function axis(container,chart){
 if(!container||!chart)return;
 const labels=[...chart.querySelectorAll('text')].filter(n=>/^(0|2|4|6|8|10)$/.test(n.textContent.trim())&&n.getAttribute('text-anchor')==='end'&&Number(n.getAttribute('x'))<=56&&n.hasAttribute('y'));
 let overlay=container.querySelector('.care-fixed-axis');
 if(!labels.length){overlay?.remove();container.classList.remove('care-axis-scroll');return;}
 const box=chart.viewBox.baseVal,signature=box.width+','+box.height+':'+labels.map(n=>n.outerHTML).join('');
 if(overlay?.dataset.signature===signature)return;
 overlay?.remove();overlay=document.createElementNS(ns,'svg');overlay.classList.add('care-fixed-axis');overlay.dataset.signature=signature;overlay.setAttribute('aria-hidden','true');overlay.setAttribute('viewBox','0 0 56 '+box.height);overlay.setAttribute('width','56');overlay.setAttribute('height',String(box.height));overlay.style.height=chart.style.height||box.height+'px';
 const ys=labels.map(n=>Number(n.getAttribute('y'))),rect=document.createElementNS(ns,'rect');rect.setAttribute('x','0');rect.setAttribute('y',String(Math.min(...ys)-18));rect.setAttribute('width','56');rect.setAttribute('height',String(Math.max(...ys)-Math.min(...ys)+27));rect.setAttribute('fill','#fff');overlay.appendChild(rect);labels.forEach(n=>overlay.appendChild(n.cloneNode(true)));container.classList.add('care-axis-scroll');container.appendChild(overlay);
}
let queued=false;
function refresh(){queued=false;axis(document.querySelector('.chart-box'),document.getElementById('chart'));axis(document.getElementById('careDailyTrend'),document.querySelector('#careDailyTrend .care-chart-svg'));const identity=window.PainGaugeCare?.identity();document.body.dataset.careRole=identity&&window.PainGaugeCareCore.isAdmin({email:identity.email,email_verified:true})?'doctor':'patient';}
new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(refresh);}}).observe(document.body,{childList:true,subtree:true});refresh();
})();
