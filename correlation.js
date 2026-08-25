(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.CorrelationEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const DAY_MS = 86400000;

  function finiteNumber(v) {
    if (v === null || v === undefined || v === "" || v === "#N/A") return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function priceChanges(entries, calcType) {
    const byDate = new Map();
    for (const entry of entries) {
      const d = Array.isArray(entry) ? entry[0] : entry.d;
      const raw = Array.isArray(entry) ? entry[1] : entry.v;
      const v = finiteNumber(raw);
      if (d && v !== null) byDate.set(String(d).slice(0, 10), v);
    }
    const sorted = [...byDate].sort((a, b) => a[0].localeCompare(b[0]));
    const out = [];
    for (let i = 1; i < sorted.length; i++) {
      const [d, v] = sorted[i], prev = sorted[i - 1][1];
      if (calcType === "diff") out.push({ d, v: v - prev });
      else if (prev !== 0) out.push({ d, v: v / prev - 1 });
    }
    return out.filter((x) => Number.isFinite(x.v));
  }

  function pearsonSums(n, sx, sy, sxx, syy, sxy) {
    if (n < 2) return null;
    const vx = n * sxx - sx * sx;
    const vy = n * syy - sy * sy;
    if (!(vx > 0) || !(vy > 0)) return null;
    const r = (n * sxy - sx * sy) / Math.sqrt(vx * vy);
    if (!Number.isFinite(r)) return null;
    return Math.max(-1, Math.min(1, r));
  }

  function pearson(points) {
    let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0, n = 0;
    for (const p of points) {
      const x = finiteNumber(p.x), y = finiteNumber(p.y);
      if (x === null || y === null) continue;
      sx += x; sy += y; sxx += x * x; syy += y * y; sxy += x * y; n++;
    }
    return pearsonSums(n, sx, sy, sxx, syy, sxy);
  }

  function sameDay(a, b) {
    const bm = new Map(b.map((x) => [x.d, x.v]));
    const out = [];
    for (const x of a) {
      const y = bm.get(x.d);
      if (y !== undefined) out.push({ d: x.d, x: x.v, y });
    }
    return out;
  }

  function upperBound(days, d) {
    let lo = 0, hi = days.length;
    while (lo < hi) {
      const mid = (lo + hi) >> 1;
      if (days[mid] <= d) lo = mid + 1; else hi = mid;
    }
    return lo;
  }

  function leadToNextMarket(source, target, targetDays, calcType) {
    const grouped = new Map();
    for (const x of source) {
      const at = upperBound(targetDays, x.d);
      if (at >= targetDays.length) continue;
      const d = targetDays[at];
      if (!grouped.has(d)) grouped.set(d, calcType === "diff" ? 0 : 1);
      grouped.set(d, calcType === "diff"
        ? grouped.get(d) + x.v
        : grouped.get(d) * (1 + x.v));
    }
    if (calcType !== "diff") grouped.forEach((v, d) => grouped.set(d, v - 1));
    const tm = new Map(target.map((x) => [x.d, x.v]));
    const out = [];
    for (const [d, x] of grouped) {
      const y = tm.get(d);
      if (y !== undefined) out.push({ d, x, y });
    }
    return out.sort((a, b) => a.d.localeCompare(b.d));
  }

  function alignPair(a, b, metaA, metaB, calendars) {
    const targetA = metaA.market === "JP" || metaA.market === "KR";
    const targetB = metaB.market === "JP" || metaB.market === "KR";
    if (metaA.market === "US" && targetB) {
      return leadToNextMarket(a, b, calendars[metaB.market] || [], metaA.calcType);
    }
    if (metaB.market === "US" && targetA) {
      return leadToNextMarket(b, a, calendars[metaA.market] || [], metaB.calcType)
        .map((p) => ({ d: p.d, x: p.y, y: p.x }));
    }
    return sameDay(a, b);
  }

  function rollingCorrelation(points, size) {
    const out = [];
    let sx = 0, sy = 0, sxx = 0, syy = 0, sxy = 0;
    for (let i = 0; i < points.length; i++) {
      const p = points[i];
      sx += p.x; sy += p.y; sxx += p.x * p.x; syy += p.y * p.y; sxy += p.x * p.y;
      if (i >= size) {
        const q = points[i - size];
        sx -= q.x; sy -= q.y; sxx -= q.x * q.x; syy -= q.y * q.y; sxy -= q.x * q.y;
      }
      if (i >= size - 1) {
        const v = pearsonSums(size, sx, sy, sxx, syy, sxy);
        if (v !== null) out.push({ d: p.d, v });
      }
    }
    return out;
  }

  function analysePair(a, b, metaA, metaB, calendars, periods) {
    const aligned = alignPair(a, b, metaA, metaB, calendars);
    const rolling = {};
    const current = {};
    for (const n of periods) {
      rolling[n] = rollingCorrelation(aligned, n);
      const last = rolling[n][rolling[n].length - 1];
      current[n] = last ? last.v : null;
    }
    return { aligned, rolling, current };
  }

  function concentrationTimeline(pairs, periods, staleDays) {
    const result = {};
    const maxAge = (staleDays || 14) * DAY_MS;
    for (const period of periods) {
      const arrays = pairs.map((p) => p.rolling[period] || []);
      const dateSet = new Set();
      arrays.forEach((a) => a.forEach((x) => dateSet.add(x.d)));
      const dates = [...dateSet].sort();
      const pos = arrays.map(() => 0), latest = arrays.map(() => null);
      const out = [];
      for (const d of dates) {
        let sum = 0, used = 0;
        const now = Date.parse(d + "T00:00:00Z");
        for (let i = 0; i < arrays.length; i++) {
          while (pos[i] < arrays[i].length && arrays[i][pos[i]].d <= d) {
            latest[i] = arrays[i][pos[i]++];
          }
          const hit = latest[i];
          if (!hit || now - Date.parse(hit.d + "T00:00:00Z") > maxAge) continue;
          sum += hit.v; used++;
        }
        if (used) out.push({ d, v: sum / used, used, total: arrays.length });
      }
      result[period] = out;
    }
    return result;
  }

  function trailingSeries(values, size, calcType) {
    const out = new Array(values.length).fill(null);
    if (size < 1) return out;
    for (let i = size - 1; i < values.length; i++) {
      let acc = calcType === "diff" ? 0 : 1;
      for (let k = i - size + 1; k <= i; k++) {
        acc = calcType === "diff" ? acc + values[k] : acc * (1 + values[k]);
      }
      out[i] = calcType === "diff" ? acc : acc - 1;
    }
    return out;
  }

  function forwardSeries(values, size, calcType) {
    const out = new Array(values.length).fill(null);
    if (size < 1) return out;
    for (let i = 0; i + size < values.length; i++) {
      let acc = calcType === "diff" ? 0 : 1;
      for (let k = i + 1; k <= i + size; k++) {
        acc = calcType === "diff" ? acc + values[k] : acc * (1 + values[k]);
      }
      out[i] = calcType === "diff" ? acc : acc - 1;
    }
    return out;
  }

  function mean(values) {
    if (!values.length) return null;
    let s = 0;
    for (const v of values) s += v;
    return s / values.length;
  }

  function stdev(values) {
    if (values.length < 2) return null;
    const m = mean(values);
    let s = 0;
    for (const v of values) s += (v - m) * (v - m);
    return Math.sqrt(s / (values.length - 1));
  }

  function quantile(values, p) {
    if (!values.length) return null;
    const sorted = [...values].sort((a, b) => a - b);
    const at = (sorted.length - 1) * p;
    const lo = Math.floor(at), hi = Math.ceil(at);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (at - lo);
  }

  function quantileRank(values, v) {
    if (!values.length || v === null || v === undefined) return null;
    let below = 0;
    for (const x of values) if (x <= v) below++;
    return below / values.length;
  }

  function regimeCorrelation(points, size, mainCalcType) {
    const trail = trailingSeries(points.map((p) => p.x), size, mainCalcType);
    const up = [], down = [];
    for (let i = 1; i < points.length; i++) {
      const state = trail[i - 1];
      if (state === null) continue;
      (state >= 0 ? up : down).push(points[i]);
    }
    return {
      up: pearson(up), down: pearson(down),
      upDays: up.length, downDays: down.length
    };
  }

  function conditionalReturns(points) {
    const up = [], down = [];
    for (const p of points) {
      if (p.y > 0) up.push(p.x);
      else if (p.y < 0) down.push(p.x);
    }
    const side = (values) => ({
      main: mean(values),
      win: values.length ? values.filter((v) => v > 0).length / values.length : null,
      n: values.length
    });
    return { subUp: side(up), subDown: side(down), base: { main: mean(points.map((p) => p.x)), n: points.length } };
  }

  function forwardAfterExtreme(points, lookback, forward, subCalcType, mainCalcType) {
    const back = trailingSeries(points.map((p) => p.y), lookback, subCalcType);
    const ahead = forwardSeries(points.map((p) => p.x), forward, mainCalcType);
    const usable = [];
    for (let i = 0; i < points.length; i++) {
      if (back[i] === null || ahead[i] === null) continue;
      usable.push({ back: back[i], ahead: ahead[i] });
    }
    if (!usable.length) return null;
    const hi = quantile(usable.map((u) => u.back), 0.75);
    const lo = quantile(usable.map((u) => u.back), 0.25);
    const pick = (test) => {
      const values = usable.filter(test).map((u) => u.ahead);
      return {
        main: mean(values),
        win: values.length ? values.filter((v) => v > 0).length / values.length : null,
        n: values.length
      };
    };
    return {
      high: pick((u) => u.back >= hi),
      low: pick((u) => u.back <= lo),
      base: { main: mean(usable.map((u) => u.ahead)), n: usable.length }
    };
  }

  function leadLag(points, shifts) {
    return shifts.map((k) => {
      const paired = [];
      for (let i = 0; i < points.length; i++) {
        const j = i - k;
        if (j < 0 || j >= points.length) continue;
        paired.push({ x: points[i].x, y: points[j].y });
      }
      return { shift: k, r: pearson(paired), n: paired.length };
    });
  }

  function sampleEvenly(series, count) {
    if (!series.length) return [];
    if (series.length <= count) return series.slice();
    const out = [];
    for (let i = 0; i < count; i++) {
      out.push(series[Math.round((series.length - 1) * (i / (count - 1)))]);
    }
    return out;
  }

  function summarizeSeries(series, calcType) {
    const rows = series.filter((p) => finiteNumber(p.v) !== null);
    if (!rows.length) return null;
    const v = rows.map((p) => Number(p.v));
    const last = v[v.length - 1], lastDate = rows[rows.length - 1].d;
    const diff = calcType === "diff";
    const move = (from) => (from === undefined || from === null) ? null : (diff ? last - from : last / from - 1);

    const back = (n) => (v.length > n ? v[v.length - 1 - n] : null);
    const ret = {};
    [5, 20, 60, 250].forEach((n) => { ret[n] = move(back(n)); });

    const year = String(lastDate).slice(0, 4);
    let at = -1;
    for (let i = 0; i < rows.length; i++) {
      if (String(rows[i].d).slice(0, 4) === year) { at = i; break; }
    }
    ret.ytd = at > 0 ? move(v[at - 1]) : null;

    const tail = v.slice(-250);
    const hi = Math.max(...tail), lo = Math.min(...tail);
    const ma200 = v.length >= 200 ? mean(v.slice(-200)) : null;

    let hv = null;
    if (!diff && v.length > 20) {
      const r = [];
      for (let i = v.length - 20; i < v.length; i++) {
        if (v[i - 1]) r.push(v[i] / v[i - 1] - 1);
      }
      const sd = stdev(r);
      if (sd !== null) hv = sd * Math.sqrt(250);
    }

    return {
      date: lastDate, close: last, n: v.length, calcType: diff ? "diff" : "return",
      ret,
      hv20: hv,
      ma200Gap: ma200 === null ? null : (diff ? last - ma200 : last / ma200 - 1),
      drawdown: diff ? null : (hi ? last / hi - 1 : null),
      rangePos: hi === lo ? null : (last - lo) / (hi - lo),
      high250: hi, low250: lo
    };
  }

  return {
    finiteNumber,
    priceChanges,
    pearson,
    sameDay,
    leadToNextMarket,
    alignPair,
    rollingCorrelation,
    analysePair,
    concentrationTimeline,
    trailingSeries,
    forwardSeries,
    quantile,
    quantileRank,
    regimeCorrelation,
    conditionalReturns,
    forwardAfterExtreme,
    leadLag,
    sampleEvenly,
    summarizeSeries
  };
});

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", () => {
    const script = document.createElement("script");
    script.src = "ui-separation.js";
    document.body.appendChild(script);
  }, { once: true });
}
