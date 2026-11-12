// Capturas mobile do Hub com API mockada (dado sintético).
// Uso: docker run --rm -v $PWD:/app -v /tmp/shots:/shots -w /app mcr.microsoft.com/playwright:v1.56.0-noble \
//   sh -c "npm ci && npx vite build && (npx vite preview --port 4173 &) && sleep 4 && npm i --no-save playwright@1.56.0 && node scripts/mobile-shots.mjs"
// Falha se alguma tela rolar na horizontal.
import { chromium, devices } from 'playwright';

const base = process.env.BASE || 'http://127.0.0.1:4173';
const out = process.env.OUT || '/shots';
const now = new Date().toISOString();
const inc = (i) => ({
  id: i, fingerprint: String(i).padStart(64, 'a'), title: `Link WAN indisponível no site ${i}`,
  host_name: `fw-cliente-${i}`, customer_name: 'Cavan', severity: [5, 4, 3, 2][i % 4],
  status: 'open', alert_count: 3, first_seen: now, last_seen: now, deskmanager_ticket_id: String(9000 + i),
});
const api = {
  '/api/auth/me': { id: 1, email: 'tecnico@example.com', full_name: 'Técnico Sintético', role: process.env.ROLE || 'noc' },
  '/api/auth/oidc/config': { enabled: false },
  '/api/dashboard/summary': { hosts_active: 1240, items_total: 98765, problems_critical: 3, problems_total: 18 },
  '/api/dashboard/problems': { problems: Array.from({ length: 6 }, (_, i) => ({ id: i, name: `CPU alta em srv-${i}`, host: `srv-${i}`, severity: (i % 5) + 1, clock: Math.floor(Date.now() / 1000) - i * 600, customer: 'Cavan' })) },
  '/api/dashboard/pipeline-status': { zabbix: { status: 'ok' }, api: { status: 'ok' }, glpi: { status: 'ok' }, deskmanager: { status: 'ok' } },
  '/api/incidents': { incidents: Array.from({ length: 8 }, (_, i) => inc(i + 1)), total: 8 },
  '/api/notifications/inbox': [],
  '/api/tenants/security-audit': [],
  '/api/tenants/list': [{ id: 'cavan', name: 'Cavan' }],
};

const browser = await chromium.launch();
const views = (process.env.VIEWS || 'login,dashboard,incidents').split(',');
for (const dev of ['iPhone 13', 'Pixel 5', 'Desktop Chrome']) {
  for (const view of views) {
    const ctx = await browser.newContext({ ...devices[dev] });
    const page = await ctx.newPage();
    await page.route('**/api/**', (route) => {
      const path = new URL(route.request().url()).pathname;
      if (view === 'login' && path === '/api/auth/me') return route.fulfill({ status: 401, body: '{}' });
      if (path.endsWith('/stream')) return route.fulfill({ status: 204, body: '' });
      const key = Object.keys(api).find((k) => path === k);
      return route.fulfill({ status: key ? 200 : 404, contentType: 'application/json', body: JSON.stringify(key ? api[key] : {}) });
    });
    await page.goto(`${base}/?view=${view}`);
    await page.waitForTimeout(1500);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    const name = `${out}/${dev.replace(/ /g, '')}-${view}.png`;
    await page.screenshot({ path: name });
    const menu = page.getByLabel('Abrir menu');
    if (view === 'incidents' && dev === 'iPhone 13' && await menu.isVisible()) { await menu.click(); await page.waitForTimeout(400); await page.screenshot({ path: `${out}/${dev.replace(/ /g, '')}-nav.png` }); }
    console.log(name, 'overflowX=', overflow);
    if (overflow > 0) process.exitCode = 1;
    await ctx.close();
  }
}
await browser.close();
