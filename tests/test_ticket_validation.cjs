const assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const code=fs.readFileSync('custom-ticket.js','utf8').split('(()=>{')[0];
const base=Date.parse('2026-11-03T12:00:00Z');
const make=(id=1,league='fra.1',date='2026-11-03T18:00:00Z')=>({id:String(id),league,date,state:'pre',completed:false,status_name:'STATUS_SCHEDULED',home:{id:String(id*2),name:'Home '+id},away:{id:String(id*2+1),name:'Away '+id}});
// Daily and personal tickets must respect the selected probability band.
const selectionContext={window:{}};
vm.createContext(selectionContext);vm.runInContext(code,selectionContext);
for(const [profile,min,max] of [['prudent',75,100],['balanced',60,80],['offensive',45,65],['mixed',55,85]]){
 const market=profile==='mixed'?'home_or_draw_and_btts':'home_or_draw';
 const select=values=>selectionContext.ticketSelection(values,profile);
 assert.equal(select({[market]:min-0.1}),null,profile+' must not fall back below its threshold');
 assert.equal(select({[market]:min}).probability,min);
 assert.equal(select({[market]:Math.min(max,99.9)}).probability,Math.min(max,99.9));
 if(max<100)assert.equal(select({[market]:max+0.1}),null,profile+' must keep its band');
 for(const invalid of [NaN,Infinity,-1,0,100])assert.equal(select({[market]:invalid}),null);
 assert.equal(select({}),null);
}
selectionContext.window.OddsTicket={rank:choices=>choices.slice().reverse()};
assert.equal(selectionContext.ticketSelection({home_or_draw:74,btts:80},'prudent').market,'btts','odds ranking cannot bypass the threshold');
assert.equal(selectionContext.ticketSelection({home_or_draw:74},'prudent'),null);
async function scenario(mode){
 let clock=base,calls=[],requests=0;
 class Clock extends Date{constructor(...args){super(...(args.length?args:[clock]));}static now(){return clock;}}
 const original=[make(1),make(2),make(3,'eng.1'),make(4,'fra.1','2026-11-04T18:00:00Z')];
 const c={window:{},Date:Clock,api:async path=>{
  calls.push(path);const p=new URL('https://test.local'+path).searchParams;
  let events=original.filter(m=>m.league===p.get('league')&&m.date.slice(0,10)===p.get('date')).map(m=>JSON.parse(JSON.stringify(m)));
  if(mode==='unavailable'||(mode==='transient'&&calls.length===1))throw Error('offline');
  if(mode==='live')events.forEach(m=>m.state='in');
  if(mode==='postponed')events.forEach(m=>m.status_name='status_postponed');
  if(mode==='canceled')events.forEach(m=>m.status_name='STATUS_CANCELED');
  if(mode==='missing')events=[];
  if(mode==='duplicate')events.push({...events[0]});
  if(mode==='wrong-team')events.forEach(m=>m.home.id='999');
  if(mode==='rescheduled')events.forEach(m=>m.date='2026-11-05T18:00:00Z');
  if(mode==='elapsed')clock=Date.parse('2026-11-04T20:00:00Z');
  return {events,partial:mode==='partial'};
 }};
 vm.createContext(c);vm.runInContext(code,c);
 const results=original.map(match=>({match}));
 if(mode==='past')clock=Date.parse('2026-11-05T12:00:00Z');
 if(mode==='bad-date')results[0].match.date='bad';
 if(mode==='bad-id')results[0].match.id='';
 const before=JSON.stringify(results);
 if(['ok','transient'].includes(mode)){
  await c.ticketVerifyFixtures(results);
  assert.equal(calls.length,mode==='transient'?4:3,'one source check per league/UTC date');
  assert.equal(JSON.stringify(results),before,'validation must not mutate analyses or picks');
  clock=Date.parse('2026-11-03T19:00:00Z');
  assert.throws(()=>c.ticketAssertFuture(results),/actualiser/);
 }else await assert.rejects(()=>c.ticketVerifyFixtures(results));
 if(['past','bad-date','bad-id'].includes(mode))assert.equal(calls.length,0);
}
(async()=>{for(const mode of ['ok','transient','live','postponed','canceled','missing','duplicate','wrong-team','rescheduled','unavailable','partial','elapsed','past','bad-date','bad-id'])await scenario(mode);console.log('Ticket validation: 14 scenarios, batched sources, identity, clock and unchanged picks OK');})().catch(e=>{console.error(e);process.exit(1);});
