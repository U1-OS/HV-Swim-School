import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const source=readFileSync(new URL('../assets/platform.js',import.meta.url),'utf8');
const start=source.indexOf('async function initLogin()');
const end=source.indexOf('const navByRole',start);
assert.ok(start>=0&&end>start);
const elements=new Map();
const getElement=id=>{
  if(!elements.has(id))elements.set(id,{value:'',events:{},classList:{add(){},remove(){}},
    addEventListener(event,handler){this.events[event]=handler;},setAttribute(){}});
  return elements.get(id);
};
// An optional provider request never resolves. Credential submission must still have
// its handler immediately; default HTML GET submission would expose input in the URL.
runInNewContext('('+source.slice(start,end)+')()',{
  document:{getElementById:getElement},URLSearchParams,location:{search:''},
  api:()=>new Promise(()=>{})
});
assert.equal(typeof getElement('login-form').events.submit,'function','Bind credential submission before waiting for provider configuration');
let prevented=false;
getElement('login-form').events.submit({preventDefault(){prevented=true;}});
assert.equal(prevented,true,'Credential submission prevents native navigation synchronously');
console.log('PASS login submission remains safe while provider lookup is pending');
