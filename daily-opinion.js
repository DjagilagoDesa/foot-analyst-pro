/* Shared daily choices: automatic refresh, no personal analyses consumed. */
(()=>{
 const targets=['homeDailyOpinion'];
 const esc=escapeHtml;
 let busy=false,lastDay='',lastBoard=null;
 const day=()=>new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
 const visible=()=>!document.hidden&&!document.getElementById('home').classList.contains('hidden');
 const message=s=>'<p class="fine">'+esc(s)+'</p>';
 function teamOdds(p){
  const quote=p.team_odds;
  const style='text-align:right;margin-top:12px;font-size:13px;font-weight:800';
  if(!quote)return '<footer class="opinion-team-odds fine" style="'+style+'">Cotes victoire non enregistrées</footer>';
  const settled=['won','lost'].includes(p.status)&&Number.isInteger(p.home_score)&&Number.isInteger(p.away_score);
  const winner=settled?(p.home_score===p.away_score?'draw':p.home_score>p.away_score?'home':'away'):null;
  const source=quote.bookmaker+' via ESPN · consultation avant-match : '+new Date(quote.observed_at).toLocaleString('fr-FR',{timeZone:'Europe/Paris'});
  return '<footer class="opinion-team-odds" style="'+style+'" title="'+esc(source)+'"><span class="fine">Cotes victoire avant-match</span>'+['home','draw','away'].filter(side=>side!=='draw'||winner==='draw').map(side=>{
   const value=quote.markets?.[side];if(!Number.isFinite(value)||value<=1)return '';
   const name=side==='draw'?'Match nul':p.match[side].name;
   const cls=winner?(side===winner?'result-won':'result-lost'):'gold';
   return '<div class="'+cls+'" data-odds-outcome="'+side+'">'+esc(name)+' · '+value.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2})+(winner?' · '+(side===winner?'✓ Gagné':'✗ Perdu'):'')+'</div>';
  }).join('')+'</footer>';
 }
 function render(board){
  lastDay=board.day;lastBoard=board;
  const date=new Date(board.day+'T12:00:00+01:00').toLocaleDateString('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'long'});
  const count=(board.groups||[]).reduce((n,g)=>n+g.picks.length,0);
  let html='<div class="row"><strong class="gold">Avis du '+esc(date)+'</strong><span class="fine">'+count+' / 6 choix</span></div>';
  const p=board.performance;
  if(p)html+='<div class="opinion-performance"><h3>Taux officiel de l’application</h3><div class="analysis"><div class="stat"><span>Réussite</span><b>'+(p.success_pct===null?'—':esc(p.success_pct)+' %')+'</b></div><div class="stat"><span>Gagnés</span><b>'+esc(p.won)+'</b></div><div class="stat"><span>Perdus</span><b>'+esc(p.lost)+'</b></div><div class="stat"><span>En attente</span><b>'+esc(p.pending)+'</b></div></div>'+(p.success_pct===null?message('Le taux apparaîtra après les premiers résultats vérifiés.'):'')+'</div>';
  if(board.status==='preparing')html+=message('Je prépare mes choix du jour. Cette page se met à jour automatiquement.');
  else if(count<6)html+=message('Sélection partielle : pas assez de rencontres à venir avec les données et probabilités requises. Je ne force aucun choix pour remplir les cases.');
  if(board.stale&&board.status!=='preparing')html+=message('Actualisation en retard : les choix restent ceux publiés à l’heure indiquée.');
  html+=(board.groups||[]).map(group=>'<div class="opinion-group"><h3>'+esc(group.title)+'</h3>'+group.picks.map(p=>{
   const m=p.match, state={won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé / non réglable',pending:new Date(m.date)>new Date()?'À venir':'Résultat à vérifier'}[p.status];
   return '<article class="opinion-pick"><div class="row"><strong>'+esc(m.home.name)+' – '+esc(m.away.name)+'</strong><span class="opinion-prob">'+esc(p.probability)+' %</span></div><p class="gold">'+esc(p.market_label)+'</p><p class="fine">'+esc(new Date(m.date).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+' · '+esc(m.league)+' · <span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(state)+'</span>'+(p.home_score!==null?' · '+esc(p.home_score)+' – '+esc(p.away_score):'')+'</p><details><summary>Pourquoi ce choix ?</summary><p>'+esc(p.rationale)+'</p><p class="fine">Buts attendus par le modèle : '+esc(p.expected_goals.home)+' – '+esc(p.expected_goals.away)+'. Estimation publiée à '+esc(new Date(p.published_at).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+'.</p><button type="button" class="day" data-opinion-match="'+esc(m.id)+'">OUVRIR LE MATCH</button></details>'+teamOdds(p)+'</article>';
  }).join('')+(!group.picks.length?message('Aucun choix admissible pour le moment.'):'')+'</div>').join('');
  html+=message('Prudent ne signifie pas certain. Les 6 choix sont des sélections individuelles, pas un combiné garanti.');
  if(board.checked_at)html+=message('Dernière vérification : '+new Date(board.checked_at).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'})+' · actualisation automatique.');
  if(board.source_errors||board.result_source_errors)html+=message('Certaines sources sont indisponibles : sélection ou résultats potentiellement incomplets.');
  html+='<details><summary>Méthode et actualisation</summary>'+message(board.method)+message(board.scope)+message(board.update_note)+'</details>';
  for(const id of targets){
   const target=document.getElementById(id);if(!target)continue;target.innerHTML=html;
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
