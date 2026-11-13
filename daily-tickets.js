/* Daily proposals use the same authenticated 10-match analyses as personal tickets. */
function longDailySelections(results){
 const candidates=results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction?.markets||{},'prudent',r.analysis.market_odds)}))
  .filter(r=>r.choice&&r.choice.probability>=75&&r.analysis.home?.matches>=10&&r.analysis.away?.matches>=10)
  .sort((a,b)=>b.choice.probability-a.choice.probability);
 const selected=[],teams=new Set(),events=new Set();
 for(const r of candidates){
  const h=String(r.match.home.id),a=String(r.match.away.id),id=String(r.match.id);
  if(teams.has(h)||teams.has(a)||events.has(id))continue;
  selected.push(r);teams.add(h);teams.add(a);events.add(id);if(selected.length===8)break;
 }
 return selected;
}
function mixedDailySelections(results){
 const candidates=results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction?.markets||{},'mixed',r.analysis.market_odds)}))
  .filter(r=>r.choice).sort((a,b)=>b.choice.probability-a.choice.probability);
 const teams=new Set(),selected=[];
 for(const r of candidates){
  const home=String(r.match.home.id),away=String(r.match.away.id);
  if(teams.has(home)||teams.has(away))continue;
  selected.push(r);teams.add(home);teams.add(away);if(selected.length===3)break;
 }
 return selected.length===3?selected:[];
}
function dailyScorerSelections(results){
 const usedTeams=new Set(),selected=[];
 for(const row of results){
  const ids=[String(row.match.home.id),String(row.match.away.id)];
  if(ids.some(id=>usedTeams.has(id)))continue;
  const picks=(row.analysis.scorer_choices?.teams||[]).flatMap(t=>t.choices||[]).filter(p=>p.player?.id&&p.player?.name&&p.availability!=='bench');
  picks.sort((a,b)=>a.rank-b.rank||((b.basis?.goals||0)/(b.basis?.appearances||1))-((a.basis?.goals||0)/(a.basis?.appearances||1)));
  const pick=picks[0];if(!pick)continue;
  const player=pick.player,market='scorer:'+player.id;
  selected.push({...row,match:{...row.match,scorer_names:{[player.id]:player.name}},choice:{market,player,rationale:pick.rationale,probability:null}});
  ids.forEach(id=>usedTeams.add(id));if(selected.length===3)break;
 }
 return selected;
}
function dailyProfilesReady(results){
 if(longDailySelections(results).length<5||mixedDailySelections(results).length<3||dailyScorerSelections(results).length<3)return false;
 return [['prudent',2],['balanced',3],['offensive',3]].every(([profile,count])=>{
  const teams=new Set();let found=0;
  for(const r of results){
   if(!ticketSelection(r.analysis.prediction?.markets||{},profile,r.analysis.market_odds))continue;
   const ids=[String(r.match.home.id),String(r.match.away.id)];
   if(ids.some(id=>teams.has(id)))continue;
   ids.forEach(id=>teams.add(id));found++;
  }
  return found>=count;
 });
}
/* An unavailable candidate must not discard the other daily proposals. */
async function dailyVerifiedSelections(results){
 const checked=new Array(results.length);let cursor=0;
 async function worker(){
  while(cursor<results.length){
   const i=cursor++,row=results[i];
   try{await ticketVerifyFixtures([row]);checked[i]=row;}catch{checked[i]=null;}
  }
 }
 await Promise.all(Array.from({length:Math.min(3,results.length)},worker));
 return checked.filter(Boolean).filter(row=>{try{ticketAssertFuture([row]);return true;}catch{return false;}});
}
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 const labels={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux équipes marquent'};
 const message=(t,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(t)+'</div>';
 function renderLongTicket(results,locked){
  const selected=longDailySelections(results),title='Ticket 4 · Grand combiné · 5 à 8 matchs';
  if(selected.length<5){unavailable.push('Grand combiné');return '';}
  simulations.push({selected,title});
  toTrack.push(...selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
  const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
  return '<div class="panel premium"><h2>'+title+'</h2><p>'+selected.length+' matchs retenus · seuil de 75 % par sélection dans le modèle.</p>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(ticketLabel(r.choice.market,r.match,labels))+'</p><p>Probabilité modèle de ce choix : '+esc(r.choice.probability)+' %</p><details><summary>Voir les arguments et les surprises possibles</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+message('Estimation combinée : '+(joint*100).toFixed(2).replace('.',',')+' % · Cote théorique : '+(1/joint).toFixed(2).replace('.',',')+'.')+'</div>';
 }
 let toTrack=[],simulations=[],unavailable=[];
 let busy=false;
 get('generateDailyTickets').onclick=async()=>{
  if(busy)return;toTrack=[];simulations=[];unavailable=[];busy=true;get('generateDailyTickets').disabled=true;
  const out=get('automaticTicketsResult'),notice=get('automaticTicketsNotice');notice.innerHTML='';
  const day=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'}),skipped=[];let results=[],locked=false;
  out.innerHTML=message('Recherche des rencontres à venir du '+day+'…');
  try{
   const feed=await api('/api/fixtures?date='+encodeURIComponent(day),45000);
   const seen=new Set();let fixtures=(feed.events||[]).filter(m=>{
    if(seen.has(String(m.id)))return false;seen.add(String(m.id));
    return m.state==='pre'&&!m.completed&&new Date(m.date)>new Date()&&!/POSTPONED|CANCELED|CANCELLED|ABANDONED|SUSPENDED/.test(m.status_name||'');
   }).sort((a,b)=>a.date.localeCompare(b.date));
   const total=fixtures.length;
   if(fixtures.length>24)fixtures=Array.from({length:24},(_,i)=>fixtures[Math.round(i*(fixtures.length-1)/23)]);
   if(!fixtures.length){out.innerHTML=message('Aucun match encore à venir retrouvé aujourd’hui dans les compétitions couvertes. Les tickets personnalisés restent disponibles ci-dessous.');return;}
   await window.Accounts.refresh(false);
   for(const m of fixtures){
    if(dailyProfilesReady(results))break;
    out.innerHTML=message('Préparation des tickets : '+results.length+' matchs analysés. Étude de '+m.home.name+' – '+m.away.name+'…');
    if(new Date(m.date)<=new Date()){skipped.push(m.home.name+' – '+m.away.name+' : déjà commencé');continue;}
    try{await ticketVerifyFixtures([{match:m}]);}catch{skipped.push(m.home.name+' – '+m.away.name+' : rencontre non confirmée');continue;}
    const d=await window.Accounts.request('/api/analyze',{league:m.league,home_id:m.home.id,away_id:m.away.id,event_id:m.id,label:m.home.name+' – '+m.away.name});
    if(d.status==='locked'){locked=true;break;}
    if(d.status!=='ok'||!d.prediction?.markets){skipped.push(m.home.name+' – '+m.away.name+' : '+(d.message||'données insuffisantes'));continue;}
    d.market_odds=await window.OddsTicket?.load(m);
    results.push({match:m,analysis:d});
   }
   notice.innerHTML=feed.partial?message('Calendrier incomplet.'):'';
   if(locked&&results.length===0){renderLockedAnalysis(out);return;}
   out.innerHTML=message('Vérification des matchs…');
   const analyzedCount=results.length;results=await dailyVerifiedSelections(results);
   if(!results.length){out.innerHTML=message('Aucune rencontre encore à venir n’a pu être confirmée. Choisis une autre date dans « Crée mon ticket ».');return;}
   if(results.length<analyzedCount)notice.innerHTML+=message((analyzedCount-results.length)+' rencontre(s) écartée(s) après actualisation.');
   const profiles=[['prudent','Ticket 1 · Prudent',2],['balanced','Ticket 2 · Équilibré',3],['scorers','Ticket 3 · Buteurs',3],['long','Ticket 4 · Grand combiné',0],['mixed','Ticket 5 · Double chance + buts sur chaque match',3]];
   const ticketsHtml=profiles.map(([profile,title,count])=>{
    if(profile==='long')return renderLongTicket(results,locked);
    if(profile==='scorers'){
     const selected=dailyScorerSelections(results);
     if(selected.length<2){unavailable.push('Buteurs');return '';}
     simulations.push({selected,title});toTrack.push(...selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
     return '<div class="panel premium"><h2>'+title+'</h2>'+selected.map(r=>'<div class="message"><strong>'+esc(r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(r.choice.player.name)+' marque au moins un but</p><p>'+esc(r.choice.rationale)+'</p></div>').join('')+'</div>';
    }

    const choices=(profile==='mixed'?mixedDailySelections(results):results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction.markets,profile,r.analysis.market_odds)})).filter(r=>r.choice).sort((a,b)=>b.choice.probability-a.choice.probability));
    const selected=[],teams=new Set();
    for(const r of choices){if(teams.has(String(r.match.home.id))||teams.has(String(r.match.away.id)))continue;selected.push(r);teams.add(String(r.match.home.id));teams.add(String(r.match.away.id));if(selected.length===count)break;}
    if(selected.length<count){unavailable.push(title.replace(/^Ticket \d+ · /,''));return '';}
    simulations.push({selected,title});
  toTrack.push(...selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
    const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
    return '<div class="panel premium"><h2>'+title+'</h2>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(ticketLabel(r.choice.market,r.match,labels))+'</p><p>Probabilité du modèle : '+esc(r.choice.probability)+' %</p><details><summary>Lire l’analyse détaillée</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+
     message('Estimation combinée : '+(joint*100).toFixed(2).replace('.',',')+' % · Cote théorique : '+(1/joint).toFixed(2).replace('.',',')+'.')+'</div>';
   }).join('');
   const unavailableHtml=unavailable.length?message(simulations.length?'Profils indisponibles : '+unavailable.join(', ')+'.':'Pas assez de matchs à venir vérifiés pour composer un ticket aujourd’hui.')+(!simulations.length?'<button type="button" class="day" data-next-day>CHOISIR LES MATCHS DE DEMAIN</button>':''):'';
   const missed=await window.Tracking.record(toTrack);
   ticketAssertFuture(simulations.flatMap(s=>s.selected));
   for(const {selected,title} of simulations)await window.Tracking.saveTicket?.(title,selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
   ticketAssertFuture(simulations.flatMap(s=>s.selected));
   out.innerHTML=ticketsHtml+unavailableHtml;
   const nextDay=out.querySelector('[data-next-day]');if(nextDay)nextDay.onclick=()=>{show('tickets');document.querySelector('[aria-controls="tickets-group-1"]')?.click();get('builderSource').value='auto';const tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);get('builderDate').value=tomorrow.toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});window.TicketBuilder?.refresh();};
   out.querySelectorAll('.panel.premium').forEach(panel=>{
    const group=simulations.shift();if(group)window.OddsTicket?.mount(panel,group.selected);
   });
   if(missed)notice.innerHTML+=message(missed+' sélection(s) non enregistrée(s) dans le suivi : rencontre non vérifiable, déjà commencée ou ancienne analyse.');
  }catch(e){out.innerHTML=message(e.message.startsWith('Ticket')?e.message:'Préparation interrompue : '+e.message,true);if(e.code==='login_required')window.Accounts.needsLogin(out);}
  finally{busy=false;get('generateDailyTickets').disabled=false;await window.Accounts.afterAnalysis();}
 };
})();




