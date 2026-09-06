// Run: node tests/test_platform_dates.mjs
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source=readFileSync(new URL('../assets/platform.js',import.meta.url),'utf8');
const from=source.indexOf('  const dOnly =');
const to=source.indexOf('  const clockTime =',from);
assert.ok(from>=0&&to>from);
const {dOnly,businessDateValue,payrollWeekDates}=runInNewContext(source.slice(from,to)+'\n({dOnly,businessDateValue,payrollWeekDates})',{Intl,Date});
assert.equal(dOnly('2026-09-05'),dOnly('2026-09-05T02:52:13.237175+00:00'),'Legacy clock timestamps render without a second T suffix');
assert.equal(dOnly('not-a-date'),'Date unavailable');
assert.equal(dOnly(null),'—');
assert.equal(businessDateValue(new Date('2026-09-05T15:30:00Z')),'2026-09-06');
assert.equal(businessDateValue(new Date('2026-10-04T13:30:00Z')),'2026-10-05','Melbourne daylight-saving offset is applied');
assert.deepEqual(Array.from(payrollWeekDates('2026-12-28'),d=>d.iso),['2026-12-28','2026-12-29','2026-12-30','2026-12-31','2027-01-01','2027-01-02','2027-01-03']);
assert.equal(payrollWeekDates('2026-09-08').length,0,'Non-Monday dates cannot relabel payroll');
assert.equal(payrollWeekDates('2026-02-30').length,0,'Date overflow is rejected');
assert.equal(payrollWeekDates('').length,0);
console.log('PASS legacy clock timestamps, Melbourne date values, DST and Monday–Sunday payroll dates');
