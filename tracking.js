/* Each ticket selection is recorded server-side before kickoff. */
(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 const market={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',away:'Victoire extérieur',draw:'Match nul',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux marquent'};
 window.Tracking={record:async picks=>{
  let missed=0;
  for(const pick of picks){
   if(!pick.analysis.tracking_id){missed++;continue;}
   try{await window.Accounts.request('/api/tracking/record',{analysis_id:pick.analysis.tracking_id,market:pick.market});}catch{missed++;}
  }
  return missed;
 },load:async()=>{
  const target=get('trackingResult'),button=get('refreshTracking');if(button.disabled)return;button.disabled=true;button.textContent='↻ VÉRIFICATION…';target.innerHTML='<div class="message">Vérification des résultats définitifs…</div>';
  try{
   const r=await fetch('/api/tracking/performance',{credentials:'same-origin',headers:{Accept:'application/json'}}),d=await r.json();if(!r.ok)throw Error(d.message||'Suivi indisponible');
   target.innerHTML='<div class="analysis"><div class="stat"><span>Ma réussite</span><b>'+(d.success_pct===null?'—':esc(d.success_pct)+' %')+'</b></div><div class="stat"><span>Paris gagnés</span><b>'+esc(d.won)+'</b></div><div class="stat"><span>Paris perdus</span><b>'+esc(d.lost)+'</b></div><div class="stat"><span>En attente</span><b>'+esc(d.pending)+'</b></div></div>'+(d.source_errors?'<div class="message">Certains résultats restent à vérifier : source temporairement indisponible.</div>':'')+'<details><summary>Voir mes sélections suivies</summary>'+(d.recent||[]).map(p=>'<div class="message"><strong>'+esc(p.label)+'</strong><p>'+esc(market[p.market]||p.market)+'</p><p><span class="'+({won:'result-won',lost:'result-lost'}[p.status]||'')+'">'+esc({won:'✓ Gagné',lost:'✗ Perdu',pending:'⏳ En attente',void:'Annulé / non réglable'}[p.status])+'</span>'+(p.home_score!==null?' · '+esc(p.home_score)+' – '+esc(p.away_score):'')+'</p></div>').join('')+'</details>';
  }catch(e){target.innerHTML='<div class="message">'+esc(e.message)+'</div>';if(/Connecte|connecte|connexion/i.test(e.message))window.Accounts.needsLogin(target);}
  finally{button.disabled=false;button.textContent='↻ ACTUALISER';}
 }};
 get('refreshTracking').onclick=window.Tracking.load;
})();



