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
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 const labels={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux équipes marquent'};
 const message=(t,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(t)+'</div>';
 function renderLongTicket(results,locked){
  const selected=longDailySelections(results),title='Ticket 4 · Grand combiné · 5 à 8 matchs';
  if(selected.length<5)return '<div class="panel"><h2>'+title+'</h2>'+message('Ticket non proposé : '+selected.length+' sélection(s) admissible(s), minimum 5. Chaque choix doit atteindre 75 % dans le modèle et disposer de 10 matchs par équipe. Aucun ajout forcé.')+(locked?message('Ton accès gratuit est terminé. Premium est nécessaire pour poursuivre l’étude des autres rencontres.'):'')+'</div>';
  simulations.push(selected);
  toTrack.push(...selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
  const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
  return '<div class="panel premium"><h2>'+title+'</h2><p>'+selected.length+' matchs retenus · seuil de 75 % par sélection dans le modèle.</p>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(labels[r.choice.market])+'</p><p>Probabilité modèle de ce choix : '+esc(r.choice.probability)+' %</p><details><summary>Voir les arguments et les surprises possibles</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+message('Estimation combinée : '+(joint*100).toFixed(2).replace('.',',')+' % · Cote théorique : '+(1/joint).toFixed(2).replace('.',',')+'.')+'</div>';
 }
 let toTrack=[],simulations=[];
 let busy=false;
 get('generateDailyTickets').onclick=async()=>{
  if(busy)return;toTrack=[];simulations=[];busy=true;get('generateDailyTickets').disabled=true;
  const out=get('automaticTicketsResult'),notice=get('automaticTicketsNotice');notice.innerHTML='';
  const day=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'}),results=[],skipped=[];let locked=false;
  out.innerHTML=message('Recherche des rencontres à venir du '+day+'…');
  try{
   const feed=await api('/api/fixtures?date='+encodeURIComponent(day),45000);
   const seen=new Set();let fixtures=(feed.events||[]).filter(m=>{
    if(seen.has(String(m.id)))return false;seen.add(String(m.id));
    return m.state==='pre'&&!m.completed&&new Date(m.date)>new Date()&&!/POSTPONED|CANCELED|CANCELLED|ABANDONED|SUSPENDED/.test(m.status_name||'');
   }).sort((a,b)=>a.date.localeCompare(b.date));
   const total=fixtures.length;fixtures=fixtures.slice(0,16);
   if(!fixtures.length){out.innerHTML=message('Aucun match encore à venir retrouvé aujourd’hui dans les compétitions couvertes. Les tickets personnalisés restent disponibles ci-dessous.');return;}
   await window.Accounts.refresh(false);
   for(const m of fixtures){
    if(results.length>=8)break;
    out.innerHTML=message('Préparation des tickets : '+results.length+' / 8 matchs analysés. Étude de '+m.home.name+' – '+m.away.name+'…');
    if(new Date(m.date)<=new Date()){skipped.push(m.home.name+' – '+m.away.name+' : déjà commencé');continue;}
    const d=await window.Accounts.request('/api/analyze',{league:m.league,home_id:m.home.id,away_id:m.away.id,event_id:m.id,label:m.home.name+' – '+m.away.name});
    if(d.status==='locked'){locked=true;break;}
    if(d.status!=='ok'||!d.prediction?.markets){skipped.push(m.home.name+' – '+m.away.name+' : '+(d.message||'données insuffisantes'));continue;}
    d.market_odds=await window.OddsTicket?.load(m);
    results.push({match:m,analysis:d});
   }
   notice.innerHTML=feed.partial?message('Calendrier incomplet.'):'';
   if(locked&&results.length===0){renderLockedAnalysis(out);return;}
   out.innerHTML=message('Vérification des matchs…');
   await ticketVerifyFixtures(results);
   const profiles=[['prudent','Ticket 1 · Prudent',2],['balanced','Ticket 2 · Équilibré',3],['offensive','Ticket 3 · Offensif',3],['long','Ticket 4 · Grand combiné',0],['mixed','Ticket 5 · Double chance + buts sur chaque match',3]];
   const ticketsHtml=profiles.map(([profile,title,count])=>{
    if(profile==='long')return renderLongTicket(results,locked);
    const choices=(profile==='mixed'?mixedDailySelections(results):results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction.markets,profile,r.analysis.market_odds)})).filter(r=>r.choice).sort((a,b)=>b.choice.probability-a.choice.probability));
    const selected=[],teams=new Set();
    for(const r of choices){if(teams.has(String(r.match.home.id))||teams.has(String(r.match.away.id)))continue;selected.push(r);teams.add(String(r.match.home.id));teams.add(String(r.match.away.id));if(selected.length===count)break;}
    if(selected.length<count)return '<div class="panel"><h2>'+title+'</h2>'+message('Pas assez de matchs distincts disposant de données suffisantes pour ce profil. Aucun ticket artificiellement complété.')+'</div>';
    simulations.push(selected);
  toTrack.push(...selected.map(r=>({analysis:r.analysis,market:r.choice.market})));
    const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
    return '<div class="panel premium"><h2>'+title+'</h2>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(labels[r.choice.market])+'</p><p>Probabilité du modèle : '+esc(r.choice.probability)+' %</p><details><summary>Lire l’analyse détaillée</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+
     message('Estimation combinée : '+(joint*100).toFixed(2).replace('.',',')+' % · Cote théorique : '+(1/joint).toFixed(2).replace('.',',')+'.')+'</div>';
   }).join('')+skipped.map(t=>message(t)).join('');
   const missed=await window.Tracking.record(toTrack);
   await ticketVerifyFixtures(results);
   out.innerHTML=ticketsHtml;
   out.querySelectorAll('.panel.premium').forEach(panel=>{
    const group=simulations.shift();if(group)window.OddsTicket?.mount(panel,group);
   });
   if(missed)notice.innerHTML+=message(missed+' sélection(s) non enregistrée(s) dans le suivi : rencontre non vérifiable, déjà commencée ou ancienne analyse.');
  }catch(e){out.innerHTML=message('Tickets non finalisés : '+e.message,true);if(e.code==='login_required')window.Accounts.needsLogin(out);}
  finally{busy=false;get('generateDailyTickets').disabled=false;await window.Accounts.afterAnalysis();}
 };
})();




