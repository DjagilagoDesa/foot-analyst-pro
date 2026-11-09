/* Personal budget: proposals never debit money until the user confirms a played ticket. */
(()=>{
 const root=document.getElementById('dailyTickets-group-3');if(!root)return;
 const esc=escapeHtml,money=n=>(n/100).toLocaleString('fr-FR',{style:'currency',currency:'EUR'});
 let generation=0;
 async function read(){const r=await fetch('/api/bankroll',{credentials:'same-origin',headers:{Accept:'application/json'}});const d=await r.json();if(!r.ok)throw Error(d.message||'Bankroll indisponible');return d;}
 function form(d){return '<details class="panel" '+(!d.configured?'open':'')+'><summary>Mon budget et mes mises</summary><form data-config><label>Budget de départ (€)<input class="day" name="initial" type="number" min="1" max="1000000" step="0.01" required value="'+(d.configured?d.initial_cents/100:100)+'" '+(d.bets?.length?'readonly':'')+'></label><label>Mise maximale par ticket<select class="day" name="risk"><option value="50">0,5 %</option><option value="100">1 %</option><option value="200">2 %</option></select></label><button class="btn">ENREGISTRER</button></form></details>';}
 async function load(){
  const id=++generation;root.innerHTML='<div class="message">Chargement de la bankroll…</div>';
  try{const d=await read();if(id!==generation)return;
   root.innerHTML='<h2>Ma bankroll</h2>'+form(d)+(d.configured?'<div class="panel"><div class="analysis">'+[['Disponible',d.available_cents],['Engagé',d.pending_cents],['Gains / pertes',d.profit_cents],['Total',d.total_cents]].map(([k,v])=>'<div class="stat"><span>'+k+'</span><b>'+money(v)+'</b></div>').join('')+'</div><p>Évolution : '+((d.total_cents-d.initial_cents)/d.initial_cents*100).toFixed(2).replace('.',',')+' %</p><p>Mise maximale actuelle : '+money(d.suggested_cents)+'</p><p>Limite quotidienne : 5 % du budget initial. Aucune hausse pour rattraper une perte.</p></div><div class="panel"><h3>Mes mises jouées</h3>'+(d.bets.length?d.bets.map((b,i)=>'<details><summary>'+esc(b.title)+' · '+money(b.stake_cents)+' · '+(b.payout_cents===null?'En attente':money(b.payout_cents-b.stake_cents))+'</summary>'+(b.payout_cents===null?'<form data-settle="'+i+'"><label>Retour réel du bookmaker (€), mise incluse<input class="day" name="payout" type="number" min="0" max="1000000" step="0.01" required placeholder="0 si perdu"></label><button class="day">CONFIRMER LE RETOUR</button></form>':'Retour enregistré : '+money(b.payout_cents))+'</details>').join(''):'Aucune mise confirmée.')+'</div>':'')+'<p>Suivi personnel : aucun pari automatique. Une progression chaque jour ne peut pas être garantie.</p><div data-feedback role="status"></div>';
   root.querySelector('[name="risk"]').value=String(d.risk_bps||100);
   const feedback=root.querySelector('[data-feedback]');
   async function submit(event,path,data){event.preventDefault();const button=event.target.querySelector('button');button.disabled=true;try{await window.Accounts.request(path,data);await load();}catch(e){feedback.textContent=e.message;button.disabled=false;}}
   root.querySelector('[data-config]').onsubmit=e=>submit(e,'/api/bankroll',{initial:e.target.elements.initial.value,risk_bps:Number(e.target.elements.risk.value)});
   root.querySelectorAll('[data-settle]').forEach(f=>f.onsubmit=e=>submit(e,'/api/bankroll/settle',{ticket_id:d.bets[Number(f.dataset.settle)].ticket_id,payout:f.elements.payout.value}));
  }catch(e){if(id===generation)root.textContent=e.message;}
 }
 async function mount(node,ticket){
  if(ticket.status!=='pending')return;
  const version=generation;
  try{const d=await read();if(version!==generation||!node.isConnected||!d.configured||d.bets.some(b=>b.ticket_id===ticket.id))return;
   const form=document.createElement('form');form.innerHTML='<label>Mise proposée (€)<input class="day" name="stake" type="number" min="0.01" max="'+d.suggested_cents/100+'" step="0.01" value="'+d.suggested_cents/100+'" required></label><button class="day" '+(d.suggested_cents<1?'disabled':'')+'>CONFIRMER COMME JOUÉ</button><p data-feedback role="status"></p>';node.appendChild(form);
   form.onsubmit=async e=>{e.preventDefault();form.querySelector('button').disabled=true;try{await window.Accounts.request('/api/bankroll/bets',{ticket_id:ticket.id,stake:form.elements.stake.value});form.textContent='Mise enregistrée dans Ma bankroll.';await load();}catch(error){form.querySelector('[data-feedback]').textContent=error.message;form.querySelector('button').disabled=false;}};
  }catch{/* Account prompt is already handled by tracking. */}
 }
 window.Bankroll={load,mount,clear(){generation++;root.textContent='';},async suggest(legs){try{const d=await read();if(!d.configured)return null;const joint=legs.reduce((p,r)=>p*(Number(r.probability)||0)/100,1);const amount=Math.floor(d.suggested_cents*(joint<.25?.25:joint<.5?.5:1));return {stake:(amount/100).toFixed(2),label:'Mise proposée : '+money(amount)+' · montant à risque, pas une probabilité de gain.'};}catch{return null;}}};
 root.closest('section').querySelector('[aria-controls="dailyTickets-group-3"]').addEventListener('click',load);
})();
