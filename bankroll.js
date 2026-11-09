/* Personal budget: proposals never debit money until the user confirms a played ticket. */
(()=>{
 const root=document.getElementById('bankrollContent');if(!root)return;
 const esc=escapeHtml,money=n=>(n/100).toLocaleString('fr-FR',{style:'currency',currency:'EUR'});
 let generation=0,historyLimit=5,draft=[],fixtures=[],requestKey=newKey(),selectedDay='',draftStake=null,bookmaker=null;
 function newKey(){return globalThis.crypto?.randomUUID?.()||Date.now()+'-'+Math.random().toString(36).slice(2);}
 async function read(){const r=await fetch('/api/bankroll',{credentials:'same-origin',headers:{Accept:'application/json'}});const d=await r.json();if(!r.ok)throw Error(d.message||'Bankroll indisponible');return d;}
 function form(d){return '<details class="panel" '+(!d.configured?'open':'')+'><summary>Mon budget et mes mises</summary><form data-config><label>Budget de départ (€)<input class="day" name="initial" type="number" min="1" max="1000000" step="0.01" required value="'+(d.configured?d.initial_cents/100:100)+'" '+(d.bets?.length?'readonly':'')+'></label><label>Mise maximale par ticket<select class="day" name="risk"><option value="50">0,5 %</option><option value="100">1 %</option><option value="200">2 %</option><option value="300">3 %</option><option value="400">4 %</option><option value="500">5 %</option><option value="600">6 %</option><option value="700">7 %</option><option value="800">8 %</option><option value="900">9 %</option><option value="1000">10 %</option></select></label><button class="btn">ENREGISTRER</button></form></details>';}
 function legMatch(l){
  const parts=String(l.label||'').split(' – '),source=l.match;
  return source||{id:l.event_id,league:l.league,date:l.date||'',home:{id:l.home_id,name:l.home_name||parts[0]||'Équipe domicile',badge:l.home_badge||''},away:{id:l.away_id,name:l.away_name||parts.slice(1).join(' – ')||'Équipe extérieure',badge:l.away_badge||''},state:l.match_state||(l.status==='pending'?'pre':'post'),completed:!!l.match_completed,home_score:l.home_score??l.live_home_score,away_score:l.away_score??l.live_away_score,status_name:l.match_status||''};
 }
 function crest(team){
  const initials=String(team.name||'').split(/\s+/).slice(0,2).map(w=>w[0]||'').join('');
  const safe=typeof team.badge==='string'&&/^https:\/\//.test(team.badge);
  return (safe?'<img src="'+esc(team.badge)+'" alt="Écusson '+esc(team.name)+'" loading="lazy" onerror="this.hidden=true;this.nextElementSibling.hidden=false">':'')+'<span class="bank-crest-fallback" '+(safe?'hidden':'')+'>'+esc(initials)+'</span>';
 }
 function teamsMarkup(m){
  const live=m.state==='in'||m.state==='post'||m.completed,score=live&&m.home_score!=null&&m.away_score!=null?esc(m.home_score)+' – '+esc(m.away_score):'VS';
  return '<span class="bank-team">'+crest(m.home)+'<strong>'+esc(m.home.name)+'</strong></span><span class="bank-vs">'+score+'</span><span class="bank-team">'+crest(m.away)+'<strong>'+esc(m.away.name)+'</strong></span>';
 }
 function gameHeader(l,attributes){const m=legMatch(l);return '<button type="button" class="bank-game" '+attributes+' aria-label="Voir '+esc(m.home.name+' – '+m.away.name)+'">'+teamsMarkup(m)+'</button>';}
 function pickName(l){const m=legMatch(l);return l.market==='home'?'Victoire '+m.home.name:l.market==='away'?'Victoire '+m.away.name:labels[l.market]||l.market;}
 function savedCard(l,bi,li){
  const status=({won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé',pending:'En cours'})[l.status]||'En cours',m=legMatch(l),date=m.date?new Date(m.date):null;
  const when=date&&Number.isFinite(date.getTime())?date.toLocaleString('fr-FR',{timeZone:'Europe/Paris',day:'numeric',month:'short',hour:'2-digit',minute:'2-digit'}):'';
  return '<article class="bank-saved-card">'+(when?'<div class="bank-game-date">'+esc(when)+'</div>':'')+gameHeader(l,'data-saved-match="'+bi+':'+li+'"')+'<div class="bank-pick-bar"><strong>'+esc(pickName(l))+'</strong><b class="bank-price">'+esc(l.odds)+'</b></div><div class="bank-result '+(l.status==='won'?'result-won':l.status==='lost'?'result-lost':'')+'">'+esc(status)+'</div></article>';
 }
 async function load(){
  const id=++generation;root.innerHTML='<div class="message">Chargement de la bankroll…</div>';
  try{const d=await read();if(id!==generation)return;
   const summary=d.configured?'<div class="panel bankroll-summary"><div><span>Disponible</span><strong>'+money(d.available_cents)+'</strong></div><div><span>Gains / pertes</span><strong class="'+(d.profit_cents<0?'result-lost':'result-won')+'">'+money(d.profit_cents)+'</strong></div></div>':'';
   const history=d.configured?'<details class="panel"><summary>Mes tickets · '+d.bets.filter(b=>b.payout_cents!==null&&b.payout_cents>b.stake_cents).length+' gagnés / '+d.bets.filter(b=>b.payout_cents!==null&&b.payout_cents<b.stake_cents).length+' perdus</summary>'+(d.bets.length?d.bets.slice(0,historyLimit).map((b,i)=>'<details><summary>'+esc(b.title)+' · '+money(b.stake_cents)+' · '+(b.payout_cents===null?'En cours':(b.payout_cents>b.stake_cents?'✓ Gagné':b.payout_cents<b.stake_cents?'✗ Perdu':'Annulé')+' · '+money(b.payout_cents-b.stake_cents))+'</summary>'+(b.automatic?b.selections.map((l,j)=>savedCard(l,i,j)).join('')+(b.payout_cents===null?'':'Retour : '+money(b.payout_cents)):(b.payout_cents===null?'<form data-settle="'+i+'"><label>Retour réel (€)<input class="day" name="payout" type="number" min="0" max="1000000" step="0.01" required></label><button class="day">ENREGISTRER</button></form>':'Retour : '+money(b.payout_cents)))+'</details>').join(''):'Aucun ticket enregistré.')+(d.bets.length>historyLimit?'<button type="button" class="day" data-history-more>VOIR PLUS</button>':'')+'</details>':'';
   const editor=d.configured?'<section class="panel" data-add><h2>Mon ticket</h2><form data-bet><div data-draft></div><details data-picker open><summary>＋ Ajouter un match</summary><input class="day" type="search" data-filter placeholder="Rechercher une équipe"><div class="bankroll-toolbar"><input class="day" data-date type="date" aria-label="Date des matchs"><button type="button" class="day" data-load aria-label="Actualiser les matchs">↻</button></div><div class="bankroll-matches" data-fixtures></div></details><label>Mise (€)<input class="day" name="stake" type="number" min="0.01" step="0.01" max="'+d.available_cents/100+'" required></label><div data-potential role="status"></div><button class="btn">ENREGISTRER MON TICKET</button></form><p data-add-feedback role="status"></p></section>':'';
   root.innerHTML=summary+editor+history+form(d)+'<div data-feedback role="status"></div>';
   root.querySelector('[name="risk"]').value=String(d.risk_bps||100);
   const feedback=root.querySelector('[data-feedback]');
   if(d.configured)bindAdd(d,id);
   root.querySelectorAll('[data-saved-match]').forEach(button=>button.onclick=()=>{const [bi,li]=button.dataset.savedMatch.split(':').map(Number);const m=legMatch(d.bets[bi].selections[li]);if(!m.date){feedback.textContent='La fiche de ce match est temporairement indisponible.';return;}openMatch(m,'bankroll');});
   const more=root.querySelector('[data-history-more]');if(more)more.onclick=()=>{historyLimit+=5;load();};
   async function submit(event,path,data){event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{await window.Accounts.request(path,data);await load();}catch(e){feedback.textContent=e.message;button.disabled=false;}}
   root.querySelector('[data-config]').onsubmit=e=>submit(e,'/api/bankroll',{initial:e.target.elements.initial.value,risk_bps:Number(e.target.elements.risk.value)});
   root.querySelectorAll('[data-settle]').forEach(f=>f.onsubmit=e=>submit(e,'/api/bankroll/settle',{ticket_id:d.bets[Number(f.dataset.settle)].ticket_id,payout:f.elements.payout.value}));
  }catch(e){if(id===generation)root.textContent=e.message;}
 }
 const labels={home:'Victoire domicile',draw:'Match nul',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts:'Les deux équipes marquent',btts_no:'Les deux équipes marquent : non'};
 for(const [side,name] of [['home_or_draw','1X'],['away_or_draw','X2']])for(const [goal,label] of [['btts','les deux équipes marquent'],['btts_no','les deux équipes marquent : non'],['over_1_5','plus de 1,5 but'],['over_2_5','plus de 2,5 buts'],['under_1_5','moins de 1,5 but'],['under_2_5','moins de 2,5 buts']])labels[side+'_and_'+goal]=name+' + '+label;
 function bindAdd(d,id){
  const get=s=>root.querySelector(s),date=get('[data-date]'),list=get('[data-fixtures]'),chosen=get('[data-draft]'),feedback=get('[data-add-feedback]'),form=get('[data-bet]');
  date.value=selectedDay||new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});form.elements.stake.value=draftStake??d.suggested_cents/100;
  let visible=5;
  const name=(l,k)=>k==='home'?'Victoire '+l.home_name:k==='away'?'Victoire '+l.away_name:labels[k]||k;
  function potential(){
   const amount=Number(form.elements.stake.value),ready=draft.length&&draft.every(l=>Number(l.odds)>1&&!l.loading),total=draft.reduce((v,l)=>v*Number(l.odds||0),1);
   get('[data-potential]').textContent=ready?'Cote '+total.toFixed(2).replace('.',',')+' · Retour potentiel '+money(Math.round(amount*100*total)):'';
   form.querySelector('.btn').disabled=!ready;
  }
  function draw(){
   chosen.innerHTML=draft.map((l,i)=>'<div class="bankroll-pick"><div class="bankroll-line">'+gameHeader(l,'data-draft-match="'+i+'"')+'<button type="button" class="day" data-remove="'+i+'" aria-label="Retirer '+esc(l.label)+'">×</button></div><select class="day" data-market="'+i+'" aria-label="Mon pari pour '+esc(l.label)+'">'+Object.keys(labels).map(k=>'<option value="'+k+'">'+esc(name(l,k))+'</option>').join('')+'</select><span data-quote>'+esc(l.loading?'Recherche de la cote…':l.odds?'Cote '+String(l.odds).replace('.',',')+(l.bookmaker?' · '+l.bookmaker:''):'Cote indisponible')+'</span>'+(!l.loading?'<details class="bankroll-adjust"><summary>'+(!l.odds?'Saisir ma cote':'Modifier la cote')+'</summary><input class="day" data-odds="'+i+'" aria-label="Cote réellement jouée" type="number" min="1.01" max="10000" step="0.01" value="'+esc(l.odds||'')+'"></details>':'')+'</div>').join('');
   chosen.querySelectorAll('[data-draft-match]').forEach(button=>button.onclick=()=>openMatch(legMatch(draft[Number(button.dataset.draftMatch)]),'bankroll'));
   chosen.querySelectorAll('[data-market]').forEach(n=>{n.value=draft[Number(n.dataset.market)].market;n.onchange=()=>{const l=draft[Number(n.dataset.market)];l.market=n.value;l.odds='';requestKey=newKey();quote(l);};});
   chosen.querySelectorAll('[data-odds]').forEach(n=>n.oninput=()=>{const l=draft[Number(n.dataset.odds)];l.odds=n.value;l.automatic_odds=false;l.bookmaker='Cote saisie';n.closest('.bankroll-pick').querySelector('[data-quote]').textContent='Cote '+String(l.odds).replace('.',',')+' · Cote saisie';requestKey=newKey();potential();});
   chosen.querySelectorAll('[data-remove]').forEach(n=>n.onclick=()=>{draft.splice(Number(n.dataset.remove),1);if(!draft.length){bookmaker=null;get('[data-picker]').open=true;}requestKey=newKey();draw();});potential();
  }
  async function quote(l,initial=false){
   l.loading=true;draw();const version=l.quoteVersion=(l.quoteVersion||0)+1;
   let data;try{data=await window.OddsTicket?.load(l.match)||{books:[]};}catch{data={books:[]};}
   if(version!==l.quoteVersion||!draft.includes(l))return;
   const book=data.books?.find(b=>!bookmaker||b.bookmaker===bookmaker);
   const quoted=k=>window.OddsTicket?.price(data,k,book?.bookmaker);
   if(initial&&!(Number(quoted(l.market))>1))l.market=Object.keys(labels).find(k=>k.startsWith('over_')&&Number(quoted(k))>1)||Object.keys(labels).find(k=>Number(quoted(k))>1)||l.market;
   const price=book?quoted(l.market):undefined;
   if(Number.isFinite(price)&&price>1){if(!bookmaker)bookmaker=book.bookmaker;l.odds=price.toFixed(2);l.bookmaker=book.bookmaker;l.expires_at=data.expires_at;l.automatic_odds=true;}
   else{l.odds='';l.bookmaker='';l.automatic_odds=false;}
   l.loading=false;requestKey=newKey();if(id===generation)draw();
  }
  function addMatch(m){
   if(draft.length>=8){feedback.textContent='8 matchs maximum.';return;}
   if(draft.some(l=>l.event_id===String(m.id)&&l.league===m.league)){feedback.textContent='Match déjà ajouté.';return;}
   const l={event_id:String(m.id),league:m.league,home_id:String(m.home.id),away_id:String(m.away.id),home_name:m.home.name,away_name:m.away.name,label:m.home.name+' – '+m.away.name,market:'over_2_5',odds:'',match:m};draft.push(l);get('[data-picker]').open=false;feedback.textContent='';quote(l,true);
  }
  function renderFixtures(){
   const q=get('[data-filter]').value.toLocaleLowerCase('fr'),filtered=fixtures.filter(m=>(m.home.name+' '+m.away.name).toLocaleLowerCase('fr').includes(q));list.innerHTML='';
   if(!filtered.length){list.textContent=q?'Aucun match trouvé.':'Aucun match disponible.';return;}
   filtered.slice(0,visible).forEach(m=>{
    const row=document.createElement('div');row.className='bankroll-fixture bankroll-line';
    const label=document.createElement('button');label.type='button';label.className='bankroll-match-link';label.innerHTML=teamsMarkup(m);label.classList.add('bank-game');label.onclick=()=>openMatch(m,'bankroll');
    const button=document.createElement('button');button.type='button';button.className='day';button.textContent=draft.some(l=>l.event_id===String(m.id)&&l.league===m.league)?'✓':'＋';button.setAttribute('aria-label','Ajouter '+m.home.name+' – '+m.away.name);button.onclick=()=>addMatch(m);row.append(label,button);list.appendChild(row);
   });
   if(filtered.length>visible){const more=document.createElement('button');more.type='button';more.className='day';more.textContent='VOIR PLUS';more.onclick=()=>{visible+=5;renderFixtures();};list.appendChild(more);}
  }
  let feedVersion=0;
  async function loadFixtures(){const button=get('[data-load]'),version=++feedVersion;selectedDay=date.value;button.disabled=true;list.textContent='Chargement…';try{const data=await api('/api/fixtures?date='+encodeURIComponent(date.value),45000);if(id!==generation||version!==feedVersion)return;fixtures=(data.events||[]).filter(m=>!m.completed&&m.state==='pre');visible=5;renderFixtures();}catch(error){if(id===generation&&version===feedVersion)list.textContent=error.message;}finally{if(version===feedVersion)button.disabled=false;}}
  get('[data-load]').onclick=loadFixtures;date.onchange=()=>{fixtures=[];loadFixtures();};get('[data-filter]').oninput=()=>{visible=5;renderFixtures();};
  get('[data-picker]').ontoggle=()=>{if(get('[data-picker]').open)renderFixtures();};
  form.elements.stake.oninput=()=>{draftStake=form.elements.stake.value;potential();};
  form.onsubmit=async e=>{e.preventDefault();if(!draft.length||draft.some(l=>l.loading||!(Number(l.odds)>1))){feedback.textContent='Une cote manque sur ton ticket.';return;}
   const expired=draft.filter(l=>l.automatic_odds&&Date.parse(l.expires_at)<=Date.now());
   if(expired.length){await Promise.all(expired.map(l=>quote(l)));feedback.textContent='Cotes actualisées. Vérifie puis enregistre ton ticket.';return;}
   const button=form.querySelector('.btn');button.disabled=true;
   try{await window.Accounts.request('/api/bankroll/manual',{request_key:requestKey,title:draft.length===1?draft[0].label:'Combiné · '+draft.length+' matchs',stake:form.elements.stake.value,selections:draft.map(l=>({event_id:l.event_id,league:l.league,home_id:l.home_id,away_id:l.away_id,market:l.market,odds:l.odds,bookmaker:l.bookmaker,automatic_odds:l.automatic_odds}))});if(id!==generation)return;draft=[];fixtures=[];draftStake=null;bookmaker=null;requestKey=newKey();await load();const message=root.querySelector('[data-feedback]');if(message)message.textContent='Ticket enregistré. Résultats et bankroll suivis automatiquement.';}catch(error){if(id===generation){feedback.textContent=error.message;potential();}}
  };
  draw();get('[data-picker]').open=!draft.length;if(fixtures.length)renderFixtures();else loadFixtures();
  for(const l of draft)if(l.loading)quote(l);
 }
 async function mount(node,ticket){
  if(ticket.status!=='pending')return;const version=generation;
  try{const d=await read();if(version!==generation||!node.isConnected||!d.configured||d.bets.some(b=>b.ticket_id===ticket.id||b.request_key==='archive:'+ticket.id))return;
   const form=document.createElement('form');form.innerHTML=ticket.selections.map((l,i)=>'<p>'+esc(l.label)+'<br><span data-price-label="'+i+'">Recherche de la cote…</span></p><details><summary>Modifier la cote</summary><input class="day" data-price="'+i+'" aria-label="Cote jouée pour '+esc(l.label)+'" type="number" min="1.01" max="10000" step="0.01"></details>').join('')+'<label>Mise (€)<input class="day" name="stake" type="number" min="0.01" max="'+d.available_cents/100+'" step="0.01" value="'+d.suggested_cents/100+'" required></label><button class="day" disabled>ENREGISTRER DANS MA BANKROLL</button><p data-feedback role="status"></p>';node.appendChild(form);
   const inputs=[...form.querySelectorAll('[data-price]')],button=form.querySelector('button');
   const valid=()=>inputs.every(n=>Number(n.value)>1)&&Number(form.elements.stake.value)>0;
   form.oninput=()=>{button.disabled=!valid();};
   form.onsubmit=async e=>{e.preventDefault();if(!valid())return;button.disabled=true;try{await window.Accounts.request('/api/bankroll/bets',{ticket_id:ticket.id,stake:form.elements.stake.value,odds:inputs.map(n=>n.value)});form.textContent='Ticket enregistré. Suivi automatique activé.';await load();}catch(error){form.querySelector('[data-feedback]').textContent=error.message;button.disabled=!valid();}};
   const data=await Promise.all(ticket.selections.map(async l=>{if(!l.league||!l.home_id||!l.away_id)return {books:[]};try{return await window.OddsTicket?.load({league:l.league,id:l.event_id,home:{id:l.home_id},away:{id:l.away_id},date:new Date(l.starts_at*1000).toISOString()})||{books:[]};}catch{return {books:[]};}}));
   if(!form.isConnected||version!==generation)return;
   const book=data[0]?.books?.[0]?.bookmaker;
   inputs.forEach((n,i)=>{const value=book?window.OddsTicket?.price(data[i],ticket.selections[i].market,book):undefined;n.value=Number.isFinite(value)?value:'';form.querySelector('[data-price-label="'+i+'"]').textContent=value?'Cote '+value+' · '+book:'Cote indisponible';});button.disabled=!valid();
  }catch{/* Account errors are handled by tracking. */}
 }
 window.Bankroll={load,mount,clear(){generation++;draft=[];fixtures=[];selectedDay='';draftStake=null;bookmaker=null;requestKey=newKey();root.textContent='';},async suggest(legs){try{const d=await read();if(!d.configured)return null;const joint=legs.reduce((p,r)=>p*(Number(r.probability)||0)/100,1);const amount=Math.floor(d.suggested_cents*(joint<.25?.25:joint<.5?.5:1));return {stake:(amount/100).toFixed(2),label:'Mise proposée : '+money(amount)+' · montant à risque, pas une probabilité de gain.'};}catch{return null;}}};
 setInterval(()=>{if(!root.closest('section').classList.contains('hidden')&&!document.hidden&&!draft.length&&draftStake===null&&!root.contains(document.activeElement))load();},60000);
})();
