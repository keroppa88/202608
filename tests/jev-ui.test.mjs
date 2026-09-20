import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const source = readFileSync(new URL('../ui-separation.js', import.meta.url), 'utf8');
const handler = source.slice(source.indexOf('  async function runAiAnalysis('), source.indexOf('  const initSeparatedUi'));
function setup(respond) {
  const nodes = Object.fromEntries(['ai-run', 'ai-jev', 'aistatus', 'ai-result', 'ai-prompt-text'].map(id => [id, { textContent: '', disabled: false }]));
  const calls = [], payload = { kind: 'tech', name: 'TEST', asOf: '2026-09-18', tuned: { recent: [1] }, corr: { subs: [1, 2] } };
  const context = vm.createContext({
    aiBusy: false, settings: { corrAiMain: 'test', corrAiSubs: ['compare'] },
    AI_ENDPOINT: 'https://worker.example',
    document: { getElementById: id => nodes[id] },
    setAiEnabled: enabled => { nodes['ai-run'].disabled = nodes['ai-jev'].disabled = !enabled; },
    closePromptModal() {}, releaseLargeAiSourceCache() {}, isMobileAiBrowser: () => false,
    drawAiControls() {}, signature: () => 'same', aiApiFailureMessage: (status, raw) => `Gemini ${status} ${raw}`,
    diagnoseLoadFailure: async () => 'network', buildStandaloneAiPayload: async () => payload,
    fetch: async (url, init) => { calls.push({ url, payload: JSON.parse(init.body) }); return respond(); }
  });
  vm.runInContext(handler, context);
  return { nodes, calls, payload, context };
}

test('both buttons use identical existing material and separate API routes', async () => {
  const s = setup(() => Response.json({ provider: 'jev', text: '短期 75% 中期 50% 長期 25%' }));
  await s.context.runAiAnalysis('jev');
  await s.context.runAiAnalysis('gemini');
  assert.deepEqual(s.calls.map(c => c.url), ['https://worker.example/jev', 'https://worker.example']);
  assert.deepEqual(s.calls[0].payload, s.calls[1].payload);
  assert.deepEqual(s.calls[0].payload, s.payload);
  assert.equal(s.nodes['ai-jev'].textContent, 'JevによるAI分析');
  assert.equal(s.nodes['ai-run'].textContent, 'GeminiAPIによるAI分析');
  assert.equal(s.nodes['ai-run'].disabled, false);
  assert.equal(s.nodes['ai-jev'].disabled, false);
});

test('Jev errors are not rendered as Gemini monthly-budget messages; buttons recover', async () => {
  const s = setup(() => Response.json({ error: 'Jevが混み合っています' }, { status: 429 }));
  await s.context.runAiAnalysis('jev');
  assert.match(s.nodes['ai-result'].textContent, /Jevが混み合っています/);
  assert.doesNotMatch(s.nodes['ai-result'].textContent, /400円|Gemini/);
  assert.equal(s.context.aiBusy, false);
  assert.equal(s.nodes['ai-jev'].disabled, false);
});

test('an old Worker returning Gemini output for /jev is detected', async () => {
  const s = setup(() => Response.json({ text: 'Gemini result' }));
  await s.context.runAiAnalysis('jev');
  assert.match(s.nodes['ai-result'].textContent, /Jevの応答形式/);
  assert.equal(s.nodes['aistatus'].textContent, 'AI分析に失敗');
});

test('duplicate clicks while an analysis is active cannot send another request', async () => {
  const s = setup(() => Response.json({}));
  s.context.aiBusy = true;
  await s.context.runAiAnalysis('jev');
  assert.equal(s.calls.length, 0);
});
