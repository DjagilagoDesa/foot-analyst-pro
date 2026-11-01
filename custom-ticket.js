/* Personal ticket builder: reuses authenticated, metered match analyses. */
function ticketMarkets(markets){
 const values={...markets};
 for(const [under,over] of [['under_1_5','over_1_5'],['under_2_5','over_2_5'],['btts_no','btts']]){
  if(!Number.isFinite(values[under])&&Number.isFinite(values[over]))values[under]=Math.round((100-values[over])*10)/10;
 }
 return values;
}
function ticketSelection(markets, profile){
 markets=ticketMarkets(markets);
 const allowed=(profile==='mixed'?[]:['home','away']).concat(['home_or_draw','away_or_draw','over_1_5','over_2_5','under_1_5','under_2_5','btts','btts_no']);
 const options=allowed.filter(k=>Number.isFinite(markets[k])&&markets[k]>0&&markets[k]<100).map(k=>({market:k,probability:markets[k]}));
 if(!options.length)return null;
 const bands={prudent:[75,100],balanced:[60,80],offensive:[45,65],mixed:[55,85]};
 const [min,max]=bands[profile]||bands.balanced;
 const pool=options.filter(x=>x.probability>=min&&x.probability<=max);
 return (pool.length?pool:options).sort((a,b)=>b.probability-a.probability||allowed.indexOf(a.market)-allowed.indexOf(b.market))[0];
}
(()=>{
 const el=id=>document.getElementById(id),esc=escapeHtml;
 let chosen=[],fixtures=[],busy=false,loadToken=0;
 const labels={home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux équipes marquent'};
 const key=m=>String(m.id),name=m=>m.home.name+' – '+m.away.name;
 const upcoming=m=>m.state==='pre'&&!m.completed&&new Date(m.date).getTime()>Date.now()&&!/POSTPONED|CANCELED|CANCELLED|ABANDONED|SUSPENDED/.test(m.status_name||'');
 const message=(s,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(s)+'</div>';
 function draw(){
  el('customCount').textContent=chosen.length+' match(s) sélectionné(s) · 10 maximum';
  el('customChosen').innerHTML=chosen.length?chosen.map((m,i)=>'<div class="panel ticket-picked"><strong>'+esc(name(m))+'</strong><p class="fine">'+esc(dateText(m.date))+' · '+esc(m.league)+'</p><button type="button" class="day" data-remove="'+i+'" '+(busy?'disabled':'')+'>RETIRER</button></div>').join(''):message('Ajoute au moins deux matchs pour construire ton combiné.');
  el('customChosen').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{if(busy)return;chosen.splice(Number(b.dataset.remove),1);el('customTicketResult').innerHTML='';draw();drawFixtures();});
  el('customGenerate').disabled=busy||chosen.length<2;
  el('customProfile').disabled=busy;
 }
 function add(m){
  if(busy)return;
  if(!upcoming(m)){el('customNotice').innerHTML=message('Choisis un match confirmé qui n’a pas encore commencé.',true);return;}
  if(chosen.some(x=>key(x)===key(m))){el('customNotice').innerHTML=message('Ce match est déjà dans ton ticket.');return;}
  if(chosen.length>=10){el('customNotice').innerHTML=message('Le ticket contient déjà 10 matchs.',true);return;}
  chosen.push(m);el('customNotice').innerHTML=message(name(m)+' ajouté au ticket.');el('customTicketResult').innerHTML='';draw();drawFixtures();
 }
 function drawFixtures(){
  const q=el('customFilter').value.trim().toLocaleLowerCase('fr');
  const list=fixtures.filter(m=>!q||name(m).toLocaleLowerCase('fr').includes(q));
  el('customFixtures').innerHTML=list.length?list.map(m=>'<button type="button" class="match" data-pick="'+esc(key(m))+'" '+(busy||chosen.some(x=>key(x)===key(m))?'disabled':'')+'>'+badge(m.home.badge,m.home.name)+'<span class="names"><strong>'+esc(name(m))+'</strong><small>'+esc(dateText(m.date))+' · '+esc(m.league)+'</small></span><span class="gold">'+(chosen.some(x=>key(x)===key(m))?'✓':'＋')+'</span></button>').join(''):message('Aucun match à venir dans cette liste. Essaie une autre date ou ajoute un match depuis sa fiche.');
  el('customFixtures').querySelectorAll('[data-pick]').forEach(b=>b.onclick=()=>add(fixtures.find(m=>key(m)===b.dataset.pick)));
 }
 async function load(){
  const token=++loadToken;el('customFixtures').innerHTML=message('Chargement des matchs à venir…');
  try{const d=await api('/api/fixtures?date='+encodeURIComponent(el('customDate').value),45000);if(token!==loadToken)return;fixtures=(d.events||[]).filter(upcoming);drawFixtures();if(d.partial)el('customNotice').innerHTML=message('Calendrier partiel : certaines compétitions sont indisponibles.');}
  catch(e){if(token===loadToken)el('customFixtures').innerHTML=message(e.message,true);}
 }
 el('customDate').value=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
 el('customLoad').onclick=load;el('customDate').onchange=load;el('customFilter').oninput=drawFixtures;
 el('customProfile').onchange=()=>{el('customTicketResult').innerHTML='';};
 el('customGenerate').onclick=async()=>{
  if(busy||chosen.length<2)return;
  busy=true;draw();drawFixtures();el('customNotice').innerHTML='';
  const target=el('customTicketResult'),batch=chosen.slice(),profile=el('customProfile').value,results=[],failures=[];
  try{
   // Preview entitlement before consuming any remaining trials.
   await window.Accounts.refresh(false);
   for(let i=0;i<batch.length;i++){
    const m=batch[i];target.innerHTML=message('Analyse '+(i+1)+' / '+batch.length+' : '+name(m)+'…');
    if(!upcoming(m)){failures.push(name(m)+' : le match a commencé ou n’est plus confirmé.');continue;}
    const d=await window.Accounts.request('/api/analyze',{league:m.league,home_id:m.home.id,away_id:m.away.id,event_id:m.id,label:name(m)});
    if(d.status==='locked'){renderLockedAnalysis(target);el('customNotice').innerHTML=message('Premium est nécessaire pour poursuivre. Les analyses déjà obtenues restent dans ton historique.');return;}
    if(d.status!=='ok'){failures.push(name(m)+' : '+(d.message||'données insuffisantes'));continue;}
    const leg=ticketSelection(d.prediction?.markets||{},profile);
    if(!leg){failures.push(name(m)+' : aucune probabilité exploitable.');continue;}
    results.push({match:m,analysis:d,...leg});
   }
   if(failures.length){target.innerHTML=message('Ticket incomplet : aucun combiné global n’est présenté, car tous tes matchs n’ont pas pu être analysés.',true)+failures.map(x=>message(x,true)).join('')+message(results.length+' analyse(s) disponible(s) dans ton historique. Retire ou remplace les rencontres signalées puis réessaie.');return;}
   const untracked=await window.Tracking.record(results.map(r=>({analysis:r.analysis,market:r.market})));
   if(untracked)el('customNotice').innerHTML=message(untracked+' sélection(s) non enregistrée(s) dans le suivi : rencontre non vérifiable, déjà commencée ou ancienne analyse.');
   let joint=results.reduce((v,r)=>v*r.probability/100,1);
   const repeated=new Set(),teams=new Set();for(const r of results){for(const id of [r.match.home.id,r.match.away.id]){if(teams.has(String(id)))repeated.add(String(id));teams.add(String(id));}}
   const profileName={prudent:'Prudent',balanced:'Équilibré',offensive:'Offensif',mixed:'Double chance & buts'}[profile];
   target.innerHTML='<div class="panel premium"><h2>Ton ticket personnalisé · '+esc(profileName)+'</h2>'+results.map((r,i)=>'<div class="panel"><h3>'+esc((i+1)+'. '+name(r.match))+'</h3><p class="gold"><strong>'+esc(labels[r.market])+'</strong></p><p>Probabilité du modèle : <strong>'+esc(r.probability)+' %</strong></p><p class="fine">Sélection dans la plage du profil choisi lorsqu’elle est disponible ; sinon, choix du marché avec la probabilité la plus élevée. Ce tri n’établit pas la rentabilité d’un pari.</p><details><summary>Pourquoi ce choix ? Voir l’analyse du match</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+
    (repeated.size?message('Plusieurs rencontres concernent la même équipe : leur dépendance empêche de présenter une probabilité combinée crédible. Les sélections sont affichées séparément.'):message('Estimation combinée sous hypothèse d’indépendance : '+(joint*100).toFixed(2).replace('.',',')+' %. Cote équitable théorique : '+(1/joint).toFixed(2).replace('.',',')+'. Ce n’est pas une cote bookmaker.'))+
    '<p class="fine">Une sélection par match. Les matchs peuvent rester dépendants ; le produit des probabilités est une approximation non calibrée. Ajouter des matchs augmente le risque d’échec. Aucune garantie de gain, aucun pari placé par l’application.</p></div>';
  }catch(e){target.innerHTML=message('Ticket non finalisé : '+e.message,true)+message('Les analyses déjà terminées restent accessibles dans ton historique.');if(e.code==='login_required')window.Accounts.needsLogin(target);}
  finally{busy=false;draw();drawFixtures();await window.Accounts.afterAnalysis();}
 };
 const originalOpen=openMatch;
 openMatch=function(m,from){originalOpen(m,from);const button=document.createElement('button');button.type='button';button.className='day';button.textContent='＋ AJOUTER À MON TICKET';button.style.cssText='width:100%;max-width:none;margin:12px 0';button.onclick=()=>{show('dailyTickets');add(m);};el('detailContent').prepend(button);};
 draw();
})();


