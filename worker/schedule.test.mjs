import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';
// package.jsonなしでも既存のWorkerをES moduleとして検査する。
const source = readFileSync(new URL('./index.js', import.meta.url), 'utf8');
const { scheduledEvents, runSchedule } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));

test('全16ワークフローの既存cronと一週間の起動対象が一致する', () => {
  const dir = new URL('../.github/workflows/', import.meta.url);
  const workflows = readdirSync(dir).flatMap(name => {
    const text = readFileSync(new URL(name, dir), 'utf8');
    const match = text.match(/cron: "([^"]+)"/);
    if (!match) return [];
    const event = `scheduled-${name.replace('.yml', '')}`;
    assert.ok(text.includes(`types: [${event}]`));
    assert.ok(text.includes("vars.CLOUDFLARE_SCHEDULE != 'true'"));
    return [{ event, cron: match[1] }];
  });
  assert.equal(workflows.length, 16);
  const start = Date.parse('2026-09-13T00:00:00Z');
  for (let i = 0; i < 7 * 24 * 60; i++) {
    const time = start + i * 60000, d = new Date(time);
    const expected = workflows.filter(({ cron }) => {
      const [m, h, , , days] = cron.split(' ');
      const [a, b] = days.split('-').map(Number);
      return d.getUTCMinutes() == m && d.getUTCHours() == h && d.getUTCDay() >= a && d.getUTCDay() <= b;
    }).map(x => x.event).sort();
    assert.deepEqual(scheduledEvents(time).sort(), expected, d.toISOString());
  }
});

test('無効化中と対象外時刻は送信せず、有効時は対象だけ1回ずつ送る', async () => {
  const calls = [];
  const send = async (url, init) => { calls.push({ url, ...JSON.parse(init.body) }); return { status: 204 }; };
  const c = { scheduledTime: Date.parse('2026-09-14T09:00:00Z') };
  const env = { SCHEDULE_ENABLED: 'true', GH_TOKEN: 'test', GH_REPO: 'keroppa88/202608' };
  await runSchedule(c, { ...env, SCHEDULE_ENABLED: 'false' }, send);
  await runSchedule({ scheduledTime: c.scheduledTime + 600000 }, env, send);
  assert.equal(calls.length, 0);
  await runSchedule(c, env, send);
  assert.equal(calls.length, 7);
  assert.equal(new Set(calls.map(x => x.event_type)).size, 7);
  assert.ok(calls.every(x => x.client_payload.scheduled_at === '2026-09-14T09:00:00.000Z'));
});

test('一つの送信が失敗しても他の対象へ送信し、全体は失敗として報告する', async () => {
  let count = 0;
  await assert.rejects(runSchedule(
    { scheduledTime: Date.parse('2026-09-14T09:00:00Z') },
    { SCHEDULE_ENABLED: 'true', GH_TOKEN: 'test', GH_REPO: 'keroppa88/202608' },
    async () => ({ status: ++count === 1 ? 403 : 204 })
  ), /GitHub HTTP 403/);
  assert.equal(count, 7);
});
