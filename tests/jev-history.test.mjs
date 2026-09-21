import test from 'node:test';
import assert from 'node:assert/strict';
import { TARGETS, EXTRAS, VERSION, MODEL, outcome, aggregate, weeks, lastFriday, makePayload } from '../src/jev-history.mjs';

test('completed weekly cutoffs and five-year calendar include holidays without assuming 50 weeks',()=>{
  assert.equal(lastFriday('2026-09-18'),'2026-09-11');
  assert.equal(lastFriday('2026-09-19'),'2026-09-18');
  assert.equal(lastFriday('2026-09-21'),'2026-09-18');
  const list=weeks('2026-09-18');assert.equal(list.length,261);
  assert.ok(list.every(d=>new Date(d+'T00:00:00Z').getUTCDay()===5));
  assert.equal(new Set([...TARGETS,...EXTRAS].map(a=>a.key)).size,9);
});
test('forward performance enters next session open and uses intraday extremes, pending is excluded',()=>{
  const rows=[{d:'2026-09-18',o:1,h:999,l:1,c:999},
    {d:'2026-09-21',o:100,h:120,l:90,c:110},{d:'2026-09-22',o:110,h:130,l:80,c:88}];
  const got=outcome(rows,'2026-09-18',2);
  assert.equal(got.entry,100);assert.equal(got.maxRise,30);assert.equal(got.maxLoss,-20);
  assert.equal(got.endReturn,-12);assert.equal(got.closeDrawdown,-20);
  assert.equal(outcome(rows,'2026-09-18',5).status,'pending');
  assert.equal(outcome([{...rows[1],o:null},rows[2]],'2026-09-18',2).status,'missing_ohlc');
});
test('thresholds are inclusive, band excludes 90, versions do not mix and unfinished periods do not win',()=>{
  const records=[80,89.9,90,100].map(score=>({version:VERSION,target:'nikkei',cutoff:'2026-09-18',response:{model:MODEL,horizons:[{days:5,score}]}}));
  records.push({...records[0],version:'old'});
  const market=Object.fromEntries(TARGETS.map(t=>[t.key,Array.from({length:5},(_,i)=>({d:`2026-09-${21+i}`,o:100,h:110,l:95,c:105}))]));
  const result=aggregate(records,market).nikkei;
  assert.equal(result.judgments,4);assert.equal(result.periods[5].gte90.n,2);assert.equal(result.periods[5].gte80.n,4);assert.equal(result.periods[5]['80to90'].n,2);
  assert.equal(result.periods[5].gte90.winRate,100);assert.equal(result.periods[100].all.n,0);assert.equal(result.periods[100].all.winRate,null);
});
test('future prices cannot change the payload, comparisons are fixed and yields are percentage-point changes',()=>{
  const series=Array.from({length:300},(_,i)=>{const d=new Date(Date.UTC(2020,0,1+i)).toISOString().slice(0,10);return {d,c:100+i*.1+Math.sin(i),o:100+i*.1,h:103+i*.1,l:97+i*.1,v:1000};});
  const market=Object.fromEntries([...TARGETS,...EXTRAS].map(a=>[a.key,series.map(r=>a.key.startsWith('rates:')?{...r,c:r.c/100}:r)]));
  const cutoff=series.at(-1).d;
  const first=makePayload(market,TARGETS[0],cutoff);
  for(const key of Object.keys(market)) market[key]=[...market[key],{d:'2030-01-01',c:999999,o:1,h:1,l:1,v:1}];
  assert.deepEqual(makePayload(market,TARGETS[0],cutoff),first);
  assert.equal(first.corr.subs.length,8);
  const yieldData=first.corr.subs.find(s=>s.key==='rates:日本 10年国債');
  assert.equal(yieldData.unit,'percentage_points');
  assert.ok(Math.abs(yieldData.change[5]-(series.at(-1).c-series.at(-6).c)/100)<.0001);
});
