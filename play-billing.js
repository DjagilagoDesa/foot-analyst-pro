/* Play confirms the payment; the server alone grants Premium. */
(() => {
  let context = null, busy = false, timer = null, catalogReady = false;
  const el = id => document.getElementById(id);
  const feedback = text => { if(el('billingFeedback')) el('billingFeedback').textContent = text; };
  const unlock = () => { busy=false; clearTimeout(timer); if(el('billingSubscribe')) el('billingSubscribe').disabled=!(context?.available && catalogReady); if(el('billingRestore')) el('billingRestore').disabled=false; };
  const lock = () => { busy=true; if(el('billingSubscribe')) el('billingSubscribe').disabled=true; if(el('billingRestore')) el('billingRestore').disabled=true; clearTimeout(timer); timer=setTimeout(()=>{unlock();feedback('Vérification non terminée. Utilise « Restaurer mon achat » pour réessayer.');},120000); };
  async function action(name) {
    if(busy) return;
    try {
      context=await window.Accounts.request('/api/billing/context',{});
      if(!window.FootPlay) {feedback('Le paiement et la restauration sont disponibles dans la version Android installée depuis Google Play.');return;}
      if(!context.available) {feedback('L’abonnement Google Play est en cours de configuration. Tes analyses gratuites restent disponibles.');return;}
      lock();feedback(name==='buy'?'Ouverture de Google Play…':'Recherche de tes achats Google Play…');
      window.FootPlay.postMessage(JSON.stringify({action:name,account_id:context.account_id}));
    } catch(e) {unlock();feedback(e.message);}
  }
  async function receive(event) {
    try {
      const data=JSON.parse(event.data);
      if(data.type==='catalog') {
        catalogReady=true;unlock();el('billingSubscribe').textContent='S’ABONNER · '+data.price+' / MOIS';
        feedback('Abonnement mensuel à renouvellement automatique. Annulable dans Google Play ; accès maintenu jusqu’à la fin de la période payée.');return;
      }
      if(data.type==='purchases') {
        lock();
        let active=false;
        for(const token of data.tokens||[]) {
          const result=await window.Accounts.request('/api/billing/verify',{purchase_token:token});
          active ||= result.status==='active';
        }
        await window.Accounts.refresh(false);
        unlock();
        if(active) {await window.Accounts.loadBilling();feedback('Premium activé sur ton compte.');}
        else feedback(data.pending?'Paiement en attente de confirmation par Google Play. Premium sera activé après validation ; utilise la restauration à ton retour.':'Aucun abonnement actif trouvé sur ce compte Google Play.');
        return;
      }
      unlock();feedback(data.message||'Google Play est indisponible. Réessaie la restauration.');
    } catch(e) {unlock();feedback(e.message||'Vérification indisponible. Réessaie la restauration.');}
  }
  async function load() {
    if(!el('billingSubscribe'))return;
    catalogReady=false;
    el('billingSubscribe').onclick=()=>action('buy');
    el('billingRestore').onclick=()=>action('restore');
    if(window.FootPlay)window.FootPlay.onmessage=receive;
    try {
      const catalog=await fetch('/api/billing/catalog',{credentials:'same-origin'}).then(r=>r.json());
      el('billingSubscribe').disabled=true;
      el('billingSubscribe').textContent='ABONNEMENT BIENTÔT DISPONIBLE';
      if(!window.FootPlay) {feedback('Pour t’abonner ou restaurer un achat, utilise la version Android Google Play.');return;}
      if(!catalog.purchase_available) {feedback('Abonnement en cours de configuration. Les 3 analyses gratuites par semaine restent disponibles.');return;}
      // Account context is authenticated and binds the purchase to the immutable user ID.
      context=await window.Accounts.request('/api/billing/context',{});
      lock();window.FootPlay.postMessage(JSON.stringify({action:'catalog',account_id:context.account_id}));
    } catch(e) {unlock();feedback(e.message);}
  }
  window.PlayBillingUI={load};
})();
