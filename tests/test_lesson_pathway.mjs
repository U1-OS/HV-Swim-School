import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const context={window:{}};
runInNewContext(readFileSync(new URL('../assets/lesson-pathway.js',import.meta.url),'utf8'),context);
const recommend=context.window.HVLessonPathway;
for (const age of ['3–5 years','6–8 years','9–12 years','Teen','Adult']) {
  for (const confidence of ['new','supported','New, cautious or nervous around water','Comfortable with support']) {
    assert.notEqual(recommend({age,confidence,goal:'technique'}).anchor,'stroke',`${age}: technique goals alone must not imply independence`);
  }
}
assert.equal(recommend({age:'Approximately 4–12 months',confidence:'independent',goal:'technique'}).anchor,'infant');
assert.equal(recommend({age:'1–2 years',goal:'personal'}).anchor,'private');
assert.equal(recommend({age:'Adult',confidence:'supported',goal:'skills'}).anchor,'private');
assert.equal(recommend({age:'6–8 years',confidence:'independent',goal:'technique'}).anchor,'stroke');
assert.equal(recommend({age:'6–8 years',confidence:'Swimming independently',goal:'technique'}).anchor,'stroke');
assert.equal(recommend({age:'6–8 years',confidence:'Would benefit from one-to-one support',goal:'skills'}).anchor,'private');
assert.equal(recommend({age:'9–12 years',confidence:'new',goal:'confidence'}).anchor,'learn');
console.log('PASS lesson pathways respect readiness, age and individual support');

for (const [page,script] of [['programs','programs'],['enquire','enquire']]) {
  const html=readFileSync(new URL(`../${page}.html`,import.meta.url),'utf8');
  const helper=html.indexOf('assets/lesson-pathway.js');
  assert.ok(helper>=0 && helper<html.indexOf(`assets/${script}.js`),'Load the shared recommendation helper before its consumers');
}
