/* Shared daily choices: automatic refresh, no personal analyses consumed. */
(()=>{
 const targets=['homeDailyOpinion'];
 const esc=escapeHtml;
 let busy=false,lastDay='',lastBoard=null,lastSignature='';
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
 function scorerPrice(p){
  const q=p.odds,price=q?.price;
  const pre=p.status==='pending'&&new Date(p.match.date)>new Date();
  const valid=q?.market==='anytime_scorer'&&q.player_id===p.player.id&&q.event_id===String(p.match.id)&&q.kind==='prematch_quote'&&Number.isFinite(price)&&price>1&&(!pre||new Date(q.expires_at)>new Date());
  if(!valid)return '<span aria-label="Cote buteur indisponible">—</span>';
  const label=price.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2});
  return '<strong class="'+({won:'result-won',lost:'result-lost'}[p.status]||'gold')+'" title="'+esc(q.bookmaker+' · '+new Date(q.observed_at).toLocaleString('fr-FR',{timeZone:'Europe/Paris'}))+'" aria-label="'+esc('Cote buteur '+q.bookmaker+' '+label)+'">'+label+'</strong>';
 }
 function scorerTracking(perf){
  let html='<section><h3>Suivi des buteurs</h3>';
  if(perf)html+='<div class="analysis"><div class="stat"><span>Réussite buteurs</span><b>'+(perf.success_pct==null?'—':esc(perf.success_pct)+' %')+'</b></div><div class="stat result-won"><span>Gagnés</span><b>'+esc(perf.won)+'</b></div><div class="stat result-lost"><span>Perdus</span><b>'+esc(perf.lost)+'</b></div></div>';
  return html+'<details data-scorer-history><summary>Historique des buteurs</summary><div data-scorer-history-content></div></details></section>';
 }
 async function historyPage(details,page){
  const content=details.querySelector('[data-scorer-history-content]');
  content.innerHTML=message('Chargement…');
  try{
   const data=await api('/api/daily-opinion/scorer-history?page='+page,15000);
   content.innerHTML=(data.items||[]).map(p=>'<article class="opinion-pick"><div class="row"><strong>'+esc(p.player.name)+'</strong>'+scorerPrice(p)+'</div><p>'+esc(p.match.home.name)+' – '+esc(p.match.away.name)+'</p><div class="row"><span>'+esc(new Date(p.day+'T12:00:00Z').toLocaleDateString('fr-FR',{timeZone:'Europe/Paris'}))+'</span><strong class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc({won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé',pending:'En attente'}[p.status]||'En attente')+'</strong></div></article>').join('')||message('Aucun buteur enregistré.');
   if(page>1||data.has_more)content.innerHTML+='<div class="row">'+(page>1?'<button type="button" class="day" data-history-prev>Précédent</button>':'')+'<span>Page '+esc(page)+'</span>'+(data.has_more?'<button type="button" class="day" data-history-next>Suivant</button>':'')+'</div>';
   const prev=content.querySelector('[data-history-prev]'),next=content.querySelector('[data-history-next]');
   if(prev)prev.onclick=()=>historyPage(details,page-1);if(next)next.onclick=()=>historyPage(details,page+1);
  }catch{content.innerHTML=message('Historique indisponible.')+'<button type="button" class="day" data-history-retry>Réessayer</button>';content.querySelector('button').onclick=()=>historyPage(details,page);}
 }
 const scorerPicks=board=>Array.isArray(board.scorers)?board.scorers:(board.scorer?[board.scorer]:[]);
 function scorerHtml(board){
  const picks=scorerPicks(board);
  return '<div class="opinion-group"><h3>⚽ Les 3 buteurs du jour</h3>'+picks.map(scorerCard).join('')+(picks.length<3?message(picks.length+'/3 buteurs sélectionnés. Recherche des choix restants…'):'')+'</div>'+scorerTracking(board.scorer_performance);
 }
 function addButton(p,kind){
  if(p.status!=='pending'||Date.parse(p.match.date)<=Date.now())return '';
  return '<button type="button" class="day" data-bank-'+kind+'="'+esc(kind==='scorer'?p.player.id:p.match.id)+'">AJOUTER À MON TICKET</button><p data-bank-feedback role="status"></p>';
 }
 function scorerCard(p){
  let html='';
  const state={won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé',pending:new Date(p.match.date)>new Date()?'À venir':'Résultat à vérifier'}[p.status];
  const lineup={reported_starter:'Titulaire indiqué par la source',unconfirmed:'Titularisation à confirmer',bench:'Remplaçant indiqué par la source',not_listed:'Présence à revérifier',unavailable:'Disponibilité à revérifier'}[p.availability]||'Titularisation à confirmer';

  html+='<article class="opinion-pick"><div class="row"><h3>'+esc(p.player.name)+'</h3><span data-scorer-odds="'+esc(p.player.id)+'">'+scorerPrice(p)+'</span></div><p class="gold">'+(p.player.competition_category==='women'?'Buteuse : ':'Buteur : ')+esc(p.player.name)+'</p><p>'+esc(p.match.home.name)+' – '+esc(p.match.away.name)+' · '+esc(new Date(p.match.date).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+'</p><p><span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(state)+'</span></p>';
  if(p.status==='pending')html+='<p>'+esc(lineup)+'</p>';
  html+='<p><strong>'+esc(p.basis.goals)+' buts · '+esc(p.basis.appearances)+' apparitions</strong></p><details><summary>Pourquoi ce buteur ?</summary><p>'+esc(p.rationale)+'</p>';

  html+='<p><a href="'+esc(p.source_url)+'" target="_blank" rel="noopener noreferrer">Voir les données du match</a></p></details><button type="button" class="day" data-scorer-match="'+esc(p.player.id)+'">OUVRIR LE MATCH</button></article>';
  return html.replace('</article>',addButton(p,'scorer')+'</article>');
 }
 function render(board){
  const signature=JSON.stringify(board);if(signature===lastSignature)return;lastSignature=signature;
  lastDay=board.day;lastBoard=board;
  const date=new Date(board.day+'T12:00:00+01:00').toLocaleDateString('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'long'});
  let html='<div class="row"><strong class="gold">Avis du '+esc(date)+'</strong></div>';
  const p=board.performance;
  if(p)html+='<div class="opinion-performance"><h3>Performance</h3><div class="analysis"><div class="stat"><span>Réussite</span><b>'+(p.success_pct===null?'—':esc(p.success_pct)+' %')+'</b></div><div class="stat"><span>Gagnés</span><b>'+esc(p.won)+'</b></div><div class="stat"><span>Perdus</span><b>'+esc(p.lost)+'</b></div><div class="stat"><span>En attente</span><b>'+esc(p.pending)+'</b></div></div>'+'</div>';
  html+='<details data-learning><summary>Bilan et amélioration de l’IA</summary><div data-learning-content></div></details>';
  if(board.status==='preparing')html+=message('Préparation des choix…');
  if(board.stale&&board.status!=='preparing')html+=message('Actualisation en retard.');
  html+=(board.groups||[]).map(group=>'<div class="opinion-group"><h3>'+esc(group.title)+'</h3>'+group.picks.map(p=>{
   const m=p.match, state={won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé / non réglable',pending:new Date(m.date)>new Date()?'À venir':'Résultat à vérifier'}[p.status];
   return '<article class="opinion-pick"><div class="row"><strong>'+esc(m.home.name)+' – '+esc(m.away.name)+'</strong><span class="opinion-prob">'+esc(p.probability)+' %</span></div><p class="gold">'+esc(p.market==='home'?'Victoire '+m.home.name:p.market==='away'?'Victoire '+m.away.name:p.market_label)+'</p><p class="opinion-state">'+esc(new Date(m.date).toLocaleTimeString('fr-FR',{timeZone:'Europe/Paris',hour:'2-digit',minute:'2-digit'}))+' · <span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc(state)+'</span>'+(p.home_score!==null?' · '+esc(p.home_score)+' – '+esc(p.away_score):'')+'</p><details><summary>Pourquoi ce choix ?</summary><p>'+esc(p.rationale)+'</p><button type="button" class="day" data-opinion-match="'+esc(m.id)+'">OUVRIR LE MATCH</button></details>'+addButton(p,'opinion')+teamOdds(p)+'</article>';
  }).join('')+(!group.picks.length?message('Aucun choix admissible pour le moment.'):'')+'</div>').join('');
  html+=scorerHtml(board);
  if(board.source_errors||board.result_source_errors)html+=message('Données partiellement indisponibles.');
  for(const id of targets){
   const target=document.getElementById(id);if(!target)continue;target.innerHTML=html;
   target.querySelectorAll('[data-bank-opinion],[data-bank-scorer]').forEach(button=>button.onclick=async()=>{
    const pick=button.dataset.bankScorer?scorerPicks(board).find(p=>String(p.player.id)===button.dataset.bankScorer):(board.groups||[]).flatMap(g=>g.picks).find(p=>String(p.match.id)===button.dataset.bankOpinion);
    if(!pick)return;button.disabled=true;
    try{await window.Bankroll.addSelection(pick);}catch(error){const feedback=button.closest('article').querySelector('[data-bank-feedback]');if(feedback)feedback.textContent=error.message;}
    finally{button.disabled=false;}
   });
   const learning=target.querySelector('[data-learning]');
   if(learning)learning.ontoggle=async()=>{
    const content=learning.querySelector('[data-learning-content]');if(!learning.open){if(content.dataset.retry){content.innerHTML='';delete content.dataset.retry;}return;}if(content.innerHTML)return;
    content.textContent='Chargement…';
    try{
     const report=await api('/api/daily-opinion/learning',15000);
     const active=(report.rules||[]).filter(r=>r.penalty>0);
     content.innerHTML='<p>'+esc(report.eligible)+' résultats vérifiés · '+esc(report.losses)+' perdus</p><p>'+esc(report.status==='active'?'Les erreurs récurrentes ajustent les prochaines sélections.':'Collecte en cours : au moins '+report.minimum_events+' matchs comparables avant un ajustement.')+'</p>'+
      (active.length?'<p>'+esc([...new Set(active.map(r=>({home:'Victoire domicile',away:'Victoire extérieure',btts:'Les deux équipes marquent',over_2_5:'Plus de 2,5 buts',over_1_5:'Plus de 1,5 but',under_2_5:'Moins de 2,5 buts',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2'})[r.market]||r.market))].join(' · '))+'</p>':'')+
      '<p>Buteurs : '+esc(report.scorer?.eligible||0)+' résultats vérifiés.</p>';
    }catch{content.textContent='Bilan indisponible. Ferme puis rouvre pour réessayer.';content.dataset.retry='true';}
   };
   const history=target.querySelector('[data-scorer-history]');if(history)history.ontoggle=()=>{if(history.open&&!history.querySelector('[data-scorer-history-content]').innerHTML)historyPage(history,1);};
   target.querySelectorAll('[data-scorer-match]').forEach(button=>button.onclick=()=>{const pick=scorerPicks(board).find(p=>String(p.player.id)===button.dataset.scorerMatch);if(pick)openMatch(pick.match,'home');});
   target.querySelectorAll('[data-opinion-match]').forEach(button=>button.onclick=()=>{
    const pick=board.groups.flatMap(g=>g.picks).find(p=>p.match.id===button.dataset.opinionMatch);
    if(pick)openMatch(pick.match,id==='homeDailyOpinion'?'home':'dailyTickets');
   });
  }
 }
 async function load(){
  if(busy)return;
  if(lastDay!==day()){
   lastBoard=null;lastDay=day();lastSignature='';
   for(const id of targets){const target=document.getElementById(id);if(target)target.innerHTML=message('Préparation de mon avis du jour…');}
  }
  busy=true;
  try{
   const board=await api('/api/daily-opinion',15000);render(board);
   for(const pick of scorerPicks(board)){
    if(pick.status!=='pending'||new Date(pick.match.date)<=new Date())continue;
    let quote=null;try{quote=(await api('/api/daily-opinion/scorer-odds?player_id='+encodeURIComponent(pick.player.id)+'&event_id='+encodeURIComponent(pick.match.id),15000)).odds;}catch{}
    const current=lastBoard?.day===board.day?scorerPicks(lastBoard).find(p=>p.player.id===pick.player.id&&String(p.match.id)===String(pick.match.id)):null;
    if(current){
     if(quote)current.odds=quote;
     for(const id of targets){const badges=document.getElementById(id)?.querySelectorAll('[data-scorer-odds]')||[];for(const badge of badges)if(badge.dataset.scorerOdds===String(current.player.id))badge.innerHTML=scorerPrice(current);}
     lastSignature=JSON.stringify(lastBoard);
    }
   }
  }
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
