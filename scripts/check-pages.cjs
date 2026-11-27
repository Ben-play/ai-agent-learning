const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { createHash } = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { after, test } = require('node:test');
const vm = require('node:vm');

const repo = path.resolve(__dirname, '..');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'course-pages-regression-'));
after(() => fs.rmSync(temp, { recursive: true, force: true, maxRetries: 3, retryDelay: 100 }));
const roots = ['/', '/ai-agent-learning/'];
const guides = [
  'code/phase1-python/phase1-practices-capstone',
  'code/phase2-model-selection/phase2-practices-capstone',
  'code/phase4-prompt-context',
  'code/phase5-agent-harness/harness-lab',
  'code/phase6-langgraph-mcp/graph-lab',
  'code/phase6-langgraph-mcp/stdio-lab',
  'code/phase6-langgraph-mcp/http-lab',
  'code/phase7-data-rag/rag-lab',
  'code/phase8-agent-engineering/engineering-lab',
  'code/phase9-advanced-agent/advanced-lab',
  'code/phase10-framework-evolution/evolution-lab',
  'code/phase11-deployment/deployment-lab',
];
const staticPaths = [
  'assets/back-to-top.js', 'assets/bottom-nav.js', 'assets/content-tools.js',
  'assets/course-bar.js', 'assets/course-catalog.js', 'assets/icons/icon-192.png',
  'assets/icons/icon-512.png', 'assets/icons/icon-maskable-512.png', 'assets/lesson-times.json',
  'assets/overview-toggle.js', 'assets/pwa.js', 'assets/quiz.js', 'assets/style.css',
  'assets/theme-toggle.js', 'assets/toc.js', 'manifest.webmanifest',
];
const htmlDirs = ['best-practices', 'lessons', 'qa', 'reference'];
const rootFiles = ['.nojekyll', '404.html', 'index.html', 'offline.html', 'service-worker.js'];
const guidePage = guide => guide + '/README.html';
const srcGuide = guide => guide + '/README.md';
const read = (dir, file) => fs.readFileSync(path.join(dir, file), 'utf8');
const guideLinks = [
  [guides[3], guides[2], 'Phase 4'],
  [guides[10], guides[4], 'Phase 6 图实验'],
  [guides[11], guides[8], 'Phase 8 工程基线'],
];
const hrefs = html => [...html.matchAll(/<a\s+[^>]*\bhref="([^"]+)"[^>]*>([^<]*)<\/a>/g)];

test('Pages upload and deployment use the same attempt-specific artifact name', () => {
  const workflow = read(repo, '.github/workflows/pages.yml');
  const upload = workflow.match(/- name: Upload Pages artifact\n([\s\S]*?)(?=\n      - name:|$)/)?.[1];
  const deploy = workflow.match(/- name: Deploy to GitHub Pages\n([\s\S]*?)(?=\n      - name:|$)/)?.[1];
  assert.ok(upload);
  assert.ok(deploy);
  const name = 'github-pages-${{ github.run_attempt }}';
  assert.ok(upload.split('\n').includes(`          name: ${name}`));
  assert.ok(deploy.split('\n').includes(`          artifact_name: ${name}`));
});

function build(source, name, siteRoot) {
  const output = path.join(temp, name);
  const result = spawnSync(process.env.PYTHON || 'python', ['-I', '-B', '-X', 'utf8',
    path.join(source, 'scripts/build-pages.py'), '--output', output, '--site-root', siteRoot],
  { encoding: 'utf8' });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return output;
}

const stages = new Map();
function stage(siteRoot) {
  if (!stages.has(siteRoot)) stages.set(siteRoot, build(repo, 'site-' + stages.size, siteRoot));
  return stages.get(siteRoot);
}

function inventory(dir, prefix = '') {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap(entry => {
    const file = prefix + entry.name;
    return entry.isDirectory() ? inventory(path.join(dir, entry.name), file + '/') : [file];
  }).sort();
}

