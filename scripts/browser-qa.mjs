#!/usr/bin/env node
// Requires agent-browser via pnpm. Sign into the isolated preview before portal checks.
// node scripts/browser-qa.mjs public|admin|staff|customer
import {spawnSync} from 'node:child_process';
const base=process.env.HV_QA_BASE_URL||'http://127.0.0.1:8772';
const role=process.argv[2]||'public';
const routes={
  public:['index.html','about.html','programs.html','locations.html','enquire.html','shop.html','login.html','privacy.html','terms.html','cookies.html','security.html','accessibility.html','photo-consent.html'],
  admin:['overview','tickets','enrolments','accounts','enquiries','incidents','terms','calendar','mail','launch','register','timesheets','roster','classes','achievements','compliance','billing','integrations','merch','website','locations','associations','notifications','audit'],
  staff:['overview','register','roster','pool','incidents','tickets','achievements','timesheets','qualifications','merch','notifications'],
  customer:['overview','classes','bookings','billing','absences','swimmers','achievements','incidents','messages','shop','notifications']
};
if(!routes[role])throw new Error('Choose public, admin, staff or customer.');
function browser(...args){
  const command=process.env.AGENT_BROWSER_BIN||'pnpm';
  const prefix=process.env.AGENT_BROWSER_BIN?[]:['dlx','agent-browser'];
  const result=spawnSync(command,[...prefix,'--session',process.env.HV_BROWSER_SESSION||'hv-premium','--json',...args],{encoding:'utf8',timeout:60000});
  if(result.status!==0)throw new Error(result.stderr||result.stdout);
  const payload=JSON.parse(result.stdout);
  if(!payload.success)throw new Error(JSON.stringify(payload.error));
  return payload.data;
}
const widths=role==='public'?[320,375,390,430,768,1024,1440]:[320,1024];
const failures=[];
let checked=0;
browser('errors','--clear');
for(const width of widths){
  browser('set','viewport',String(width),'900');
  for(const route of routes[role]){
    const page=role==='public'?route:'platform.html#'+route;
    browser('open',base+'/'+page);
    browser('wait','--load','networkidle');
    const result=browser('eval',`({
      title:document.title,
      actualRole:[...document.body.classList].find(value=>value.startsWith('role-'))||'',
      view:document.body.dataset.portalView||'',
      heading:document.querySelector('h1')?.innerText||'',
      width:innerWidth,scroll:document.documentElement.scrollWidth,
      failed:document.body.innerText.includes("We couldn't load this view."),
      brokenImages:[...document.images].filter(image=>image.complete&&!image.naturalWidth&&image.getBoundingClientRect().width>0).map(image=>image.getAttribute('src'))
    })`).result;
    if(role!=='public'&&result.actualRole!=='role-'+role)throw new Error('Expected '+role+' login, found '+result.actualRole+'. Sign in before running this matrix.');
    const ok=result.heading&&!result.failed&&result.scroll<=result.width+1&&!result.brokenImages.length&&(role==='public'||result.view===route);
    checked++;
    if(!ok)failures.push({page,width,...result});
    console.log((ok?'PASS':'FAIL')+' '+width+' '+page);
  }
}
const errors=browser('errors').errors||[];
console.log(JSON.stringify({checked,failures,browserErrors:errors},null,2));
browser('set','viewport','1280','900');
if(failures.length||errors.length)process.exitCode=1;
