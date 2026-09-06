// Exercise optional WebGL failure guards without requiring a GPU in CI.
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source=readFileSync(new URL('../assets/aquatic-scene.js',import.meta.url),'utf8');
function run({missing=false,reduced=false,saveData=false,memory=8,context=null}={}){
  let created=0,attached=0,removed=0,frames=0;
  const hero={dataset:{},prepend(){attached++;}};
  const canvas={setAttribute(){},getContext(){if(context instanceof Error)throw context;return context;},remove(){removed++;}};
  runInNewContext(source,{
    document:{querySelector:()=>missing?null:hero,createElement(){created++;return canvas;}},
    navigator:{connection:{saveData},deviceMemory:memory},
    matchMedia:()=>({matches:reduced}),requestAnimationFrame(){frames++;},
  });
  return {created,attached,removed,frames,state:hero.dataset.aquatic};
}
for(const option of [{missing:true},{reduced:true},{saveData:true},{memory:2}])assert.equal(run(option).created,0);
assert.equal(run().attached,0,'No WebGL leaves the existing CSS scene untouched');
assert.equal(run({context:new Error('Context denied')}).frames,0);
let deleted=0;
const gl={createShader:()=>({}),shaderSource(){},compileShader(){},getShaderParameter:()=>false,deleteShader(){deleted++;}};
const failure=run({context:gl});
assert.equal(failure.state,'fallback');assert.equal(failure.attached,0);assert.equal(deleted,1);assert.equal(failure.frames,0);
console.log('PASS optional water: reduced motion, low-power, missing WebGL and shader failure keep the site usable');