function buildDigest(output, files, version) {
  const digest = createHash('sha256');
  function frame(buffer) {
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(buffer.length));
    digest.update(length).update(buffer);
  }
  for (const file of files) {
    frame(Buffer.from(file));
    const bytes = file === 'service-worker.js' ? Buffer.from(read(output, file).replace(
      `var CACHE_VERSION = '${version}';`, "var CACHE_VERSION = '';")) : fs.readFileSync(path.join(output, file));
    frame(bytes);
  }
  return digest.digest('hex');
}

for (const siteRoot of roots) {
  test(`${siteRoot}: worker embeds the exact staged HTML and static inventories before hashing`, () => {
    const output = stage(siteRoot);
    const files = inventory(output);
    const worker = read(output, 'service-worker.js');
    const pages = [...rootFiles.filter(file => file.endsWith('.html')), ...guides.map(guidePage),
      ...htmlDirs.flatMap(dir => fs.readdirSync(path.join(repo, dir))
        .filter(file => file.endsWith('.html')).map(file => dir + '/' + file))].sort();
    assert.deepEqual(files, [...pages, ...staticPaths, '.nojekyll', '.pages-artifact', 'service-worker.js'].sort());
    const embedded = worker.match(/^var PUBLISHED_PATHS = (.+);$/m);
    assert.ok(embedded, 'The artifact should embed its publication paths in the worker');
    assert.deepEqual(JSON.parse(embedded[1]), { pages, static: staticPaths });
    const version = worker.match(/^var CACHE_VERSION = '([a-f0-9]{64})';$/m)?.[1];
    assert.ok(version, 'The worker must be versioned');
    assert.equal(buildDigest(output, files, version), version);
  });

  test(`${siteRoot}: all three public sibling guide links use staged HTML targets`, () => {
    const output = stage(siteRoot);
    for (const [source, target, label] of guideLinks) {
      const anchors = hrefs(read(output, guidePage(source)));
      assert.deepEqual(anchors.filter(([, , text]) => text === label).map(([, href]) => href),
        [siteRoot + guidePage(target)]);
    }
    const evolution = hrefs(read(output, guidePage(guides[10]))).map(([, href]) => href);
    assert.ok(evolution.includes('https://github.com/Ben-play/ai-agent-learning'));
    assert.ok(evolution.includes('../../../lessons/0106-phase10-framework-evolution-outline.html'));
  });
}

test('guide Markdown accepts only the exact approved raw target from the approved source', () => {
  const fixture = path.join(temp, 'guide-fixture');
  const copy = file => {
    const target = path.join(fixture, file);
    fs.mkdirSync(path.dirname(target), { recursive: true });
    fs.copyFileSync(path.join(repo, file), target);
  };
  for (const file of [...rootFiles, ...staticPaths, ...guides.map(srcGuide), 'scripts/build-pages.py',
    ...htmlDirs.flatMap(dir => fs.readdirSync(path.join(repo, dir)).map(file => dir + '/' + file))]) {
    copy(file);
  }
  function append(guide, links) {
    fs.appendFileSync(path.join(fixture, srcGuide(guide)), '\n\n' + links.join('\n\n') + '\n');
  }
  append(guides[3], [
    '[Other public target](../../phase6-langgraph-mcp/graph-lab/README.md)',
    '[Equivalent spelling](../../phase4-prompt-context/./README.md)',
    '[Fragment variation](../../phase4-prompt-context/README.md#intro)',
    '[Unpublished source](../lab.py)',
  ]);
  append(guides[4], ['[Wrong source](../../phase4-prompt-context/README.md)']);
  const output = build(fixture, 'guide-fixture-output', roots[1]);
  const rendered = guide => hrefs(read(output, guidePage(guide))).map(([, , label]) => label);
  assert.ok(rendered(guides[3]).includes('Phase 4'));
  for (const label of ['Other public target', 'Equivalent spelling', 'Fragment variation', 'Unpublished source']) {
    assert.ok(!rendered(guides[3]).includes(label), `${label} must not become a link`);
  }
  assert.ok(!rendered(guides[4]).includes('Wrong source'));
});

