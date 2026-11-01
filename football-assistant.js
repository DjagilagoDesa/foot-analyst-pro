(()=>{
 const get=id=>document.getElementById(id),esc=escapeHtml;
 let history=[],busy=false;
 function card(role,text){const div=document.createElement('div');div.className='message '+(role==='user'?'assistant-user':'');div.innerHTML='<strong>'+esc(role==='user'?'Toi':'✦ FOOT ANALYST IA')+'</strong><div class="assistant-text">'+esc(text)+'</div>';get('assistantConversation').appendChild(div);return div;}
 const greeting='Demande-moi ce que tu veux sur le football. Pour un ticket visant une cote Winamax de 30 à 50, colle les sélections et leurs cotes réelles : je vérifierai le total. Les cotes Winamax ne sont pas connectées en direct.';
 card('assistant',greeting);
 get('assistantExample').onclick=()=>{get('assistantQuestion').value='Crée-moi un ticket entre 30 et 50 avec ces cotes :\nMatch 1 | Pari choisi | Cote\nMatch 2 | Pari choisi | Cote\nMatch 3 | Pari choisi | Cote';get('assistantQuestion').focus();};
 get('assistantForm').onsubmit=async e=>{
  e.preventDefault();if(busy)return;const prompt=get('assistantQuestion').value.trim();if(prompt.length<3)return;
  busy=true;get('assistantSend').disabled=true;card('user',prompt);const pending=card('assistant','Je prépare ma réponse…');
  try{
   const d=await window.Accounts.request('/api/assistant',{prompt,label:'FOOT ANALYST IA · '+prompt.slice(0,90),history:history.map(m=>({role:m.role,content:m.content.slice(0,1500)}))});pending.remove();
   if(d.status==='locked'){const box=card('assistant','Ton accès gratuit est terminé.');renderLockedAnalysis(box);return;}
   if(d.status!=='ok'){card('assistant',d.message||'Il me manque des informations pour répondre.');return;}
   const box=card('assistant',d.assistant_reply);
   if(d.ticket){const t=d.ticket;box.innerHTML+='<div class="panel"><h3>Ton ticket sur les cotes fournies</h3>'+t.legs.map((p,i)=>'<p><strong>'+esc((i+1)+'. '+p.match)+'</strong><br>'+esc(p.market)+' · cote fournie : '+esc(p.odds)+'</p>').join('')+'<h3>Cote combinée : '+esc(t.combined_odds)+'</h3><p class="fine">Cible : '+esc(t.target[0])+'–'+esc(t.target[1])+'. Cotes saisies par toi, non vérifiées auprès du bookmaker. Aucun pari placé.</p></div>';}
   history=history.concat([{role:'user',content:prompt},{role:'assistant',content:d.assistant_reply}]).slice(-6);get('assistantQuestion').value='';
  }catch(error){pending.remove();const box=card('assistant',error.message);if(error.code==='login_required')window.Accounts.needsLogin(box);}
  finally{busy=false;get('assistantSend').disabled=false;await window.Accounts.afterAnalysis();}
 };
 window.FootballAssistant={clear:()=>{history=[];get('assistantConversation').innerHTML='';get('assistantQuestion').value='';card('assistant',greeting);}};
})();
