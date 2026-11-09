/* Personal budget: proposals never debit money until the user confirms a played ticket. */
(()=>{
 const root=document.getElementById('bankrollContent');if(!root)return;
 const esc=escapeHtml,money=n=>(n/100).toLocaleString('fr-FR',{style:'currency',currency:'EUR'});
 let generation=0,historyLimit=5,draft=[],fixtures=[],requestKey=newKey(),selectedDay='',draftStake=null;
 function newKey(){return globalThis.crypto?.randomUUID?.()||Date.now()+'-'+Math.random().toString(36).slice(2);}
 async function read(){const r=await fetch('/api/bankroll',{credentials:'same-origin',headers:{Accept:'application/json'}});const d=await r.json();if(!r.ok)throw Error(d.message||'Bankroll indisponible');return d;}
 function form(d){return '<details class="panel" '+(!d.configured?'open':'')+'><summary>Mon budget et mes mises</summary><form data-config><label>Budget de départ (€)<input class="day" name="initial" type="number" min="1" max="1000000" step="0.01" required value="'+(d.configured?d.initial_cents/100:100)+'" '+(d.bets?.length?'readonly':'')+'></label><label>Mise maximale par ticket<select class="day" name="risk"><option value="50">0,5 %</option><option value="100">1 %</option><option value="200">2 %</option><option value="300">3 %</option><option value="400">4 %</option><option value="500">5 %</option><option value="600">6 %</option><option value="700">7 %</option><option value="800">8 %</option><option value="900">9 %</option><option value="1000">10 %</option></select></label><button class="btn">ENREGISTRER</button></form></details>';}
 async function load(){
  const id=++generation;root.innerHTML='<div class="message">Chargement de la bankroll…</div>';
  try{const d=await read();if(id!==generation)return;
   root.innerHTML=form(d)+(d.configured?'<div class="panel"><div class="analysis">'+[['Disponible',d.available_cents],['Engagé',d.pending_cents],['Gains / pertes',d.profit_cents],['Total',d.total_cents]].map(([k,v])=>'<div class="stat"><span>'+k+'</span><b>'+money(v)+'</b></div>').join('')+'</div><p>Évolution : '+((d.total_cents-d.initial_cents)/d.initial_cents*100).toFixed(2).replace('.',',')+' %</p><p>Mise maximale actuelle : '+money(d.suggested_cents)+'</p><p>Limite quotidienne : '+((d.daily_limit_bps||500)/100)+' % du budget initial. Aucune hausse pour rattraper une perte.</p></div><div class="panel"><h3>Mes mises jouées</h3>'+(d.bets.length?d.bets.slice(0,historyLimit).map((b,i)=>'<details><summary>'+esc(b.title)+' · '+money(b.stake_cents)+' · '+(b.payout_cents===null?'En attente':money(b.payout_cents-b.stake_cents))+'</summary>'+(b.automatic?b.selections.map(l=>'<div class="message"><strong>'+esc(l.label)+'</strong><p>'+esc(labels[l.market]||l.market)+' · '+esc(l.odds)+'</p><span>'+esc(({won:'✓ Gagné',lost:'✗ Perdu',void:'Annulé',pending:'En attente'})[l.status])+'</span></div>').join('')+(b.payout_cents===null?'Résultat en attente de confirmation.':'Retour calculé : '+money(b.payout_cents)):(b.payout_cents===null?'<form data-settle="'+i+'"><label>Retour réel du bookmaker (€), mise incluse<input class="day" name="payout" type="number" min="0" max="1000000" step="0.01" required placeholder="0 si perdu"></label><button class="day">CONFIRMER LE RETOUR</button></form>':'Retour enregistré : '+money(b.payout_cents)))+'</details>').join(''):'Aucune mise confirmée.')+(d.bets.length>historyLimit?'<button type="button" class="day" data-history-more>VOIR PLUS</button>':'')+'</div>':'')+(d.configured?'<details class="panel" data-add open><summary>＋ Ajouter mes paris joués</summary><label>Date des matchs<input class="day" data-date type="date"></label><button class="day" data-load>ACTUALISER LES MATCHS</button><label>Rechercher une équipe<input class="day" type="search" data-filter placeholder="Marseille, Arsenal…"></label><div class="bankroll-matches" data-fixtures></div><form data-bet><div data-draft></div><label>Mise réellement jouée (€)<input class="day" name="stake" type="number" min="0.01" step="0.01" max="'+d.available_cents/100+'" required></label><div data-potential role="status"></div><button class="btn">ENREGISTRER MON PARI JOUÉ</button></form><p data-add-feedback role="status"></p></details>':'')+'<div data-feedback role="status"></div>';
   root.querySelector('[name="risk"]').value=String(d.risk_bps||100);
   const feedback=root.querySelector('[data-feedback]');
   if(d.configured)bindAdd(d,id);
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
  function potential(){const amount=Number(form.elements.stake.value),total=draft.reduce((v,l)=>v*Number(l.odds||0),1);get('[data-potential]').textContent=draft.length&&amount>0&&total>1?'Retour potentiel : '+money(Math.round(amount*100*total))+' · bénéfice potentiel : '+money(Math.round(amount*100*(total-1))):'';}
  function draw(){
   chosen.innerHTML=draft.map((l,i)=>'<div class="bankroll-pick"><strong>'+esc(l.label)+'</strong><label>Mon pronostic<select class="day" data-market="'+i+'">'+Object.entries(labels).map(([k,v])=>'<option value="'+k+'">'+esc(k==='home'?'Victoire '+l.home_name:k==='away'?'Victoire '+l.away_name:v)+'</option>').join('')+'</select></label><label>Cote jouée<input class="day" data-odds="'+i+'" type="number" min="1.01" max="10000" step="0.01" required value="'+esc(l.odds)+'"></label><button type="button" class="day" data-remove="'+i+'">RETIRER</button></div>').join('');
   chosen.querySelectorAll('[data-market]').forEach(n=>{n.value=draft[Number(n.dataset.market)].market;n.onchange=()=>{draft[Number(n.dataset.market)].market=n.value;requestKey=newKey();};});
   chosen.querySelectorAll('[data-odds]').forEach(n=>n.oninput=()=>{draft[Number(n.dataset.odds)].odds=n.value;requestKey=newKey();potential();});
   chosen.querySelectorAll('[data-remove]').forEach(n=>n.onclick=()=>{draft.splice(Number(n.dataset.remove),1);requestKey=newKey();draw();});
   form.querySelector('.btn').disabled=!draft.length;potential();
  }
  function addMatch(m,market,odds){
   if(draft.length>=8){feedback.textContent='8 matchs maximum par combiné.';return false;}
   if(draft.some(l=>l.event_id===String(m.id)&&l.league===m.league)){feedback.textContent='Ce match est déjà dans ta liste.';return false;}
   draft.push({event_id:String(m.id),league:m.league,home_id:String(m.home.id),away_id:String(m.away.id),home_name:m.home.name,away_name:m.away.name,label:m.home.name+' – '+m.away.name,market,odds});requestKey=newKey();feedback.textContent='Match ajouté à ta liste.';draw();return true;
  }
  function renderFixtures(){
   const q=get('[data-filter]').value.toLocaleLowerCase('fr');list.innerHTML='';
   const filtered=fixtures.filter(m=>(m.home.name+' '+m.away.name).toLocaleLowerCase('fr').includes(q));
   if(!filtered.length){list.textContent=q?'Aucun match trouvé pour cette équipe.':'Aucun match disponible pour cette date.';return;}
   filtered.slice(0,50).forEach(m=>{
    const card=document.createElement('article');card.className='bankroll-fixture';
    card.innerHTML='<strong>'+esc(m.home.name+' – '+m.away.name)+'</strong><label>Le pari que je joue<select class="day" data-fixture-market>'+Object.entries(labels).map(([k,v])=>'<option value="'+k+'">'+esc(k==='home'?'Victoire '+m.home.name:k==='away'?'Victoire '+m.away.name:v)+'</option>').join('')+'</select></label><label>Ma cote<input class="day" data-fixture-odds type="number" min="1.01" max="10000" step="0.01" placeholder="Ex. 1,85"></label><div class="bankroll-actions"><button type="button" class="day" data-view-match>VOIR LE MATCH</button><button type="button" class="btn" data-add-match>＋ AJOUTER À MA LISTE</button></div>';
    const market=card.querySelector('[data-fixture-market]'),odds=card.querySelector('[data-fixture-odds]');market.value='home_or_draw';
    const existing=draft.find(l=>l.event_id===String(m.id)&&l.league===m.league);if(existing){market.value=existing.market;odds.value=existing.odds;}
    card.querySelector('[data-add-match]').onclick=()=>{if(addMatch(m,market.value,odds.value)){chosen.scrollIntoView?.({behavior:'smooth',block:'nearest'});}};
    card.querySelector('[data-view-match]').onclick=()=>{
     const choice=market.value,price=odds.value;openMatch(m,'bankroll');
     const detail=document.getElementById('detailContent'),button=document.createElement('button');button.className='btn';button.type='button';button.textContent='＋ AJOUTER CE PARI À MA BANKROLL';
     button.onclick=()=>{addMatch(m,choice,price);show('bankroll');};detail?.prepend(button);
    };list.appendChild(card);
   });
   if(filtered.length>50){const note=document.createElement('p');note.textContent='50 matchs affichés. Recherche une équipe pour affiner.';list.appendChild(note);}
  }
  let feedVersion=0;
  async function loadFixtures(){const button=get('[data-load]'),version=++feedVersion;selectedDay=date.value;button.disabled=true;list.textContent='Chargement des matchs…';feedback.textContent='';try{const data=await api('/api/fixtures?date='+encodeURIComponent(date.value),45000);if(id!==generation||version!==feedVersion)return;fixtures=(data.events||[]).filter(m=>!m.completed&&['pre','in'].includes(m.state));renderFixtures();if(data.partial)feedback.textContent='Certains championnats restent indisponibles.';}catch(error){if(id===generation&&version===feedVersion){list.textContent='';feedback.textContent=error.message;}}finally{if(version===feedVersion)button.disabled=false;}}
  get('[data-load]').onclick=loadFixtures;date.onchange=()=>{fixtures=[];loadFixtures();};
  get('[data-filter]').oninput=renderFixtures;
  form.elements.stake.oninput=()=>{draftStake=form.elements.stake.value;potential();};
  form.onsubmit=async e=>{e.preventDefault();const button=form.querySelector('.btn');button.disabled=true;try{await window.Accounts.request('/api/bankroll/manual',{request_key:requestKey,title:draft.length===1?draft[0].label:'Combiné · '+draft.length+' matchs',stake:form.elements.stake.value,selections:draft.map(l=>({...l}))});if(id!==generation)return;draft=[];fixtures=[];draftStake=null;requestKey=newKey();await load();}catch(error){if(id===generation){feedback.textContent=error.message;button.disabled=false;}}};
  draw();if(fixtures.length)renderFixtures();else loadFixtures();
 }
 async function mount(node,ticket){
  if(ticket.status!=='pending')return;
  const version=generation;
  try{const d=await read();if(version!==generation||!node.isConnected||!d.configured||d.bets.some(b=>b.ticket_id===ticket.id||b.request_key==='archive:'+ticket.id))return;
   const form=document.createElement('form');form.innerHTML=ticket.selections.map((l,i)=>'<label>'+esc(l.label)+' · cote jouée<input class="day" data-price="'+i+'" type="number" min="1.01" max="10000" step="0.01" required></label>').join('')+'<label>Mise proposée (€)<input class="day" name="stake" type="number" min="0.01" max="'+d.suggested_cents/100+'" step="0.01" value="'+d.suggested_cents/100+'" required></label><button class="day" '+(d.suggested_cents<1?'disabled':'')+'>CONFIRMER COMME JOUÉ</button><p data-feedback role="status"></p>';node.appendChild(form);
   form.onsubmit=async e=>{e.preventDefault();form.querySelector('button').disabled=true;try{await window.Accounts.request('/api/bankroll/bets',{ticket_id:ticket.id,stake:form.elements.stake.value,odds:[...form.querySelectorAll('[data-price]')].map(n=>n.value)});form.textContent='Mise enregistrée dans Ma bankroll.';await load();}catch(error){form.querySelector('[data-feedback]').textContent=error.message;form.querySelector('button').disabled=false;}};
  }catch{/* Account prompt is already handled by tracking. */}
 }
 window.Bankroll={load,mount,clear(){generation++;draft=[];fixtures=[];selectedDay='';draftStake=null;requestKey=newKey();root.textContent='';},async suggest(legs){try{const d=await read();if(!d.configured)return null;const joint=legs.reduce((p,r)=>p*(Number(r.probability)||0)/100,1);const amount=Math.floor(d.suggested_cents*(joint<.25?.25:joint<.5?.5:1));return {stake:(amount/100).toFixed(2),label:'Mise proposée : '+money(amount)+' · montant à risque, pas une probabilité de gain.'};}catch{return null;}}};
 setInterval(()=>{if(!root.closest('section').classList.contains('hidden')&&!document.hidden&&!draft.length&&draftStake===null&&!root.contains(document.activeElement)&&![...root.querySelectorAll('[data-fixture-odds]')].some(n=>n.value))load();},60000);
})();
