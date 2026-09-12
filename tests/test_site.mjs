// Public shell contracts: reduced motion, blocked storage, request errors, stale data,
// escaped announcements and network-only operational APIs.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source = readFileSync(new URL('../assets/site.js',import.meta.url),'utf8');
function element(){return {dataset:{},events:{},attributes:{},textContent:'',hidden:false,innerHTML:'',classList:{add(){},toggle(){}},addEventListener(k,fn){(this.events[k]??=[]).push(fn);},setAttribute(k,v){this.attributes[k]=v;},replaceChildren(){this.innerHTML='';}};}
async function run({reduced=false,saved=null,blocked=false,hidden=false,age=0,failed=false}={}) {
 const root=element(),button=element(),doc=element(),win=element(),reduce=element(),narrow=element();
 reduce.matches=reduced;narrow.matches=false;doc.documentElement=root;doc.hidden=hidden;
 const weather=element(),weatherNote=element(),pool=element(),poolNote=element(),status=element(),alerts=element();
 const single={'.public-alerts':alerts,'[data-weather-value]':weather,'[data-pool-value]':pool,'[data-venue-status]':status};
 const all={'[data-venue-status]':[status],'[data-pool-value]':[pool],'[data-pool-note]':[poolNote],'[data-motion-toggle]':[button],'[data-weather-value]':[weather],'[data-weather-note]':[weatherNote],'[data-pool-value="wood-street"]':[pool],'[data-pool-note="wood-street"]':[poolNote],'[data-venue-status="wood-street"]':[status]};
 doc.querySelector=s=>single[s]||null;doc.querySelectorAll=s=>all[s]||[];
 const scheduled=new Map();let timerId=0,calls=0;
 const date=new Date(Date.now()-age).toISOString();
 const api={
 '/api/public/site-settings':{mode:'preview',settings:{}},
 '/api/public/weather':{observed_at:date,stale:false,current:{temperature_2m:12.4,weather_code:2}},
 '/api/public/locations':{locations:[{slug:'wood-street',public_status:'Lessons running',reading_stale:false,latest_reading:{temperature:31.2,created_at:date}}]},
 '/api/public/alerts':{alerts:[{title:'<img src=x>',message:'<script>alert(1)</script>'}]}
 };
 const fetch=async url=>{calls++;if(failed)throw Error('Offline');return {ok:url in api,status:url in api?200:422,json:async()=>api[url]||{detail:'Check this value'}};};
 const storage={getItem(){if(blocked)throw Error('Blocked');return saved;},setItem(k,v){if(blocked)throw Error('Blocked');saved=v;}};
 runInNewContext(source,{document:doc,window:win,matchMedia:s=>s.includes('reduced-motion')?reduce:narrow,localStorage:storage,navigator:{},location:{protocol:'http:'},fetch,AbortController,URL,Date,setTimeout:(fn,ms)=>{scheduled.set(++timerId,{fn,ms});return timerId;},clearTimeout:id=>scheduled.delete(id)});
 for(let i=0;i<30;i++)await Promise.resolve();
 return {root,button,doc,win,weather,weatherNote,pool,poolNote,status,alerts,reduce,scheduled,calls:()=>calls,toggle:()=>button.events.click[0]()};
}
const normal=await run();
assert.equal(normal.root.dataset.motion,'on');normal.toggle();assert.equal(normal.root.dataset.motion,'off');normal.toggle();assert.equal(normal.root.dataset.motion,'on');
assert.equal((await run({saved:'off'})).root.dataset.motion,'off');
const blocked=await run({blocked:true});blocked.toggle();assert.equal(blocked.root.dataset.motion,'off');
const reduced=await run({reduced:true});assert.equal(reduced.root.dataset.motion,'off');assert.equal(reduced.button.disabled,true);reduced.reduce.matches=false;reduced.reduce.events.change[0]();assert.equal(reduced.root.dataset.motion,'on');
const hidden=await run({hidden:true});assert.equal(hidden.root.dataset.pageHidden,'true');assert.equal(hidden.calls(),1,'Hidden tabs only load initial settings, no weather/alert polling');
assert.equal(normal.weather.textContent,'12.4°C');assert.equal(normal.pool.textContent,'31.2°C');assert.match(normal.poolNote.textContent,/staff reading/);
assert.match(normal.alerts.innerHTML,/&lt;script&gt;/);assert.doesNotMatch(normal.alerts.innerHTML,/<script>/);assert.match(normal.alerts.innerHTML,/All locations/);
assert.equal((await run({age:25*60*60*1000})).pool.textContent,'Awaiting a reading');
assert.equal((await run({age:-5*60*1000})).weather.textContent,'Update needed');
const offline=await run({failed:true});assert.equal(offline.status.textContent,'Contact us for current status');assert.equal(offline.alerts.hidden,true);
assert.ok([...normal.scheduled.values()].filter(t=>t.ms===60000).length===2,'Alerts and conditions refresh while visible');
await assert.rejects(normal.win.HVSwim.fetchJSON('/bad'),/Check this value/);
assert.equal(normal.win.HVSwim.formatClassTime('13:05'),'1:05 pm');
const sw=readFileSync(new URL('../service-worker.js',import.meta.url),'utf8');
const apiBranch=sw.slice(sw.indexOf("if (pathname.startsWith('/api/'))"),sw.indexOf("if (event.request.mode === 'navigate')"));
assert.doesNotMatch(apiBranch,/caches\.(match|open)|cache\.put/,'Never present old availability or stock as current');
console.log('PASS public motion, storage failures, stale/future readings, escaped notices, network errors and offline API boundary');
