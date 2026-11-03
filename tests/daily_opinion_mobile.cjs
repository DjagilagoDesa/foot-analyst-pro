const assert=require('node:assert/strict');
module.exports=async function(browser){
 for(const width of [360,390]){
  const page=await browser.newPage({viewport:{width,height:844}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const day=new Date().toLocaleDateString('en-CA',{timeZone:'Europe/Paris'});
  const groups=[['prudent',3,'Mes 3 choix prudents',80],['challenge',2,'Mes 2 choix plus difficiles',65],['surprise',1,'Ma surprise du jour',35]];
  let id=0;
  const board={day,status:'ready',stale:false,checked_at:new Date().toISOString(),method:'Données de test',scope:'Périmètre de test',update_note:'Actualisation automatique',performance:{won:2,lost:1,pending:3,void:0,success_pct:66.7},groups:groups.map(([group,count,title,probability])=>({id:group,title,target:count,picks:Array.from({length:count},()=>{
   const n=++id;
   return {group,probability,market_label:'Double chance 1X',rationale:'Explication propre à la rencontre de test '+n,expected_goals:{home:2,away:1},published_at:new Date().toISOString(),status:'pending',home_score:null,away_score:null,
    match:{id:String(n),league:'fra.1',date:new Date(Date.now()+3600000).toISOString(),state:'pre',completed:false,status_name:'STATUS_SCHEDULED',home:{id:String(n*2),name:'Paris Saint-Germain '+n,badge:''},away:{id:String(n*2+1),name:'Olympique de Marseille '+n,badge:''}}};
  })}))};
  const picks=board.groups.flatMap(g=>g.picks);
  for(const p of picks.slice(0,3))p.team_odds={bookmaker:'Example <book>',observed_at:new Date().toISOString(),markets:{home:2.05,draw:3.5,away:3.05}};
  Object.assign(picks[0].team_odds,{kind:'historical_close',observed_at:null,retrieved_at:new Date().toISOString(),source_url:'https://www.espn.com/soccer/match/_/gameId/123'});
  Object.assign(picks[0],{status:'won',market_label:'Plus de 1,5 but',home_score:1,away_score:3});
  Object.assign(picks[1],{status:'lost',home_score:3,away_score:1});
  Object.assign(picks[2],{status:'won',home_score:1,away_score:1});
  await page.route('**/api/daily-opinion',r=>r.fulfill({contentType:'application/json',body:JSON.stringify(board)}));
  await page.route('**/api/tracking/performance',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({won:99,lost:0,pending:0,void:0,success_pct:100,recent:[],note:'Personal history'})}));
  await page.goto('http://127.0.0.1:19047/');
  await page.locator('#homeDailyOpinion .opinion-pick').first().waitFor();
  assert.equal(await page.locator('#homeDailyOpinion .opinion-pick').count(),6);
  assert.equal(await page.locator('#homeDailyOpinion .opinion-group').count(),3);
  const cards=page.locator('#homeDailyOpinion .opinion-pick');
  assert.match(await cards.nth(0).locator('[data-odds-outcome="away"].result-won').innerText(),/3,05/);
  assert.match(await cards.nth(0).locator('.opinion-team-odds').innerText(),/clôture récupérées/);
  assert.equal(await cards.nth(0).locator('.opinion-team-odds a').getAttribute('href'),'https://www.espn.com/soccer/match/_/gameId/123');

  assert.match(await cards.nth(0).locator('[data-odds-outcome="home"].result-lost').innerText(),/2,05/);
  assert.match(await cards.nth(1).locator('[data-odds-outcome="home"].result-won').innerText(),/2,05/);
  assert.match(await cards.nth(2).locator('[data-odds-outcome="draw"].result-won').innerText(),/3,50/);
  assert.match(await cards.nth(3).locator('.opinion-team-odds').innerText(),/non enregistrées/);
  assert.equal(await cards.nth(0).locator('.opinion-team-odds').evaluate(el=>getComputedStyle(el).textAlign),'right');

  assert.match(await page.locator('#homeDailyOpinion .opinion-performance').innerText(),/66.7 %/);
  assert.doesNotMatch(await page.locator('#homeDailyOpinion .opinion-performance').innerText(),/Uniquement les choix quotidiens|Calcul :/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.locator('#homeDailyOpinion .opinion-pick details summary').first().click();
  await page.locator('#homeDailyOpinion [data-opinion-match]').first().click();
  await page.locator('#detail:not(.hidden) #analyzeBtn').waitFor();
  await page.locator('nav [data-page="dailyTickets"]').click();
  await page.locator('#trackingResult .stat').first().waitFor();
  assert.equal(await page.locator('#dailyTickets .opinion-performance').count(),0);
  assert.equal(await page.locator('#dailyOpinionResult').count(),0);
  assert.match(await page.locator('#trackingResult').innerText(),/Ma réussite\s+100 %/);
  assert.doesNotMatch(await page.locator('#trackingResult').innerText(),/66.7 %/);
  // No settled personal selections means no personal rate, never the public rate.
  await page.unroute('**/api/tracking/performance');
  await page.route('**/api/tracking/performance',r=>r.fulfill({contentType:'application/json',body:JSON.stringify({won:0,lost:0,pending:1,void:0,success_pct:null,recent:[]})}));
  await page.locator('#refreshTracking').click();
  await page.waitForFunction(()=>!document.getElementById('refreshTracking').disabled);
  assert.match(await page.locator('#trackingResult').innerText(),/Ma réussite\s+—/);
  assert.doesNotMatch(await page.locator('#trackingResult').innerText(),/66.7 %|100 %/);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  await page.waitForFunction(()=>!window.DailyOpinion.isLoading());
  // A source failure must keep the current day's published choices with a stale notice.
  await page.unroute('**/api/daily-opinion');
  await page.route('**/api/daily-opinion',r=>r.fulfill({status:503,contentType:'application/json',body:'{}'}));
  await page.locator('nav [data-page="home"]').click();
  await page.waitForFunction(()=>!window.DailyOpinion.isLoading());
  await page.evaluate(()=>window.DailyOpinion.load());
  assert.equal(await page.locator('#homeDailyOpinion .opinion-pick').count(),6);
  assert.match(await page.locator('#homeDailyOpinion').innerText(),/Actualisation en retard/);
  assert.deepEqual(errors,[]);
  console.log('Daily opinion mobile '+width+': 3/2/1, fixture navigation, no overflow, stale handling OK');
  await page.close();
 }
};
