const fs=require('fs');
module.exports=async browser=>{
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.clock.install();
 const styles=fs.readFileSync('index.html','utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
 await page.setContent('<html lang="fr"><head><style>'+styles+'</style></head><body><main><section id="detail"><div id="analysisResult"><div class="analysis-report"><section class="report-section" data-personnel-section><h3>Compositions et disponibilités signalées</h3><p>Composition indisponible lors de la première analyse.</p></section></div></div></section></main></body></html>');
 await page.evaluate(()=>{
  window.escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const now=Date.now();window.calls=[];
  const first={observed_at:new Date(now-600000).toISOString(),kickoff:new Date(now+86400000).toISOString(),teams:{'1':{starters:[],availability:[]}}};
  const latest={...first,observed_at:new Date(now).toISOString(),teams:{'1':{starters:[{name:'Titulaire <img src=x onerror=alert(1)>'}],availability:[]}}};
  window.testPersonnel={tracking_id:'saved-id',league:'fra.1',event_id:'123',home_id:'1',away_id:'2',home_name:'Paris',away_name:'Lyon',personnel_context:first,personnel_snapshots:[first]};
  window.Accounts={request:async(path,data)=>{window.calls.push({path,data});return {status:'updated',personnel_context:latest,personnel_snapshots:[first,latest],section:{title:'Compositions et disponibilités signalées',text:'Paris : titulaire signalé par la source. Confirmation officielle non vérifiée.',source_url:'https://www.espn.com/soccer/match/_/gameId/123'}};}};
 });
 await page.addScriptTag({path:'personnel.js'});
 await page.evaluate(()=>window.Personnel.attach(document.getElementById('analysisResult'),window.testPersonnel));
 await page.getByRole('button',{name:'ACTUALISER LES EFFECTIFS',exact:false}).click();
 await page.getByText('Confirmation officielle non vérifiée.',{exact:false}).waitFor();
 await page.locator('.personnel-history summary').click();
 if(await page.locator('.personnel-history img').count())throw Error('Unescaped upstream player name');
 if(!(await page.locator('.personnel-history').innerText()).includes('Titulaire <img'))throw Error('Missing archived player name');
 const calls=await page.evaluate(()=>window.calls);
 if(calls.length!==1||calls[0].path!=='/api/account/analysis/saved-id/personnel')throw Error('Personnel refresh used wrong endpoint');
 await page.clock.fastForward(300001);
 await page.waitForFunction(()=>window.calls.length===2);
 await page.evaluate(()=>document.getElementById('detail').classList.add('hidden'));
 await page.clock.fastForward(300001);
 if(await page.evaluate(()=>window.calls.length)!==2)throw Error('Hidden analysis made a request');
 await page.evaluate(()=>{window.Personnel.stop();document.getElementById('detail').classList.remove('hidden');});
 if(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth))throw Error('Personnel panel overflows mobile');
 fs.mkdirSync('artifacts',{recursive:true});await page.screenshot({path:'artifacts/personnel-mobile.png',fullPage:true});
 if(errors.length)throw Error(errors.join('; '));
 console.log('Personnel mobile: saved-analysis refresh, escaped snapshots, foreground timer and mobile layout OK');
 await page.close();
};
if(require.main===module){const {chromium}=require('playwright');(async()=>{const b=await chromium.launch({headless:true});try{await module.exports(b);}finally{await b.close();}})().catch(e=>{console.error(e);process.exit(1);});}
