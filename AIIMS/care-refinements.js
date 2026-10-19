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

// Freeze only the on-screen chart title and colour legend; preserve scales and exported SVG.
const stationaryStyle=document.createElement('style');
stationaryStyle.textContent='.care-axis-scroll{position:relative}.care-axis-scroll .care-stationary-overlay{position:absolute;left:40px;right:0;top:0;overflow:hidden;pointer-events:none;z-index:2}.care-axis-scroll .care-stationary-overlay>svg{display:block;max-width:none;margin-left:-40px}.care-axis-scroll .care-plot-scroll .care-stationary-source{visibility:hidden}';
document.head.appendChild(stationaryStyle);
function stationary(container,chart){
 if(!container)return;
 const scroller=container.querySelector('.care-plot-scroll');
 let overlay=container.querySelector('.care-stationary-overlay');
 if(!chart||!scroller||!chart.querySelector('polyline')){overlay?.remove();return;}
 const patient=chart.id==='chart';
 const nodes=patient?[...chart.children].filter(n=>
  (n.tagName.toLowerCase()==='line'&&n.getAttribute('x1')==='56'&&n.getAttribute('x2')==='76')||
  (n.tagName.toLowerCase()==='text'&&n.getAttribute('x')==='84')||
  (n.tagName.toLowerCase()==='text'&&n.getAttribute('x')==='44'&&n.getAttribute('text-anchor')==='start')
 ):[];
 if(!patient){
  // The doctor's location-colour legend is already outside the scrolling plot.
  const plot=chart.querySelector('rect[x="54"]');
  const title=document.createElementNS(ns,'text');
  title.setAttribute('x','54');title.setAttribute('y',String(Math.max(14,Number(plot?.getAttribute('y')||20)-9)));
  title.setAttribute('font-family','Arial, sans-serif');title.setAttribute('font-size','11');
  title.setAttribute('font-weight','600');title.setAttribute('fill','#334155');title.textContent='Pain Score';
  nodes.push(title);
 }
 if(patient)nodes.forEach(n=>n.classList.add('care-stationary-source'));
 const signature=chart.getAttribute('viewBox')+'|'+nodes.map(n=>n.outerHTML).join('|');
 if(overlay?.dataset.signature===signature)return;
 overlay?.remove();
 overlay=document.createElement('div');overlay.className='care-stationary-overlay';overlay.dataset.signature=signature;
 const copy=document.createElementNS(ns,'svg');copy.setAttribute('viewBox',chart.getAttribute('viewBox'));
 copy.setAttribute('aria-hidden','true');copy.setAttribute('focusable','false');
 const box=chart.viewBox.baseVal;
 copy.setAttribute('width',String(box.width));copy.setAttribute('height',String(box.height));
 copy.style.width=box.width+'px';copy.style.height=box.height+'px';
 for(const n of nodes){const item=n.cloneNode(true);item.classList.remove('care-stationary-source');copy.appendChild(item);}
 overlay.appendChild(copy);container.appendChild(overlay);
}

let queued=false;
function refresh(){queued=false;axis(document.querySelector('.chart-box'),document.getElementById('chart'));axis(document.getElementById('careDailyTrend'),document.querySelector('#careDailyTrend .care-chart-svg'));stationary(document.querySelector('.chart-box'),document.getElementById('chart'));stationary(document.getElementById('careDailyTrend'),document.querySelector('#careDailyTrend .care-chart-svg'));const identity=window.PainGaugeCare?.identity();document.body.dataset.careRole=identity&&window.PainGaugeCareCore.isAdmin({email:identity.email,email_verified:true})?'doctor':'patient';if(document.body.dataset.careRole==='doctor'){const subtitle=document.getElementById('careBrandSubtitle');if(subtitle&&subtitle.textContent!=='Doctor’s Dashboard')subtitle.textContent='Doctor’s Dashboard';}}
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
