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
  'height', 'float', 'visibility', 'opacity', 'white-space', 'border-collapse', 'border-spacing',
  'transform', 'zoom', 'writing-mode', 'direction',
  'overflow-x', 'overflow-y', 'clip-path',
  // Appearance of slide boxes (P13-006): corners, flex alignment, shadows and gradient text.
  'border-top-left-radius', 'border-top-right-radius', 'border-bottom-left-radius', 'border-bottom-right-radius',
  'justify-content', 'align-items', 'flex-direction', 'box-shadow', '-webkit-text-fill-color', 'background-clip',
  '-webkit-background-clip',
];
// What a decorative ::before/::after needs to be drawn: its box comes from these.
const PSEUDO_PROPERTIES = [
  'content', 'position', 'top', 'right', 'bottom', 'left', 'width', 'height', 'background-color', 'background-image',
  'border-top-left-radius', 'opacity', 'display',
];
// A slide is a <section> or an element with the class "slide", not inside another one (html_slides.collect_slides).
const SLIDE_SELECTOR = 'section, .slide';

// Passed to page.evaluate; any additional style source rejects this bounded mapping.
function unsupportedStyleSources() {
  try {
    if (!('adoptedStyleSheets' in document)) return { checked: false };
    return { checked: true, document_adopted_count: document.adoptedStyleSheets.length,
      open_shadow_root_count: [...document.querySelectorAll('*')].filter(element => element.shadowRoot).length };
  } catch (error) { return { checked: false, error: String(error) }; }
}

