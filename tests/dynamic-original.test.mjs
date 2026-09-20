import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const section = (start, end) => html.slice(html.indexOf(start), html.indexOf(end, html.indexOf(start)));
const code = [
  section('function parseCsv(', '// Yahoo年次CSV'),
  section('async function allSeriesOf(', 'async function fetchJson('),
  section('function splitKey(', 'function labelOf('),
  section('function isNum(', 'function fmt('),
].join('\n');

function setup(csv) {
  const calls = [];
  const context = vm.createContext({
    fetchCsv: async path => { calls.push(path); return context.parseCsv(csv); },
    fetchJson: async () => { throw Error('Dynamic manifest unavailable'); },
  });
  vm.runInContext(code, context);
  return { context, calls };
}

test('original Dynamic history survives an unavailable manifest and excludes other indices and invalid values', async () => {
  const { context, calls } = setup('trade_date,name,close\n2019-01-04,脳Hack指数,100\n2020-07-28,脳Hack指数,120\n2023-08-25,脳Hack指数,180\n2026-09-18,脳Hack指数,400\n2020-07-29,別指数,999\n2020-07-30,脳Hack指数,\n2020-07-31,脳Hack指数,NaN\n');
  const map = await context.allSeriesOf('original:脳Hack指数');
  assert.deepEqual(Array.from(map, ([date, value]) => [date, value]), [['2019-01-04','100'], ['2020-07-28','120'], ['2023-08-25','180'], ['2026-09-18','400']]);
  assert.deepEqual(calls, ['data/original_index.csv']);
});

test('real 脳Hack history contains the reported Dynamic window and uses the same source as year view', async () => {
  const csv = readFileSync(new URL('../data/original_index.csv', import.meta.url), 'utf8');
  const { context } = setup(csv);
  const map = await context.allSeriesOf('original:脳Hack指数');
  const rows = context.parseCsv(csv).filter(row => row.name === '脳Hack指数' && row.trade_date >= '2020-07-28' && row.trade_date <= '2023-08-25');
  assert.ok(rows.length > 700);
  for (const row of rows) assert.equal(map.get(row.trade_date), row.close);
  assert.ok(Number(map.get('2020-07-28')) > 0);
  assert.ok(Number(map.get('2023-08-25')) > 0);
});
