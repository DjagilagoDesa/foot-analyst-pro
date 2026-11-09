/* Observed prices and a local ticket simulator. No bet or payment is submitted. */
(() => {
 const esc=escapeHtml, cache=new Map(), panels=new WeakMap();
 const labels={home:'Victoire domicile',draw:'Match nul',away:'Victoire extérieur',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',over_3_5:'Plus de 3,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',under_3_5:'Moins de 3,5 buts',btts:'Les deux équipes marquent',btts_no:'Les deux équipes marquent : non'};
 const label=(k,match)=>k.split('_and_').map(x=>x==='home'&&match?.home?.name?'Victoire '+match.home.name:x==='away'&&match?.away?.name?'Victoire '+match.away.name:labels[x]||x).join(' + ');
 const number=v=>{const s=String(v??'').trim();return /^\d+(?:[.,]\d+)?$/.test(s)?Number(s.replace(',','.')):NaN;};
 const fmt=n=>n.toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2});
 const date=v=>new Date(v).toLocaleString('fr-FR',{timeZone:'Europe/Paris'});
 const fresh=data=>!!data&&Date.parse(data.expires_at)>Date.now();
 function calculate(prices,stake){
  if(!prices.length||!Number.isFinite(stake)||stake<=0||stake>1000000||prices.some(p=>!Number.isFinite(p)||p<=1||p>10000))return null;
  const total=prices.reduce((a,b)=>a*b,1),gross=stake*total;
  return Number.isFinite(gross)&&gross<=Number.MAX_SAFE_INTEGER/100?{total,gross,net:gross-stake}:null;
 }
 async function load(match,force=false){
  const key=[match.league,match.id,match.home.id,match.away.id,match.date].join(':');
  const found=cache.get(key);
  if(!force&&found&&Date.now()-found.time<60000&&fresh(found.data))return found.data;
  const params=new URLSearchParams({league:match.league,event_id:match.id,home_id:match.home.id,away_id:match.away.id,date:match.date?.slice(0,10)||''});
  try{const data=await api('/api/odds?'+params,15000);cache.set(key,{time:Date.now(),data});if(cache.size>100)cache.delete(cache.keys().next().value);return data;}
  catch{return {books:[],message:'Cotes indisponibles. Tu peux saisir celles de ton bookmaker.'};}
 }
 function price(data,market,book){return fresh(data)?data.books?.find(b=>!book||b.bookmaker===book)?.markets?.[market]:undefined;}
 function rank(options,data){
  const quoted=options.filter(o=>Number.isFinite(price(data,o.market)));
  if(!quoted.length)return options.sort((a,b)=>b.probability-a.probability);
  return quoted.sort((a,b)=>b.probability*price(data,b.market)-a.probability*price(data,a.market));
 }
 function summary(data,match){
  if(!data.books?.length)return '<p class="fine">'+esc(data.message||'Cotes indisponibles.')+'</p>';
  return data.books.map(b=>'<div class="message" title="'+esc(b.bookmaker+' via ESPN')+'"><div class="analysis">'+Object.entries(b.markets).map(([k,v])=>'<div class="stat"><span>'+esc(k==='home'?match.home.name:k==='away'?match.away.name:label(k))+'</span><b>'+fmt(v)+'</b></div>').join('')+'</div></div>').join('');
 }
 async function matchPanel(match){
  const root=document.getElementById('detailContent');if(!root)return;
  const panel=document.createElement('section');panel.className='panel';panel.innerHTML='<h3>Cotes du match · 90 minutes</h3><div data-prices>Chargement des cotes…</div><button type="button" class="day">ACTUALISER LES COTES</button>';
  root.querySelector('#analyzeBtn')?.before(panel);
  const out=panel.querySelector('[data-prices]'),button=panel.querySelector('button');
  async function update(){
   button.disabled=true;const data=await load(match,true);
   if(panel.isConnected){
    out.innerHTML=summary(data,match);button.disabled=false;
    for(const side of ['home','away']){
     const badge=root.querySelector('[data-team-price="'+side+'"]');
     const value=price(data,side);if(badge)badge.textContent=value?'Cote : '+fmt(value):'Cote indisponible';
    }
   }
  }
  button.onclick=update;await update();
 }
 async function mount(target,results){
  if(!target||!results.length)return;
  const host=document.createElement('section');host.className='panel premium';host.dataset.oddsTicket='';
  host.innerHTML='<h3>🎟️ Simulation de ton ticket</h3><p>Chargement des cotes de tes sélections…</p>';target.appendChild(host);
  const legs=results.map(r=>({...r,market:r.market||r.choice?.market,probability:r.probability??r.choice?.probability}));
  await Promise.all(legs.map(async r=>{r.odds=r.analysis?.market_odds||await load(r.match);}));
  if(!host.isConnected)return;
  const books=[...new Set(legs.flatMap(r=>(r.odds.books||[]).map(b=>b.bookmaker)))];
  host.innerHTML='<h3>🎟️ Simulation de ton ticket</h3><div data-legs></div><label>Mise (€) <input data-stake type="text" inputmode="decimal" placeholder="Ta mise" autocomplete="off"></label><div data-total role="status" aria-live="polite"></div><button class="day" type="button" data-refresh>ACTUALISER LES COTES</button>';
  const book=books[0],rows=host.querySelector('[data-legs]'),stake=host.querySelector('[data-stake]'),out=host.querySelector('[data-total]');
  function draw(){
   rows.innerHTML=legs.map((r,i)=>{
    const quote=price(r.odds,r.market,book);
    r.quote=quote;
    return '<div class="message"><strong>'+esc(r.match.home.name+' – '+r.match.away.name)+'</strong><p class="gold">'+esc(label(r.market,r.match))+'</p><label>Cote décimale <input data-odd="'+i+'" type="text" inputmode="decimal" autocomplete="off" '+(quote?'value="'+quote+'" readonly':'placeholder="Ex. 1,85"')+'></label></div>';
   }).join('');update();
  }
  function update(){
   const inputs=[...rows.querySelectorAll('[data-odd]')],prices=inputs.map(input=>number(input.value));
   let expired=false;
   inputs.forEach((input,i)=>{
    const r=legs[i];if(r.quote&&!fresh(r.odds))expired=true;
   });
   const repeated=new Set(),seen=new Set();
   for(const r of legs)for(const id of [r.match.home.id,r.match.away.id]){if(seen.has(String(id)))repeated.add(id);seen.add(String(id));}
   const started=legs.some(r=>!Number.isFinite(Date.parse(r.match.date))||Date.parse(r.match.date)<=Date.now());
   const value=calculate(prices,number(stake.value));
   out.textContent=started?'Le match a commencé : simulation avant-match indisponible.':expired?'Consultation des cotes expirée : actualise avant de calculer.':repeated.size?'Plusieurs rencontres concernent la même équipe : simulation combinée indisponible.':!value?'Renseigne une cote valide pour chaque sélection et ta mise pour calculer le ticket.':'Cote totale : '+fmt(value.total)+' · Retour potentiel : '+fmt(value.gross)+' € · Bénéfice potentiel : '+fmt(value.net)+' € si toutes les sélections gagnent.';
  }
  rows.oninput=update;stake.oninput=update;
  host.querySelector('[data-refresh]').onclick=async e=>{
   const button=e.currentTarget;button.disabled=true;
   await Promise.all(legs.map(async r=>{r.odds=await load(r.match,true);}));
   if(host.isConnected){draw();button.disabled=false;}
  };
  panels.set(host,update);draw();
  if(window.Bankroll){const proposal=await window.Bankroll.suggest(legs);if(proposal&&host.isConnected){stake.value=proposal.stake;const note=document.createElement('p');note.textContent=proposal.label;stake.closest('label').after(note);update();}}
 }
 document.addEventListener('visibilitychange',()=>{if(!document.hidden)document.querySelectorAll('[data-odds-ticket]').forEach(p=>panels.get(p)?.());});
 setInterval(()=>document.querySelectorAll('[data-odds-ticket]').forEach(p=>panels.get(p)?.()),30000);
 window.OddsTicket={load,price,rank,mount,matchPanel,calculate,number,label};
})();
