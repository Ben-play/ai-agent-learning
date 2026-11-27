const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const catalogScript = fs.readFileSync(path.join(__dirname, '../assets/course-catalog.js'), 'utf8');
const pwaScript = fs.readFileSync(path.join(__dirname, '../assets/pwa.js'), 'utf8');
const root = 'https://example.test/ai-agent-learning/';
const stateKey = 'ai-course:learning:v2:%2Fai-agent-learning%2F';
const overview = root + 'lessons/0001-ai-agent-learning-path-overview.html';
const ids = (first, last) => Array.from({ length: last - first + 1 }, (_, i) =>
  'L' + String(first + i).padStart(2, '0'));

class Events {
  listeners = new Map();
  addEventListener(type, handler) {
    if (!this.listeners.has(type)) this.listeners.set(type, []);
    this.listeners.get(type).push(handler);
  }
  dispatch(type, event = {}) {
    for (const handler of this.listeners.get(type) || []) handler(event);
  }
}

class Element extends Events {
  attributes = new Map();
  children = [];
  parentNode = null;
  style = {};
  classList = { toggle() {} };
  #text = '';

  constructor(tag) {
    super();
    this.tagName = tag.toUpperCase();
  }
  matches(selector) {
    const attribute = selector.match(/^([a-z]*)\[([^=\]]+)(?:="([^"]*)")?\]$/);
    if (attribute) {
      const [, tag, name, value] = attribute;
      return (!tag || this.tagName === tag.toUpperCase()) && this.hasAttribute(name) &&
        (value === undefined || this.getAttribute(name) === value);
    }
    if (selector.startsWith('.')) return this.className?.split(' ').includes(selector.slice(1));
    return this.tagName === selector.toUpperCase();
  }
  querySelectorAll(selector) {
    const selectors = selector.split(', ');
    return this.children.flatMap(child => [
      ...(selectors.some(value => child.matches(value)) ? [child] : []),
      ...child.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  hasAttribute(name) { return this.attributes.has(name); }
  setAttribute(name, value) { this.attributes.set(name, value); }
  getAttribute(name) { return this.attributes.get(name) ?? null; }
  appendChild(child) { return this.insertBefore(child, null); }
  insertBefore(child, reference) {
    child.parentNode = this;
    this.children.splice(reference ? this.children.indexOf(reference) : this.children.length, 0, child);
    return child;
  }
  remove() {
    if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1);
    this.parentNode = null;
  }
  get isConnected() { return Boolean(this.parentNode); }
  get textContent() { return this.#text + this.children.map(child => child.textContent).join(''); }
  set textContent(value) { this.#text = value; this.children.length = 0; }
  set innerHTML(value) {
    assert.equal(value, '', 'The status element is cleared before rendering');
    this.textContent = '';
  }
}

function add(parent, tag, attributes = {}) {
  const node = parent.appendChild(new Element(tag));
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function fakeClock() {
  const jobs = new Map();
  let now = 0;
  let nextId = 0;
  return {
    setTimeout(callback, delay) {
      const id = ++nextId;
      jobs.set(id, [now + delay, callback]);
      return id;
    },
    clearTimeout(id) { jobs.delete(id); },
    tick(ms) {
      const end = now + ms;
      while (jobs.size) {
        const [id, [at, callback]] = [...jobs].sort((a, b) => a[1][0] - b[1][0])[0];
        if (at > end) break;
        jobs.delete(id);
        now = at;
        callback();
      }
      now = end;
    },
  };
}

function openPage({ page = '', lastVisited, completed = [], legacyCatalog = false,
  legacyState, serviceWorker } = {}) {
  const document = new Element('document');
  document.currentScript = { src: root + 'assets/pwa.js' };
  document.readyState = 'complete';
  document.createElement = tag => new Element(tag);
  document.documentElement = add(document, 'html');
  document.documentElement.scrollHeight = 1200;
  document.head = add(document.documentElement, 'head');
  document.body = add(document.documentElement, 'body');
  const main = add(document.body, 'main');
  const resume = add(main, 'div', { 'data-continue-learning': '' });
  const resumeLink = add(add(resume, 'div'), 'a');
  resumeLink.href = overview;
  resumeLink.textContent = '打开学习路径总览';
  add(resume, 'span', { 'aria-hidden': 'true' }).textContent = 'L00';
  const required = add(main, 'div', { 'data-learning-progress': 'required' });
  add(required, 'strong');
  add(required, 'span');
  const full = add(main, 'div', { 'data-learning-progress': 'all' });
  const toolbar = add(add(main, 'div'), 'div', { 'data-course-progress': 'completed' });
  add(main, 'header').className = 'lesson-header';

  const stored = new Map();
  if (legacyState) stored.set('ai-course:learning:v1', JSON.stringify(legacyState));
  else if (lastVisited || completed.length) stored.set(stateKey, JSON.stringify({
    version: 2, lastVisited, completed: Object.fromEntries(completed.map(id => [id, 1])),
  }));
  const clock = fakeClock();
  const window = Object.assign(new Events(), clock, {
    location: new URL(page, root),
    localStorage: {
      getItem(key) { return stored.get(key) ?? null; },
      setItem(key, value) { stored.set(key, value); },
      removeItem(key) { stored.delete(key); },
    },
    requestAnimationFrame(callback) { callback(); },
    innerHeight: 600,
    scrollY: 0,
    scrollTo({ top }) { this.scrollY = top; },
  });
  const navigator = { onLine: true };
  if (serviceWorker) navigator.serviceWorker = serviceWorker;
  const sandbox = vm.createContext({ window, document, navigator, URL,
    setTimeout: clock.setTimeout, clearTimeout: clock.clearTimeout });
  vm.runInContext(catalogScript, sandbox, { filename: 'course-catalog.js' });
  if (legacyCatalog) {
    const catalog = window.CourseCatalog;
    window.CourseCatalog = {
      context: catalog.context,
      lessons: () => catalog.lessons().map(({ elective, ...item }) => item),
    };
  }
  const source = serviceWorker ? pwaScript.replace('__PWA_BUILT__', 'true') : pwaScript;
  vm.runInContext(source, sandbox, { filename: 'pwa.js' });
  return { document, window, clock, stored, resumeLink, required, full, toolbar };
}

function fraction(node) {
  return `${node.getAttribute('data-completed')}/${node.getAttribute('data-total')}`;
}

test('first visit starts at the overview and separates required progress from all lessons', () => {
  const { resumeLink, required, full } = openPage();
  assert.equal(resumeLink.href, overview);
  assert.doesNotMatch(resumeLink.textContent, /已完成/);
  assert.equal(fraction(required), '0/89');
  assert.equal(fraction(full), '0/98');
  assert.match(required.textContent, /必修/);
  assert.match(full.textContent, /含选修/);
});

test('default resume skips elective blocks without changing all-lesson toolbar progress', () => {
  const cases = [
    [79, '0098-L85-versioned-graph-state.html'],
    [88, '0107-L93-fastapi-persistent-state.html'],
  ];
  for (const [last, file] of cases) {
    const { resumeLink, required, full, toolbar } = openPage({
      lastVisited: `L${last}`, completed: ids(1, last),
    });
    assert.equal(resumeLink.href, root + 'lessons/' + file);
    assert.equal(fraction(required), last === 79 ? '79/89' : '83/89');
    assert.equal(fraction(full), `${last}/98`);
    assert.equal(fraction(toolbar), `${last}/98`);
  }
});

test('a saved elective visit continues forward on the required route before revisiting earlier gaps', () => {
  const { resumeLink } = openPage({ lastVisited: 'L82' });
  assert.match(resumeLink.href, /-L85-/);
  const fallback = openPage({ lastVisited: 'L82', completed: [...ids(85, 88), ...ids(93, 98)] });
  assert.match(fallback.resumeLink.href, /-L01-/);
});

test('completing all required lessons has its own overview label even with electives unfinished', () => {
  const first = openPage();
  const { resumeLink, required, full } = openPage({
    lastVisited: 'L98', completed: [...ids(1, 79), ...ids(85, 88), ...ids(93, 98)],
  });
  assert.equal(resumeLink.href, overview);
  assert.notEqual(resumeLink.textContent, first.resumeLink.textContent);
  assert.match(resumeLink.textContent, /必修已完成/);
  assert.equal(fraction(required), '89/89');
  assert.equal(fraction(full), '89/98');
});

test('elective completion and legacy visit/reading data keep the v2 storage contract', () => {
  const page = 'lessons/0092-L80-reasoning-effort.html';
  const { document, window, clock, stored, required, full, toolbar } = openPage({ page, legacyState: {
    version: 1, completed: { L01: 1 }, lastVisited: { lessonId: 'L01' },
    reading: { [page]: { anchor: null, offset: 0, ratio: 0.5 } },
  } });
  clock.tick(150);
  assert.equal(window.scrollY, 300);
  assert.equal(stored.has('ai-course:learning:v1'), false);
  const toggle = document.querySelector('[data-lesson-completion="L80"]');
  toggle.dispatch('click');
  assert.equal(toggle.getAttribute('aria-pressed'), 'true');
  assert.equal(fraction(required), '1/89');
  assert.equal(fraction(full), '2/98');
  assert.equal(fraction(toolbar), '2/98');
  const state = JSON.parse(stored.get(stateKey));
  assert.equal(state.version, 2);
  assert.equal(state.lastVisited, 'L80');
  assert.equal(state.reading[page].ratio, 0.5);
  assert.ok(state.completed.L01 && state.completed.L80);
  toggle.dispatch('click');
  assert.equal(fraction(full), '1/98');
  assert.equal(JSON.parse(stored.get(stateKey)).completed.L80, undefined);
});

test('a legacy catalog still resumes without claiming a required-course total', () => {
  const { resumeLink, required, full } = openPage({ legacyCatalog: true,
    lastVisited: 'L79', completed: [...ids(1, 79), 'L82', 'L100'] });
  assert.match(resumeLink.href, /-L80-/);
  assert.equal(required.getAttribute('data-total'), null);
  assert.match(required.textContent, /暂不可用/);
  assert.equal(fraction(full), '80/98');
  const done = openPage({ legacyCatalog: true, lastVisited: 'L98', completed: ids(1, 98) });
  assert.equal(done.resumeLink.href, overview);
  assert.doesNotMatch(done.resumeLink.textContent, /必修已完成/);
});

function workerMock() {
  const sent = [];
  const worker = Object.assign(new Events(), {
    postMessage(data) { sent.push({ ...data }); },
  });
  return { worker, sent };
}

async function connectedPage({ controlled = false, waiting = null } = {}) {
  const { worker, sent } = workerMock();
  const registration = Object.assign(new Events(), { active: worker, waiting });
  const serviceWorker = Object.assign(new Events(), {
    controller: controlled ? worker : null,
    ready: Promise.resolve(registration),
    async register(script, { scope }) {
      assert.equal(script, root + 'service-worker.js');
      assert.equal(scope, '/ai-agent-learning/');
      return registration;
    },
  });
  const page = openPage({ serviceWorker });
  // Drain the register/ready promise chain (no real time or network needed).
  await new Promise(resolve => setImmediate(resolve));
  return { ...page, serviceWorker, registration, worker, sent,
    reply(data, source = worker) {
      serviceWorker.dispatch('message', { source,
        data: { type: 'CACHE_VISITED_PAGE_RESULT', ...data },
      });
    },
  };
}

test('modern acknowledgments correlate individual attempts and stop on permanent rejection', async () => {
  const { sent, reply, clock } = await connectedPage();
  assert.equal(typeof sent[0]?.id, 'string');
  assert.equal(sent[0].url, root);
  reply({ ok: false, id: sent[0].id, retryable: true });
  clock.tick(20_000);
  assert.ok(sent.length >= 2);
  assert.equal(new Set(sent.map(item => item.id)).size, sent.length);

  const stale = sent[0].id;
  const before = sent.length;
  reply({ ok: true, id: stale });
  clock.tick(40_000);
  assert.ok(sent.length > before, 'A late acknowledgment from a previous attempt must not stop retries');

  const latest = sent.at(-1).id;
  const atRejection = sent.length;
  reply({ ok: false, id: latest, retryable: false });
  clock.tick(120_000);
  assert.equal(sent.length, atRejection);
});

for (const oldReply of [null, { ok: false }]) {
  test(`first visit retry budget is finite with ${oldReply ? 'legacy false' : 'no acknowledgment'}`, async () => {
    const { sent, reply, clock } = await connectedPage();
    for (let i = 0; i < 20; i++) {
      if (oldReply) reply(oldReply);
      clock.tick(30_000);
    }
    assert.ok(sent.length > 1 && sent.length <= 5, `Expected a short retry budget, got ${sent.length}`);
    const exhausted = sent.length;
    clock.tick(300_000);
    assert.equal(sent.length, exhausted);
  });
}

test('successful replies stop first-visit retries only for the active request', async () => {
  for (const modern of [false, true]) {
    const { sent, reply, clock } = await connectedPage();
    assert.equal(sent.length, 1);
    const ack = modern ? { ok: true, id: sent[0].id } : { ok: true };
    reply(ack, workerMock().worker);
    clock.tick(25_000);
    assert.equal(sent.length, 2, 'An unrelated worker cannot acknowledge the visit');
    reply(modern ? { ok: true, id: sent[1].id } : ack);
    clock.tick(120_000);
    assert.equal(sent.length, 2);
  }
});

test('controlled pages keep the opt-in waiting-worker update and save before reload', async () => {
  const { worker: waiting, sent: updates } = workerMock();
  const { document, window, stored, serviceWorker, sent } = await connectedPage({ controlled: true, waiting });
  assert.equal(sent.length, 0);
  let reloads = 0;
  window.location.reload = () => { reloads += 1; };
  window.scrollY = 300;
  const update = document.querySelector('[data-pwa-status="update"]').querySelector('.pwa-status-action');
  assert.equal(update.textContent, '刷新更新');
  update.dispatch('click');
  assert.deepEqual(updates, [{ type: 'SKIP_WAITING' }]);
  assert.equal(JSON.parse(stored.get(stateKey)).reading['index.html'].ratio, 0.5);
  assert.equal(reloads, 0);
  serviceWorker.controller = waiting;
  serviceWorker.dispatch('controllerchange');
  assert.equal(reloads, 1);
});