// Independent proof for natural row minima; blockers do not alter legacy CSSOM flags.
function rowHeightAuthorAudit() {
  const result = { checked: true, declarations: [], unsupported_rules: [], html_height_attrs: [], errors: [] };
  const blocked = new Set(['height', 'min-height', 'max-height', 'block-size', 'min-block-size', 'max-block-size',
    'all', 'aspect-ratio', 'contain', 'content-visibility', 'animation', 'animation-name', 'transition', 'transition-property']);
  let count = 0;
  function inspect(style, origin) {
    if (!style) throw new Error('AUTHOR_DECLARATION_UNAVAILABLE');
    for (const name of Array.from(style)) {
      if (blocked.has(name.toLowerCase())) result.declarations.push({ origin, property: name, value: style.getPropertyValue(name) });
    }
  }
  function visit(rules, depth = 0) {
    if (depth > 32) throw new Error('AUTHOR_RULE_DEPTH');
    for (const rule of rules) {
      if (++count > 10000) throw new Error('AUTHOR_RULE_COUNT');
      if (rule.type !== CSSRule.STYLE_RULE || depth) result.unsupported_rules.push({ type: rule.type, depth });
      if (rule.style) inspect(rule.style, 'stylesheet');
      if (rule.cssRules) visit(rule.cssRules, depth + 1);
    }
  }
  try {
    for (const sheet of document.styleSheets) visit(sheet.cssRules);
    for (const node of document.querySelectorAll('[style]')) inspect(node.style, 'inline');
    for (const node of document.querySelectorAll('[height]')) result.html_height_attrs.push(node.tagName);
  } catch (error) { result.checked = false; result.errors.push(String(error)); }
  return result;
}

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
    const elements = await page.evaluate(([properties, pseudoProperties]) => {
      const result = {};
      // "line-height: normal" depends on the font: measure it once per font, so that a document can set the line
      // the browser drew (WPS gives Microsoft YaHei a taller "single" line than the browser's normal one).
      const normal = new Map();
      // The sample has a CJK glyph only when the element's text does: a fallback CJK font makes the line taller
      // than a Latin-only one in the same font (a Consolas code block measured 17 px instead of 14 px).
      const normalLine = (style, text) => {
        const cjk = /[\u3000-\u9fff\uff00-\uffef]/.test(text);
        const key = [style.fontFamily, style.fontSize, style.fontWeight, style.fontStyle, cjk].join('|');
        if (!normal.has(key)) {
          const probe = document.createElement('div');
          probe.style.cssText = 'position:absolute;left:-10000px;top:0;visibility:hidden;white-space:nowrap;' +
            'line-height:normal;margin:0;padding:0;border:0';
          probe.style.fontFamily = style.fontFamily;
          probe.style.fontSize = style.fontSize;
          probe.style.fontWeight = style.fontWeight;
          probe.style.fontStyle = style.fontStyle;
          probe.textContent = cjk ? '\u56fdAg' : 'Ag';
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
          values['line-height-normal'] = `${normalLine(style, element.textContent || '')}px`;
        }
        // How many lines the element's text takes here, so a slide can keep one line from wrapping in a wider font.
        if ((element.textContent || '').trim()) {
          const range = document.createRange();
          range.selectNodeContents(element);
          const tops = new Set();
          for (const rect of range.getClientRects()) if (rect.height > 0) tops.add(Math.round(rect.top / 2));
          values['text-lines'] = String(tops.size);
        }
        const pseudo = [];
        for (const which of ['::before', '::after']) {
          const p = getComputedStyle(element, which);
          if (!p.content || p.content === 'none' || p.content === 'normal' || p.display === 'none') continue;
          const v = { which };
          for (const name of pseudoProperties) v[name] = p.getPropertyValue(name);
          pseudo.push(v);
        }
        if (pseudo.length) values['pseudo'] = pseudo;
        if (element.tagName === 'SUMMARY') {
          const marker = getComputedStyle(element, '::marker');
          const range = document.createRange();
          range.selectNodeContents(element);
          const props = ['display', 'list-style-type', 'list-style-position', 'list-style-image',
            'direction', 'writing-mode', 'text-indent', 'font-size', 'font-family', 'font-style', 'font-weight', 'color'];
          const mprops = ['content', 'font-size', 'font-family', 'font-style', 'font-weight', 'color'];
          values['summary-marker'] = {
            style: Object.fromEntries(props.map(p => [p, style.getPropertyValue(p)])),
            marker: Object.fromEntries(mprops.map(p => [p, marker.getPropertyValue(p)])),
            box: { x: box.x, y: box.y, width: box.width, height: box.height },
            textRects: Array.from(range.getClientRects()).map(r => ({ x: r.x, y: r.y, width: r.width, height: r.height })),
          };
        }
        result[element.getAttribute('data-wps-i')] = {
          tag: element.tagName.toLowerCase(),
          box: { x: box.left + window.scrollX, y: box.top + window.scrollY, width: box.width, height: box.height },
          style: values,
        };
      }
      return result;
    }, [PROPERTIES, PSEUDO_PROPERTIES]);
    // Qualification metadata is observational; uncertain CSSOM/identity never grants a mapping.
    let printContext = {};
    try {
      const cssom = await page.evaluate(() => {
        let complete = true, count = 0;
        const errors = [], pageRules = [], imports = [];
        function visit(rules, depth = 0) {
          if (depth > 32) throw new Error('CSSOM nesting limit');
          for (const rule of rules) {
            if (++count > 10000) throw new Error('CSSOM rule limit');
            if (rule.type === CSSRule.PAGE_RULE) pageRules.push(rule.cssText);
            if (rule.type === CSSRule.IMPORT_RULE) imports.push(rule.cssText);
            if (rule.cssRules) visit(rule.cssRules, depth + 1);
          }
        }
        const links = [...document.querySelectorAll('link[rel~="stylesheet"]')].map(link => {
          if (!link.sheet) { complete = false; errors.push('STYLESHEET_UNAVAILABLE: ' + link.href); }
          return { href: link.href, has_sheet: !!link.sheet };
        });
        for (const sheet of document.styleSheets) {
          try { visit(sheet.cssRules); } catch (error) { complete = false; errors.push(String(error)); }
        }
        return { complete, links, page_rules: pageRules, imports, errors };
      });
      const sources = await page.evaluate(unsupportedStyleSources);
      cssom.style_sources = sources;
      cssom.row_height_audit = await page.evaluate(rowHeightAuthorAudit);
      if (!sources.checked || sources.document_adopted_count || sources.open_shadow_root_count) {
        cssom.complete = false;
        cssom.errors.push('UNSUPPORTED_ADOPTED_OR_SHADOW_STYLE_SOURCE');
      }
      const cdp = await context.newCDPSession(page);
      printContext = { platform: process.platform, executable: fs.realpathSync(request.browser_executable),
        runtime: await cdp.send('Browser.getVersion'), cssom };
      await cdp.detach();
    } catch (error) { printContext = { error: String(error) }; }
    const shots = [];
    if (request.section_screenshots_dir) {
      const sections = [];
      for (const element of await page.$$(SLIDE_SELECTOR)) {
        if (await element.evaluate((node, selector) => !node.parentElement?.closest(selector), SLIDE_SELECTOR)) {
          sections.push(element);
        }
      }
      let index = 0;
      for (const section of sections) {
        index += 1;
        const file = path.join(request.section_screenshots_dir, `section-${String(index).padStart(3, '0')}.png`);
        await section.screenshot({ path: file, animations: 'disabled' });
        shots.push(file);
      }
    }
    process.stdout.write(JSON.stringify({ ok: true, browser: await browser.version(), elements, section_screenshots: shots, print_context: printContext }));
  } finally {
    await browser.close();
  }
}

module.exports = { unsupportedStyleSources, rowHeightAuthorAudit };

if (require.main === module) main().catch(error => {
  process.stdout.write(JSON.stringify({ ok: false, code: error.code || 'LAYOUT_FAILED', message: String(error.message || error).slice(0, 1000) }));
  process.exitCode = 1;
});
