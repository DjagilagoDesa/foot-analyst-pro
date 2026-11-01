/* Capture the real public application, without fake match data or a personal session. */
const {chromium}=require('playwright');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:360,height:640},deviceScaleFactor:3,reducedMotion:'reduce',locale:'fr-FR',timezoneId:'Europe/Paris'});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 fs.mkdirSync('store-assets/screenshots',{recursive:true});
 await page.goto('https://foot-analyst-pro.onrender.com/',{waitUntil:'domcontentloaded',timeout:120000});
 await page.locator('#homeDailyOpinion .opinion-group').first().waitFor({timeout:90000});
 await page.screenshot({path:'store-assets/screenshots/01-accueil.png'});
 await page.locator('nav [data-page="dailyTickets"]').click();
 await page.locator('#dailyOpinionResult .opinion-group').first().waitFor();
 await page.screenshot({path:'store-assets/screenshots/02-avis-du-jour.png'});
 await page.locator('nav [data-page="calendar"]').click();
 await page.waitForFunction(()=>{const text=document.getElementById('fixtures')?.innerText||'';return text&&!/Chargement/.test(text);},{},{timeout:90000});
 await page.screenshot({path:'store-assets/screenshots/03-calendrier.png'});
 if(errors.length)throw Error(errors.join('; '));
 fs.writeFileSync('store-assets/screenshots/capture-info.json',JSON.stringify({captured_at:new Date().toISOString(),origin:'https://foot-analyst-pro.onrender.com/',viewport:{width:360,height:640},pixels:{width:1080,height:1920},data:'Real public service; no user account and no invented fixtures'},null,2));
 await browser.close();
 console.log('Three real application screenshots captured at 1080×1920.');
})().catch(e=>{console.error(e);process.exit(1)});
