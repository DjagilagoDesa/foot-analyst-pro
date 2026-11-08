const {JSDOM}=require('jsdom'),fs=require('fs'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8').replace(/<script[\s\S]*?<\/script>/g,'');
const dom=new JSDOM(html,{runScripts:'outside-only',url:'https://foot-analyst-pro.onrender.com'}),w=dom.window,d=w.document;
w.escapeHtml=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
w.setInterval=()=>0;let opened;
w.openMatch=m=>opened=m.id;
const match={id:'42',date:'2026-11-09T20:00:00Z',home:{id:'1',name:'Club A'},away:{id:'2',name:'Club B'}};
let board={day:new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'}),status:'partial',groups:[],scorer:{player:{id:'11',name:'Joueur <img src=x>',team_name:'Club A'},match,status:'pending',availability:'unconfirmed',basis:{goals:6,appearances:9},rationale:'Ses raisons <script>bad</script>',source_url:'https://www.espn.com/soccer/match/_/gameId/42'},scorer_performance:{won:2,lost:1,success_pct:66.7}};
let quote=null;w.api=async path=>path.includes('/scorer-history')?{items:[{...board.scorer,day:board.day,status:'won'}],page:1,has_more:false}:path.endsWith('/scorer-odds')?{odds:quote}:JSON.parse(JSON.stringify(board));
w.eval(fs.readFileSync('organization.js','utf8'));w.eval(fs.readFileSync('daily-opinion.js','utf8'));
const tick=()=>new Promise(r=>setTimeout(r,0));
(async()=>{
 await tick();const area=d.getElementById('homeDailyOpinion');
 assert(area.textContent.includes('⚽ Buteur du jour'));assert(area.textContent.includes('6 buts · 9 apparitions'));assert(area.textContent.includes('Titularisation à confirmer'));
 assert(area.textContent.includes('Réussite buteurs'));
 const history=area.querySelector('[data-scorer-history]');history.open=true;history.ontoggle();await tick();
 assert(history.textContent.includes('✓ Gagné'));assert(!history.querySelector('img'));
 assert(!area.querySelector('img'));assert(!area.querySelector('script'));assert.equal(area.querySelector('details').open,false);
 area.querySelector('details').open=true;await w.DailyOpinion.load();await tick();assert.equal(area.querySelector('details').open,true);
 assert(area.querySelector('[data-scorer-odds]').textContent.includes('—'));
 quote={price:1.75,bookmaker:'Unibet',market:'anytime_scorer',event_id:'42',player_id:'11',kind:'prematch_quote',observed_at:new Date().toISOString(),expires_at:new Date(Date.now()+120000).toISOString()};
 await w.DailyOpinion.load();await tick();assert.equal(area.querySelector('[data-scorer-odds]').textContent,'1,75');
 quote.player_id='wrong';await w.DailyOpinion.load();await tick();assert(area.querySelector('[data-scorer-odds]').textContent.includes('—'));
 quote.player_id='11';quote.expires_at='2020-01-01T00:00:00Z';await w.DailyOpinion.load();await tick();assert(area.querySelector('[data-scorer-odds]').textContent.includes('—'));
 board.scorer.odds=quote;
 area.querySelector('[data-scorer-match]').click();assert.equal(opened,'42');
 for(const [status,label] of [['won','✓ Gagné'],['lost','✗ Perdu'],['void','Annulé']]){
  board.scorer.status=status;await w.DailyOpinion.load();await tick();assert(area.textContent.includes(label));assert(!area.textContent.includes('Titularisation à confirmer'));
 }
 board={day:'2026-11-10',status:'partial',groups:[],scorer:null};await w.DailyOpinion.load();await tick();assert(area.textContent.includes('Aucun buteur sélectionné'));assert(!area.textContent.includes('Joueur'));
 console.log('Buteur quotidien : rubrique repliable, données échappées, match ouvrable, résultats et remise à zéro validés.');w.close();
})().catch(e=>{console.error(e);process.exitCode=1;w.close();});
