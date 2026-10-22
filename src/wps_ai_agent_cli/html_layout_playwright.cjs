// Computed styles and positions for html_styles.py (P13-004, P13-006).
// Reads a request on stdin: { input_path, resource_root, browser_executable, viewport_width, viewport_height,
// timeout_seconds, section_screenshots_dir? }. The HTML has a data-wps-i attribute on every element; the reply
// lists, for each, the computed style properties the converters use and the element's box in CSS pixels.
// Network access is blocked and JavaScript is off, as in html_render_playwright.cjs.
const fs = require('node:fs');
const path = require('node:path');
const { fileURLToPath, pathToFileURL } = require('node:url');

const PROPERTIES = [
  'display', 'position', 'font-family', 'font-size', 'font-weight', 'font-style', 'color', 'background-color',
  'background-image', 'text-decoration-line', 'letter-spacing', 'vertical-align', 'text-align', 'line-height',
  'margin-top', 'margin-bottom', 'margin-left', 'margin-right', 'padding-top', 'padding-bottom', 'padding-left',
  'padding-right', 'text-indent', 'border-top-width', 'border-top-style', 'border-top-color', 'border-bottom-width',
  'border-bottom-style', 'border-bottom-color', 'border-left-width', 'border-left-style', 'border-left-color',
  'border-right-width', 'border-right-style', 'border-right-color', 'break-before', 'page-break-before', 'width',
  'height', 'float', 'visibility', 'opacity', 'white-space',
];

async function main() {
  const request = JSON.parse(fs.readFileSync(0, 'utf8'));
  const { chromium } = require('playwright');
  const root = fs.realpathSync(request.resource_root);
  const mainFile = fs.realpathSync(request.input_path);
  const browser = await chromium.launch({ headless: true, executablePath: request.browser_executable });
  try {
    const context = await browser.newContext({
      viewport: { width: request.viewport_width, height: request.viewport_height },
      javaScriptEnabled: false,
      acceptDownloads: false,
    });
    const page = await context.newPage();
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
      return route.continue();
    });
    await page.goto(pathToFileURL(mainFile).href, { waitUntil: 'load', timeout: request.timeout_seconds * 1000 });
    await page.evaluate(() => document.fonts.ready);
    const elements = await page.evaluate(properties => {
      const result = {};
      // "line-height: normal" depends on the font: measure it once per font, so that a document can set the line
      // the browser drew (WPS gives Microsoft YaHei a taller "single" line than the browser's normal one).
      const normal = new Map();
      const normalLine = style => {
        const key = [style.fontFamily, style.fontSize, style.fontWeight, style.fontStyle].join('|');
        if (!normal.has(key)) {
          const probe = document.createElement('div');
          probe.style.cssText = 'position:absolute;left:-10000px;top:0;visibility:hidden;white-space:nowrap;' +
            'line-height:normal;margin:0;padding:0;border:0';
          probe.style.fontFamily = style.fontFamily;
          probe.style.fontSize = style.fontSize;
          probe.style.fontWeight = style.fontWeight;
          probe.style.fontStyle = style.fontStyle;
          probe.textContent = '\u56fdAg';
          document.body.appendChild(probe);
          normal.set(key, probe.getBoundingClientRect().height);
          probe.remove();
        }
        return normal.get(key);
      };
      for (const element of document.querySelectorAll('[data-wps-i]')) {
        const style = getComputedStyle(element);
        const box = element.getBoundingClientRect();
        const values = {};
        for (const name of properties) values[name] = style.getPropertyValue(name);
        if (values['line-height'] === 'normal' && document.body) {
          values['line-height-normal'] = `${normalLine(style)}px`;
        }
        result[element.getAttribute('data-wps-i')] = {
          tag: element.tagName.toLowerCase(),
          box: { x: box.left + window.scrollX, y: box.top + window.scrollY, width: box.width, height: box.height },
          style: values,
        };
      }
      return result;
    }, PROPERTIES);
    const shots = [];
    if (request.section_screenshots_dir) {
      const sections = await page.$$('section');
      let index = 0;
      for (const section of sections) {
        index += 1;
        const file = path.join(request.section_screenshots_dir, `section-${String(index).padStart(3, '0')}.png`);
        await section.screenshot({ path: file, animations: 'disabled' });
        shots.push(file);
      }
    }
    process.stdout.write(JSON.stringify({ ok: true, browser: await browser.version(), elements, section_screenshots: shots }));
  } finally {
    await browser.close();
  }
}

main().catch(error => {
  process.stdout.write(JSON.stringify({ ok: false, code: error.code || 'LAYOUT_FAILED', message: String(error.message || error).slice(0, 1000) }));
  process.exitCode = 1;
});
