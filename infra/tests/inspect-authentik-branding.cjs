const { chromium } = require('playwright');
const path = require('path');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true });
  try {
    for (const width of [1440, 390]) {
      const page = await browser.newPage({ viewport: { width, height: 900 }, locale: 'pt-BR', reducedMotion: 'reduce' });
      await page.goto('https://sso.ness.com.br/if/flow/default-authentication-flow/', { waitUntil: 'networkidle' });
      const result = await page.evaluate(() => {
        const elements = [];
        function visit(root) {
          for (const el of root.querySelectorAll('*')) {
            if (el.shadowRoot) visit(el.shadowRoot);
            if (el.matches('h1,h2,input,button,img') && el.getBoundingClientRect().width) {
              const box = el.getBoundingClientRect(), style = getComputedStyle(el);
              elements.push({ tag: el.tagName, text: el.matches('input') ? '' : el.textContent.trim().slice(0, 100),
                classes: el.className, src: el.matches('img') ? new URL(el.src).pathname : undefined,
                x: box.x, width: box.width, height: box.height, filter: style.filter,
                background: style.backgroundImage, color: style.color,
                backgroundColor: style.backgroundColor, transition: style.transitionDuration });
            }
          }
        }
        visit(document);
        return { title: document.title, overflow: document.documentElement.scrollWidth > innerWidth, elements };
      });
      console.log(JSON.stringify({ width, ...result }));
      await page.screenshot({ path: path.join(process.env.AUTHENTIK_SCREENSHOT_DIR, `authentik-${process.env.AUTHENTIK_PHASE || 'before'}-${width}.png`), fullPage: true });
      if (process.env.AUTHENTIK_PHASE === 'after') {
        assert(!result.overflow, 'Login must not overflow');
        assert(result.elements.some(e => e.text === 'Acesse sua conta'), 'Login heading missing');
        assert(!result.elements.some(e => /^ness\.$/i.test(e.text)), 'Duplicate textual brand heading');
        assert(result.elements.some(e => e.tag === 'INPUT'), 'Login input missing');
        for (const button of result.elements.filter(e => e.tag === 'BUTTON')) {
          assert(button.height >= 48, 'Touch target too small');
          assert(button.background === 'none', 'Brand action must not use a gradient');
          assert(button.backgroundColor === 'rgb(0, 173, 232)', 'BlueDot action color changed');
          assert(button.color === 'rgb(0, 0, 0)', 'Action contrast changed');
          assert(button.transition === '0s', 'Reduced-motion must disable action transitions');
        }
      }
      await page.close();
    }
  } finally { await browser.close(); }
})().catch(e => { console.error(e.message); process.exitCode = 1; });
