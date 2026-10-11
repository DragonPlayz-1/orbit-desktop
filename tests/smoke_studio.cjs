// Install Playwright externally, then NODE_PATH=<node_modules> node tests/smoke_studio.cjs.
// Starts an isolated Studio instance and leaves user settings untouched.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {spawn} = require('node:child_process');
const delay = ms => new Promise(r=>setTimeout(r,ms));
(async () => {
  const home=fs.mkdtempSync(path.join(os.tmpdir(),'orbit-browser-'));
  const env={...process.env,HOME:home,XDG_CONFIG_HOME:path.join(home,'config'),XDG_CACHE_HOME:path.join(home,'cache'),XDG_STATE_HOME:path.join(home,'state'),XDG_DATA_HOME:path.join(home,'data'),EWW_BIN:'orbit-no-eww-for-browser-test',PYTHONDONTWRITEBYTECODE:'1'};
  for(const key of ['DASHBOARD_CONFIG_HOME','DASHBOARD_CONFIG_FILE','DASHBOARD_SETTINGS_FILE'])delete env[key];
  const server=spawn('python3',[path.resolve(__dirname,'../eww/dashboard/lib/studio.py'),'--no-browser','--port','18765'],{env,stdio:['ignore','pipe','pipe']});
  let logs='',url='';server.stdout.on('data',b=>{logs+=b;const match=logs.match(/Orbit Studio: (http[^\s]+)/);if(match)url=match[1];});server.stderr.on('data',b=>logs+=b);
  let browser;
  try {
    for(let i=0;i<100&&!url;i++)await delay(100);
    assert(url,logs||'Studio did not start');
    browser = await chromium.launch({headless:true});
    const page = await browser.newPage({viewport:{width:1440,height:1050}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(url);
    await page.getByRole('heading',{name:'Good things start here.'}).waitFor();
    const nav=name=>page.getByRole('navigation').getByRole('button',{name,exact:true}).click();
    for(const name of ['Appearance','Layout & cards','Profile & clock','Weather','Music & system','Applications','Links','Places','Advanced','Backups & health','Overview']) {
      await nav(name);await page.locator('#content h1').waitFor();
    }
    await nav('Appearance');
    await page.getByRole('button',{name:'midnight',exact:true}).click();
    await page.getByLabel('Corner radius',{exact:true}).fill('18');
    await page.getByRole('button',{name:/Save & apply/}).click();
    await page.locator('#message').filter({hasText:'Saved.'}).waitFor();
    await page.reload();await page.getByRole('heading',{name:'Good things start here.'}).waitFor();
    await nav('Appearance');assert.equal(await page.getByLabel('Corner radius',{exact:true}).inputValue(),'18');
    if(process.env.ORBIT_SCREENSHOT)await page.screenshot({path:process.env.ORBIT_SCREENSHOT,fullPage:true});
    await nav('Profile & clock');await page.getByLabel('Display name',{exact:true}).fill('Renée " ${literal}');
    await page.getByRole('button',{name:'Discard changes',exact:true}).click();
    assert.notEqual(await page.getByLabel('Display name',{exact:true}).inputValue(),'Renée " ${literal}');
    await nav('Appearance');await page.getByLabel('Corner radius',{exact:true}).fill('100');
    await page.getByRole('button',{name:/Save & apply/}).click();await page.locator('#message.error').filter({hasText:'appearance.radius'}).waitFor();
    await page.getByRole('button',{name:'Discard changes',exact:true}).click();
    await nav('Weather');
    // Deterministic geocoder fixture; no public network dependency in CI.
    await page.route('**/api/search',route=>route.fulfill({json:{results:[{name:'Copenhagen, Denmark',latitude:'55.68',longitude:'12.57'}]}}));
    await page.getByLabel('City name',{exact:true}).fill('Copenhagen');await page.getByRole('button',{name:'Search cities',exact:true}).click();
    await page.getByRole('button',{name:'Copenhagen, Denmark',exact:true}).click();
    assert.equal(await page.getByLabel('Location label',{exact:true}).inputValue(),'Copenhagen, Denmark');
    await page.getByRole('button',{name:'Discard changes',exact:true}).click();
    await nav('Backups & health');
    const exported=JSON.parse(fs.readFileSync(path.join(home,'config/eww-dashboard/settings.json'),'utf8'));
    exported.profile.name='Imported profile';exported.advanced.enabled=true;
    await page.locator('#import-file').setInputFiles({name:'settings.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(exported))});
    await page.locator('#message').filter({hasText:'Imported into your draft'}).waitFor();
    await nav('Advanced');assert.equal(await page.getByRole('checkbox').first().isChecked(),false);
    await page.getByRole('button',{name:'Discard changes',exact:true}).click();
    await nav('Appearance');
    for(const width of [390,768,1366,1920]) {
      await page.setViewportSize({width,height:900});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`UI overflows at ${width}px`);
    }
    assert.deepEqual(errors,[]);
    console.log('PASS: Studio sections, save/reload/discard, invalid settings, city search, import, disabled commands, four viewport sizes');
  } finally {
    if(browser)await browser.close();
    const exited=new Promise(resolve=>server.once('exit',resolve));
    server.kill('SIGTERM');await Promise.race([exited,delay(5000)]);
    fs.rmSync(home,{recursive:true,force:true});
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
