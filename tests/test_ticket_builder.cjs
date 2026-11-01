const fs=require('fs'),vm=require('vm'),assert=require('assert');
async function run(mode){
 const ids={};for(const id of ['builderDate','builderSource','builderCount','builderChoose','builderSourceInfo','builderRisk','builderMarket','builderForm','builderResult','builderSubmit','customDate'])ids[id]={value:'',disabled:false,hidden:false,textContent:'',innerHTML:'',scrollIntoView(){}};
 ids.builderSource.value=mode==='personal'?'personal':'auto';ids.builderCount.value='3';ids.builderRisk.value='balanced';ids.builderMarket.value='joint';
 const fixtures=Array.from({length:3},(_,i)=>({id:i,league:'fra.1',state:'pre',date:new Date(Date.now()+3600000*(i+1)).toISOString(),home:{id:i*2,name:'Home'+i},away:{id:i*2+1,name:'Away'+i}}));let calls=0;
 const c={document:{getElementById:id=>ids[id]},escapeHtml:x=>String(x),Date,Set,api:async()=>({events:mode==='empty'?[]:fixtures}),show(){},renderAnalysisReport:()=>'<p>Rapport</p>',renderLockedAnalysis:el=>el.innerHTML='LOCKED',window:{PersonalTicket:{getMatches:()=>fixtures.slice(0,2)},Tracking:{record:async()=>0},Accounts:{refresh:async()=>{},afterAnalysis:async()=>{},needsLogin(){},request:async()=>{calls++;return mode==='locked'?{status:'locked'}:{status:'ok',prediction:{markets:{home_or_draw:90,home_or_draw_and_btts:65}}};}}}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('custom-ticket.js','utf8').split('(()=>{')[0]+fs.readFileSync('ticket-builder.js','utf8'),c);
 await ids.builderForm.onsubmit({preventDefault(){}});
 if(mode==='ok'){assert.equal(calls,3);assert(ids.builderResult.innerHTML.includes('1X + Les deux'));}
 if(mode==='personal'){assert.equal(calls,2);assert(ids.builderResult.innerHTML.includes('2 matchs'));assert(ids.builderCount.disabled);}
 if(mode==='empty'){assert.equal(calls,0);assert(ids.builderResult.innerHTML.includes('Pas assez'));}
 if(mode==='locked'){assert.equal(calls,1);assert.equal(ids.builderResult.innerHTML,'LOCKED');}
 assert(!ids.builderSubmit.disabled);
 assert.equal(c.builderSelection({home_or_draw_and_btts:60},'prudent','joint'),null);
}
(async()=>{for(const m of ['ok','personal','empty','locked'])await run(m);console.log('4 parcours vérifiés : automatique, sélection personnelle complète, calendrier vide, accès Premium.');})();
