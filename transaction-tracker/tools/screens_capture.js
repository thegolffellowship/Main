// Node runner for email_parser/screens_capture.py when Python Playwright is
// not installed (Claude Code sandboxes). Reads a jobs JSON written by
// capture_all and writes the same files. Never used by production.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const jobs = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
  const b = await chromium.launch();
  const out = { done: [], errors: [] };
  for (const j of jobs) {
    const ctx = await b.newContext({ viewport: { width: j.w, height: j.h }, deviceScaleFactor: j.scale, isMobile: j.mobile });
    await ctx.addInitScript(() => { try { sessionStorage.setItem('tgf_session_active', '1'); } catch (e) {} });
    const p = await ctx.newPage();
    try {
      if (j.html_file) { await p.setContent(fs.readFileSync(j.html_file, 'utf8'), { waitUntil: 'load' }); await p.waitForTimeout(300); }
      else { await p.goto(j.url, { waitUntil: 'domcontentloaded', timeout: 45000 }); await p.waitForTimeout(5000); }
      await p.screenshot({ path: j.path, fullPage: j.full });
      out.done.push(j.name);
    } catch (e) { out.errors.push({ name: j.name, error: String(e).slice(0, 200) }); }
    await ctx.close();
  }
  await b.close();
  console.log(JSON.stringify(out));
})();
