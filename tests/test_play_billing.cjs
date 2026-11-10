const {JSDOM}=require('jsdom');
const fs=require('fs'),assert=require('assert');
function setup({native=true,available=true}={}){
 const dom=new JSDOM('<button id="billingSubscribe" disabled></button><button id="billingRestore"></button><div id="billingFeedback"></div>',{runScripts:'outside-only'});
 const w=dom.window,calls=[];
 w.fetch=async()=>({json:async()=>({purchase_available:available})});
 w.Accounts={request:async(path,body)=>{calls.push({path,body});return path.endsWith('context')?{available,account_id:'a'.repeat(64)}:{status:'active'};},refresh:async()=>{},loadBilling:async()=>{}};
 if(native)w.FootPlay={postMessage:msg=>calls.push(JSON.parse(msg))};
 w.eval(fs.readFileSync('play-billing.js','utf8'));
 return {w,calls,dom,button:()=>w.document.getElementById('billingSubscribe'),text:()=>w.document.getElementById('billingFeedback').textContent};
}
(async()=>{
 let s=setup({native:false});await s.w.PlayBillingUI.load();assert(s.button().disabled);assert(s.text().includes('version Android'));s.dom.window.close();
 s=setup({available:false});await s.w.PlayBillingUI.load();assert(s.button().disabled);assert(!s.calls.length);s.dom.window.close();
 s=setup();await s.w.PlayBillingUI.load();assert(s.button().disabled);assert(s.calls.some(c=>c.action==='catalog'));
 await s.w.FootPlay.onmessage({data:JSON.stringify({type:'catalog',price:'29,90 €'})});assert(!s.button().disabled);assert(s.button().textContent.includes('29,90 €'));
 await s.button().onclick();assert(s.calls.some(c=>c.action==='buy'));assert(s.button().disabled);
 await s.w.FootPlay.onmessage({data:JSON.stringify({type:'cancelled',message:'Achat annulé.'})});assert(!s.button().disabled);assert(s.text().includes('annulé'));
 await s.w.FootPlay.onmessage({data:JSON.stringify({type:'purchases',tokens:[],pending:true})});assert(s.text().includes('en attente'));assert(!s.calls.some(c=>c.path?.endsWith('verify')));
 await s.w.document.getElementById('billingRestore').onclick();assert(s.calls.some(c=>c.action==='restore'));
 await s.w.FootPlay.onmessage({data:JSON.stringify({type:'purchases',tokens:['verified-token'],pending:false})});assert(s.calls.some(c=>c.path==='/api/billing/verify'&&c.body.purchase_token==='verified-token'));assert(s.text().includes('Premium activé'));
 s.dom.window.close();console.log('Play Billing UI: passed');
})().catch(e=>{console.error(e);process.exit(1);});
