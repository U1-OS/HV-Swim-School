// Run: node tests/test_experience.mjs
// Exercise the shipped interaction code, including restricted browser storage and keyboard input.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source = readFileSync(new URL('../assets/experience.js',import.meta.url),'utf8');
function element(dataset={}) {
  return {dataset,events:{},attributes:{},style:{setProperty(k,v){this[k]=v;}},
    addEventListener(k,fn){this.events[k]=fn;},
    setAttribute(k,v){this.attributes[k]=v;},removeAttribute(k){delete this.attributes[k];},
    setPointerCapture(){},querySelector(){return null;},querySelectorAll(){return [];}};
}
function run({saved=null,reduced=false,blocked=false}={}) {
  const root=element(),button=element(),viewport=element(),object=element(),reset=element();
  const scene=element({scene:'pool'});
  scene.querySelector=s=>({'.scene-viewport':viewport,'[data-scene-object]':object,'[data-scene-reset]':reset}[s]||null);
  const media=element(); media.matches=reduced;
  const document=element(); document.documentElement=root;
  document.querySelectorAll=s=>s==='[data-scene]'?[scene]:s==='[data-motion-toggle]'?[button]:[];
  const frames=[];
  const storage={getItem(){if(blocked)throw Error('Storage blocked');return saved;},setItem(k,v){if(blocked)throw Error('Storage blocked');saved=v;}};
  runInNewContext(source,{document,window:element(),matchMedia:s=>s.includes('reduced-motion')?media:{matches:false},
    localStorage:storage,requestAnimationFrame:fn=>(frames.push(fn),frames.length)});
  const flush=()=>{while(frames.length)frames.shift()();};
  const press=key=>{let prevented=false;viewport.events.keydown({key,preventDefault(){prevented=true;}});flush();return prevented;};
  return {root,button,object,viewport,reset,media,frames,flush,press,toggle:()=>document.events.click({target:{closest:()=>button}})};
}
const ordinary=run();
assert.equal(ordinary.root.dataset.motion,'on');
assert.equal(ordinary.frames.length,0,'No render loop runs without input');
assert.equal(ordinary.press('ArrowRight'),true);
assert.equal(ordinary.object.style['--scene-y'],'-20deg');
for(let i=0;i<30;i++)ordinary.press('ArrowRight');
assert.equal(ordinary.object.style['--scene-y'],'25deg','Pool cannot rotate past its supported faces');
assert.equal(ordinary.press('Tab'),false,'Keyboard traversal stays native');
ordinary.reset.events.click();ordinary.flush();
assert.equal(ordinary.object.style['--scene-y'],'-28deg');
ordinary.viewport.events.pointerdown({button:0,pointerId:1,clientX:20,clientY:20});
ordinary.viewport.events.pointermove({pointerId:1,pointerType:'touch',clientX:60,clientY:100});ordinary.flush();
assert.equal(ordinary.object.style['--scene-x'],'57deg','Touch vertical movement remains page scrolling');
assert.equal(ordinary.object.style['--scene-y'],'-20deg');
ordinary.viewport.events.pointercancel();
ordinary.viewport.events.pointermove({pointerId:1,pointerType:'touch',clientX:200,clientY:100});ordinary.flush();
assert.equal(ordinary.object.style['--scene-y'],'-20deg','Cancelled drags must stop updating');
ordinary.toggle();assert.equal(ordinary.root.dataset.motion,'off');
ordinary.toggle();assert.equal(ordinary.root.dataset.motion,'on');
assert.equal(run({saved:'off'}).root.dataset.motion,'off');
const accessible=run({reduced:true});accessible.toggle();
assert.equal(accessible.root.dataset.motion,'off');assert.equal(accessible.button.disabled,true);
accessible.media.matches=false;accessible.media.events.change();
assert.equal(accessible.root.dataset.motion,'on','Follow a changed OS preference');
const privateBrowser=run({blocked:true});privateBrowser.toggle();
assert.equal(privateBrowser.root.dataset.motion,'off','Motion controls work with storage blocked');
console.log('PASS 3D input bounds, reset, cancellation, native scrolling, motion preference and restricted storage');
