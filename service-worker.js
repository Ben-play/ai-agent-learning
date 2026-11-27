/* AI Agent 学习路径：scope 隔离、内容版本化的离线缓存 */
'use strict';

/* 构建器注入精确发布清单，再计算完整产物的内容摘要。 */
var CACHE_VERSION = '__BUILD_VERSION__';
var PUBLISHED_PATHS = '__PUBLISHED_PATHS__';
var SCOPE_URL = new URL(self.registration.scope);
var SCOPE_KEY = encodeURIComponent(SCOPE_URL.href);
/* github.io 根 scope 会接管同源所有 Project Pages；仅在该共享宿主上清理并注销。 */
var RETIRE_ROOT_SCOPE = SCOPE_URL.pathname === '/' && /(?:^|\.)github\.io$/i.test(SCOPE_URL.hostname);
var CACHE_PREFIX = 'ai-agent-learning:' + SCOPE_KEY + ':';
var META_CACHE = CACHE_PREFIX + 'meta';
var SHELL_CACHE = CACHE_PREFIX + 'shell-' + CACHE_VERSION;
var PAGES_CACHE = CACHE_PREFIX + 'pages-' + CACHE_VERSION;
var STATIC_CACHE = CACHE_PREFIX + 'static-' + CACHE_VERSION;
var ACTIVE_VERSION_URL = new URL('./__pwa_active_version__', SCOPE_URL).href;
var VERSION_CREATED_PREFIX = new URL('./__pwa_version_created__/', SCOPE_URL).href;
var NETWORK_TIMEOUT_MS = 15000;
var ORPHAN_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;

