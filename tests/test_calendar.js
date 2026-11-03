// Test the actual inline client script with a minimal DOM: no browser dependencies.
const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',innerHTML:'',textContent:'',classList:{toggle(){},add(){},remove(){}},addEventListener(){},querySelectorAll(){return []},querySelector(){return null}});return elements.get(id)}
const context={document:{hidden:false,body:element('body'),getElementById:element,querySelectorAll:()=>[],addEventListener(){}},window:{scrollTo(){}},location:{protocol:'https:'},setTimeout:()=>1,clearTimeout(){},AbortController,URLSearchParams,FormData,fetch:async()=>({ok:true,json:async()=>({status:'ok'})}),console};
vm.createContext(context);
const script=fs.readFileSync('index.html','utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
vm.runInContext(script,context);
vm.runInContext(`
const live={state:'in',completed:false,home_score:'2',away_score:'1',status_detail:"67'",date:'2026-11-01T14:00:00Z',home:{name:'A'},away:{name:'B'},league:'fra.1'};
const final={...live,state:'post',completed:true,home_score:'0',away_score:'0'};
const upcoming={...live,state:'pre',home_score:'0',away_score:'0'};
globalThis.results={liveScore:matchScore(live),zeroScore:matchScore(final),upcoming:matchScore(upcoming),liveBadge:statusBadge(live),finalBadge:statusBadge(final)};
calendarCache=[final,upcoming,live];calendarDay=$('date').value;matchFilter='all';renderCalendar();globalThis.allHtml=$('fixtures').innerHTML;
matchFilter='live';renderCalendar();globalThis.liveHtml=$('fixtures').innerHTML;
matchFilter='finished';renderCalendar();globalThis.finalHtml=$('fixtures').innerHTML;
calendarCache=[];renderCalendar();globalThis.emptyHtml=$('fixtures').innerHTML;
const quoted={...upcoming,date:new Date(Date.now()+3600000).toISOString(),market_odds:{expires_at:new Date(Date.now()+60000).toISOString(),observed_at:new Date().toISOString(),books:[{bookmaker:'Source <img>',markets:{home:2.05,draw:4.2,away:3.05}}]}};
calendarCache=[quoted];matchFilter='all';renderCalendar();globalThis.oddsHtml=$('fixtures').innerHTML;
quoted.market_odds.expires_at='2000-01-01T00:00:00Z';renderCalendar();globalThis.expiredOddsHtml=$('fixtures').innerHTML;

`,context);
assert.equal(context.results.liveScore,'2 – 1');assert.equal(context.results.zeroScore,'0 – 0');assert.equal(context.results.upcoming,'VS');
assert.match(context.results.liveBadge,/EN DIRECT/);assert.match(context.results.liveBadge,/67/);assert.match(context.results.finalBadge,/TERMINÉ/);
assert.equal((context.allHtml.match(/data-match=/g)||[]).length,3);
assert.equal((context.liveHtml.match(/data-match=/g)||[]).length,1);assert.match(context.liveHtml,/2 – 1/);
assert.equal((context.finalHtml.match(/data-match=/g)||[]).length,1);assert.match(context.finalHtml,/0 – 0/);
assert.match(context.emptyHtml,/Aucun match terminé/);
console.log('Calendar UI: live/final scores, zero scores, filters and empty state OK');

assert.match(context.oddsHtml,/2,05/);assert.match(context.oddsHtml,/3,05/);assert.doesNotMatch(context.oddsHtml,/Match nul|Source|odds-source|fra\.1/);assert(!context.oddsHtml.includes('<img>'));assert.match(context.expiredOddsHtml,/—/);assert(!context.expiredOddsHtml.includes('2,05'));
