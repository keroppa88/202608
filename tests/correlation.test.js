"use strict";

const assert = require("assert");
const C = require("../correlation.js");

const points = Array.from({ length: 140 }, (_, i) => ({
  d: `2024-${String(Math.floor(i / 28) + 1).padStart(2, "0")}-${String(i % 28 + 1).padStart(2, "0")}`,
  x: i + 1,
  y: i + 1
}));
assert(Math.abs(C.pearson(points) - 1) < 1e-12, "同一系列は1");
assert(Math.abs(C.pearson(points.map((p) => ({ ...p, y: -p.x }))) + 1) < 1e-12, "逆系列は-1");
assert.strictEqual(C.finiteNumber("#N/A"), null);
assert.strictEqual(C.finiteNumber(""), null);
assert(Math.abs(C.pearson([{ x: 1, y: 2 }, { x: 2, y: 4 }, { x: NaN, y: 9 }]) - 1) < 1e-12,
  "欠損は除外する");

const jpDays = ["2024-08-09", "2024-08-13", "2024-08-14"];
const us = [{ d: "2024-08-09", v: 0.01 }, { d: "2024-08-12", v: 0.02 }];
const jp = [{ d: "2024-08-13", v: 0.03 }, { d: "2024-08-14", v: -0.01 }];
const lead = C.leadToNextMarket(us, jp, jpDays, "return");
assert.strictEqual(lead[0].d, "2024-08-13", "米国日は次の日本取引日へ送る");
assert(Math.abs(lead[0].x - 0.0302) < 1e-12, "日本連休中は複利合成する");
assert.strictEqual(lead.length, 1, "米国データが無い日本日はゼロ補完しない");

const jpKr = C.alignPair(
  [{ d: "2024-08-13", v: 0.1 }], [{ d: "2024-08-13", v: 0.2 }],
  { market: "JP", calcType: "return" }, { market: "KR", calcType: "return" }, {}
);
assert.strictEqual(jpKr.length, 1, "日本と韓国は同日対応");

assert.strictEqual(C.rollingCorrelation(points, 20).length, 121, "20個の有効観測を使う");
assert.strictEqual(C.rollingCorrelation(points, 60).length, 81, "60個の有効観測を使う");
assert.strictEqual(C.rollingCorrelation(points, 120).length, 21, "120個の有効観測を使う");

/* ---- AI に渡す数字の計算 ---- */

assert.deepStrictEqual(C.trailingSeries([0.1, 0.1, 0.1], 2, "diff"), [null, 0.2, 0.2],
  "差分は足し算で累積する");
const compound = C.trailingSeries([0.1, 0.1], 2, "return");
assert(Math.abs(compound[1] - 0.21) < 1e-12, "騰落率は複利で累積する");
assert.deepStrictEqual(C.forwardSeries([0, 0.1, 0.2], 1, "diff"), [0.1, 0.2, null],
  "先を見る側は自分を含めない");

assert.strictEqual(C.quantile([1, 2, 3, 4], 0.5), 2.5);
assert.strictEqual(C.quantileRank([1, 2, 3, 4], 2), 0.5);

// メインが上げている間だけ逆方向に動くサブ。局面で分ければ符号が割れる
const regimePoints = [];
for (let i = 0; i < 200; i++) {
  const rising = Math.floor(i / 50) % 2 === 0;
  const x = rising ? 0.01 : -0.01;
  regimePoints.push({ d: `d${i}`, x, y: (rising ? -1 : 1) * (i % 2 ? 0.01 : 0.02) });
}
const regime = C.regimeCorrelation(regimePoints, 5, "return");
assert(regime.upDays > 0 && regime.downDays > 0, "上昇局面と下落局面の両方を拾う");

const cond = C.conditionalReturns([
  { x: 0.02, y: 0.01 }, { x: -0.01, y: 0.01 },
  { x: -0.03, y: -0.01 }, { x: 0, y: 0 }
]);
assert.strictEqual(cond.subUp.n, 2, "サブが上がった日を数える");
assert.strictEqual(cond.subUp.win, 0.5, "そのうちメインが上がった割合");
assert.strictEqual(cond.subDown.n, 1, "サブが下がった日は別に数える");

const fwdPoints = Array.from({ length: 120 }, (_, i) => ({ d: `d${i}`, x: 0.01, y: i / 1000 }));
const fwd = C.forwardAfterExtreme(fwdPoints, 5, 5, "return", "return");
assert(fwd.high.n > 0 && fwd.low.n > 0, "上位25%と下位25%の両方が取れる");
assert(Math.abs(fwd.base.main - (Math.pow(1.01, 5) - 1)) < 1e-12, "全体の平均も一緒に返す");

const lagPoints = Array.from({ length: 60 }, (_, i) => ({ d: `d${i}`, x: Math.sin(i / 3), y: 0 }));
for (let i = 1; i < lagPoints.length; i++) lagPoints[i].y = lagPoints[i - 1].x;
const lag = C.leadLag(lagPoints, [-1, 0, 1]);
const byShift = new Map(lag.map((x) => [x.shift, x.r]));
assert(byShift.get(-1) > byShift.get(0), "サブが1つ遅れて同じ動きをするなら k=-1 が強い");

assert.strictEqual(C.sampleEvenly([1, 2, 3], 5).length, 3, "点が足りなければそのまま返す");
const sampled = C.sampleEvenly(Array.from({ length: 100 }, (_, i) => i), 12);
assert.strictEqual(sampled.length, 12);
assert.strictEqual(sampled[0], 0);
assert.strictEqual(sampled[11], 99, "端は必ず含める");

const summary = C.summarizeSeries(
  Array.from({ length: 300 }, (_, i) => ({ d: `2025-01-${i}`, v: 100 + i })), "return");
assert.strictEqual(summary.close, 399);
assert(Math.abs(summary.ret[5] - (399 / 394 - 1)) < 1e-12, "5観測前からの騰落率");
assert(Math.abs(summary.drawdown) < 1e-12, "最高値そのものならドローダウンは0");
assert(Math.abs(summary.rangePos - 1) < 1e-12, "直近レンジの上端");
assert.strictEqual(C.summarizeSeries([], "return"), null, "空なら null");

console.log("correlation tests: ok");
