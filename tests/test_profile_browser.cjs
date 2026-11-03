const {chromium}=require('playwright');
const fs=require('fs');
const {randomUUID}=require('node:crypto');
const testEmail='mobile-'+randomUUID()+'@example.com';
const testPassword=randomUUID()+randomUUID();
fs.mkdirSync('artifacts',{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true});
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 for(let i=0;i<60;i++){try{await page.goto('http://127.0.0.1:19047/');break;}catch(e){if(i===59)throw e;await new Promise(r=>setTimeout(r,500));}}
 await page.locator('nav [data-page="info"]').click();
 await page.locator('[data-auth-tab="register"]').click();
 await page.locator('#authForm [name="nickname"]').fill('Jordan Test');
 await page.locator('#authForm [name="email"]').fill(testEmail);
 await page.locator('#authForm [name="password"]').fill(testPassword);
 await page.locator('#authForm [name="password_confirm"]').fill(testPassword);
 await page.locator('#authForm [name="accept_privacy"]').check();
 await page.locator('#authForm button[type="submit"], #authForm > button.btn').click();
 await page.locator('#recoveryCode').waitFor();
 await page.screenshot({path:'artifacts/profile-mobile.png',fullPage:true});
 if(!await page.locator('.profile-count').innerText().then(s=>s.includes('3')))throw Error('Missing trial count');
 await page.locator('#nicknameForm [name="nickname"]').fill('Jordan Pro');
 await page.locator('#nicknameForm .btn').click();
 await page.getByRole('heading',{name:'Jordan Pro',exact:true}).waitFor();
 await page.locator('nav [data-page="tickets"]').click();
 const data={home:'Paris',away:'Lyon',home_scored_avg:2,home_conceded_avg:1,away_scored_avg:1.5,away_conceded_avg:1.2,sample_matches_per_team:10};
 // The manual form was replaced by the ticket builder. Exercise the metered
 // analysis endpoint through the signed-in browser, then verify quota/history UI.
 const analysis=await page.evaluate(data=>window.Accounts.request('/api/analyse-statistique',data),data);
 if(analysis.error || analysis.status==='locked')throw Error('Metered analysis failed: '+JSON.stringify(analysis));
 await page.locator('nav [data-page="info"]').click();
 await page.waitForFunction(()=>document.querySelector('.profile-count')?.textContent.includes('2'));
 await page.locator('#logoutAccount').click();
 await page.locator('#authForm [name="email"]').waitFor();
 // The previous registration tab may remain selected after logout; select login explicitly.
 await page.locator('[data-auth-tab="login"]').click();
 await page.locator('#authForm [name="email"]').fill(testEmail);
 await page.locator('#authForm [name="password"]').fill(testPassword);
 await page.locator('#authForm > button.btn').click();
 await page.locator('#profileHistory [data-history="0"]').waitFor();
 await page.locator('#profileHistory [data-history="0"]').click();
 await page.locator('#profileHistory .analysis').waitFor();
 await page.locator('nav [data-page="premium"]').click();
 await page.locator('#premiumSubscribe').click();
 await page.locator('#billingAccount').waitFor();
 if(await page.locator('#billingSubscribe').isEnabled())throw Error('Unconfigured purchase must stay disabled');
 const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth);
 if(overflow)throw Error('Horizontal overflow');
 if(errors.length)throw Error(errors.join('; '));
 console.log('Mobile browser: registration, recovery code, profile edit, analysis, quota, logout/login and private history OK');
 await page.goto('http://127.0.0.1:19047/account-deletion');
 await page.locator('#deletePanel:not([hidden])').waitFor();
 await page.locator('#webDeleteConfirm [name="password"]').fill(testPassword);
 await page.locator('#webDeleteConfirm [name="confirmation"]').fill('SUPPRIMER');
 await page.locator('#webDeleteConfirm button').click();
 await page.waitForFunction(()=>document.getElementById('feedback').textContent.includes('ont été supprimés'));
 if(!await page.locator('#deletePanel').isVisible().then(visible=>!visible))throw Error('Deletion form remains visible after account deletion');
 console.log('Web account deletion: authenticated account and private data deleted OK');
 await require('./daily_opinion_mobile.cjs')(browser);
 await require('./personnel_mobile.cjs')(browser);
 await require('./odds_mobile.cjs')(browser);
 await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});

