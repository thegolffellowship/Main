// Node runner for email_parser/screens_capture.py when Python Playwright is
// not installed (Claude Code sandboxes). Reads a jobs JSON written by
// capture_all and writes the same files. Never used by production.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  // Fonts must match the live Tracker (Kerry 10/26): route through the
  // sandbox proxy so Google Fonts (Bitter) load, and fail a shot whose page
  // asks for a web font that did not load, never save a fallback.
  const proxy = process.env.HTTPS_PROXY || process.env.https_proxy;
  // A demo page is served on 127.0.0.1 by tools/screens_demo.py: never through the proxy.
  const b = await chromium.launch(proxy ? { proxy: { server: proxy, bypass: '127.0.0.1,localhost' } } : {});
  const out = { done: [], errors: [] };
  for (const j of jobs) {
    const ctx = await b.newContext({ viewport: { width: j.w, height: j.h }, deviceScaleFactor: j.scale, isMobile: j.mobile,
                                     ignoreHTTPSErrors: !!proxy });
    await ctx.addInitScript(() => { try { sessionStorage.setItem('tgf_session_active', '1'); } catch (e) {} });
    const p = await ctx.newPage();
    try {
      if (j.html_file) { await p.setContent(fs.readFileSync(j.html_file, 'utf8'), { waitUntil: 'load' }); await p.waitForTimeout(300); }
      else {
        await p.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 45000 }); await p.waitForTimeout(5000);
        for (const sel of (j.click || [])) { await p.locator(sel).first().click({ timeout: 8000 }); await p.waitForTimeout(j.wait || 2500); }
      }
      await p.evaluate(() => document.fonts.ready);
      const missing = await p.evaluate(() => {
        const want = [...document.querySelectorAll('link[href*="fonts.googleapis"]')].length > 0;
        if (!want) return null;
        return document.fonts.check('700 16px Bitter') ? null : 'Bitter did not load';
      });
      if (missing) throw new Error(missing);
      await p.screenshot({ path: j.path, fullPage: j.full });
      out.done.push(j.name);
    } catch (e) { out.errors.push({ name: j.name, error: String(e).slice(0, 200) }); }
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out));
})();
