/* Shared daily choices: automatic refresh, no personal analyses consumed. */
(()=>{
 const targets=['homeDailyOpinion'];
 const esc=escapeHtml;
 let busy=false,lastDay='',lastBoard=null;
 const day=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
 const visible=()=>!document.hidden&&!document.getElementById('home').classList.contains('hidden');
 const message=s=>'<p class="opinion-state">'+esc(s)+'</p>';
 function teamOdds(p){
  if(!['won','lost'].includes(p.status)||!Number.isInteger(p.home_score)||!Number.isInteger(p.away_score)||p.home_score===p.away_score)return '';
  const side=p.home_score>p.away_score?'home':'away';
  const value=p.team_odds?.markets?.[side];
  if(!Number.isFinite(value)||value<=1)return '';
  const cls=p.status==='won'?'result-won':'result-lost';
  return '<footer class="opinion-team-odds '+cls+'" style="text-align:right;margin-top:12px;font-size:13px;font-weight:800" data-odds-outcome="'+side+'">'+value.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2})+'</footer>';
 }
 function scorerHtml(board){
  const p=board.scorer;
  let html='<div class="opinion-group"><h3>⚽ Buteur du jour</h3>';
  if(!p)return html+message('Aucun buteur sélectionné pour le moment.')+'</div>';
  const state={won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé',pending:new Date(p.match.date)>new Date()?'À venir':'Résultat à vérifier'}[p.status];
  const lineup={reported_starter:'Titulaire indiqué par la source',unconfirmed:'Titularisation à confirmer',bench:'Remplaçant indiqué par la source',not_listed:'Présence à revérifier',unavailable:'Disponibilité à revérifier'}[p.availability]||'Titularisation à confirmer';
  const perf=board.scorer_performance;
  html+='<article class="opinion-pick"><h3>'+esc(p.player.name)+'</h3><p class="gold">'+esc(p.player.team_name)+' · Buteur</p><p>'+esc(p.match.home.name)+' – '+esc(p.match.away.name)+' · '+esc(new Date(p.match.date).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+'</p><p><span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(state)+'</span></p>';
  if(p.status==='pending')html+='<p>'+esc(lineup)+'</p>';
  html+='<p><strong>'+esc(p.basis.goals)+' buts · '+esc(p.basis.appearances)+' apparitions</strong></p><details><summary>Pourquoi ce buteur ?</summary><p>'+esc(p.rationale)+'</p>';
  if(perf)html+='<p>Suivi buteurs : '+esc(perf.won)+' gagnés · '+esc(perf.lost)+' perdus'+(perf.success_pct==null?'':' · '+esc(perf.success_pct)+' %')+'</p>';
  html+='<p><a href="'+esc(p.source_url)+'" target="_blank" rel="noopener noreferrer">Voir les données du match</a></p></details><button type="button" class="day" data-scorer-match>OUVRIR LE MATCH</button></article></div>';
  return html;
 }
 function render(board){
  lastDay=board.day;lastBoard=board;
  const date=new Date(board.day+'T12:00:00+01:00').toLocaleDateString('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'long'});
  let html='<div class="row"><strong class="gold">Avis du '+esc(date)+'</strong></div>';
  const p=board.performance;
  if(p)html+='<div class="opinion-performance"><h3>Performance</h3><div class="analysis"><div class="stat"><span>Réussite</span><b>'+(p.success_pct===null?'—':esc(p.success_pct)+' %')+'</b></div><div class="stat"><span>Gagnés</span><b>'+esc(p.won)+'</b></div><div class="stat"><span>Perdus</span><b>'+esc(p.lost)+'</b></div><div class="stat"><span>En attente</span><b>'+esc(p.pending)+'</b></div></div>'+'</div>';
  if(board.status==='preparing')html+=message('Préparation des choix…');
  if(board.stale&&board.status!=='preparing')html+=message('Actualisation en retard.');
  html+=(board.groups||[]).map(group=>'<div class="opinion-group"><h3>'+esc(group.title)+'</h3>'+group.picks.map(p=>{
   const m=p.match, state={won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé / non réglable',pending:new Date(m.date)>new Date()?'À venir':'Résultat à vérifier'}[p.status];
   return '<article class="opinion-pick"><div class="row"><strong>'+esc(m.home.name)+' – '+esc(m.away.name)+'</strong><span class="opinion-prob">'+esc(p.probability)+' %</span></div><p class="gold">'+esc(p.market==='home'?'Victoire '+m.home.name:p.market==='away'?'Victoire '+m.away.name:p.market_label)+'</p><p class="opinion-state">'+esc(new Date(m.date).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+' · <span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(state)+'</span>'+(p.home_score!==null?' · '+esc(p.home_score)+' – '+esc(p.away_score):'')+'</p><details><summary>Pourquoi ce choix ?</summary><p>'+esc(p.rationale)+'</p><button type="button" class="day" data-opinion-match="'+esc(m.id)+'">OUVRIR LE MATCH</button></details>'+teamOdds(p)+'</article>';
  }).join('')+(!group.picks.length?message('Aucun choix admissible pour le moment.'):'')+'</div>').join('');
  html+=scorerHtml(board);
  if(board.source_errors||board.result_source_errors)html+=message('Données partiellement indisponibles.');
  for(const id of targets){
   const target=document.getElementById(id);if(!target)continue;target.innerHTML=html;
   const scorerButton=target.querySelector('[data-scorer-match]');if(scorerButton)scorerButton.onclick=()=>openMatch(board.scorer.match,'home');
   target.querySelectorAll('[data-opinion-match]').forEach(button=>button.onclick=()=>{
    const pick=board.groups.flatMap(g=>g.picks).find(p=>p.match.id===button.dataset.opinionMatch);
    if(pick)openMatch(pick.match,id==='homeDailyOpinion'?'home':'dailyTickets');
   });
  }
 }
 async function load(){
  if(busy)return;
  if(lastDay!==day()){
   lastBoard=null;lastDay=day();
   for(const id of targets){const target=document.getElementById(id);if(target)target.innerHTML=message('Préparation de mon avis du jour…');}
  }
  busy=true;
  try{render(await api('/api/daily-opinion',15000));}
  catch(error){for(const id of targets){const target=document.getElementById(id);if(!target)continue;
   if(lastBoard){render({...lastBoard,stale:true});break;}
   target.innerHTML=message('Avis du jour temporairement indisponible. Nouvelle tentative automatique.');
  }}finally{busy=false;}
 }
 window.DailyOpinion={load,isLoading:()=>busy};
 setInterval(()=>{if(visible())load();},30000);
 document.addEventListener('visibilitychange',()=>{if(visible())load();});
 load();
})();
