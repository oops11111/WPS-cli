// In-memory browser evidence only: no printing or original-document mutation.
const {chromium}=require('playwright');
const {unsupportedStyleSources}=require('../../src/wps_ai_agent_cli/html_layout_playwright.cjs');
(async()=>{
  const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'});
  try {
    const context=await browser.newContext({javaScriptEnabled:false});const page=await context.newPage();
    await page.setContent('<body>PROBE</body>');
    const observation=await page.evaluate(()=>{
      const adopted=new CSSStyleSheet();adopted.replaceSync('@page {margin:12mm} body {color:red}');document.adoptedStyleSheets=[adopted];
      const host=document.createElement('div');document.body.append(host);const shadow=host.attachShadow({mode:'open'});
      shadow.innerHTML='<style>@page {margin:14mm} span {color:blue}</style><span>SHADOW</span>';
      const sheet=new CSSStyleSheet();sheet.replaceSync('@page {margin:16mm}');shadow.adoptedStyleSheets=[sheet];
      const rules=s=>[...s.cssRules].map(r=>({type:r.type,text:r.cssText}));
      return {documentSheets:document.styleSheets.length,documentAdoptedRules:rules(adopted),shadowRules:rules(shadow.styleSheets[0]),shadowAdoptedRules:rules(sheet),bodyColor:getComputedStyle(document.body).color,shadowColor:getComputedStyle(shadow.querySelector('span')).color};
    });
    const detector=await page.evaluate(unsupportedStyleSources);
    console.log(JSON.stringify({browser:await browser.version(),kind:'in-memory CSSOM/cascade probe; no print test',observation,detector},null,2));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
