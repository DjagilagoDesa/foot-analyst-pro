/* Button-driven ticket creation, powered by the existing football model. */
function builderSelection(markets,risk,type){
 const values=ticketMarkets(markets);
 const types={all:['home','away','home_or_draw','away_or_draw','over_1_5','over_2_5','under_1_5','under_2_5','btts','btts_no'],double:['home_or_draw','away_or_draw'],goals:['over_1_5','over_2_5','under_1_5','under_2_5'],btts:['btts','btts_no'],joint:['home_or_draw','away_or_draw'].flatMap(s=>['btts','btts_no','over_1_5','over_2_5','under_1_5','under_2_5'].map(g=>s+'_and_'+g))};
 const [min,max]=({prudent:[75,100],balanced:[60,80],offensive:[45,65]})[risk]||[60,80];
 const choices=(types[type]||types.all).filter(k=>Number.isFinite(values[k])&&values[k]>=min&&values[k]<=max&&values[k]<100).map(market=>({market,probability:values[market]}));
 return choices.sort((a,b)=>b.probability-a.probability)[0]||null;
}
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 let busy=false,generation=0;
 const labels={home:'Victoire domicile',away:'Victoire extérieur',home_or_draw:'1X',away_or_draw:'X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts:'Les deux équipes marquent : oui',btts_no:'Les deux équipes marquent : non'};
 const label=k=>k.includes('_and_')?k.split('_and_').map(p=>labels[p]||p).join(' + '):labels[k]||k;
 const message=(text,error=false)=>'<div class="message '+(error?'error':'')+'">'+esc(text)+'</div>';
 const upcoming=m=>m.state==='pre'&&!m.completed&&new Date(m.date)>new Date()&&!/POSTPONED|CANCELED|CANCELLED|ABANDONED|SUSPENDED/.test(m.status_name||'');
 get('builderDate').value=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
 function refresh(){const personal=get('builderSource').value==='personal';get('builderCount').disabled=personal||busy;get('builderDate').disabled=personal||busy;get('builderChoose').hidden=!personal;const n=window.PersonalTicket?.getMatches().length||0;get('builderSourceInfo').textContent=personal?n+' match(s) sélectionné(s). Tous seront inclus ; choisis de 2 à 8 matchs.':'L’application étudie les prochaines rencontres de la date choisie, dans les compétitions couvertes.';}
 get('builderSource').onchange=refresh;
 get('builderChoose').onclick=()=>{show('dailyTickets');get('customDate').scrollIntoView({behavior:'smooth',block:'center'});};
 get('builderForm').onsubmit=async e=>{
  e.preventDefault();if(busy)return;busy=true;const run=++generation;
  const target=get('builderResult'),button=get('builderSubmit');button.disabled=true;refresh();
  const personal=get('builderSource').value==='personal',risk=get('builderRisk').value,type=get('builderMarket').value,skipped=[],results=[];
  try{
   let matches=personal?(window.PersonalTicket?.getMatches()||[]):[],count=personal?matches.length:Number(get('builderCount').value),available=0;
   if(count<2||count>8){target.innerHTML=message('Sélectionne de 2 à 8 matchs dans ton ticket personnalisé avant de composer.',true);return;}
   if(!personal){target.innerHTML=message('Recherche des rencontres à venir…');const feed=await api('/api/fixtures?date='+encodeURIComponent(get('builderDate').value),45000);matches=(feed.events||[]).filter(upcoming).sort((a,b)=>a.date.localeCompare(b.date));available=matches.length;matches=matches.slice(0,16);}
   if(matches.length<count){target.innerHTML=message('Pas assez de rencontres à venir retrouvées pour '+count+' matchs. Choisis une autre date ou un ticket plus court.',true);return;}
   await window.Accounts.refresh(false);
   const teams=new Set(),events=new Set();
   for(const match of matches){
    if(run!==generation)return;
    if(!personal&&results.length===count)break;
    const name=match.home.name+' – '+match.away.name;
    if(events.has(String(match.id)))continue;events.add(String(match.id));
    if(!upcoming(match)){skipped.push(name+' : déjà commencé ou non confirmé');continue;}
    if(teams.has(String(match.home.id))||teams.has(String(match.away.id))){skipped.push(name+' : équipe déjà présente dans le combiné');continue;}
    target.innerHTML=message('Composition : '+results.length+' / '+count+' sélections. Analyse de '+name+'…');
    const d=await window.Accounts.request('/api/analyze',{league:match.league,home_id:match.home.id,away_id:match.away.id,event_id:match.id,label:name});
    if(run!==generation)return;
    if(d.status==='locked'){renderLockedAnalysis(target);return;}
    if(d.status!=='ok'){skipped.push(name+' : '+(d.message||'données insuffisantes'));continue;}
    const choice=builderSelection(d.prediction?.markets||{},risk,type);
    if(!choice){skipped.push(name+' : aucun pari ne respecte le profil et le type choisis');continue;}
    results.push({match,analysis:d,...choice});teams.add(String(match.home.id));teams.add(String(match.away.id));
   }
   if(results.length!==count){target.innerHTML=message('Je ne peux pas proposer les '+count+' matchs demandés avec ces critères. '+results.length+' sélection(s) admissible(s) trouvée(s). Aucun ticket incomplet présenté comme terminé.',true)+skipped.map(s=>message(s)).join('')+message('Les analyses terminées sont conservées dans ton historique. Essaie un autre profil, davantage de types de paris ou moins de matchs.');return;}
   const missed=await window.Tracking.record(results.map(r=>({analysis:r.analysis,market:r.market})));
   if(run!==generation)return;
   const joint=results.reduce((p,r)=>p*r.probability/100,1);
   target.innerHTML='<div class="panel premium"><h2>Ton ticket · '+count+' matchs</h2>'+results.map((r,i)=>'<div class="message"><strong>'+esc((i+1)+'. '+r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(label(r.market))+'</p><p>Probabilité du modèle : '+esc(r.probability)+' %</p><details><summary>Analyse, surprises et confrontations</summary>'+renderAnalysisReport(r.analysis)+'</details></div>').join('')+message('Probabilité combinée estimée sous hypothèse d’indépendance : '+(joint*100).toFixed(2).replace('.',',')+' %. Cote équitable théorique : '+(1/joint).toFixed(2).replace('.',',')+' — pas une cote Winamax ou bookmaker.')+(missed?message(missed+' sélection(s) non enregistrée(s) dans le suivi : rencontre non vérifiable, ancienne analyse ou match commencé.'):message('Sélections enregistrées dans Mon suivi IA.'))+'<p class="fine">'+(personal?'Tous les matchs de ta sélection ont été inclus.':esc(available)+' matchs à venir retrouvés ; au maximum 16 étudiés dans l’ordre horaire. Ce périmètre ne garantit pas les meilleurs choix disponibles.')+' Les doubles conditions sur un match sont calculées conjointement. Les probabilités ne garantissent pas le résultat ; les matchs peuvent aussi être dépendants. Aucun pari n’est placé.</p></div>';
  }catch(error){if(run===generation){target.innerHTML=message(error.message,true);if(error.code==='login_required')window.Accounts.needsLogin(target);}}
  finally{busy=false;button.disabled=false;refresh();await window.Accounts.afterAnalysis();}
 };
 window.TicketBuilder={refresh,clear:()=>{generation++;get('builderResult').textContent='';}};
 refresh();
})();
