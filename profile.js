/* Personal account UI. Passwords and session tokens are never kept in localStorage. */
(() => {
  const id = value => document.getElementById(value);
  const esc = escapeHtml;
  let state = {available: null, user: null}, csrf = '', tab = 'login', recovery = '', busy = false, authGeneration = 0;
  const date = seconds => new Date(seconds * 1000).toLocaleDateString('fr-FR');
  const message = (text, error=false) => '<div class="message '+(error?'error':'')+'" role="status">'+esc(text)+'</div>';
  const field = (name,label,type='text',extra='') => '<label class="profile-field">'+label+'<input class="day" name="'+name+'" type="'+type+'" required '+extra+'></label>';

  async function raw(path, options={}) {
    const ctl = new AbortController(), timeout = setTimeout(()=>ctl.abort(), 60000);
    try {
      const headers = {Accept:'application/json'};
      if (options.body) Object.assign(headers, {'Content-Type':'application/json','X-App-Request':'1','X-CSRF-Token':csrf});
      const response = await fetch(path, {...options, credentials:'same-origin',headers,signal:ctl.signal});
      let data;try{data=await response.json();}catch{throw new Error('Le service est momentanément indisponible. Réessaie dans un instant.');}
      if (!response.ok) { const e=new Error(data.message||'Le service est momentanément indisponible.'); e.code=data.error;e.status=response.status;throw e; }
      if (/\/api\/account\/(register|login|password|recover|logout|delete)$/.test(path)) authGeneration++;
      if (path!=='/api/account') {if(data.csrf_token)csrf=data.csrf_token;if(data.user)state.user=data.user;}
      if (data.recovery_code) recovery=data.recovery_code;
      return data;
    } catch(e) {
      if(e.name==='AbortError') throw new Error('La réponse prend trop de temps. Vérifie ton profil et ton historique avant de réessayer.');
      throw e;
    } finally {clearTimeout(timeout);}
  }
  async function refresh(render=true) {
    const generation=authGeneration;const data=await raw('/api/account');
    if(generation!==authGeneration)return state;
    state=data;csrf=data.csrf_token||'';
    if(render && page==='info') draw();
    return state;
  }
  async function request(path, data) {
    if(!state.user || !csrf) await refresh(false);
    if(!state.user) { const e=new Error(state.available===false?'Les comptes sont en cours d’activation.':'Connecte-toi pour utiliser tes 3 analyses gratuites par semaine.');e.code='login_required';throw e; }
    try { return await raw(path,{method:'POST',body:JSON.stringify(data)}); }
    catch(e) {
      if(e.status===401){state.user=null;csrf='';}
      if(e.code==='csrf_invalid'){await refresh(false);return raw(path,{method:'POST',body:JSON.stringify(data)});}
      throw e;
    }
  }
  function recoveryPanel() {
    if(!recovery) return '';
    return '<div class="panel recovery-panel"><h2>🔑 Ton code de récupération</h2><p>Conserve ce code dans un endroit sûr. Il permet de rétablir l’accès à ton compte si tu oublies ton mot de passe. Il ne sera plus affiché après fermeture de l’application.</p><code id="recoveryCode">'+esc(recovery)+'</code><button class="btn" id="copyRecovery">COPIER LE CODE</button><button class="profile-link" id="hideRecovery">J’ai conservé mon code</button><div id="copyFeedback" aria-live="polite"></div></div>';
  }
  function bindRecovery() {
    if(id('copyRecovery')) id('copyRecovery').onclick=async()=>{try{await navigator.clipboard.writeText(recovery);id('copyFeedback').textContent='Code copié. Conserve-le dans un endroit sûr.';}catch{id('copyFeedback').textContent='Sélectionne le code affiché et copie-le manuellement.';}};
    if(id('hideRecovery'))id('hideRecovery').onclick=()=>{recovery='';draw();};
  }
  function privacy() {
    return '<details class="profile-privacy"><summary>Mes données personnelles</summary><p>Ton e-mail sert à te connecter ; ton pseudo identifie ton profil. Ton mot de passe est stocké sous forme d’empreinte sécurisée. Nous conservons ton compteur hebdomadaire, ton historique d’analyses et les sessions actives. Des compteurs temporaires limitent les tentatives de connexion.</p><p>Tu peux télécharger tes données et supprimer ton compte depuis le Profil. Le code de récupération permet de réinitialiser ton mot de passe : ne le partage pas. L’offre gratuite ne demande pas de carte bancaire. Seul un achat confirmé dans Google Play démarre l’abonnement Premium.</p><p><a href="/privacy">Politique de confidentialité</a> · <a href="/terms">Conditions du service</a> · <a href="/account-deletion">Suppression de compte sur le Web</a>. Les informations éditeur de la version préparatoire restent à confirmer avant publication.</p></details>';
  }
  function draw() {
    const target=id('profileContent'); if(!target)return;
    if(state.available===null){target.innerHTML=message('Chargement de ton espace personnel…');return;}
    if(state.available===false){target.innerHTML='<div class="panel"><h2>Ton espace personnel arrive</h2><p>La création de compte est en cours d’activation. Les matchs restent accessibles.</p><button class="btn" id="retryAccount">RÉESSAYER</button></div>'+privacy();id('retryAccount').onclick=load;return;}
    if(!state.user){
      const form = tab==='register' ? '<h2>Créer mon compte</h2><p>3 analyses gratuites par semaine · sans carte bancaire</p>'+field('nickname','Pseudo','text','minlength="2" maxlength="32" autocomplete="nickname"')+field('email','Adresse e-mail','email','maxlength="254" autocomplete="email"')+field('password','Mot de passe — 12 caractères minimum','password','minlength="12" maxlength="128" autocomplete="new-password"')+field('password_confirm','Confirmer le mot de passe','password','minlength="12" maxlength="128" autocomplete="new-password"')+'<label class="profile-consent"><input type="checkbox" name="accept_privacy" required> J’ai lu les informations ci-dessous et la <a href="/privacy">politique de confidentialité</a>.</label><button class="btn">CRÉER MON COMPTE GRATUIT</button>' : tab==='recover' ? '<h2>Récupérer mon compte</h2><p>Saisis ton code de récupération.</p>'+field('email','Adresse e-mail','email','autocomplete="email"')+field('recovery_code','Code de récupération','text','maxlength="200" autocomplete="off"')+field('password','Nouveau mot de passe','password','minlength="12" maxlength="128" autocomplete="new-password"')+field('password_confirm','Confirmer le mot de passe','password','minlength="12" maxlength="128" autocomplete="new-password"')+'<button class="btn">RÉTABLIR MON ACCÈS</button>' : '<h2>Bienvenue sur ton profil</h2>'+field('email','Adresse e-mail','email','autocomplete="username" maxlength="254"')+field('password','Mot de passe','password','maxlength="128" autocomplete="current-password"')+'<button class="btn">ME CONNECTER</button><button type="button" class="profile-link" id="recoverAccount">Mot de passe oublié ?</button>';
      target.innerHTML='<div class="profile-tabs"><button data-auth-tab="login" class="'+(tab==='login'?'active':'')+'">Connexion</button><button data-auth-tab="register" class="'+(tab==='register'?'active':'')+'">Créer un compte</button></div><div class="panel"><form id="authForm" class="profile-form">'+form+'</form><div id="authFeedback" aria-live="polite"></div></div>'+privacy()+about();
      target.querySelectorAll('[data-auth-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.authTab;draw();});
      if(id('recoverAccount'))id('recoverAccount').onclick=()=>{tab='recover';draw();};
      id('authForm').onsubmit=async event=>{
        event.preventDefault(); if(busy)return;
        const data=Object.fromEntries(new FormData(event.target).entries());
        if(data.password_confirm!==undefined&&data.password_confirm!==data.password){id('authFeedback').innerHTML=message('Les mots de passe ne correspondent pas.',true);return;}
        delete data.password_confirm;data.accept_privacy=data.accept_privacy==='on';
        await runForm(event.target,'authFeedback',async()=>{
          await raw('/api/account/'+(tab==='register'?'register':tab==='recover'?'recover':'login'),{method:'POST',body:JSON.stringify(data)});
          event.target.reset();await refresh(false);draw();
        });
      };
      return;
    }
    const u=state.user, title=u.premium_active?'PREMIUM ACTIF':u.trial_remaining?'DÉCOUVERTE GRATUITE':'QUOTA HEBDOMADAIRE UTILISÉ';
    target.innerHTML=recoveryPanel()+'<div class="panel profile-header"><div class="profile-avatar" aria-hidden="true">'+esc(u.nickname.slice(0,1).toUpperCase())+'</div><h2>'+esc(u.nickname)+'</h2><p class="profile-email">'+esc(u.email)+'</p><span class="pill">'+title+'</span></div><div class="panel"><h2>Mes analyses de la semaine</h2><div class="profile-count">'+u.trial_remaining+' <small>/ 3 restantes</small></div><progress max="3" value="'+u.trial_used+'" aria-label="Analyses offertes utilisées"></progress><p>Renouvellement lundi à minuit (heure de Paris).</p><button class="btn" id="profileMatches">CHOISIR UN MATCH</button></div><div class="panel"><h2>Mon abonnement</h2><p>'+(u.complimentary_premium?'Premium offert · accès propriétaire sans abonnement':u.premium_active?'Premium actif jusqu’au '+date(u.premium_until):'Aucun abonnement actif')+'</p></div><details class="panel profile-settings"><summary>Mon pseudo</summary><form id="nicknameForm" class="profile-form">'+field('nickname','Pseudo','text','minlength="2" maxlength="32" autocomplete="nickname" value="'+esc(u.nickname)+'"')+'<button class="btn">ENREGISTRER</button></form><div id="nicknameFeedback" aria-live="polite"></div></details><details class="panel profile-settings"><summary>Sécurité du compte</summary><form id="passwordForm" class="profile-form">'+field('current_password','Mot de passe actuel','password','maxlength="128" autocomplete="current-password"')+field('password','Nouveau mot de passe','password','minlength="12" maxlength="128" autocomplete="new-password"')+field('password_confirm','Confirmer le nouveau mot de passe','password','minlength="12" maxlength="128" autocomplete="new-password"')+'<button class="btn">MODIFIER MON MOT DE PASSE</button></form><p>Les autres sessions seront fermées et ton code de récupération renouvelé.</p><div id="passwordFeedback" aria-live="polite"></div></details><div class="panel"><h2>Mon historique</h2><div id="profileHistory">Chargement…</div></div><div class="panel"><h2>Mes données et ma connexion</h2><button class="profile-link" id="exportAccount">AFFICHER / EXPORTER MES DONNÉES</button><div id="exportData"></div><button class="day" id="logoutAccount">ME DÉCONNECTER</button><div id="logoutFeedback" aria-live="polite"></div>'+privacy()+'<details class="profile-delete"><summary>Supprimer mon compte</summary><p>Cette action supprime définitivement ton profil, ton compteur hebdomadaire et ton historique dans la base active.</p><form id="deleteForm" class="profile-form">'+field('password','Mot de passe','password','maxlength="128" autocomplete="current-password"')+field('confirmation','Écris SUPPRIMER','text','pattern="SUPPRIMER" autocomplete="off"')+'<button class="profile-danger">SUPPRIMER DÉFINITIVEMENT</button></form><div id="deleteFeedback" aria-live="polite"></div></details></div>'+about();
    if(u.complimentary_premium){
      const count=target.querySelector('.profile-count');
      if(count){const card=count.closest('.panel');card.querySelector('h2').textContent='Mes analyses Premium';count.textContent='Accès gratuit';card.querySelector('progress')?.remove();}
    }
    bindRecovery();
    id('exportAccount').onclick=async()=>{try{const data=await raw('/api/account/export');id('exportData').innerHTML='<textarea class="profile-export" readonly aria-label="Mes données au format JSON">'+esc(JSON.stringify(data,null,2))+'</textarea>'; }catch(e){id('exportData').innerHTML=message(e.message,true);}};
    id('profileMatches').onclick=()=>show('calendar');
    id('nicknameForm').onsubmit=e=>{e.preventDefault();runForm(e.target,'nicknameFeedback',async()=>{await request('/api/account/profile',Object.fromEntries(new FormData(e.target)));draw();});};
    id('passwordForm').onsubmit=e=>{e.preventDefault();const data=Object.fromEntries(new FormData(e.target));if(data.password!==data.password_confirm){id('passwordFeedback').innerHTML=message('Les mots de passe ne correspondent pas.',true);return;}delete data.password_confirm;runForm(e.target,'passwordFeedback',async()=>{await request('/api/account/password',data);e.target.reset();draw();});};
    id('logoutAccount').onclick=()=>runForm(null,'logoutFeedback',async()=>{await request('/api/account/logout',{});state.user=null;csrf='';recovery='';draw();clearHistory();});
    id('deleteForm').onsubmit=e=>{e.preventDefault();runForm(e.target,'deleteFeedback',async()=>{await request('/api/account/delete',Object.fromEntries(new FormData(e.target)));state.user=null;csrf='';recovery='';draw();clearHistory();});};
    loadHistory();
  }
  function about(){return '<details class="panel"><summary>À propos de FOOT ANALYST PRO</summary><p class="fine">Probabilités statistiques par modèle Poisson à partir des résultats disponibles. Elles ne garantissent aucun résultat. Les effectifs signalés par la source sont consultables selon sa couverture ; ils ne modifient pas automatiquement les probabilités.</p></details>';}
  async function runForm(form,feedback,action){
    if(busy)return;busy=true;const buttons=form?form.querySelectorAll('button'):[];buttons.forEach(b=>b.disabled=true);
    if(id(feedback))id(feedback).innerHTML=message('Traitement en cours…');
    try{await action();}catch(e){if(id(feedback))id(feedback).innerHTML=message(e.message,true);}finally{busy=false;buttons.forEach(b=>b.disabled=false);}
  }
  function clearHistory(){window.Tracking?.clear();window.Personnel?.stop();window.TicketBuilder?.clear();for(const name of ['analysisResult','manualResult','customTicketResult','automaticTicketsResult','automaticTicketsNotice','trackingResult'])if(id(name))id(name).textContent='';if(id('analysisHistory'))id('analysisHistory').innerHTML=message('Connecte-toi pour retrouver ton historique.');}
  async function loadHistory(){
    const targets=['profileHistory','analysisHistory'].map(id).filter(Boolean);
    try{
      if(!state.user){targets.forEach(el=>el.innerHTML=message('Connecte-toi depuis Profil pour retrouver tes analyses.'));return;}
      const owner=state.user.id;const data=await raw('/api/account/history');
      if(!state.user||state.user.id!==owner)return;
      const html=data.analyses.length?data.analyses.map((a,i)=>'<button class="match" data-history="'+i+'"><span class="names"><strong>'+esc(a.label)+'</strong><small>'+date(a.created_at)+'</small></span><span class="gold">Voir ›</span></button>').join(''):message('Ton historique est vide. Choisis un match pour commencer.');
      targets.forEach(el=>{el.innerHTML=html;window.CompactLists?.paginate(el);el.querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>{
        const a=data.analyses[Number(b.dataset.history)],r=a.result;const probs=r.prediction?.markets||r.probabilities||{};
        const labels={home_or_draw_and_btts:"1X + les deux équipes marquent",home_or_draw_and_btts_no:"1X + les deux équipes marquent : non",home_or_draw_and_over_1_5:"1X + plus de 1,5 but",home_or_draw_and_over_2_5:"1X + plus de 2,5 buts",home_or_draw_and_under_1_5:"1X + moins de 1,5 but",home_or_draw_and_under_2_5:"1X + moins de 2,5 buts",away_or_draw_and_btts:"X2 + les deux équipes marquent",away_or_draw_and_btts_no:"X2 + les deux équipes marquent : non",away_or_draw_and_over_1_5:"X2 + plus de 1,5 but",away_or_draw_and_over_2_5:"X2 + plus de 2,5 buts",away_or_draw_and_under_1_5:"X2 + moins de 1,5 but",away_or_draw_and_under_2_5:"X2 + moins de 2,5 buts",home:'Victoire domicile',home_win:'Victoire domicile',draw:'Nul',away:'Victoire extérieur',away_win:'Victoire extérieur',over_1_5:'Plus de 1,5 but',over_2_5:'Plus de 2,5 buts',under_1_5:'Moins de 1,5 but',under_2_5:'Moins de 2,5 buts',btts_no:'Les deux équipes marquent : non',btts:'Les deux marquent',both_score:'Les deux marquent',home_or_draw:'Double chance 1X',away_or_draw:'Double chance X2'};
        el.innerHTML=(r.assistant_reply?'<div class="message assistant-text">'+esc(r.assistant_reply)+'</div>':'')+renderAnalysisReport(r)+'<button class="day" id="historyBack">← Historique</button><h3>'+esc(a.label)+'</h3><div class="analysis">'+Object.entries(probs).filter(([k])=>labels[k]).map(([k,v])=>'<div class="stat"><span>'+esc(['home','home_win'].includes(k)?'Victoire '+(r.home_name||r.home?.name||(typeof r.home==='string'?r.home:a.label.split(' – ')[0])):['away','away_win'].includes(k)?'Victoire '+(r.away_name||r.away?.name||(typeof r.away==='string'?r.away:a.label.split(' – ')[1])):labels[k])+'</span><b>'+esc(v)+' %</b></div>').join('')+'</div>';
        window.Personnel?.attach(el,{...r,tracking_id:a.id});
        el.querySelector('#historyBack').onclick=()=>{window.Personnel?.stop();loadHistory();};
      });});
    }catch(e){targets.forEach(el=>el.innerHTML=message(e.message,true));}
  }
  async function loadBilling(){
    try{
      await refresh(false);const u=state.user;
      id('billingAccount').textContent=u?(u.complimentary_premium?'Premium offert · aucun abonnement à payer':u.premium_active?'Premium actif jusqu’au '+date(u.premium_until):u.nickname+' · '+u.trial_remaining+' analyse(s) gratuite(s) restante(s) cette semaine'):'Connecte-toi ou crée ton compte pour utiliser tes 3 analyses gratuites par semaine.';
    }catch{id('billingAccount').textContent='Impossible de charger ton compte. Réessaie depuis Profil.';}
    window.PlayBillingUI?.load();
    id('billingProfile').onclick=()=>show('info');
    id('billingManage').onclick=()=>{window.location.href='https://play.google.com/store/account/subscriptions';};
  }
  async function load(){try{await refresh(false);draw();}catch(e){id('profileContent').innerHTML=message('Ton profil est momentanément indisponible. '+e.message,true);}}
  window.Accounts={request,refresh,loadHistory,loadBilling,render:load,afterAnalysis:async()=>{try{await refresh(false);}catch{}},needsLogin:el=>{const b=document.createElement('button');b.className='btn';b.textContent='OUVRIR MON PROFIL';b.onclick=()=>show('info');el.appendChild(b);}};
  refresh(false).catch(()=>{});
})();







window.addEventListener('DOMContentLoaded',()=>{if(location.hash==='#profile')show('info');});
