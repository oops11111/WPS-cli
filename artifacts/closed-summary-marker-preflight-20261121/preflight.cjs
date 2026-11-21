const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL, fileURLToPath } = require('node:url');
const { chromium } = require('playwright');
(async () => {
 const input=path.resolve('fixtures/html_complex/report.html');
 const root=path.dirname(input);
 const out=path.resolve('artifacts/closed-summary-marker-preflight-20261121');
 const browser=await chromium.launch({headless:true,executablePath:'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'});
 try {
  const context=await browser.newContext({viewport:{width:1280,height:900},javaScriptEnabled:false,acceptDownloads:false});
  const page=await context.newPage();
  await page.route('**/*', async route => {
   const url=route.request().url();
   if(url.startsWith('data:')||url.startsWith('about:')) return route.continue();
   if(!url.startsWith('file:'))return route.abort();
   try {const local=fs.realpathSync(fileURLToPath(url));const relative=path.relative(root,local);
    if(relative.startsWith('..')||path.isAbsolute(relative))return route.abort();
   }catch{return route.abort();}
   return route.continue();
  });
  await page.goto(pathToFileURL(input).href,{waitUntil:'load'});
  await page.evaluate(()=>document.fonts.ready);
  const collect=()=>page.evaluate(()=>Array.from(document.querySelectorAll('details > summary')).map(summary=>{
   const style=getComputedStyle(summary),marker=getComputedStyle(summary,'::marker');
   const props=['display','list-style-type','list-style-position','list-style-image','direction','writing-mode','text-indent','font-size','font-family','font-style','font-weight','color','position','visibility','opacity'];
   const mprops=['content','font-size','font-family','font-style','font-weight','color'];
   const range=document.createRange();range.selectNodeContents(summary);
   const box=summary.getBoundingClientRect();
   return {open:summary.parentElement.hasAttribute('open'),text:summary.textContent,
    style:Object.fromEntries(props.map(p=>[p,style.getPropertyValue(p)])),
    marker:Object.fromEntries(mprops.map(p=>[p,marker.getPropertyValue(p)])),
    box:{x:box.x,y:box.y,width:box.width,height:box.height},
    textRects:Array.from(range.getClientRects()).map(r=>({x:r.x,y:r.y,width:r.width,height:r.height}))};
  }));
  const screen1=await collect(),screen2=await collect();
  await page.emulateMedia({media:'print'});
  const print1=await collect(),print2=await collect();
  await page.pdf({path:path.join(out,'browser.pdf'),format:'A4',printBackground:true,preferCSSPageSize:true,margin:{top:'10mm',right:'10mm',bottom:'10mm',left:'10mm'}});
  fs.writeFileSync(path.join(out,'browser-metadata.json'),JSON.stringify({browser:await browser.version(),input:'fixtures/html_complex/report.html',screen1,screen2,print1,print2},null,2));
 }finally{await browser.close();}
})().catch(error=>{process.stderr.write(error.stack);process.exitCode=1;});