function runWorker(output, scope) {
  const handlers = new Map();
  const names = new Map();
  const fetched = [];
  const requestUrl = request => typeof request === 'string' ? request : request.url;
  const caches = {
    async open(name) {
      // Cache Storage may complete after the browser starts reading its response.
      if (downloadOnResponse) await new Promise(resolve => setImmediate(resolve));
      if (!names.has(name)) names.set(name, new Map());
      const records = names.get(name);
      return {
        async put(request, response) { records.set(requestUrl(request), response.clone()); },
        async match(request) { return records.get(requestUrl(request))?.clone(); },
        async delete(request) { return records.delete(requestUrl(request)); },
        async keys() { return [...records.keys()].map(url => new Request(url)); },
      };
    },
    async keys() { return [...names.keys()]; },
    async delete(name) { return names.delete(name); },
  };
  let network = request => responseAt(request.url);
  let downloadOnResponse = false;
  const lifecycle = [];
  const self = {
    registration: { scope, async unregister() { lifecycle.push('unregister'); } },
    clients: { async claim() { lifecycle.push('claim'); } },
    async skipWaiting() { lifecycle.push('skipWaiting'); },
    addEventListener(type, handler) { handlers.set(type, handler); },
  };
  vm.runInNewContext(read(output, 'service-worker.js'), { self, URL, Request, Response, caches,
    setTimeout, clearTimeout, fetch: async request => {
      fetched.push(request.url);
      return network(request);
    },
  }, { filename: 'service-worker.js' });

  async function dispatch(type, props) {
    const deferred = [];
    let reply;
    handlers.get(type)({ ...props,
      waitUntil(promise) { deferred.push(promise); },
      respondWith(promise) { reply = downloadOnResponse ? promise.then(async response => {
        const status = response.status;
        const body = await response.text();
        return new Response(body, { status });
      }) : promise; },
    });
    await Promise.all(deferred);
    return reply && await reply;
  }
  return {
    lifecycle, fetched, caches,
    network(handler) { network = handler; },
    consumeNavigation() { downloadOnResponse = true; },
    async message(data, sourceUrl = scope + 'index.html') {
      const replies = [];
      await dispatch('message', { data, source: { url: sourceUrl,
        postMessage(result) { replies.push({ ...result }); },
      } });
      return replies;
    },
    fetch(url, { mode = 'navigate', destination = 'document', method = 'GET', headers = new Headers() } = {}) {
      return dispatch('fetch', { request: { url, method, mode, destination, headers } });
    },
    install() { return dispatch('install'); },
    activate() { return dispatch('activate'); },
  };
}

function responseAt(url, status = 200, redirected = false) {
  const response = new Response(url, { status });
  Object.defineProperties(response, { url: { value: url }, redirected: { value: redirected } });
  return response;
}

const visit = (url, id) => ({ type: 'CACHE_VISITED_PAGE', url, id });
const offline = () => { throw new Error('Fake network unavailable'); };
const example = 'https://example.test';
const unpublished = [
  'lessons/not-published.html', 'qa/not-published.html', 'assets/not-published.js',
  'assets/course-catalog.JS', 'assets/nested/style.css', 'code/README.md',
  'code/phase1-python/phase1-practices-capstone/README.md',
  'code/phase1-python/phase1-practices-capstone/main.py',
  'code/phase8-agent-engineering/engineering-lab/README.html.bak',
  'lessons/%30%30%30%31-ai-agent-learning-path-overview.html',
  'service-worker.js', 'service-worker.html', '.pages-artifact', '.nojekyll',
  '__pwa_active_version__', '__pwa_version_created__/123',
];

