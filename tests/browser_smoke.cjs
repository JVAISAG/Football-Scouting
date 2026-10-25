/* Optional browser QA. Requires Playwright and an installed Chromium/Edge browser. */
const fs=require('fs'),path=require('path'),assert=require('assert'),{pathToFileURL}=require('url');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
(async()=>{
 const browser=await chromium.launch({headless:true,args:["--disable-crash-reporter","--disable-crashpad","--noerrdialogs","--disable-gpu"],...(process.env.TOUCHLINE_BROWSER?{executablePath:process.env.TOUCHLINE_BROWSER}:(process.env.TOUCHLINE_USE_BUNDLED?{}:{channel:'msedge'}))});
 const context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 await context.setOffline(true);
 const page=await context.newPage(),errors=[],checks=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'dashboard.html')).href,{waitUntil:'load'});
 await page.locator('#overview-kpis .kpi').first().waitFor();
 assert.strictEqual(await page.locator('#overview-kpis .kpi').count(),4);checks.push('Overview and real-data metrics render offline');
 const qa=path.join(root,'reports','browser_qa');fs.mkdirSync(qa,{recursive:true});
 await page.screenshot({path:path.join(qa,'overview-desktop.png'),fullPage:true});
 await page.locator('[data-tab="scouting"]').click();
 await page.selectOption('#role-filter','Winger');
 const initial=await page.evaluate(()=>Touchline.getRows());assert(initial.length>0);
 await page.fill('#search-filter',initial[0].display_name);assert.strictEqual(await page.locator('#scouting-table tr[data-player]').count(),1);
 await page.fill('#search-filter','no-such-player-xyz');assert((await page.locator('#scouting-table').innerText()).includes('No players'));
 await page.fill('#search-filter','');await page.selectOption('#minute-filter','1800');
 assert(await page.evaluate(()=>Touchline.getRows().every(r=>r.minutes>=1800&&r.role==='Winger')));checks.push('Role, name, empty-result and minimum-minute filters');
 await page.selectOption('#minute-filter','900');
 const club=initial[0].team;await page.selectOption('#club-filter',club);assert(await page.evaluate(c=>Touchline.getRows().every(r=>r.team===c),club));await page.selectOption('#club-filter','');checks.push('Club filter');
 await page.locator('[data-sort="npxg_p90"]').click();assert(await page.evaluate(()=>{let r=Touchline.getRows();return r.every((x,i)=>i===0||r[i-1].npxg_p90>=x.npxg_p90);}));checks.push('Numeric sorting');
 await page.locator('#scouting-table tr[data-player]').nth(1).click();
 const chosen=await page.locator('#scouting-table tr.selected strong').innerText();assert.strictEqual(await page.locator('#profile-name').innerText(),chosen);checks.push('Player profile and grouped shot map update');
 const downloadPromise=page.waitForEvent('download');await page.locator('#export-button').click();const download=await downloadPromise;await download.saveAs(path.join(qa,'shortlist-export.csv'));assert(fs.readFileSync(path.join(qa,'shortlist-export.csv'),'utf8').includes('display_name'));checks.push('CSV shortlist export');
 await page.screenshot({path:path.join(qa,'scouting-desktop.png'),fullPage:true});
 await page.locator('[data-tab="xg"]').click();const before=await page.locator('#shot-probability').innerText();
 await page.locator('#shot-x').evaluate(el=>{el.value='114';el.dispatchEvent(new Event('input',{bubbles:true}));});const after=await page.locator('#shot-probability').innerText();assert.notStrictEqual(before,after);checks.push('Interactive shot location changes model prediction');
 const fixtures=JSON.parse(fs.readFileSync(path.join(root,'reports','browser_model_fixtures.json'),'utf8'));
 const probabilities=await page.evaluate(rows=>rows.map(r=>Touchline.predictXg(r.features)),fixtures.predictions);
 const maxError=Math.max(...probabilities.map((p,i)=>Math.abs(p-fixtures.predictions[i].expected)));
 assert(maxError<1e-10);checks.push(`Browser/Python model parity: ${probabilities.length} shots, maximum error ${maxError}`);
 await page.screenshot({path:path.join(qa,'xg-desktop.png'),fullPage:true});
 const scenarios=await page.evaluate(budgets=>budgets.map(b=>Touchline.optimizeRecruitment(Touchline.getData().scouting,b)),fixtures.optimizations.map(x=>x.budget));
 scenarios.forEach((r,i)=>{let e=fixtures.optimizations[i];assert.strictEqual(r.feasible,e.feasible);if(r.feasible){assert.strictEqual(r.total_cost,e.total_cost);assert(Math.abs(r.total_score-e.total_score)<1e-6);assert.deepStrictEqual(r.selection.map(x=>x.player_id),e.selection.map(x=>x.player_id));}});checks.push('Browser/Python exact optimization parity for seven budgets');
 await page.locator('[data-tab="recruitment"]').click();await page.locator('#budget-slider').evaluate(el=>{el.value='30';el.dispatchEvent(new Event('change',{bubbles:true}));});assert.strictEqual(await page.locator('#recruitment-cards .recruit').count(),0);assert((await page.locator('#recruitment-status').innerText()).includes('No eligible'));checks.push('Infeasible budget has an explicit empty state');
 await page.locator('#budget-slider').evaluate(el=>{el.value='90';el.dispatchEvent(new Event('input',{bubbles:true}));});await page.locator('#optimize-button').click();assert.strictEqual(await page.locator('#recruitment-cards .recruit').count(),3);checks.push('Budget control and optimization action');
 await page.screenshot({path:path.join(qa,'recruitment-desktop.png'),fullPage:true});
 await page.locator('[data-tab="methods"]').click();assert((await page.locator('#methods').innerText()).includes('in-sample'));checks.push('Methods and limitations render');
 await page.setViewportSize({width:390,height:844});
 for(const tab of ['overview','scouting','xg','recruitment','methods']){
  await page.locator(`[data-tab="${tab}"]`).click();
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Horizontal page overflow in mobile ${tab}`);
  if(tab==='overview'||tab==='recruitment')await page.screenshot({path:path.join(qa,`${tab}-mobile.png`),fullPage:true});
 }
 checks.push('All five sections fit a 390-pixel mobile viewport');
 assert.deepStrictEqual(errors,[]);checks.push('No browser JavaScript errors');
 const result={checks_passed:checks.length,checks,console_errors:errors,model_max_absolute_error:maxError,browser:await browser.version(),offline:true};
 fs.writeFileSync(path.join(root,'reports','browser_validation.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result,null,2));await browser.close();
})().catch(e=>{console.error(e);process.exit(1);});

