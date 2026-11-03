const fs=require('fs');
module.exports=async browser=>{
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));await page.clock.install();
 const styles=fs.readFileSync('index.html','utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
 await page.setContent('<html lang="fr"><head><style>'+styles+'</style></head><body><main id="ticket"></main></body></html>');
 await page.evaluate(()=>{
  window.escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  window.api=async()=>({books:[{bookmaker:'Example <book>',markets:{btts:1.85,over_2_5:2.1}}],observed_at:new Date().toISOString(),expires_at:new Date(Date.now()+300000).toISOString()});
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
 if(errors.length)throw Error(errors.join('; '));await page.close();
 console.log('Odds mobile: automatic prices, source escaping, stake, expiry, manual prices and net gain OK');
};
