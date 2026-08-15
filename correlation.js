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

  return {
    finiteNumber,
    priceChanges,
    pearson,
    sameDay,
    leadToNextMarket,
    alignPair,
    rollingCorrelation,
    analysePair,
    concentrationTimeline
  };
});
