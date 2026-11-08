const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
async function run(mode){
 const base=Date.parse('2026-11-08T12:00:00Z');let clock=base,feeds=0,recorded=[],analyses=0;
 class Clock extends Date{constructor(...a){super(...(a.length?a:[clock]));}static now(){return clock;}}
 const nodes=Object.fromEntries(['generateDailyTickets','automaticTicketsResult','automaticTicketsNotice'].map(id=>[id,{innerHTML:'',disabled:false,querySelectorAll:()=>[],querySelector:()=>null}]));
 const matches=Array.from({length:mode==='search-more'?12:4},(_,i)=>({id:String(i+1),league:'fra.1',date:new Date(base+3600000*(i+1)).toISOString(),state:'pre',completed:false,home:{id:String(i*2+1),name:'Home'+i},away:{id:String(i*2+2),name:'Away'+i}}));
 const c={Date:Clock,document:{getElementById:id=>nodes[id]},escapeHtml:String,renderAnalysisReport:()=>'',renderLockedAnalysis:()=>{},api:async()=>{
  feeds++;return {events:matches.map((m,i)=>({...m,state:feeds>1&&(mode==='all-invalid'||(i===0&&mode!=='search-more'))?'in':m.state}))};
 },window:{Accounts:{refresh:async()=>{},afterAnalysis:async()=>{},request:async()=>{analyses++;return ({status:'ok',prediction:{markets:mode==='search-more'&&analyses<=8?{}:{home_or_draw:78,btts:65,over_2_5:50,home_or_draw_and_btts:65}},home:{matches:10},away:{matches:10}});}},Tracking:{record:async p=>{recorded=p;return 0;},saveTicket:async()=>{if(mode==='elapsed')clock=base+20*3600000;}}}};
 vm.createContext(c);vm.runInContext(fs.readFileSync('custom-ticket.js','utf8').split('(()=>{')[0]+fs.readFileSync('daily-tickets.js','utf8'),c);
 await nodes.generateDailyTickets.onclick();
 const html=nodes.automaticTicketsResult.innerHTML;
 if(mode==='search-more'){assert(analyses>8,'search must continue past eight analyses when profiles remain incomplete');assert(html.includes('Ticket 1'));}
 if(mode==='one-invalid'){
  assert(html.includes('Ticket 1'));assert(html.includes('Ticket 5'));assert(!html.includes('Home0'));assert(recorded.length>0);
 }
 if(mode==='all-invalid'){assert(!html.includes('Ticket 1'));assert(html.includes('Aucune rencontre'));assert.equal(recorded.length,0);}
 if(mode==='elapsed'){assert(!html.includes('Ticket 1'));assert(html.includes('actualiser'));}
 assert(!html.includes('artificiellement'));assert(!html.includes('Ticket non proposé'));
 assert(!nodes.generateDailyTickets.disabled);
}
(async()=>{for(const mode of ['one-invalid','all-invalid','elapsed','search-more'])await run(mode);console.log('Daily tickets: invalid candidate isolated, all-invalid handled, kickoff during save blocked.');})().catch(e=>{console.error(e);process.exitCode=1;});
