const fs = require('node:fs');
const path = require('node:path');
const { fileURLToPath, pathToFileURL } = require('node:url');

async function main() {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const { chromium } = require('playwright');
  const root = fs.realpathSync(request.resource_root);
  const mainFile = fs.realpathSync(request.input_path);
  const browser = await chromium.launch({ headless: true, executablePath: request.browser_executable });
  try {
    const context = await browser.newContext({
      viewport: { width: request.viewport_width, height: request.viewport_height },
      javaScriptEnabled: request.allow_javascript,
      acceptDownloads: false,
    });
    const page = await context.newPage();
    const seen = new Set();
    let bytes = 0;
    await page.route('**/*', async route => {
      const url = route.request().url();
      if (url.startsWith('data:') || url.startsWith('about:')) return route.continue();
      if (!url.startsWith('file:')) return route.abort('blockedbyclient');
      let local;
      try { local = fs.realpathSync(fileURLToPath(url)); } catch { return route.abort('blockedbyclient'); }
      const relative = path.relative(root, local);
      if (relative.startsWith('..' + path.sep) || relative === '..' || path.isAbsolute(relative)) {
        return route.abort('blockedbyclient');
      }
      try {
        const stat = fs.statSync(local);
        if (!stat.isFile() || stat.size > 20 * 1024 * 1024) return route.abort('blockedbyclient');
        if (!seen.has(local)) {
          if (bytes + stat.size > 100 * 1024 * 1024) return route.abort('blockedbyclient');
          seen.add(local);
          bytes += stat.size;
        }
        return route.continue();
      } catch { return route.abort('blockedbyclient'); }
    });
    // page.route only covers HTTP(S)/file fetches. When JavaScript is enabled, close
    // WebSocket attempts so network_access:false still holds for that channel.
    page.on('websocket', ws => {
      try { ws.close(); } catch { /* ignore */ }
    });
    if (typeof page.routeWebSocket === 'function') {
      await page.routeWebSocket(/.*/, route => {
        try { route.abort(); } catch { try { route.close(); } catch { /* ignore */ } }
      });
    }
    await page.goto(pathToFileURL(mainFile).href, { waitUntil: 'load', timeout: request.timeout_seconds * 1000 });
    await page.evaluate(() => document.fonts.ready);
    const details = await page.evaluate(() => ({
      title: document.title || '',
      height: Math.max(document.documentElement.scrollHeight, document.body?.scrollHeight || 0),
    }));
    if (details.height > 20000) throw Object.assign(new Error('Rendered document exceeds the 20,000 pixel height limit.'), { code: 'DOCUMENT_TOO_TALL' });
    if (request.format === 'pdf') {
      await page.emulateMedia({ media: 'print' });
      await page.pdf({ path: request.output_path, format: request.page_size, printBackground: true, preferCSSPageSize: true });
    } else {
      await page.screenshot({ path: request.output_path, fullPage: true, type: 'png', timeout: request.timeout_seconds * 1000 });
    }
    process.stdout.write(JSON.stringify({
      ok: true, browser: await browser.version(), page_title: details.title,
      document_height: details.height, local_resources: seen.size, local_resource_bytes: bytes,
    }));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  process.stdout.write(JSON.stringify({ ok: false, code: error.code || 'RENDER_FAILED', message: String(error.message || error).slice(0, 1000) }));
  process.exitCode = 1;
});
