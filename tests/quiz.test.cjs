const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function setup() {
  const elements = {};
  function element() {
    return { children: [], style: {}, textContent: '', append(...items) { this.children.push(...items); }, appendChild(item) { this.append(item); }, replaceChildren() { this.children = []; } };
  }
  for (const id of ['scoreDisplay', 'quizContainer', 'retryBtn', 'customTopic']) elements[id] = element();
  const state = { selected: null, calls: [], alerts: [], fail: false };
  const ctx = vm.createContext({
    localStorage: { getItem: () => 'test', setItem() {} }, crypto: { randomUUID: () => 'test' },
    window: {}, URLSearchParams,
    alert: message => state.alerts.push(message),
    document: {
      getElementById: id => elements[id] || (id.startsWith('explanation') ? elements[id] = element() : null),
      querySelector: () => state.selected,
      createElement: element, createTextNode: text => ({ textContent: text })
    },
    fetch: async (url, options) => {
      state.calls.push({url, options});
      if (state.fail) throw new Error('Offline');
      return { ok: true, json: async () => ({ correct: true, explanation: '<b>plain text</b>' }) };
    }
  });
  vm.runInContext(fs.readFileSync('frontend/shared/quiz.js', 'utf8'), ctx);
  vm.runInContext('renderQuiz([{question: "<script>unsafe</script>", options: ["a", "b", "c", "d"], answer: "a"}], "custom topic")', ctx);
  return { ctx, state, elements };
}

test('empty submit can be retried and successful answer counts once', async () => {
  const { ctx, state, elements } = setup();
  await vm.runInContext('submitAnswer(0)', ctx);
  assert.equal(state.calls.length, 0);
  state.selected = {value: 'a'};
  await vm.runInContext('submitAnswer(0)', ctx);
  await vm.runInContext('submitAnswer(0)', ctx);
  assert.equal(state.calls.length, 1);
  assert.equal(elements.scoreDisplay.textContent, 'Score: 1 / 1');
  assert.equal(JSON.parse(state.calls[0].options.body).topic, 'custom topic');
  assert.equal(elements.explanation0.textContent, '<b>plain text</b>');
  assert.equal(elements.quizContainer.children[0].children[0].textContent, 'Q1: <script>unsafe</script>');
});

test('network failure releases submission for retry', async () => {
  const {ctx, state, elements} = setup();
  state.selected = {value: 'a'};
  state.fail = true;
  await vm.runInContext('submitAnswer(0)', ctx);
  assert.match(elements.explanation0.textContent, /retry/);
  state.fail = false;
  await vm.runInContext('submitAnswer(0)', ctx);
  assert.equal(elements.scoreDisplay.textContent, 'Score: 1 / 1');
});

test('duplicate in-flight submission and stale response do not change score', async () => {
  const {ctx, state, elements} = setup();
  state.selected = {value: 'a'};
  let resolve;
  ctx.fetch = () => new Promise(done => {resolve = done;});
  const first = vm.runInContext('submitAnswer(0)', ctx);
  await vm.runInContext('submitAnswer(0)', ctx);
  vm.runInContext('quizVersion++; renderQuiz([], "new")', ctx);
  resolve({ok: true, json: async () => ({correct: true, explanation: 'old'})});
  await first;
  assert.equal(elements.scoreDisplay.textContent, 'Score: 0 / 0');
});
