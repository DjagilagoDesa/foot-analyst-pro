/* Each ticket selection is recorded server-side before kickoff. */
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 const market={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',away:'Victoire extérieur',draw:'Match nul',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux marquent'};
 let epoch=0,view=0;
 const statusLabel={won:'✓ Gagné',lost:'✗ Perdu',pending:'⏳ En cours',void:'Annulé'};
 const choiceLabel=p=>p.market==='home'?'Victoire '+p.label.split(' – ')[0]:p.market==='away'?'Victoire '+p.label.split(' – ')[1]:market[p.market]||p.market;
 const date=t=>new Date(t*1000).toLocaleDateString('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'short',year:'numeric'});
 const renderPick=p=>'<div class="message"><strong>'+esc(p.label)+'</strong><p>'+esc(choiceLabel(p))+'</p><span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(statusLabel[p.status]||p.status)+'</span>'+(p.home_score!=null?' · '+esc(p.home_score)+' – '+esc(p.away_score):'')+'</div>';
 async function archive(status,offset,requestEpoch,requestView){
  const target=get('ticketArchive');if(!target)return;
  try{
   const r=await fetch('/api/tracking/tickets?status='+status+'&offset='+offset,{credentials:'same-origin',headers:{Accept:'application/json'}}),d=await r.json();
   if(requestEpoch!==epoch||requestView!==view)return;
   if(!r.ok)throw Error(d.message||'Archive indisponible');
   if(!offset)target.innerHTML='';
   for(const ticket of d.tickets||[]){
    const node=document.createElement('details');node.className='panel';
    node.innerHTML='<summary><strong>'+esc(ticket.title)+'</strong><br><span class="'+({won:'result-won',lost:'result-lost'}[ticket.status]||'')+'">'+esc(statusLabel[ticket.status])+'</span> · '+esc(date(ticket.created_at))+' · '+esc(ticket.selections.length)+' matchs</summary>'+ticket.selections.map(renderPick).join('');target.appendChild(node);
   }
   if(!offset&&!d.tickets?.length)target.innerHTML='<div class="message">Aucun ticket '+(status==='pending'?'en cours':'passé')+'.</div>';
   if(d.next_offset!=null){const more=document.createElement('button');more.type='button';more.className='day list-more';more.textContent='VOIR PLUS';more.onclick=()=>{more.remove();archive(status,d.next_offset,requestEpoch,requestView);};target.appendChild(more);}
  }catch(e){if(requestEpoch===epoch&&requestView===view){const error=document.createElement('div');error.className='message';error.textContent=e.message;target.appendChild(error);}}
 }
 window.Tracking={
 clear:()=>{epoch++;view++;const target=get('trackingResult');if(target)target.textContent='';},
 saveTicket:async(title,picks)=>{
  const selections=picks.map(p=>({analysis_id:p.analysis.tracking_id,market:p.market}));
  if(selections.some(p=>!p.analysis_id))throw Error('Ticket non archivé : sélection non enregistrée.');
  return window.Accounts.request('/api/tracking/tickets',{title,selections});
 },
 record:async picks=>{
  let missed=0;
  for(const pick of picks){
   if(!pick.analysis.tracking_id){missed++;continue;}
   try{await window.Accounts.request('/api/tracking/record',{analysis_id:pick.analysis.tracking_id,market:pick.market});}catch{missed++;}
  }
  return missed;
 },load:async()=>{
  const target=get('trackingResult'),button=get('refreshTracking');if(button.disabled)return;
  const requestEpoch=++epoch;button.disabled=true;button.textContent='↻ VÉRIFICATION…';target.innerHTML='<div class="message">Vérification des résultats…</div>';
  try{
   const r=await fetch('/api/tracking/performance',{credentials:'same-origin',headers:{Accept:'application/json'}}),d=await r.json();
   if(requestEpoch!==epoch)return;
   if(!r.ok)throw Error(d.message||'Suivi indisponible');
   target.innerHTML='<div class="section-tabs" aria-label="Mes tickets"><button type="button" data-status="pending" aria-pressed="true">En cours</button><button type="button" data-status="past" aria-pressed="false">Passés</button></div><div id="ticketArchive" aria-live="polite"></div><details><summary>Statistiques et paris individuels</summary><div class="analysis"><div class="stat"><span>Ma réussite</span><b>'+(d.success_pct===null?'—':esc(d.success_pct)+' %')+'</b></div><div class="stat"><span>Paris gagnés</span><b>'+esc(d.won)+'</b></div><div class="stat"><span>Paris perdus</span><b>'+esc(d.lost)+'</b></div><div class="stat"><span>En attente</span><b>'+esc(d.pending)+'</b></div></div><div id="trackedSelections"></div></details>'+(d.source_errors?'<div class="message">Certains résultats restent à vérifier.</div>':'');
   const list=get('trackedSelections'),rows=d.recent||[];let limit=0;
   const more=document.createElement('button');more.type='button';more.className='day list-more';more.textContent='VOIR PLUS';
   const append=()=>{rows.slice(limit,limit+5).forEach(p=>{const node=document.createElement('div');node.innerHTML=renderPick(p);list.insertBefore(node,more);});limit+=5;more.hidden=limit>=rows.length;};list.appendChild(more);more.onclick=append;append();
   target.querySelectorAll('[data-status]').forEach(b=>b.onclick=()=>{target.querySelectorAll('[data-status]').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));get('ticketArchive').innerHTML='<div class="message">Chargement…</div>';archive(b.dataset.status,0,requestEpoch,++view);});
   await archive('pending',0,requestEpoch,++view);
  }catch(e){if(requestEpoch===epoch){target.innerHTML='<div class="message">'+esc(e.message)+'</div>';if(/Connecte|connecte|connexion/i.test(e.message))window.Accounts.needsLogin(target);}}
  finally{button.disabled=false;button.textContent='↻ ACTUALISER';}
 }};
 get('refreshTracking').onclick=window.Tracking.load;
})();
