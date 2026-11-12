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
 if(daily){const n=[...daily.children].slice(1);tabs(daily,[['Tickets IA',n.slice(1,3)],['Suivi',n.slice(0,1)],['Créer',n.slice(3)]]);
  const summary=document.createElement('div');summary.id='ticketPerformance';summary.className='panel';summary.setAttribute('aria-live','polite');
  daily.insertBefore(summary,document.getElementById('dailyTickets-group-0'));
 }
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
 const opinions=document.getElementById('homeDailyOpinion');
 if(opinions)new MutationObserver(()=>{
  for(const group of [...opinions.children].filter(n=>n.classList.contains('opinion-group'))){
   const heading=group.querySelector('h3');if(!heading)continue;
   const details=document.createElement('details'),summary=document.createElement('summary');summary.textContent=heading.textContent;
   group.replaceWith(details);details.append(summary,group);heading.hidden=true;
  }
 }).observe(opinions,{childList:true});
 window.CompactLists={paginate(target,size=5,key=''){

  const rows=[...target.querySelectorAll(':scope > .match')];if(rows.length<=size)return;
  let count=target.dataset.listKey===key?Number(target.dataset.listCount)||size:size;target.dataset.listKey=key;target.dataset.listCount=String(count);rows.forEach((row,i)=>row.hidden=i>=count);
  const more=document.createElement('button');more.type='button';more.className='day list-more';more.textContent='VOIR PLUS';
  more.onclick=()=>{count+=size;target.dataset.listCount=String(count);rows.forEach((row,i)=>row.hidden=i>=count);more.hidden=count>=rows.length;};target.appendChild(more);
 }};
})();

/* Shared competition selector for calendar and manual tickets. */
(()=>{
 let catalogue;
 const french={'uefa.nations':'Ligue des nations UEFA','uefa.w.nations':'Ligue des nations féminine UEFA','fifa.world':'Coupe du monde','fifa.wwc':'Coupe du monde féminine','uefa.champions':'Ligue des champions','uefa.wchampions':'Ligue des champions féminine','uefa.europa':'Ligue Europa','uefa.europa.conf':'Ligue Conférence','fra.1':'Ligue 1','fra.2':'Ligue 2','eng.1':'Premier League','esp.1':'Liga','ita.1':'Serie A','ger.1':'Bundesliga','fifa.friendly':'Matchs amicaux internationaux','fifa.friendly.w':'Matchs amicaux internationaux féminins','club.friendly':'Matchs amicaux de clubs','caf.nations':"Coupe d’Afrique des nations",'uefa.euro':'Euro','uefa.weuro':'Euro féminin'};
 window.CompetitionPicker={async fill(select){
  const value=select.value||'all';
  try{
   if(!catalogue)catalogue=api('/api/leagues').catch(e=>{catalogue=null;throw e;});
   const data=await catalogue,fragment=document.createDocumentFragment();
   const all=document.createElement('option');all.value='all';all.textContent='Toutes les compétitions';fragment.append(all);
   const entries=(data.leagues||[]).map(code=>[code,french[code]||data.names?.[code]||code]).sort((a,b)=>a[1].localeCompare(b[1],'fr'));
   for(const [code,name] of entries){const option=document.createElement('option');option.value=code;option.textContent=name;fragment.append(option);}
   select.replaceChildren(fragment);select.value=entries.some(([code])=>code===value)?value:'all';
  }catch{select.title='Liste des compétitions indisponible. Réessaie en ouvrant la liste.';}
 }};
 const select=document.getElementById('calendarCompetition');
 if(select)window.CompetitionPicker.fill(select);
})();
