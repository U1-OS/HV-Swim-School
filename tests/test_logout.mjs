import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

// Exercise the actual registered handler; the transport alone is replaced to reproduce
// an expired CSRF session without using a real account or weakening the server boundary.
const source=readFileSync(new URL('../assets/platform.js',import.meta.url),'utf8');
const start=source.indexOf("document.querySelectorAll('#logout-button,[data-logout]')");
const end=source.indexOf("document.getElementById('notification-button')",start);
assert.ok(start>=0&&end>start,'Find the shared logout event registration');
for(const fails of [true,false]){
  let click;
  const button={disabled:false,addEventListener:(_,handler)=>{click=handler;}};
  const location={href:'platform.html'};
  const messages=[];
  runInNewContext(source.slice(start,end),{
    document:{querySelectorAll:()=>[button]},location,
    api:async()=>{if(fails)throw new Error('Session changed');},
    setBusy:(control,busy)=>{control.disabled=busy;},
    toast:message=>messages.push(message)
  });
  await assert.doesNotReject(()=>click(),'Logout failures must be handled, not become uncaught errors');
  assert.equal(location.href,fails?'platform.html':'login.html','Redirect only after confirmed logout');
  if(fails){assert.equal(button.disabled,false);assert.ok(messages[0]?.includes('sign out'));}
}
console.log('PASS logout failure recovery and confirmed-success redirect');