for (const siteRoot of roots) {
  const scope = example + siteRoot;
  const page = scope + guidePage(guides[8]);
  const asset = scope + 'assets/lesson-times.json';
  const aliases = [scope, scope + 'index.html'];
  if (siteRoot !== '/') aliases.push(scope.slice(0, -1));

  test(`${siteRoot}: explicit first visits accept public guides and normalize home to one offline key`, async () => {
    const worker = runWorker(stage(siteRoot), scope);
    for (const [index, alias] of aliases.entries()) {
      const [reply] = await worker.message(visit(alias + '?source=home#top', `home-${index}`), alias);
      assert.equal(reply?.ok, true);
      assert.equal(reply.id, `home-${index}`);
    }
    assert.deepEqual(worker.fetched, aliases.map(() => scope + 'index.html'));
    assert.deepEqual(await worker.message({ type: 'CACHE_VISITED_PAGE', url: page }),
      [{ type: 'CACHE_VISITED_PAGE_RESULT', ok: true }]);
    worker.network(offline);
    assert.equal(await (await worker.fetch(scope + '?a=1')).text(), scope + 'index.html');
    assert.equal(await (await worker.fetch(scope + 'index.html#a')).text(), scope + 'index.html');
    assert.equal(await (await worker.fetch(page + '?view=1')).text(), page);
  });

  test(`${siteRoot}: worker excludes unpublished/reserved destinations and separates fetching by kind`, async () => {
    const worker = runWorker(stage(siteRoot), scope);
    for (const relative of unpublished) {
      const url = scope + relative;
      assert.equal(await worker.fetch(url), undefined, relative);
      assert.equal(await worker.fetch(url, { mode: 'cors', destination: 'script' }), undefined, relative);
      const [reply] = await worker.message(visit(url, relative));
      assert.deepEqual(reply, { type: 'CACHE_VISITED_PAGE_RESULT', ok: false, id: relative, retryable: false });
    }
    assert.equal(await worker.fetch(asset), undefined);
    assert.deepEqual(await worker.message(visit(asset, 'asset')),
      [{ type: 'CACHE_VISITED_PAGE_RESULT', ok: false, id: 'asset', retryable: false }]);
    assert.equal(await worker.fetch(page, { mode: 'cors', destination: 'script' }), undefined);
    assert.deepEqual(worker.fetched, []);
    assert.equal(await (await worker.fetch(asset + '?theme=light', { mode: 'cors', destination: '' })).text(),
      asset + '?theme=light');
    worker.consumeNavigation();
    assert.equal(await (await worker.fetch(page)).text(), page);
    worker.network(offline);
    assert.equal(await (await worker.fetch(asset + '?theme=light', { mode: 'cors', destination: '' })).text(),
      asset + '?theme=light');
    assert.equal(await (await worker.fetch(page)).text(), page);
  });
}

test('unpublished, static and out-of-scope sources cannot request caching or activate a waiting worker', async () => {
  const scope = example + roots[1];
  const worker = runWorker(stage(roots[1]), scope);
  const denied = [scope + 'assets/pwa.js', scope + 'lessons/not-published.html', scope + '__pwa_active_version__',
    example + '/index.html', example + '/ai-agent-learning-copy/index.html',
    'https://unrelated.test/ai-agent-learning/index.html'];
  for (const source of denied) {
    assert.deepEqual(await worker.message(visit(scope, 'invalid-source'), source), []);
    await worker.message({ type: 'SKIP_WAITING' }, source);
  }
  assert.deepEqual(worker.lifecycle, []);
  assert.deepEqual(worker.fetched, []);
  await worker.message({ type: 'SKIP_WAITING' }, scope + guidePage(guides[4]));
  assert.deepEqual(worker.lifecycle, ['skipWaiting']);
});

test('explicit cache replies distinguish transient failures, rejections and legacy messages', async () => {
  const scope = example + roots[1];
  const worker = runWorker(stage(roots[1]), scope);
  const page = scope + guidePage(guides[8]);
  const reply = (ok, extra) => [{ type: 'CACHE_VISITED_PAGE_RESULT', ok, ...extra }];
  for (const status of [404, 410, 429, 503]) {
    worker.network(() => responseAt(page, status));
    assert.deepEqual(await worker.message(visit(page, String(status))),
      reply(false, { id: String(status), retryable: status >= 429 }));
  }
  worker.network(offline);
  assert.deepEqual(await worker.message(visit(page, 'offline')), reply(false, { id: 'offline', retryable: true }));
  assert.deepEqual(await worker.message({ type: 'CACHE_VISITED_PAGE', url: page }), reply(false));

  const rejected = [scope + 'assets/style.css', scope + 'lessons/not-published.html',
    'https://unrelated.test/ai-agent-learning/index.html'];
  for (const url of rejected) {
    worker.network(() => responseAt(url));
    assert.deepEqual(await worker.message(visit(page, 'wrong-response')),
      reply(false, { id: 'wrong-response', retryable: false }));
  }
  worker.network(() => responseAt(page, 200, true));
  assert.deepEqual(await worker.message(visit(page, 'redirected')), reply(false, { id: 'redirected', retryable: false }));
  worker.network(request => {
    if (request.redirect === 'error') throw new TypeError('Fetch rejects an HTTP redirect');
    assert.equal(request.redirect, 'manual');
    return { status: 0, ok: false, type: 'opaqueredirect' };
  });
  assert.deepEqual(await worker.message(visit(page, 'redirect-status')),
    reply(false, { id: 'redirect-status', retryable: false }));
  worker.network(() => responseAt(page));
  assert.deepEqual(await worker.message(visit(page, 'index')), reply(true, { id: 'index' }));
});

