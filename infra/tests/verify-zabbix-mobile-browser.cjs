// Isolated native-dashboard geometry check; no cookie/token/trace persisted.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const assert = require('node:assert/strict');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const context = await browser.newContext({viewport:{width:1600,height:1000}});
  const page = await context.newPage();
  let logoutUrl;
  try {
    await page.goto('https://zabbix-uat.ness.com.br/zabbix/index.php?form=default');
    assert(await page.locator('#name').isVisible());
    const secret = execFileSync('wsl.exe',['ssh','-o','BatchMode=yes','-o','ConnectTimeout=15',
      '-i','/home/resper/.ssh/ness_os_zbx_prd_01','ness_admin@169.58.234.9',
      'sudo','cat','/etc/ness-os/zabbix-uat-recovery.password'],
      {encoding:'utf8',stdio:['ignore','pipe','pipe']}).trim();
    await page.locator('#name').fill('ness_uat_breakglass');
    await page.locator('#password').fill(secret);
    await page.locator('#enter').click();
    await page.waitForURL(/zabbix\.php/,{timeout:20000});
    logoutUrl = await page.locator('a').filter({hasText:/^(Sign out|Desconectar|Sair)$/}).first().getAttribute('href');
    assert(logoutUrl, 'Trusted logout link must exist');
    logoutUrl = new URL(logoutUrl,page.url()).href;
    assert.equal(new URL(logoutUrl).hostname,'zabbix-uat.ness.com.br');
    for (const id of [406,407]) {
      await page.goto('https://zabbix-uat.ness.com.br/zabbix/zabbix.php?action=dashboard.view&dashboardid='+id);
      await page.locator('.dashboard-grid-widget').first().waitFor();
      await page.setViewportSize({width:390,height:844});
      const hide = page.locator('button.js-sidebar-mode.button-hide');
      if (await hide.isVisible()) await hide.click();
      await page.waitForTimeout(2000);
      const sizes = await page.locator('.dashboard-grid-widget').evaluateAll(nodes => nodes.map(node => {
        const r=node.getBoundingClientRect();
        return {x:r.x,right:r.right,width:r.width,height:r.height};
      }));
      assert(sizes.length > 0);
      if (!sizes.every(r=>r.x>=0 && r.right<=390 && r.width>=300 && r.height>0)) {
        const diagnostics = await page.locator('.dashboard-grid').evaluate(node=>{
          const parents=[];
          for (let p=node;p;p=p.parentElement) {
            const s=getComputedStyle(p),r=p.getBoundingClientRect();
            parents.push({tag:p.tagName,class:p.className,width:r.width,minWidth:s.minWidth,display:s.display});
          }
          return {parents,cssLoaded:[...document.querySelectorAll('link[rel="stylesheet"]')]
            .some(l=>l.href.includes('ness-mobile.css'))};
        });
        console.log(JSON.stringify({mobile_geometry:'FAIL',dashboard:id,sizes,diagnostics}));
      }
      assert(sizes.every(r=>r.x>=0 && r.right<=390 && r.width>=300 && r.height>0),
        'Every mobile widget must fit and remain readable, not merely hide overflow');
      const content = await page.locator('.item-time, .item-value-content').evaluateAll(nodes=>nodes.map(n=>{
        const w=n.closest('.dashboard-grid-widget').getBoundingClientRect(),r=n.getBoundingClientRect();
        return {fits:r.left>=w.left&&r.right<=w.right&&n.scrollWidth<=n.clientWidth+1};
      }));
      if (id===407) assert(content.length>=12, 'Value and time must be present for each link metric');
      assert(content.every(n=>n.fits), 'Values and timestamps must not be clipped inside a fitted widget');
      await page.locator('h1').first().scrollIntoViewIfNeeded();
      if (process.argv[2]) await page.screenshot({path:process.argv[2].replace('.png','-'+id+'-top.png'),fullPage:true});
      const edit = page.locator('#dashboard-edit');
      if (id===407 && await edit.isVisible() && await edit.isEnabled()) {
        await edit.click();
        await page.locator('.dashboard-is-edit-mode').waitFor();
        const position = await page.locator('.dashboard-grid-widget').first()
          .evaluate(n=>getComputedStyle(n).position);
        assert.equal(position,'absolute','Mobile read layout must not override native edit geometry');
        await page.locator('#dashboard-cancel').click();
        await page.locator('.dashboard:not(.dashboard-is-edit-mode)').waitFor();
        console.log('native_edit_mode=PASS; saved_layout=NOT_CHANGED');
      }
      await page.locator('.dashboard-grid-widget').last().scrollIntoViewIfNeeded();
      const last = await page.locator('.dashboard-grid-widget').last().boundingBox();
      assert(last && last.y>=0 && last.y<844, 'Last widget must be reachable by scrolling');
      if (process.argv[2]) await page.screenshot({path:process.argv[2].replace('.png','-'+id+'.png'),fullPage:true});
      await page.setViewportSize({width:1600,height:1000});
      await page.waitForTimeout(500);
      const desktop = await page.locator('.dashboard-grid-widget').first().boundingBox();
      assert(desktop && desktop.width>0 && desktop.x>=0);
      console.log('mobile_geometry=PASS; dashboard='+id+'; widgets='+sizes.length+'; desktop=PASS; sso=NOT_TESTED');
    }
  } finally {
    try {
      if (logoutUrl) {
        await page.goto(logoutUrl,{waitUntil:'domcontentloaded',timeout:20000});
        console.log('browser_logout=EXECUTED');
      }
    } finally {
      await context.close();
      await browser.close();
    }
  }
})().catch(error=>{console.error('Mobile verification failed: '+error.name);process.exitCode=1;});
