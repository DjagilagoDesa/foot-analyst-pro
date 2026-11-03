const fs=require('fs');
module.exports=async browser=>{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.clock.install();
 const styles=fs.readFileSync('index.html','utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
 await page.setContent('<html lang="fr"><head><style>'+styles+'</style></head><body><main id="ticket"></main></body></html>');
 await page.evaluate(()=>{
  window.escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  window.api=async()=>({books:[{bookmaker:'Example <book>',markets:{home:2.05,draw:4.2,away:3.05,btts:1.85,over_2_5:2.1}}],observed_at:new Date().toISOString(),expires_at:new Date(Date.now()+300000).toISOString()});
 });
 await page.addScriptTag({path:'odds-ticket.js'});
 await page.evaluate(async()=>{
  const match=i=>({id:String(i),league:'fra.1',date:new Date(Date.now()+3600000).toISOString(),home:{id:String(i*2),name:'Équipe <img src=x onerror=alert(1)>'},away:{id:String(i*2+1),name:'Extérieur'}});
  await window.OddsTicket.mount(document.getElementById('ticket'),[{match:match(1),market:'btts',probability:60},{match:match(2),market:'over_2_5',probability:65}]);
 });
 await page.locator('[data-stake]').fill('10');
 await page.waitForFunction(()=>document.querySelector('[data-total]').textContent.includes('38,85'));
 if(await page.locator('img,book').count())throw Error('Unescaped source content');
 await page.clock.fastForward(300001);
 await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));
 if(!(await page.locator('[data-total]').innerText()).includes('expirée'))throw Error('Expired odds still calculate a payout');
 await page.locator('[data-book]').selectOption('manual');
 await page.locator('[data-odd="0"]').fill('1,85');
 if((await page.locator('[data-total]').innerText()).includes('Retour potentiel'))throw Error('Missing leg produced a total');
 await page.locator('[data-odd="1"]').fill('2,10');
 await page.waitForFunction(()=>document.querySelector('[data-total]').textContent.includes('28,85'));
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Odds ticket overflows mobile');
 fs.mkdirSync('artifacts',{recursive:true});await page.screenshot({path:'artifacts/odds-mobile.png',fullPage:true});
 await page.evaluate(async()=>{
  const root=document.createElement('div');root.id='detailContent';
  root.innerHTML='<span data-team-price="home"></span><span data-team-price="away"></span><button id="analyzeBtn">Analyser</button>';
  document.body.appendChild(root);
  await window.OddsTicket.matchPanel({id:'1',league:'fra.1',date:new Date(Date.now()+3600000).toISOString(),home:{id:'1',name:'Paris'},away:{id:'2',name:'Lyon'}});
 });
 if(!(await page.locator('[data-team-price="home"]').innerText()).includes('2,05'))throw Error('No price beside home team');
 if(!(await page.locator('[data-team-price="away"]').innerText()).includes('3,05'))throw Error('No price beside away team');
 if(!(await page.locator('[data-prices]').innerText()).includes('Paris'))throw Error('Odds missing actual team names');
 if(errors.length)throw Error(errors.join('; '));await page.close();
 const calendar=await browser.newPage({viewport:{width:390,height:844}});
 await calendar.route('**/api/fixtures?**',async route=>{
  const now=Date.now();const event={id:'123',league:'fra.1',state:'pre',date:new Date(now+3600000).toISOString(),home:{id:'1',name:'Borussia Mönchengladbach'},away:{id:'2',name:'Stade Brestois 29'},market_odds:{observed_at:new Date(now).toISOString(),expires_at:new Date(now+300000).toISOString(),books:[{bookmaker:'Example book',markets:{home:2.05,draw:4.2,away:3.05}}]}};
  await route.fulfill({json:{events:[event],updated_at:new Date(now).toISOString()}});
 });
 await calendar.goto('http://127.0.0.1:19047/');
 await calendar.locator('nav [data-page="calendar"]').click();
 await calendar.locator('#fixtures .team-odd').first().waitFor();
 const listing=await calendar.locator('#fixtures').innerText();
 if(!['2,05','3,05','4,20','Example book'].every(s=>listing.includes(s)))throw Error('Calendar does not show sourced 1X2 odds');
 for(const [side,price] of [['home','2,05'],['away','3,05']]){
  const group=calendar.locator('[data-crest-side="'+side+'"]');
  if((await group.locator('.team-odd').innerText())!==price)throw Error('Price under wrong team crest');
  const icon=await group.locator('.crest,.placeholder').boundingBox(),odd=await group.locator('.team-odd').boundingBox();
  if(!icon||!odd||odd.y<icon.y+icon.height)throw Error('Price is not below its crest');
 }
 if(await calendar.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Calendar odds overflow mobile');
 await calendar.screenshot({path:'artifacts/odds-calendar-mobile.png',fullPage:true});
 await calendar.close();
 console.log('Odds mobile: automatic prices, source escaping, stake, expiry, manual prices and net gain OK');
};
