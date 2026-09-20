import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('./index.js', import.meta.url), 'utf8');
const { default: worker, buildJevRequest, parseJevAnalysis, formatJevAnalysis } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'));
const payload = {
  kind: 'tech', name: '検証銘柄', asOf: '2026-09-18', span: { rows: 300, from: '2025-07-01', to: '2026-09-18' },
  params: { base: { ma: [5, 25, 75] }, tuned: { ma: [7, 36, 240] } },
  tuned: { recent: [{ chg5: 1, dev0: 2, chg20: -3, dev1: -1, chg100: 10, dev2: 12 }] },
  corr: { subs: [{ name: '比較銘柄', r: { 60: 0.8 } }] }, like: { short: null, long: null }
};
function fixture() {
  const answers = {};
  for (const [id, score] of [['short', 4], ['medium', 2], ['long', 0]]) {
    answers[`${id}_material`] = { type: 'choice', choice: 'sufficient', confidence: 1, probabilities: { sufficient: 1, insufficient: 0 } };
    answers[id] = { type: 'score', score, confidence: 1, probabilities: Object.fromEntries([0, 1, 2, 3, 4].map(n => [n, Number(n === score)])) };
  }
  return { model: 'jev-1.13.0', usage: { input_tokens: 1000, output_tokens: 50 }, answers };
}
let ip = 0;
const request = (body = payload, path = '/jev', origin = 'https://keroppa88.github.io') => new Request(`https://worker.test${path}`, {
  method: 'POST', headers: { origin, 'content-type': 'application/json', 'cf-connecting-ip': `test-${++ip}` }, body: JSON.stringify(body)
});
const env = { TYPESAFE_API_KEY: 'test-jev-secret', ALLOWED_ORIGINS: 'https://keroppa88.github.io' };

test('existing material is preserved; 3 periods share one request with six questions', () => {
  const built = buildJevRequest(payload);
  assert.deepEqual(built.state, payload);
  assert.equal(Object.keys(built.questions).length, 6);
  for (const [id, days] of [['short', 5], ['medium', 20], ['long', 100]]) assert.match(built.questions[id].instructions, new RegExp(`今後${days}営業日`));
  const result = parseJevAnalysis(fixture(), built);
  assert.deepEqual(result.map(h => h.score), [100, 50, 0]);
  const text = formatJevAnalysis(payload, result);
  assert.match(text, /短期（5営業日以内）　100%/);
  assert.match(text, /中期（20営業日以内）　50%/);
  assert.match(text, /長期（100営業日以内）　0%/);
});

test('continuous values and rounding are preserved; malformed scores fail', () => {
  const built = buildJevRequest(payload), response = fixture();
  response.answers.short = { type: 'score', score: 2.48, confidence: 0.5, probabilities: { 0: 0, 1: 0, 2: 0.5, 3: 0.49, 4: 0 } };
  assert.equal(parseJevAnalysis(response, built)[0].score, 62);
  response.answers.short.score = 4.5;
  assert.throws(() => parseJevAnalysis(response, built), /評価値が不正/);
  response.answers.short.score = 0;
  assert.throws(() => parseJevAnalysis(response, built), /一致しない/);
});

test('missing data and model insufficiency are withheld rather than scored 50', () => {
  const sparse = structuredClone(payload);
  sparse.span.rows = 10;
  sparse.tuned.recent[0].chg5 = null;
  const built = buildJevRequest(sparse);
  assert.equal(Object.keys(built.questions).length, 0);
  const response = fixture();
  response.answers.medium_material.choice = 'insufficient';
  response.answers.medium_material.probabilities = { sufficient: 0, insufficient: 1 };
  delete response.answers.medium;
  const result = parseJevAnalysis(response, buildJevRequest(payload));
  assert.equal(result[1].score, null);
  assert.match(formatJevAnalysis(payload, result), /中期（20営業日以内）　判定保留/);
});

test('Jev endpoint works without Gemini key and sends bearer auth only server-side', async t => {
  let calls = 0;
  t.mock.method(globalThis, 'fetch', async (url, init) => {
    calls++;
    assert.equal(url, 'https://api.typesafe.ai/v1/systemone');
    assert.equal(init.headers.authorization, `Bearer ${env.TYPESAFE_API_KEY}`);
    assert.equal(init.redirect, 'manual');
    assert.deepEqual(JSON.parse(init.body).state, payload);
    return Response.json(fixture());
  });
  const response = await worker.fetch(request(), env);
  assert.equal(response.status, 200);
  const result = await response.json();
  assert.equal(result.provider, 'jev');
  assert.equal(calls, 1);
  assert.equal(JSON.stringify(result).includes(env.TYPESAFE_API_KEY), false);
  assert.equal(response.headers.get('access-control-allow-origin'), env.ALLOWED_ORIGINS);
});

test('bad payload, missing key, foreign origin and oversized body never call API', async t => {
  t.mock.method(globalThis, 'fetch', () => { throw new Error('must not call'); });
  assert.equal((await worker.fetch(request(), {})).status, 503);
  assert.equal((await worker.fetch(request({ kind: 'market' }), env)).status, 400);
  const malformed = structuredClone(payload);
  malformed.tuned.recent = [null];
  assert.equal((await worker.fetch(request(malformed), env)).status, 400);
  assert.equal((await worker.fetch(request(payload, '/jev', 'https://foreign.example'), env)).status, 403);
  assert.equal((await worker.fetch(request({ ...payload, padding: 'あ'.repeat(40000) }), env)).status, 413);
});

test('rate limits, malformed responses and upstream failures remain visible', async t => {
  const responses = [new Response('secret echo', { status: 429 }), Response.json({ answers: {} }), new Response(env.TYPESAFE_API_KEY, { status: 401 })];
  t.mock.method(globalThis, 'fetch', async () => responses.shift());
  const limited = await worker.fetch(request(), env);
  assert.equal(limited.status, 429);
  assert.doesNotMatch(await limited.text(), /400円|secret echo/);
  assert.equal((await worker.fetch(request(), env)).status, 502);
  const unauthorized = await worker.fetch(request(), env);
  assert.equal(unauthorized.status, 502);
  assert.equal((await unauthorized.text()).includes(env.TYPESAFE_API_KEY), false);
});

test('existing Gemini and prompt routes keep their behavior', async t => {
  t.mock.method(globalThis, 'fetch', async url => {
    assert.match(url, /generativelanguage.googleapis.com/);
    return Response.json({ candidates: [{ content: { parts: [{ text: 'Geminiの分析結果' }] } }] });
  });
  const response = await worker.fetch(request(payload, '/'), { ...env, GEMINI_API_KEY: 'test-gemini' });
  assert.deepEqual(await response.json(), { text: 'Geminiの分析結果' });
  const prompt = await worker.fetch(new Request('https://worker.test/prompt', { headers: { origin: env.ALLOWED_ORIGINS } }), env);
  assert.equal(prompt.status, 200);
  assert.match(await prompt.text(), /AI主観コメント/);
});
