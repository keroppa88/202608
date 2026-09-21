import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import crypto from 'node:crypto';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const C = createRequire(import.meta.url)('../correlation.js');
export const TARGETS = [
  ['nikkei', '日経平均', 'yahoo:^N225'], ['topix', 'TOPIX', 'jpx:TOPIX'],
  ['dow', 'NYダウ', 'yahoo:^DJI'], ['sox', 'SOX', 'yahoo:^SOX'],
  ['sp500', 'S&P500', 'yahoo:^GSPC'], ['nasdaq', 'ナスダック総合', 'yahoo:^IXIC'],
].map(([id, name, key]) => ({ id, name, key }));
export const EXTRAS = [
  { key: 'yahoo:USDJPY=X', name: 'ドル円' },
  { key: 'rates:米国 10年国債', name: '米国10年国債利回り' },
  { key: 'rates:日本 10年国債', name: '日本10年国債利回り' },
];
export const ASSETS = [...TARGETS, ...EXTRAS];
export const MODEL = 'jev-1.13.0';
export const DAYS = [5, 20, 100];
export const hash = value => crypto.createHash('sha256').update(typeof value === 'string' ? value : JSON.stringify(value)).digest('hex');
const html = fs.readFileSync(path.join(ROOT, 'index.html'), 'utf8');
const between = (start, end) => {
  const a = html.indexOf(start), b = html.indexOf(end, a);
  if (a < 0 || b < 0) throw Error(`Technical engine boundary missing: ${start}`);
  return html.slice(a, b);
};
// 画面と同じ指標・最適化・類似局面の関数を使う。DOMや画面設定は実行しない。
const engineSource = [
  between('const DEFAULT_TECH_PARAMS =', '// 覚えていた数字'),
  between('const TECH_CHG =', '/* 数字の欄'),
  between('function sma(', 'function paramGet('),
  between('function aiRound(', 'function aiScale('),
  between('const AI_TECH_YEARS =', '// 送る数字をぜんぶ作る'),
].join('\n');
const engine = vm.createContext({});
vm.runInContext(engineSource, engine);
const workerSource = fs.readFileSync(path.join(ROOT, 'worker/index.js'), 'utf8');
export const workerApi = await import('data:text/javascript;base64,' + Buffer.from(workerSource).toString('base64'));
// 実績は実装・モデル・質問文ごとに分離する。古い実績は上書きしない。
export const VERSION = 'weekly-v1-c0cb345f448c';
export const IMPLEMENTATION_HASH = hash((engineSource + fs.readFileSync(fileURLToPath(import.meta.url), 'utf8') + workerSource.slice(workerSource.indexOf('const JEV_HORIZONS'), workerSource.indexOf('async function callJev')) + fs.readFileSync(path.join(ROOT, 'correlation.js'), 'utf8')).replace(/\r\n/g, '\n'));
export function splitCsv(line) {
  const out = []; let value = '', quoted = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') { if (quoted && line[i + 1] === '"') { value += '"'; i++; } else quoted = !quoted; }
    else if (ch === ',' && !quoted) { out.push(value); value = ''; }
    else if (ch !== '\r') value += ch;
  }
  out.push(value); return out;
}
const number = v => v !== undefined && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null;
export async function loadMarket(dataDir = path.join(ROOT, 'data')) {
  const maps = Object.fromEntries(ASSETS.map(a => [a.key, new Map()]));
  const specs = fs.readdirSync(dataDir).filter(n => /^overseas_\d{4}\.csv$/.test(n)).sort().map(n => [n, 'symbol', 'close', 'yahoo']);
  specs.push(['jpx_index.csv', 'name', 'close', 'jpx'], ['rates.csv', 'name', 'value', 'rates']);
  for (const [file, column, value, prefix] of specs) {
    let head;
    for await (const line of readline.createInterface({ input: fs.createReadStream(path.join(dataDir, file)), crlfDelay: Infinity })) {
      if (!head) { head = splitCsv(line.replace(/^\uFEFF/, '')); continue; }
      const cells = splitCsv(line), get = k => cells[head.indexOf(k)];
      const key = prefix + ':' + get(column);
      if (!maps[key]) continue;
      const c = number(get(value)), d = get('trade_date');
      if (c === null || !/^\d{4}-\d{2}-\d{2}$/.test(d)) continue;
      maps[key].set(d, { d, c, o: number(get('open')), h: number(get('high')), l: number(get('low')), v: number(get('volume')) });
    }
  }
  return Object.fromEntries(Object.entries(maps).map(([key, map]) => [key, [...map.values()].sort((a,b) => a.d.localeCompare(b.d))]));
}
export function lastFriday(today = new Date().toISOString().slice(0,10)) {
  const date = new Date(today + 'T00:00:00Z');
  // 当日金曜は未確定なので前週まで。土曜以降に当週分を扱う。
  const n = (date.getUTCDay() + 2) % 7;
  date.setUTCDate(date.getUTCDate() - (n || 7));
  return date.toISOString().slice(0,10);
}
export function weeks(end, years = 5) {
  const start = new Date(end + 'T00:00:00Z'); start.setUTCFullYear(start.getUTCFullYear() - years);
  const out = [];
  for (let d = new Date(end + 'T00:00:00Z'); d > start; d.setUTCDate(d.getUTCDate() - 7)) out.push(d.toISOString().slice(0,10));
  return out.reverse();
}
const round = v => Number.isFinite(v) ? Math.round(v * 1e4) / 1e4 : null;
export function makePayload(market, target, cutoff) {
  const year = Number(cutoff.slice(0,4));
  const from = `${year - 11}-01-01`;
  const histories = Object.fromEntries(ASSETS.map(a => [a.key, (market[a.key] || []).filter(r => r.d <= cutoff && r.d >= from)]));
  const rows = histories[target.key];
  if (rows.length < 250) throw Error(`${target.name}: 250 observations required at ${cutoff}`);
  const age = d => (Date.parse(cutoff) - Date.parse(d)) / 864e5;
  if (age(rows.at(-1).d) > 7) throw Error(`${target.name}: stale data at ${cutoff}`);
  engine.rows = rows;
  const tech = vm.runInContext(`(() => {
    const base = JSON.parse(JSON.stringify(DEFAULT_TECH_PARAMS));
    const at = rows.length - 1;
    const tuned = techAutoFit(rows, Math.min(250, Math.floor(rows.length / 4)), at, base);
    const b = techIndicators(rows, base), t = techIndicators(rows, tuned);
    const back = (ind, fields) => Object.fromEntries(AI_TECH_BACK.map(n => [n, at >= n ? aiTechRow(ind, rows, at-n, fields) : null]));
    return { params:{base,tuned}, base:{now:aiTechRow(b,rows,at,AI_BASE_FIELDS),back:back(b,AI_BASE_FIELDS)},
      tuned:{recent:rows.slice(-AI_TECH_RECENT).map((_,j)=>aiTechRow(t,rows,rows.length-Math.min(rows.length,AI_TECH_RECENT)+j,AI_TECH_FIELDS)),back:back(t,AI_TECH_FIELDS)},
      like:{short:aiLike(t,rows,AI_LIKE_SHORT,at),long:aiLike(t,rows,AI_LIKE_LONG,at)} };
  })()`, engine);
  const mainMeta = { market: target.id === 'nikkei' || target.id === 'topix' ? 'JP' : 'US', calcType:'return' };
  const changes = (data, diff) => data.slice(1).map((r,i)=>({d:r.d,v:diff ? r.c-data[i].c : r.c/data[i].c-1}));
  const mainChanges = changes(rows, false);
  const subs = ASSETS.filter(a=>a.key!==target.key).map(a=>{
    const data = histories[a.key], diff = a.key.startsWith('rates:');
    if (data.length < 250 || age(data.at(-1).d) > 7) throw Error(`${a.name}: insufficient/stale comparison history at ${cutoff}`);
    const last = data.at(-1);
    const meta = {market: a.id === 'nikkei' || a.id === 'topix' || a.key === 'rates:日本 10年国債' ? 'JP' : a.key === 'yahoo:USDJPY=X' ? 'FX' : 'US', calcType:diff?'diff':'return'};
    const points = C.alignPair(mainChanges, changes(data,diff), mainMeta, meta, {JP:histories['yahoo:^N225'].map(r=>r.d)});
    return {key:a.key,name:a.name,asOf:last.d,unit:diff?'percentage_points':'percent',level:last.c,
      change:Object.fromEntries([5,20,100].map(n=>[n,round(diff ? last.c-data.at(-1-n).c : (last.c/data.at(-1-n).c-1)*100)])),
      r:Object.fromEntries([20,60,120].map(n=>[n,round(C.pearson(points.slice(-n)))])),
      n:points.length, recent:data.slice(-10).map(r=>[r.d,r.c])};
  });
  return {kind:'tech',name:target.name,asOf:rows.at(-1).d,span:{from:rows[0].d,to:rows.at(-1).d,rows:rows.length},...JSON.parse(JSON.stringify(tech)),
    corr:{asOf:cutoff,subs}, evaluation:{version:VERSION,cutoff,decision:'週末。日米の当週取引終了後に評価し、翌週最初の取引日の始値で購入を仮定',
      rates:'国債利回りのlevelは%、changeは差分（%ポイント）。価格騰落率ではない。',comparisonKeys:subs.map(s=>s.key)}};
}
export function outcome(rows, cutoff, days) {
  const future = rows.filter(r=>r.d>cutoff);
  if (future.length < days) return {status:'pending',observations:future.length};
  const period = future.slice(0,days), entry = period[0].o;
  if (!(entry > 0) || period.some(r=>!(r.h>0) || !(r.l>0) || !(r.c>0))) return {status:'missing_ohlc'};
  const highs = period.map(r=>r.h), lows=period.map(r=>r.l);
  // 日足内の高値・安値の順序は不明。MDDは終値系列（最初は購入価格）で計算。
  let peak=entry, mdd=0;
  for (const r of period) { peak=Math.max(peak,r.c); mdd=Math.min(mdd,(r.c/peak-1)*100); }
  return {status:'complete',entryDate:period[0].d,endDate:period.at(-1).d,entry,
    maxRise:round(Math.max(0,(Math.max(...highs)/entry-1)*100)),maxLoss:round(Math.min(0,(Math.min(...lows)/entry-1)*100)),
    endReturn:round((period.at(-1).c/entry-1)*100),closeDrawdown:round(mdd)};
}
export function aggregate(records, market) {
  const output = {};
  for (const t of TARGETS) {
    const list=records.filter(r=>r.target===t.id && r.version===VERSION && r.response.model===MODEL);
    output[t.id]={name:t.name,key:t.key,judgments:list.length,periods:{}};
    for (const days of DAYS) {
      const all=list.map(r=>({cutoff:r.cutoff,score:r.response.horizons.find(h=>h.days===days)?.score,...outcome(market[t.key],r.cutoff,days)}));
      const groups=[['all',()=>true],['gte90',r=>r.score!==null&&r.score>=90],['gte80',r=>r.score!==null&&r.score>=80],['80to90',r=>r.score!==null&&r.score>=80&&r.score<90]];
      output[t.id].periods[days]=Object.fromEntries(groups.map(([key,select])=>{
        const selected=all.filter(select), complete=selected.filter(r=>r.status==='complete');
        const stats={n:complete.length,pending:selected.filter(r=>r.status==='pending').length,missing:selected.filter(r=>r.status==='missing_ohlc').length,
          winRate:complete.length?round(100*complete.filter(r=>r.endReturn>0).length/complete.length):null,insufficient:complete.length<20};
        for(const field of ['maxRise','maxLoss','endReturn','closeDrawdown']) {
          const values=complete.map(r=>r[field]).sort((a,b)=>a-b);
          stats[field]={mean:values.length?round(values.reduce((a,b)=>a+b,0)/values.length):null,median:values.length?round(C.quantile(values,.5)):null};
        }
        return [key,stats];
      }));
    }
  }
  return output;
}
