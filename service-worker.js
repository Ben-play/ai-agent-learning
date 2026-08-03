/* AI Agent 学习路径：scope 隔离、内容版本化的离线缓存 */
'use strict';

/* 构建器会把占位符替换为完整发布产物的内容摘要。 */
var CACHE_VERSION = '__BUILD_VERSION__';
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

var SHELL_ASSETS = [
  './index.html',
  './404.html',
  './offline.html'
];

var STATIC_ASSETS = [
  './manifest.webmanifest',
  './assets/style.css',
  './assets/course-catalog.js',
  './assets/content-tools.js',
  './assets/bottom-nav.js',
  './assets/theme-toggle.js',
  './assets/back-to-top.js',
  './assets/course-bar.js',
  './assets/quiz.js',
  './assets/toc.js',
  './assets/overview-toggle.js',
  './assets/pwa.js',
  './assets/icons/icon-192.png',
  './assets/icons/icon-512.png',
  './assets/icons/icon-maskable-512.png'
];

function scopedUrl(path) {
  return new URL(path, SCOPE_URL).href;
}

function isWithinScope(url) {
  var scopePath = SCOPE_URL.pathname;
  return url.origin === SCOPE_URL.origin &&
    (url.pathname === scopePath.slice(0, -1) || url.pathname.startsWith(scopePath));
}

function isCoursePath(url) {
  var relative;
  if (!isWithinScope(url)) return false;
  relative = url.pathname.slice(SCOPE_URL.pathname.length);
  if (!relative && url.pathname === SCOPE_URL.pathname.slice(0, -1)) relative = '';
  return relative === '' ||
    /^(?:index|404|offline|service-worker)\.html$/.test(relative) ||
    relative === 'manifest.webmanifest' ||
    relative.startsWith('assets/') ||
    relative.startsWith('lessons/') ||
    relative.startsWith('qa/') ||
    relative.startsWith('reference/') ||
    relative.startsWith('best-practices/') ||
    relative.startsWith('code/phase1-python/phase1-practices-capstone/') ||
    relative.startsWith('code/phase2-model-selection/phase2-practices-capstone/');
}

function isCacheableResponse(response) {
  return Boolean(response && response.ok && !response.redirected && response.type !== 'opaqueredirect');
}

function isPageRequest(request) {
  return request.mode === 'navigate' || request.destination === 'document';
}

function isStaticRequest(request, url) {
  if (['style', 'script', 'image', 'font'].indexOf(request.destination) !== -1) return true;
  return /\.(?:css|js|mjs|png|jpe?g|gif|webp|svg|ico|woff2?|ttf|otf|json|webmanifest)$/i.test(url.pathname);
}

function pageCacheKey(request) {
  var url = new URL(request.url);
  url.hash = '';
  /* 本站 HTML 不以 query 选择内容；移除追踪参数，避免无限缓存副本。 */
  url.search = '';
  if (url.pathname === SCOPE_URL.pathname || url.pathname === SCOPE_URL.pathname.slice(0, -1)) {
    url = new URL('./index.html', SCOPE_URL);
  }
  return new Request(url.href, { credentials: 'same-origin' });
}

function staticCacheKey(request) {
  var url = new URL(request.url);
  url.hash = '';
  return new Request(url.href, { credentials: 'same-origin' });
}

