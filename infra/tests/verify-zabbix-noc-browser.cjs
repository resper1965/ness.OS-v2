// Isolated browser smoke test. No trace, credentials, cookies or session IDs are saved.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.name));
    await page.goto('https://zabbix-uat.ness.com.br/zabbix/index.php?form=default', { waitUntil: 'domcontentloaded' });
    const user = page.locator('#name');
    const password = page.locator('#password');
    if (!(await user.isVisible()) || !(await password.isVisible())) {
      throw new Error('Local login fields unavailable; no credential submission');
    }
    const secret = execFileSync('wsl.exe', ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
      '-i', '/home/resper/.ssh/ness_os_zbx_prd_01', 'ness_admin@169.58.234.9',
      'sudo', 'cat', '/etc/ness-os/zabbix-uat-recovery.password'], { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
    await user.fill('ness_uat_breakglass');
    await password.fill(secret);
    await page.locator('#enter').click();
    await page.waitForURL(/zabbix\.php/, { timeout: 20000 });
    await page.goto('https://zabbix-uat.ness.com.br/zabbix/zabbix.php?action=dashboard.view&dashboardid=406', { waitUntil: 'domcontentloaded' });
    await page.getByText('UAT — NOC (snapshot 11/10/2026; sem coleta)', { exact: false }).first().waitFor({ timeout: 20000 });
    await page.waitForTimeout(3000);
    const pageChecks = [
      [/^NOC — Visão Geral$/, 'NOC — Disponibilidade Global de Hosts'],
      [/^Alupar\s*\(BR · CO · PE\)$/, 'Alupar — Disponibilidade de Hosts'],
      [/^TBE \+ TNE \(Transmissoras\)$/, 'TBE — Disponibilidade de Hosts'],
      [/^Corporativos$/, 'Target — Disponib.'],
      [/^Mapa — São Paulo$/, 'Distribuição geográfica — centro São Paulo'],
    ];
    const renderedPages = [];
    for (const [tab, title] of pageChecks) {
      await page.getByText(tab).first().click();
      await page.getByText(title, { exact: true }).first().waitFor({ timeout: 20000 });
      await page.waitForTimeout(1000);
      if (/Error connecting to database|Access denied for user|Fatal error/.test(await page.locator('body').innerText())) {
        throw new Error('Frontend error on dashboard page');
      }
      renderedPages.push(title);
    }
    await page.getByText(/^NOC — Visão Geral$/).first().click();
    await page.getByText('NOC — Disponibilidade Global de Hosts', { exact: true }).waitFor();
    const body = await page.locator('body').innerText();
    if (/Error connecting to database|Access denied for user|Fatal error/.test(body)) {
      throw new Error('Frontend error rendered');
    }
    if (errors.length) throw new Error('Client-side page error');
    if (process.argv[2]) await page.screenshot({ path: process.argv[2], fullPage: true });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(1000);
    const mobile = await page.evaluate(() => ({ viewport: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      overflow: document.documentElement.scrollWidth > window.innerWidth }));
    if (process.argv[2]) await page.screenshot({ path: process.argv[2].replace('.png', '-mobile.png'), fullPage: true });
    await page.setViewportSize({ width: 1600, height: 1000 });
    const result = { browser_login: 'PASS', dashboard: 406, rendered: true,
      rendered_pages: renderedPages.length, mobile, nominal_sso: 'NOT_TESTED', page_errors: errors };
    console.log(JSON.stringify(result));
    const logout = page.getByText(/Sign out|Desconectar|Sair/, { exact: true }).first();
    if (await logout.isVisible()) {
      await logout.click();
      await page.waitForLoadState('domcontentloaded');
      console.log('browser_logout=EXECUTED');
    } else {
      throw new Error('Logout control unavailable; inspect session expiry');
    }
    await context.close();
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error('Browser verification failed: ' + error.name);
  process.exitCode = 1;
});
