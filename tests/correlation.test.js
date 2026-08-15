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

console.log("correlation tests: ok");