async function cacheResponse(cacheName, request, response) {
  var copy;
  if (!isCacheableResponse(response)) return false;
  try {
    var requestUrl = new URL(request.url);
    var responseUrl = new URL(response.url);
    if (!isCoursePath(requestUrl) || !isCoursePath(responseUrl)) return false;
    copy = response.clone();
    await (await caches.open(cacheName)).put(request, copy);
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
  if (new URL(key.url).pathname === new URL('./index.html', SCOPE_URL).pathname) {
    cached = await matchFrom(SHELL_CACHE, scopedUrl('./index.html'));
    if (cached) return cached;
  }
  return undefined;
}

async function offlineFallback() {
  return matchFrom(SHELL_CACHE, scopedUrl('./offline.html'));
}

function networkFirstPage(request, event) {
  var key = pageCacheKey(request);
  var network = settleWithin(fetch(request), NETWORK_TIMEOUT_MS);

  event.waitUntil(network.then(function (response) {
    if (response.status === 404 || response.status === 410) {
      return caches.open(PAGES_CACHE).then(function (cache) { return cache.delete(key); });
    }
    return isCacheableResponse(response) ? cacheResponse(PAGES_CACHE, key, response) : false;
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

function networkFirstStatic(request, event) {
  var key = staticCacheKey(request);
  var network = settleWithin(fetch(request), NETWORK_TIMEOUT_MS);
  event.waitUntil(network.then(function (response) {
    return isCacheableResponse(response) ? cacheResponse(STATIC_CACHE, key, response) : false;
  }).catch(function () { return false; }));
  return network.then(async function (response) {
    if (response.status >= 500) return (await matchFrom(STATIC_CACHE, key)) || response;
    return response;
  }).catch(async function () {
    return (await matchFrom(STATIC_CACHE, key)) || Response.error();
  });
}

async function precache(cacheName, paths) {
  var cache = await caches.open(cacheName);
  await Promise.all(paths.map(async function (path) {
    var request = new Request(scopedUrl(path), {
      credentials: 'same-origin',
      redirect: 'error',
      cache: 'reload'
    });
    var response = await fetch(request);
    var responseUrl = new URL(response.url);
    if (!isCacheableResponse(response) || !isCoursePath(responseUrl)) {
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
  var candidates = Object.create(null);
  for (var n = 0; n < names.length; n += 1) {
    var source = await caches.open(names[n]);
    var requests = await source.keys();
    for (var i = 0; i < requests.length; i += 1) {
      var key = pageCacheKey(requests[i]);
      if (!isCoursePath(new URL(key.url))) continue;
      candidates[key.url] = key;
    }
  }
  return candidates;
}

async function migrateVisitedPages() {
  var destination = await caches.open(PAGES_CACHE);
  var candidates = await visitedPageCandidates();
  await Promise.all(Object.keys(candidates).map(async function (url) {
    var pageKey = candidates[url];
    try {
      var response = await settleWithin(fetch(new Request(pageKey.url, {
        credentials: 'same-origin',
        redirect: 'error',
        cache: 'reload'
      })), NETWORK_TIMEOUT_MS);
      if (isCacheableResponse(response) && isCoursePath(new URL(response.url))) {
        await destination.put(pageKey, response);
      }
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
      precache(SHELL_CACHE, SHELL_ASSETS),
      precache(STATIC_CACHE, STATIC_ASSETS),
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
  if (request.method !== 'GET') return;

  var url;
  try {
    url = new URL(request.url);
  } catch (error) {
    return;
  }
  if (!isCoursePath(url)) return;

  if (isPageRequest(request)) {
    event.respondWith(networkFirstPage(request, event));
    return;
  }
  if (isStaticRequest(request, url)) {
    event.respondWith(networkFirstStatic(request, event));
  }
});

function sourceIsCourseClient(event) {
  if (!event.source || typeof event.source.url !== 'string') return false;
  try {
    return isCoursePath(new URL(event.source.url));
  } catch (error) {
    return false;
  }
}

self.addEventListener('message', function (event) {
  var data = event.data;
  if (!sourceIsCourseClient(event)) return;

  if (data && typeof data === 'object' && data.type === 'SKIP_WAITING') {
    event.waitUntil(self.skipWaiting());
    return;
  }

  if (!data || typeof data !== 'object' || data.type !== 'CACHE_VISITED_PAGE') return;
  if (typeof data.url !== 'string' || data.url.length === 0 || data.url.length > 2048) return;

  var pageUrl;
  try {
    pageUrl = new URL(data.url, SCOPE_URL);
  } catch (error) {
    return;
  }
  pageUrl.hash = '';
  pageUrl.search = '';
  if (!isCoursePath(pageUrl) || pageUrl.username || pageUrl.password) return;
  if (!/\.(?:html?|md|markdown)$/i.test(pageUrl.pathname)) return;

  var request = new Request(pageUrl.href, {
    method: 'GET',
    credentials: 'same-origin',
    redirect: 'error',
    cache: 'reload'
  });
  event.waitUntil(
    fetch(request)
      .then(function (response) { return cacheResponse(PAGES_CACHE, request, response); })
      .catch(function () { return false; })
      .then(function (ok) {
        if (event.source && typeof event.source.postMessage === 'function') {
          event.source.postMessage({ type: 'CACHE_VISITED_PAGE_RESULT', ok: ok === true });
        }
      })
  );
});
