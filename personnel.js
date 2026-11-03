/* Match personnel updates reuse saved analyses and never spend a trial. */
(() => {
  let timer=null, generation=0;
  const TITLE='Compositions et disponibilités signalées';
  const esc=value=>escapeHtml(value==null?'':String(value));
  const stamp=value=>{
    const d=new Date(value);
    return Number.isNaN(d.getTime())?'date indisponible':d.toLocaleString('fr-FR',{timeZone:'Europe/Paris'});
  };
  function stop(){clearTimeout(timer);timer=null;generation++;}
  function visible(el){return el.isConnected&&!document.hidden&&!el.closest('.hidden');}
  function historyMarkup(snapshots,names){
    if(!Array.isArray(snapshots)||snapshots.length<2)return '';
    return '<details class="personnel-history"><summary>Historique des effectifs ('+snapshots.length+' états)</summary>'+snapshots.map(s=>{
      const teams=Object.entries(s.teams||{}).map(([team,t])=>{
        const starters=(t.starters||[]).map(p=>p.name).join(', ')||'Composition indisponible';
        const absences=(t.availability||[]).map(p=>p.name+' : '+({reported_out:'forfait signalé',doubtful:'incertain',questionable:'disponibilité incertaine',suspension_unverified_scope:'suspension, portée non vérifiée'}[p.status]||'statut non vérifié')).join(' ; ');
        return '<p><strong>'+esc(names[team]||'Équipe')+'</strong> : '+esc(starters)+(absences?'<br>'+esc(absences):'')+'</p>';
      }).join('');
      return '<div class="personnel-snapshot"><strong>'+esc(stamp(s.observed_at))+'</strong>'+ (teams||'<p>Informations indisponibles lors de cette consultation.</p>')+'</div>';
    }).join('')+'</details>';
  }
  function attach(el,data){
    stop();
    if(!data||!data.tracking_id||!data.league||!/^\d+$/.test(String(data.event_id||'')))return;
    const token=generation;
    let context=data.personnel_context||null,snapshots=data.personnel_snapshots||[];
    let section=el.querySelector('[data-personnel-section]');
    if(!section){
      section=document.createElement('section');section.className='report-section';section.dataset.personnelSection='';
      section.innerHTML='<h3>'+TITLE+'</h3><p>Les effectifs n’ont pas encore été vérifiés pour cette analyse.</p>';
      (el.querySelector('.analysis-report')||el).appendChild(section);
    }
    section.querySelector('.personnel-controls')?.remove();
    const controls=document.createElement('div');controls.className='personnel-controls';
    controls.innerHTML='<button class="day" type="button">↻ ACTUALISER LES EFFECTIFS</button><p class="fine" role="status" aria-live="polite"></p><div class="personnel-archive"></div>';
    section.appendChild(controls);
    const button=controls.querySelector('button'),status=controls.querySelector('[role="status"]'),archive=controls.querySelector('.personnel-archive');
    function ended(){return context?.kickoff&&new Date(context.kickoff).getTime()<=Date.now();}
    function draw(){
      archive.innerHTML=historyMarkup(snapshots,{[data.home_id]:data.home_name||'Domicile',[data.away_id]:data.away_name||'Extérieur'});
      button.disabled=!!ended();
      status.textContent=ended()?'Archive figée après le coup d’envoi.':context?.observed_at?'Dernière consultation : '+stamp(context.observed_at)+'. Actualisation toutes les 5 minutes tant que cette analyse est affichée.':'Actualisation sans utiliser d’analyse offerte supplémentaire.';
    }
    async function update(){
      if(token!==generation||!visible(el)||ended())return;
      button.disabled=true;status.textContent='Vérification des effectifs…';
      try{
        const result=await window.Accounts.request('/api/account/analysis/'+encodeURIComponent(data.tracking_id)+'/personnel',{});
        if(token!==generation||!visible(el))return;
        context=result.personnel_context||context;snapshots=result.personnel_snapshots||snapshots;
        if(result.section){
          section.querySelector('h3').textContent=result.section.title;
          let p=section.querySelector(':scope > p');if(!p){p=document.createElement('p');section.insertBefore(p,controls);}
          p.textContent=result.section.text;
          let link=section.querySelector(':scope > a');if(link)link.remove();
          if(/^https:\/\/www\.espn\.com\/soccer\/match\/_\/gameId\/\d+$/.test(result.section.source_url||'')){
            link=document.createElement('a');link.href=result.section.source_url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='Consulter la source ESPN';section.insertBefore(link,controls);
          }
        }
        draw();
        if(result.status!=='updated'&&!ended())status.textContent='Pas de nouvelle information vérifiée. '+(context?.observed_at?'Dernière consultation conservée : '+stamp(context.observed_at)+'.':'Réessaie avant le match.');
      }catch(e){if(token===generation&&visible(el))status.textContent='Effectifs non actualisés : '+e.message;}
      finally{if(token===generation){button.disabled=!!ended();schedule();}}
    }
    function schedule(){
      clearTimeout(timer);
      if(token===generation&&!ended())timer=setTimeout(()=>{if(visible(el))update();else schedule();},300000);
    }
    button.onclick=update;draw();schedule();
  }
  window.Personnel={attach,stop};
})();
