/* Run with NODE_PATH pointing to a jsdom installation. */
const {JSDOM}=require('jsdom'),fs=require('fs'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://foot-analyst-pro.onrender.com'}),w=dom.window,d=w.document;
w.escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
w.Accounts={request:async()=>({status:'saved'}),needsLogin(){}};
const ticket=(id,status='pending')=>({id,title:'Ticket '+id,status,created_at:1794139200,selections:[{label:'Alpha – Beta',market:'home',status,home_score:null},{label:'Gamma – Delta',market:'btts',status,home_score:null}]});
let pendingResolve;
w.fetch=async url=>({ok:true,json:async()=>url.includes('performance')?{success_pct:50,won:1,lost:1,pending:1,recent:Array.from({length:8},()=>ticket(1).selections[0])}:url.includes('status=past')?{tickets:[ticket('passé','lost')],next_offset:null}:url.includes('offset=5')?{tickets:[ticket(6)],next_offset:null}:{tickets:Array.from({length:5},(_,i)=>ticket(i)),next_offset:5}});
w.eval(fs.readFileSync('organization.js','utf8'));w.eval(fs.readFileSync('tracking.js','utf8'));
const click=selector=>{assert(d.querySelector(selector),selector);d.querySelector(selector).click();};
const tick=()=>new Promise(r=>setTimeout(r,0));
(async()=>{
 assert.equal(d.getElementById('dailyTickets-group-0').hidden,false);
 click('[aria-controls="dailyTickets-group-1"]');assert.equal(d.getElementById('dailyTickets-group-0').hidden,true);
 click('[aria-controls="dailyTickets-group-2"]');assert(d.getElementById('dailyTickets-group-2').contains(d.getElementById('customDate')));
 click('[aria-controls="tickets-group-1"]');assert(d.getElementById('tickets-group-1').contains(d.getElementById('builderForm')));
 d.getElementById('automaticTicketsResult').innerHTML='<div class="panel premium"><h2>Ticket 1</h2><p>Choix</p></div><div class="panel"><h2>Ticket 2</h2></div>';
 await tick();assert.equal(d.querySelectorAll('#automaticTicketsResult > details').length,2);assert.equal(d.querySelector('#automaticTicketsResult > details').open,false);
 await w.Tracking.load();assert.equal(d.querySelectorAll('#ticketArchive > details').length,5);
 click('#ticketArchive button');await tick();assert.equal(d.querySelectorAll('#ticketArchive > details').length,6);
 click('[data-status="past"]');await tick();assert(d.getElementById('ticketArchive').textContent.includes('Perdu'));assert(!d.getElementById('ticketArchive').textContent.includes('Ticket 0'));
 assert.equal(d.querySelectorAll('#trackedSelections > div').length,5);click('#trackedSelections button');assert.equal(d.querySelectorAll('#trackedSelections > div').length,8);
 const target=d.getElementById('analysisHistory');target.innerHTML=Array.from({length:12},(_,i)=>'<button class="match">'+i+'</button>').join('');w.CompactLists.paginate(target);
 assert.equal([...target.querySelectorAll('.match')].filter(n=>!n.hidden).length,5);target.lastChild.click();assert.equal([...target.querySelectorAll('.match')].filter(n=>!n.hidden).length,10);
 // Late responses from an earlier tab or account may never replace the current view.
 w.fetch=async url=>url.includes('status=pending')?new Promise(resolve=>pendingResolve=resolve):{ok:true,json:async()=>({tickets:[ticket('new','lost')],next_offset:null})};
 click('[data-status="pending"]');click('[data-status="past"]');await tick();pendingResolve({ok:true,json:async()=>({tickets:[ticket('stale')],next_offset:null})});await tick();assert(!d.getElementById('ticketArchive').textContent.includes('stale'));
 w.Tracking.clear();assert.equal(d.getElementById('trackingResult').textContent,'');
 assert(!d.querySelector('.promo').textContent.includes('Sans carte bancaire'));
 console.log('Navigation, cartes repliées, archives en cours/passées, pagination et réponses tardives : OK.');w.close();
})().catch(e=>{console.error(e);process.exitCode=1;w.close();});