/* 迁移清理：旧实现曾以 32 位 FNV 指纹作为缓存命名空间。 */
function legacyScopeFingerprint(value) {
  var hash = 2166136261;
  for (var i = 0; i < value.length; i += 1) {
    hash ^= value.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}
var LEGACY_CACHE_PREFIX = 'ai-agent-learning-' + legacyScopeFingerprint(SCOPE_URL.href) + '-';

var SHELL_ASSETS = ['index.html', '404.html', 'offline.html'];
var STATIC_ASSETS = PUBLISHED_PATHS.static || [];
var PAGE_PATHS = new Set((PUBLISHED_PATHS.pages || []).map(scopedPath));
var STATIC_PATHS = new Set(STATIC_ASSETS.map(scopedPath));
var HOME_PATH = scopedPath('index.html');

function scopedPath(path) {
  return SCOPE_URL.pathname + path.split('/').map(encodeURIComponent).join('/');
}

function scopedUrl(path) {
  return new URL(scopedPath(path), SCOPE_URL).href;
}

function publishedUrl(value, kind, base) {
  var url;
  try { url = new URL(value, base); } catch (error) { return null; }
  if (url.origin !== SCOPE_URL.origin || url.username || url.password) return null;
  if (kind === 'page') {
    if (url.pathname === SCOPE_URL.pathname || url.pathname === SCOPE_URL.pathname.slice(0, -1)) {
      url.pathname = HOME_PATH;
    }
    /* 本站 HTML 不以 query 选择内容；移除追踪参数，避免无限缓存副本。 */
    url.search = '';
  }
  url.hash = '';
  return (kind === 'page' ? PAGE_PATHS : STATIC_PATHS).has(url.pathname) ? url : null;
}

function isPublishedResponse(response, kind) {
  return Boolean(response && response.ok && !response.redirected && response.type !== 'opaqueredirect' &&
    publishedUrl(response.url, kind));
}

function isPageRequest(request) {
  return request.mode === 'navigate' || request.destination === 'document';
}

async function storeResponse(cacheName, key, response) {
  try {
    /* 导航可能先读走原始响应流，必须在等待 Cache Storage 前复制。 */
    var copy = response.clone();
    await (await caches.open(cacheName)).put(key, copy);
    return true;
  } catch (error) {
    return false;
  }
}

function settleWithin(promise, timeoutMs) {
  return new Promise(function (resolve, reject) {
    var timer = setTimeout(function () {
      reject(new Error('Network timeout'));
    }, timeoutMs);
    promise.then(function (value) {
      clearTimeout(timer);
      resolve(value);
    }, function (error) {
      clearTimeout(timer);
      reject(error);
    });
  });
}

async function matchFrom(cacheName, request) {
  try {
    return await (await caches.open(cacheName)).match(request);
  } catch (error) {
    return undefined;
  }
}

async function pageFallback(key) {
  var cached = await matchFrom(PAGES_CACHE, key);
  if (cached) return cached;
  if (new URL(key.url).pathname === HOME_PATH) {
    cached = await matchFrom(SHELL_CACHE, scopedUrl('index.html'));
    if (cached) return cached;
  }
  return undefined;
}

async function offlineFallback() {
  return matchFrom(SHELL_CACHE, scopedUrl('offline.html'));
}

function networkFirstPage(request, event, url) {
  var key = new Request(url.href, { credentials: 'same-origin' });
  var network = settleWithin(fetch(request), NETWORK_TIMEOUT_MS);

  event.waitUntil(network.then(function (response) {
    if (response.status === 404 || response.status === 410) {
      return caches.open(PAGES_CACHE).then(function (cache) { return cache.delete(key); });
    }
    return isPublishedResponse(response, 'page') ? storeResponse(PAGES_CACHE, key, response) : false;
  }).catch(function () { return false; }));

  return network.then(async function (response) {
    if (response.status >= 500) return (await pageFallback(key)) || response;
    return response;
  }).catch(async function () {
    return (await pageFallback(key)) || (await offlineFallback()) || new Response('Offline', {
      status: 503,
      headers: { 'Content-Type': 'text/plain; charset=utf-8' }
    });
  });
}

function networkFirstStatic(request, event, url) {
  var key = new Request(url.href, { credentials: 'same-origin' });
  var network = settleWithin(fetch(request), NETWORK_TIMEOUT_MS);
  event.waitUntil(network.then(function (response) {
    return isPublishedResponse(response, 'static') ? storeResponse(STATIC_CACHE, key, response) : false;
  }).catch(function () { return false; }));
  return network.then(async function (response) {
    if (response.status >= 500) return (await matchFrom(STATIC_CACHE, key)) || response;
    return response;
  }).catch(async function () {
    return (await matchFrom(STATIC_CACHE, key)) || Response.error();
  });
}

async function precache(cacheName, paths, kind) {
  var cache = await caches.open(cacheName);
  await Promise.all(paths.map(async function (path) {
    var request = new Request(scopedUrl(path), {
      credentials: 'same-origin',
      redirect: 'error',
      cache: 'reload'
    });
    var response = await fetch(request);
    if (!isPublishedResponse(response, kind)) {
      throw new Error('Required offline asset is not cacheable: ' + request.url);
    }
    await cache.put(request, response);
  }));
}

async function previousPageCacheNames() {
  var names = await caches.keys();
  return names.filter(function (name) {
    return (name === CACHE_PREFIX + 'pages' ||
      name.startsWith(CACHE_PREFIX + 'pages-') ||
      name === LEGACY_CACHE_PREFIX + 'pages' ||
      name.startsWith(LEGACY_CACHE_PREFIX + 'pages-')) && name !== PAGES_CACHE;
  }).sort(function (left, right) {
    return right.localeCompare(left);
  });
}

async function visitedPageCandidates() {
  var names = await previousPageCacheNames();
  var candidates = new Set();
  for (var n = 0; n < names.length; n += 1) {
    var source = await caches.open(names[n]);
    var requests = await source.keys();
    for (var i = 0; i < requests.length; i += 1) {
      var pageUrl = publishedUrl(requests[i].url, 'page');
      if (pageUrl) candidates.add(pageUrl.href);
    }
  }
  return candidates;
}

async function migrateVisitedPages() {
  var destination = await caches.open(PAGES_CACHE);
  var candidates = await visitedPageCandidates();
  await Promise.all(Array.from(candidates, async function (url) {
    try {
      var request = new Request(url, {
        credentials: 'same-origin',
        redirect: 'error',
        cache: 'reload'
      });
      var response = await settleWithin(fetch(request), NETWORK_TIMEOUT_MS);
      if (isPublishedResponse(response, 'page')) await destination.put(request, response);
    } catch (error) {
      /* 未能重新验证的旧页面不带入新发布版本。 */
    }
  }));
}

async function writeVersionCreated() {
  try {
    await (await caches.open(META_CACHE)).put(
      VERSION_CREATED_PREFIX + CACHE_VERSION,
      new Response(String(Date.now()), { headers: { 'Content-Type': 'text/plain' } })
    );
  } catch (error) {
    /* 创建时间仅用于回收孤立 waiting 缓存。 */
  }
}

async function readVersionCreated(version) {
  try {
    var response = await (await caches.open(META_CACHE)).match(VERSION_CREATED_PREFIX + version);
    return response ? Number(await response.text()) : 0;
  } catch (error) {
    return 0;
  }
}

async function deleteVersionCreated(version) {
  try {
    await (await caches.open(META_CACHE)).delete(VERSION_CREATED_PREFIX + version);
  } catch (error) {
    /* best effort */
  }
}

async function readActiveVersion() {
  try {
    var response = await (await caches.open(META_CACHE)).match(ACTIVE_VERSION_URL);
    return response ? await response.text() : null;
  } catch (error) {
    return null;
  }
}

async function writeActiveVersion() {
  await (await caches.open(META_CACHE)).put(
    ACTIVE_VERSION_URL,
    new Response(CACHE_VERSION, { headers: { 'Content-Type': 'text/plain' } })
  );
}

function versionCacheNames(version) {
  return [
    CACHE_PREFIX + 'shell-' + version,
    CACHE_PREFIX + 'pages-' + version,
    CACHE_PREFIX + 'static-' + version
  ];
}

function cacheVersion(name) {
  var kinds = ['shell-', 'pages-', 'static-'];
  for (var i = 0; i < kinds.length; i += 1) {
    var prefix = CACHE_PREFIX + kinds[i];
    if (name.startsWith(prefix)) return name.slice(prefix.length);
  }
  return null;
}

async function knownVersions() {
  var names = await caches.keys();
  var versions = [];
  names.forEach(function (name) {
    var version = cacheVersion(name);
    if (version && versions.indexOf(version) === -1) versions.push(version);
  });
  return versions;
}

async function deleteVersion(version) {
  await Promise.all(versionCacheNames(version).map(function (name) {
    return caches.delete(name);
  }));
  await deleteVersionCreated(version);
}

async function cleanSupersededWaitingCaches() {
  var activeVersion = await readActiveVersion();
  var versions = await knownVersions();
  var now = Date.now();
  await Promise.all(versions.map(async function (version) {
    if (version === CACHE_VERSION || version === activeVersion) return;
    var createdAt = await readVersionCreated(version);
    /* 无元数据的版本来自旧实现；它们不可能是当前 waiting Worker。 */
    if (!createdAt || now - createdAt > ORPHAN_MAX_AGE_MS) await deleteVersion(version);
  }));
}

async function cleanActivatedCaches() {
  var activatedAt = await readVersionCreated(CACHE_VERSION);
  var versions;
  /* 再迁移一次，覆盖 install 快照后、activate 前由旧 Worker 新缓存的页面。 */
  await migrateVisitedPages();
  versions = await knownVersions();
  await Promise.all(versions.map(async function (version) {
    if (version === CACHE_VERSION) return;
    var createdAt = await readVersionCreated(version);
    /* 保留更晚开始安装的版本，避免旧 waiting Worker 激活时删掉新安装缓存。 */
    if (!createdAt || !activatedAt || createdAt <= activatedAt) await deleteVersion(version);
  }));
  var names = await caches.keys();
  await Promise.all(names.map(function (name) {
    return name === CACHE_PREFIX + 'pages' || name.startsWith(LEGACY_CACHE_PREFIX)
      ? caches.delete(name)
      : false;
  }));
}

self.addEventListener('install', function (event) {
  if (RETIRE_ROOT_SCOPE) {
    event.waitUntil(self.skipWaiting());
    return;
  }
  event.waitUntil(writeVersionCreated().then(function () {
    return Promise.all([
      precache(SHELL_CACHE, SHELL_ASSETS, 'page'),
      precache(STATIC_CACHE, STATIC_ASSETS, 'static'),
      migrateVisitedPages()
    ]);
  }).then(function () {
    return cleanSupersededWaitingCaches();
  }).catch(async function (error) {
    await Promise.all([
      caches.delete(SHELL_CACHE),
      caches.delete(STATIC_CACHE),
      caches.delete(PAGES_CACHE),
      deleteVersionCreated(CACHE_VERSION)
    ]);
    throw error;
  }));
});

self.addEventListener('activate', function (event) {
  if (RETIRE_ROOT_SCOPE) {
    event.waitUntil(
      caches.keys()
        .then(function (names) {
          return Promise.all(names.map(function (name) {
            return name.startsWith(CACHE_PREFIX) || name.startsWith(LEGACY_CACHE_PREFIX)
              ? caches.delete(name)
              : false;
          }));
        })
        .then(function () { return self.registration.unregister(); })
    );
    return;
  }
  event.waitUntil(
    writeActiveVersion()
      .then(cleanActivatedCaches)
      .then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (event) {
  var request = event.request;
  if (RETIRE_ROOT_SCOPE || request.method !== 'GET') return;
  var page = isPageRequest(request);
  var url = publishedUrl(request.url, page ? 'page' : 'static');
  if (!url) return;
  event.respondWith(page ? networkFirstPage(request, event, url) : networkFirstStatic(request, event, url));
});

function sourceIsCourseClient(event) {
  return event.source && typeof event.source.url === 'string' && publishedUrl(event.source.url, 'page');
}

function replyToVisit(event, ok, retryable) {
  if (typeof event.source.postMessage !== 'function') return;
  var reply = { type: 'CACHE_VISITED_PAGE_RESULT', ok: ok };
  var id = event.data.id;
  if (typeof id === 'string' && id.length > 0 && id.length <= 128) {
    reply.id = id;
    if (!ok) reply.retryable = retryable;
  }
  event.source.postMessage(reply);
}

async function cacheVisitedPage(event, url) {
  var request = new Request(url.href, {
    credentials: 'same-origin',
    redirect: 'manual', // 不跟随重定向，且能把重定向与临时网络失败区分开。
    cache: 'reload'
  });
  var response;
  try {
    response = await settleWithin(fetch(request), NETWORK_TIMEOUT_MS);
  } catch (error) {
    replyToVisit(event, false, true);
    return;
  }
  if (!isPublishedResponse(response, 'page')) {
    var status = response.status;
    replyToVisit(event, false, status === 408 || status === 429 || status >= 500);
    return;
  }
  var ok = await storeResponse(PAGES_CACHE, request, response);
  replyToVisit(event, ok, !ok);
}

self.addEventListener('message', function (event) {
  var data = event.data;
  if (RETIRE_ROOT_SCOPE || !data || typeof data !== 'object' || !sourceIsCourseClient(event)) return;

  if (data.type === 'SKIP_WAITING') {
    event.waitUntil(self.skipWaiting());
    return;
  }
  if (data.type !== 'CACHE_VISITED_PAGE') return;

  var pageUrl = typeof data.url === 'string' && data.url.length > 0 && data.url.length <= 2048 &&
    publishedUrl(data.url, 'page', SCOPE_URL);
  if (!pageUrl) {
    replyToVisit(event, false, false);
    return;
  }
  event.waitUntil(cacheVisitedPage(event, pageUrl));
});
