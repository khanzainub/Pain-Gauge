/* Shared chart presentation only. Stored records and consent remain canonical. */
(()=>{
'use strict';
const ns='http://www.w3.org/2000/svg';
function axis(container,chart){
 if(!container||!chart)return;
 const labels=[...chart.querySelectorAll('text')].filter(n=>/^(0|2|4|6|8|10)$/.test(n.textContent.trim())&&n.getAttribute('text-anchor')==='end'&&Number(n.getAttribute('x'))<=56&&n.hasAttribute('y'));
 let pane=container.querySelector('.care-fixed-axis'),scroller=container.querySelector('.care-plot-scroll');
 if(!labels.length){pane?.remove();if(scroller){container.insertBefore(chart,scroller);scroller.remove();}container.classList.remove('care-axis-scroll');return;}
 if(!scroller){scroller=document.createElement('div');scroller.className='care-plot-scroll';container.insertBefore(scroller,chart);scroller.appendChild(chart);}
 labels.forEach(n=>n.classList.add('care-scroll-axis-label'));
 const box=chart.viewBox.baseVal,signature=box.width+','+box.height+':'+labels.map(n=>n.outerHTML).join('');
 container.classList.add('care-axis-scroll');
 if(pane?.dataset.signature===signature)return;
 pane?.remove();pane=document.createElementNS(ns,'svg');pane.classList.add('care-fixed-axis');pane.dataset.signature=signature;pane.setAttribute('aria-hidden','true');pane.setAttribute('viewBox','0 0 40 '+box.height);pane.setAttribute('width','40');pane.setAttribute('height',String(box.height));pane.style.height=chart.style.height||box.height+'px';
 const rect=document.createElementNS(ns,'rect');rect.setAttribute('width','40');rect.setAttribute('height',String(box.height));rect.setAttribute('fill','#fff');pane.appendChild(rect);labels.forEach(n=>{const label=n.cloneNode(true);label.classList.remove('care-scroll-axis-label');label.setAttribute('x','28');pane.appendChild(label);});container.insertBefore(pane,scroller);
}
let queued=false;
function refresh(){queued=false;axis(document.querySelector('.chart-box'),document.getElementById('chart'));axis(document.getElementById('careDailyTrend'),document.querySelector('#careDailyTrend .care-chart-svg'));const identity=window.PainGaugeCare?.identity();document.body.dataset.careRole=identity&&window.PainGaugeCareCore.isAdmin({email:identity.email,email_verified:true})?'doctor':'patient';}
new MutationObserver(()=>{if(!queued){queued=true;requestAnimationFrame(refresh);}}).observe(document.body,{childList:true,subtree:true});refresh();
// Patient desktop layout: move existing nodes only; restore their exact mobile positions.
// BEGIN PATIENT DESKTOP LAYOUT
const desktop=matchMedia('(min-width:901px)'),profile=document.getElementById('profileSection'),daily=document.getElementById('dailySection'),download=document.getElementById('exportSection'),drive=document.getElementById('careDrivePanel');
const profileAnchor=document.createComment('patient profile position'),downloadAnchor=document.createComment('patient download position'),driveAnchor=document.createComment('patient Drive position');
profile.before(profileAnchor);download.before(downloadAnchor);drive.before(driveAnchor);
let tools=null;
function desktopLayout(){
 if(desktop.matches){
  if(tools)return;
  daily.prepend(profile);
  tools=document.createElement('div');tools.className='care-desktop-tools';downloadAnchor.after(tools);tools.append(download,drive);
 }else if(tools){profileAnchor.after(profile);downloadAnchor.after(download);driveAnchor.after(drive);tools.remove();tools=null;}
}
desktop.addEventListener('change',desktopLayout);desktopLayout();
// END PATIENT DESKTOP LAYOUT
})();
