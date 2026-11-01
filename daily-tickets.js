/* Daily proposals use the same authenticated 10-match analyses as personal tickets. */
function longDailySelections(results){
 const candidates=results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction?.markets||{},'prudent')}))
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
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 const labels={home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',btts:'Les deux équipes marquent'};
 const message=(t,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(t)+'</div>';
 function renderLongTicket(results,locked){
  const selected=longDailySelections(results),title='Ticket 4 · Grand combiné · 5 à 8 matchs';
  if(selected.length<5)return '<div class="panel premium"><h2>'+title+'</h2>'+message('Ticket non proposé : '+selected.length+' sélection(s) admissible(s), minimum 5. Chaque choix doit atteindre 75 % dans le modèle et disposer de 10 matchs par équipe. Aucun ajout forcé.')+(locked?message('Ton accès gratuit est terminé. Premium est nécessaire pour poursuivre l’étude des autres rencontres.'):'')+'</div>';
  const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
  return '<div class="panel premium"><h2>'+title+'</h2><p>'+selected.length+' matchs retenus · seuil de 75 % par sélection dans le modèle.</p>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(labels[r.choice.market])+'</p><p>Probabilité modèle de ce choix : '+esc(r.choice.probability)+' %</p><details><summary>Voir les arguments et les surprises possibles</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+message('Probabilité estimée que tout le combiné passe, sous hypothèse d’indépendance : '+(joint*100).toFixed(2).replace('.',',')+' %. Cote équitable théorique : '+(1/joint).toFixed(2).replace('.',',')+' ; ce n’est pas une cote bookmaker.')+message('Probabilités individuelles élevées ne signifie pas forte confiance dans le ticket complet. Le seuil de 75 % est un filtre, pas un taux de réussite vérifié. Les absences et compositions ne sont pas contrôlées et des dépendances peuvent subsister entre matchs.')+'</div>';
 }
 let busy=false;
 get('generateDailyTickets').onclick=async()=>{
  if(busy)return;busy=true;get('generateDailyTickets').disabled=true;
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
    results.push({match:m,analysis:d});
   }
   notice.innerHTML=message(day+' · '+total+' rencontre(s) à venir retrouvée(s). Les 16 prochaines au maximum sont examinées dans l’ordre horaire jusqu’à obtenir 8 analyses. Ce n’est pas une sélection exhaustive des meilleurs paris.'+(feed.partial?' Couverture partielle.':''));
   if(locked&&results.length===0){renderLockedAnalysis(out);return;}
   const profiles=[['prudent','Ticket 1 · Prudent',2],['balanced','Ticket 2 · Équilibré',3],['offensive','Ticket 3 · Offensif',3]];
   out.innerHTML=profiles.map(([profile,title,count])=>{
    const choices=results.map(r=>({...r,choice:ticketSelection(r.analysis.prediction.markets,profile)})).filter(r=>r.choice).sort((a,b)=>b.choice.probability-a.choice.probability);
    const selected=[],teams=new Set();
    for(const r of choices){if(teams.has(String(r.match.home.id))||teams.has(String(r.match.away.id)))continue;selected.push(r);teams.add(String(r.match.home.id));teams.add(String(r.match.away.id));if(selected.length===count)break;}
    if(selected.length<count)return '<div class="panel"><h2>'+title+'</h2>'+message('Pas assez de matchs distincts disposant de données suffisantes pour ce profil. Aucun ticket artificiellement complété.')+'</div>';
    const joint=selected.reduce((p,r)=>p*r.choice.probability/100,1);
    return '<div class="panel premium"><h2>'+title+'</h2>'+selected.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(labels[r.choice.market])+'</p><p>Probabilité du modèle : '+esc(r.choice.probability)+' %</p><details><summary>Lire l’analyse détaillée</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+
     message('Probabilité combinée sous hypothèse d’indépendance : '+(joint*100).toFixed(2).replace('.',',')+' %. Cote équitable théorique : '+(1/joint).toFixed(2).replace('.',',')+' — ce n’est pas une cote bookmaker.')+'</div>';
   }).join('')+renderLongTicket(results,locked)+skipped.map(t=>message(t)).join('')+'<p class="fine">Les quatre tickets peuvent partager des matchs et des sélections : ce ne sont pas quatre tickets indépendants. Aucun gain garanti. Les profils utilisent les probabilités du modèle, sans connaître les cotes réelles ni vérifier les compositions.</p>';
  }catch(e){out.innerHTML=message('Tickets non finalisés : '+e.message,true);if(e.code==='login_required')window.Accounts.needsLogin(out);}
  finally{busy=false;get('generateDailyTickets').disabled=false;await window.Accounts.afterAnalysis();}
 };
})();

