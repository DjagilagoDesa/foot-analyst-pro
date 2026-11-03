/* Personal ticket builder: reuses authenticated, metered match analyses. */
function ticketMarkets(markets){
 const values={...markets};
 for(const [under,over] of [['under_1_5','over_1_5'],['under_2_5','over_2_5'],['btts_no','btts']]){
  if(!Number.isFinite(values[under])&&Number.isFinite(values[over]))values[under]=Math.round((100-values[over])*10)/10;
 }
 return values;
}
function ticketSelection(markets, profile, odds){
 markets=ticketMarkets(markets);
 const jointKeys=['home_or_draw','away_or_draw'].flatMap(side=>['btts','btts_no','over_1_5','over_2_5','under_1_5','under_2_5'].map(goal=>side+'_and_'+goal));
 const allowed=profile==='mixed'?jointKeys:['home','away','home_or_draw','away_or_draw','over_1_5','over_2_5','under_1_5','under_2_5','btts','btts_no'];
 const options=allowed.filter(k=>Number.isFinite(markets[k])&&markets[k]>0&&markets[k]<100).map(k=>({market:k,probability:markets[k]}));
 if(!options.length)return null;
 const bands={prudent:[75,100],balanced:[60,80],offensive:[45,65],mixed:[55,85]};
 const [min,max]=bands[profile]||bands.balanced;
 const pool=options.filter(x=>x.probability>=min&&x.probability<=max);
 const choices=pool.length?pool:options;
 return (window.OddsTicket?.rank(choices,odds)||choices.sort((a,b)=>b.probability-a.probability||allowed.indexOf(a.market)-allowed.indexOf(b.market)))[0];
}
/* Re-check the source calendar once per league/date before finalizing a ticket. */
function ticketAssertFuture(results){
 const invalid=results.find(r=>{
  const m=r.match;
  return m.state!=='pre'||m.completed||!Number.isFinite(Date.parse(m.date))||Date.parse(m.date)<=Date.now()||/POSTPONED|CANCEL|ABANDON|SUSPEND/i.test(m.status_name||'');
 });
 if(invalid)throw Error('Ticket à actualiser : '+invalid.match.home.name+' – '+invalid.match.away.name+'.');
}
async function ticketVerifyFixtures(results){
 if(!results.length)throw Error('Aucune rencontre à vérifier.');
 ticketAssertFuture(results);
 const groups=new Map();
 for(const r of results){
  const m=r.match;
  if(typeof m.league!=='string'||!m.league||![m.id,m.home?.id,m.away?.id].every(id=>/^\d+$/.test(String(id))))throw Error('Rencontre non vérifiable.');
  const key=m.league+'|'+new Date(m.date).toISOString().slice(0,10);
  if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);
 }
 try{
  await Promise.all([...groups.entries()].map(async([key,rows])=>{
   const [league,date]=key.split('|');
   const feed=await api('/api/fixtures?league='+encodeURIComponent(league)+'&date='+encodeURIComponent(date),45000);
   if(feed.partial||!Array.isArray(feed.events))throw Error('source_unavailable');
   for(const r of rows){
    const m=r.match;
    const found=feed.events.filter(e=>e.league===m.league&&String(e.id)===String(m.id));
    if(found.length!==1)throw Error('match_not_verified');
    const current=found[0];
    if(String(current.home?.id)!==String(m.home.id)||String(current.away?.id)!==String(m.away.id)||Date.parse(current.date)!==Date.parse(m.date))throw Error('fixture_changed');
    ticketAssertFuture([{match:current}]);
   }
  }));
 }catch{throw Error('Ticket non finalisé : une rencontre a changé ou ne peut pas être vérifiée. Réessaie.');}
 // Source calls or a suspended phone tab can cross the kickoff boundary.
 ticketAssertFuture(results);
}
(()=>{
 const el=id=>document.getElementById(id),esc=escapeHtml;
 let chosen=[],fixtures=[],busy=false,loadToken=0;
 const labels={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux équipes marquent'};
 const key=m=>String(m.id),name=m=>m.home.name+' – '+m.away.name;
 const upcoming=m=>m.state==='pre'&&!m.completed&&new Date(m.date).getTime()>Date.now()&&!/POSTPONED|CANCELED|CANCELLED|ABANDONED|SUSPENDED/.test(m.status_name||'');
 const message=(s,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(s)+'</div>';
 function draw(){
  el('customCount').textContent=chosen.length+' match(s) sélectionné(s) · 10 maximum';
  el('customChosen').innerHTML=chosen.length?chosen.map((m,i)=>'<div class="panel ticket-picked"><strong>'+esc(name(m))+'</strong><p class="fine">'+esc(dateText(m.date))+' · '+esc(m.league)+'</p><button type="button" class="day" data-remove="'+i+'" '+(busy?'disabled':'')+'>RETIRER</button></div>').join(''):message('Ajoute au moins deux matchs pour construire ton combiné.');
  el('customChosen').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{if(busy)return;chosen.splice(Number(b.dataset.remove),1);el('customTicketResult').innerHTML='';draw();drawFixtures();});
  const button=el('customGenerate');
  button.disabled=busy;
  button.textContent=busy?'ANALYSE EN COURS…':chosen.length<2?'AJOUTER '+(2-chosen.length)+' MATCH'+(chosen.length===0?'S':'')+' POUR CRÉER MON TICKET':'ANALYSER MES '+chosen.length+' MATCHS ET CRÉER LE TICKET';
  button.setAttribute('aria-describedby','customCount');
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
  if(busy)return;
  if(chosen.length<2){
   el('customNotice').innerHTML=message('Ajoute encore '+(2-chosen.length)+' match'+(chosen.length===0?'s':'')+' avec le bouton ＋, puis lance la création du ticket.');
   el('customNotice').scrollIntoView({behavior:'smooth',block:'center'});
   if(!fixtures.length)await load();
   return;
  }
  busy=true;draw();drawFixtures();el('customNotice').innerHTML='';
  const target=el('customTicketResult'),batch=chosen.slice(),profile=el('customProfile').value,results=[],failures=[];
  try{
   // Preview entitlement before consuming any remaining trials.
   await window.Accounts.refresh(false);
   for(let i=0;i<batch.length;i++){
    const m=batch[i];target.innerHTML=message('Analyse '+(i+1)+' / '+batch.length+' : '+name(m)+'…');
    if(!upcoming(m)){failures.push(name(m)+' : le match a commencé ou n’est plus confirmé.');continue;}
    try{
    const d=await window.Accounts.request('/api/analyze',{league:m.league,home_id:m.home.id,away_id:m.away.id,event_id:m.id,label:name(m)});
    if(d.status==='locked'){renderLockedAnalysis(target);el('customNotice').innerHTML=message('Premium est nécessaire pour poursuivre. Les analyses déjà obtenues restent dans ton historique.');return;}
    if(d.status!=='ok'){failures.push(name(m)+' : '+(d.message||'données insuffisantes'));continue;}
    d.market_odds=await window.OddsTicket?.load(m);
    const leg=ticketSelection(d.prediction?.markets||{},profile,d.market_odds);
    if(!leg){failures.push(name(m)+' : aucune probabilité exploitable.');continue;}
    results.push({match:m,analysis:d,...leg});
    }catch(error){if(error.code==='login_required')throw error;failures.push(name(m)+' : '+error.message);}
   }
   if(failures.length){target.innerHTML=message('Ticket incomplet : aucun combiné global n’est présenté, car tous tes matchs n’ont pas pu être analysés.',true)+failures.map(x=>message(x,true)).join('')+message(results.length+' analyse(s) disponible(s) dans ton historique. Retire ou remplace les rencontres signalées puis réessaie.');return;}
   target.innerHTML=message('Vérification des matchs…');
   await ticketVerifyFixtures(results);
   const untracked=await window.Tracking.record(results.map(r=>({analysis:r.analysis,market:r.market})));
   await ticketVerifyFixtures(results);
   if(untracked)el('customNotice').innerHTML=message(untracked+' sélection(s) non enregistrée(s) dans le suivi : rencontre non vérifiable, déjà commencée ou ancienne analyse.');
   let joint=results.reduce((v,r)=>v*r.probability/100,1);
   const repeated=new Set(),teams=new Set();for(const r of results){for(const id of [r.match.home.id,r.match.away.id]){if(teams.has(String(id)))repeated.add(String(id));teams.add(String(id));}}
   const profileName={prudent:'Prudent',balanced:'Équilibré',offensive:'Offensif',mixed:'Double chance & buts'}[profile];
   const limited=results.filter(r=>r.analysis.analysis_basis&&['home','away'].some(side=>r.analysis.analysis_basis[side].sample<10));
   target.innerHTML=(limited.length?message('Échantillon limité pour '+limited.map(r=>name(r.match)).join(', ')+'. Les probabilités et le combiné sont particulièrement incertains ; consulte les bases de calcul dans les analyses.'):'' )+'<div class="panel premium"><h2>Ton ticket personnalisé · '+esc(profileName)+'</h2>'+results.map((r,i)=>'<div class="panel"><h3>'+esc((i+1)+'. '+name(r.match))+'</h3><p class="gold"><strong>'+esc(labels[r.market])+'</strong></p><p>Probabilité du modèle : <strong>'+esc(r.probability)+' %</strong></p><details><summary>Pourquoi ce choix ? Voir l’analyse du match</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+
    (repeated.size?message('Plusieurs rencontres concernent la même équipe : leur dépendance empêche de présenter une probabilité combinée crédible. Les sélections sont affichées séparément.'):message('Estimation combinée : '+(joint*100).toFixed(2).replace('.',',')+' % · Cote théorique : '+(1/joint).toFixed(2).replace('.',',')+'.'))+
    '</div>';
   window.OddsTicket?.mount(target,results);
  }catch(e){target.innerHTML=message('Ticket non finalisé : '+e.message,true)+message('Les analyses déjà terminées restent accessibles dans ton historique.');if(e.code==='login_required')window.Accounts.needsLogin(target);}
  finally{busy=false;draw();drawFixtures();await window.Accounts.afterAnalysis();}
 };
 window.PersonalTicket={getMatches:()=>chosen.slice()};
 const originalOpen=openMatch;
 openMatch=function(m,from){originalOpen(m,from);const button=document.createElement('button');button.type='button';button.className='day';button.textContent='＋ AJOUTER À MON TICKET';button.style.cssText='width:100%;max-width:none;margin:12px 0';button.onclick=()=>{show('dailyTickets');add(m);};el('detailContent').prepend(button);};
 draw();
})();





