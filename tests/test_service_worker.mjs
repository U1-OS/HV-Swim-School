import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source=readFileSync(new URL('../service-worker.js',import.meta.url),'utf8');
async function navigation(path,{type='text/html',policy='public, max-age=0',offline=false}={}) {
 const handlers={},writes=[],reads=[];
 const response={ok:true,type:'basic',headers:new Headers({'Content-Type':type,'Cache-Control':policy}),clone(){return this;}};
 const caches={open:async()=>({put:async req=>writes.push(req.url)}),match:async req=>{reads.push(req);return new Response('offline public shell');}};
 const self={addEventListener:(type,fn)=>{handlers[type]=fn;},location:{origin:'https://swim.example'}};
 runInNewContext(source,{self,caches,URL,Response,fetch:async()=>{if(offline)throw Error('Offline');return response;}});
 let pending;
 handlers.fetch({request:{url:'https://swim.example'+path,method:'GET',mode:'navigate'},respondWith(value){pending=value;}});
 const result=await pending;
 return {writes,reads,result};
}
for(const path of ['/api/customer/swimmers','/api%2Fcustomer%2Fswimmers','/%61pi/customer/swimmers']){
 const result=await navigation(path,{type:'application/json',policy:'private, no-store'});
 assert.equal(result.writes.length,0,`Private records must never be cached: ${path}`);
 const offline=await navigation(path,{offline:true});
 assert.equal(offline.reads.length,0,`Encoded API paths must never read old cache: ${path}`);
 assert.equal(offline.result.status,503);
}
assert.equal((await navigation('/index.html')).writes.length,1,'Eligible public HTML can work offline');
assert.equal((await navigation('/index.html',{type:'application/json'})).writes.length,0,'No JSON response on a public URL is cached');
assert.equal((await navigation('/index.html',{policy:'private,no-store'})).writes.length,0,'Honour response cache policy');
assert.equal((await navigation('/platform.html')).writes.length,0,'Protected workspace navigation is not cached');
assert.equal((await navigation('/api/products',{offline:true})).reads.length,0,'Stock does not come from an old offline cache');
console.log('PASS offline private-data isolation, encoded API paths, public HTML allowlist and cache-control');