test('bad response destinations never become offline hits for page or static requests', async () => {
  const scope = example + roots[1];
  const worker = runWorker(stage(roots[1]), scope);
  const page = scope + guidePage(guides[8]);
  const asset = scope + 'assets/style.css';
  const style = { mode: 'cors', destination: 'style' };
  worker.network(() => responseAt(asset));
  assert.equal(await (await worker.fetch(page)).text(), asset);
  worker.network(() => responseAt(page));
  assert.equal(await (await worker.fetch(asset, style)).text(), page);
  worker.network(offline);
  assert.equal((await worker.fetch(page)).status, 503);
  assert.equal((await worker.fetch(asset, style)).type, 'error');
});

test('migration revalidates published pages only; root retirement never takes over GitHub traffic', async () => {
  const scope = example + roots[1];
  const worker = runWorker(stage(roots[1]), scope);
  const guide = scope + guidePage(guides[8]);
  const guideWithBadResponse = scope + guidePage(guides[7]);
  const old = await worker.caches.open(`ai-agent-learning:${encodeURIComponent(scope)}:pages-old`);
  const retired = [...unpublished, 'assets/style.css'].map(file => scope + file);
  for (const url of [guide + '?x=1', guideWithBadResponse, scope + '?source=legacy', ...retired]) {
    await old.put(url, responseAt(url));
  }
  worker.network(request => responseAt(request.url === guideWithBadResponse ? scope + 'assets/style.css' : request.url));
  await worker.install();
  await worker.activate();
  assert.ok(worker.fetched.includes(guide));
  assert.ok(worker.fetched.includes(guideWithBadResponse));
  assert.equal(worker.fetched.filter(url => url === scope + 'index.html').length, 2, 'Shell and migration use the same canonical home URL');
  const allowedStatic = staticPaths.map(file => scope + file);
  assert.deepEqual(worker.fetched.filter(url => retired.includes(url) && !allowedStatic.includes(url)), []);
  assert.equal(worker.fetched.filter(url => url === scope + 'assets/style.css').length, 1);
  assert.ok(!worker.fetched.some(url => url.includes('?')));
  assert.deepEqual(worker.lifecycle, ['claim']);
  worker.network(offline);
  assert.equal(await (await worker.fetch(guide)).text(), guide);
  assert.equal(await (await worker.fetch(guideWithBadResponse)).text(), scope + 'offline.html');
  assert.equal(await (await worker.fetch(scope)).text(), scope + 'index.html');

  const githubRoot = 'https://example.github.io/';
  const retiredRoot = runWorker(stage('/'), githubRoot);
  const siblingCache = `ai-agent-learning:${encodeURIComponent(githubRoot + 'sibling/')}:pages-other`;
  await retiredRoot.caches.open(siblingCache);
  await retiredRoot.caches.open(`ai-agent-learning:${encodeURIComponent(githubRoot)}:pages-old`);
  await retiredRoot.install();
  await retiredRoot.activate();
  assert.deepEqual(await retiredRoot.caches.keys(), [siblingCache]);
  assert.equal(await retiredRoot.fetch(githubRoot), undefined);
  assert.deepEqual(await retiredRoot.message(visit(githubRoot, 'retired'), githubRoot), []);
  assert.deepEqual(retiredRoot.lifecycle, ['skipWaiting', 'unregister']);
  assert.deepEqual(retiredRoot.fetched, []);
});
