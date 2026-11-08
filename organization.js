/* Short sections keep navigation and existing forms in place. */
(()=>{
 function tabs(section,groups){
  const nav=document.createElement('div');nav.className='section-tabs';nav.setAttribute('aria-label','Rubriques');
  const panes=groups.map(([label,nodes],i)=>{
   const pane=document.createElement('div');pane.id=section.id+'-group-'+i;
   nodes.forEach(n=>pane.appendChild(n));section.appendChild(pane);
   const button=document.createElement('button');button.type='button';button.textContent=label;button.setAttribute('aria-controls',pane.id);
   button.onclick=()=>panes.forEach((p,j)=>{p.hidden=j!==i;nav.children[j].setAttribute('aria-pressed',String(j===i));});
   nav.appendChild(button);pane.hidden=i!==0;button.setAttribute('aria-pressed',String(i===0));return pane;
  });section.insertBefore(nav,section.children[1]);
 }
 const daily=document.getElementById('dailyTickets');
 if(daily){const n=[...daily.children].slice(1);tabs(daily,[['Du jour',n.slice(1,3)],['En cours / Passés',n.slice(0,1)],['Personnalisé',n.slice(3)]]);}
 const analyses=document.getElementById('tickets');
 if(analyses)tabs(analyses,[['Mes analyses',[analyses.children[1]]],['Créer un ticket',[analyses.children[2]]]]);
 function compact(target){
  const panels=[...target.children].filter(n=>n.classList.contains('panel'));
  panels.forEach(panel=>{
   const heading=panel.querySelector('h2');if(!heading)return;
   const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=heading.textContent;
   panel.replaceWith(details);details.appendChild(summary);details.appendChild(panel);heading.hidden=true;
  });target.classList.add('compact-list');
 }
 for(const id of ['automaticTicketsResult']){const target=document.getElementById(id);if(target)new MutationObserver(()=>{if([...target.children].some(n=>n.classList.contains('panel')))compact(target);}).observe(target,{childList:true});}
 window.CompactLists={paginate(target,size=5){
  const rows=[...target.querySelectorAll(':scope > .match')];if(rows.length<=size)return;
  let count=size;rows.forEach((row,i)=>row.hidden=i>=count);
  const more=document.createElement('button');more.type='button';more.className='day list-more';more.textContent='VOIR PLUS';
  more.onclick=()=>{count+=size;rows.forEach((row,i)=>row.hidden=i>=count);more.hidden=count>=rows.length;};target.appendChild(more);
 }};
})();
