/**
 * 课程 PWA 与共享学习状态
 * - 根级 Service Worker 注册、已访问页面缓存消息与用户可控更新
 * - L01–L38 手动完成度、继续学习、多标签同步
 * - 标题锚点 + 相对偏移 + 比例后备的阅读位置保存与恢复
 * - 所有能力均为渐进增强；存储、目录或 Worker 不可用时不阻断正文
 */
(function () {
  'use strict';

  if (window.__aiCoursePwaV1Initialized) return;
  window.__aiCoursePwaV1Initialized = true;

  var BUILT_SITE = '__PWA_BUILT__' === 'true';
  var STATE_VERSION = 2;
  var TOP_THRESHOLD = 120;
  var SAVE_DELAY = 700;
  var CATALOG_RETRIES = 100;
  var script = document.currentScript;
  var scriptUrl = script && script.src;
  var siteRoot = null;
  try { siteRoot = scriptUrl ? new URL('../', scriptUrl) : null; } catch (error) { /* 特殊 URL 降级。 */ }
  var appScopePath = siteRoot ? siteRoot.pathname : null;
  var storageScope = siteRoot ? encodeURIComponent(siteRoot.pathname) : 'local';
  var STORAGE_KEY = 'ai-course:learning:v2:' + storageScope;
  var SCOPED_LEGACY_STORAGE_KEY = 'ai-course:learning:v1:' + storageScope;
  var UNSCOPED_LEGACY_STORAGE_KEY = 'ai-course:learning:v1';
  var currentPath = siteRelativePath(window.location.href);
  var state;
  var catalog = null;
  var lessons = [];
  var context = null;
  var visitRecorded = false;
  var saveTimer = null;
  var restoring = false;
  var statusRegion = null;
  var waitingWorker = null;
  var registration = null;
  var refreshRequested = false;
  var reloadTriggered = false;
  var updateRecoveryTimer = null;
  var hadController = !!(navigator.serviceWorker && navigator.serviceWorker.controller);
  var initiallyControlled = hadController;
  var cacheVisitPending = false;
  var cacheVisitTimer = null;

  function installManifestLink() {
    if (!BUILT_SITE || !siteRoot || window.location.protocol === 'file:' ||
        document.querySelector('link[rel="manifest"]')) return;
    var link = document.createElement('link');
    link.rel = 'manifest';
    link.href = new URL('manifest.webmanifest', siteRoot).href;
    document.head.appendChild(link);
  }

  installManifestLink();

  function blankState() {
    return {
      version: STATE_VERSION,
      completed: {},
      completionUpdated: {},
      lastVisited: null,
      lastVisitedAt: 0,
      reading: {},
      readingUpdated: {}
    };
  }

  function isObject(value) {
    return !!value && typeof value === 'object' && !Array.isArray(value);
  }

  function isLessonId(value) {
    return /^L\d{2,3}$/.test(String(value || ''));
  }

  function finiteNumber(value) {
    return typeof value === 'number' && isFinite(value);
  }

  function timestamp(value) {
    var parsed;
    if (finiteNumber(value) && value > 0) return value;
    if (typeof value === 'string') {
      parsed = Date.parse(value);
      if (isFinite(parsed) && parsed > 0) return parsed;
    }
    return null;
  }

  function nextRevision(previous) {
    return Math.max(Date.now(), (finiteNumber(previous) ? previous : 0) + 1);
  }

  function safePath(value) {
    return typeof value === 'string' && value.length > 0 && value.length <= 512 &&
      !/^[a-z][a-z0-9+.-]*:/i.test(value) && value.indexOf('..') === -1;
  }

  function normalizeState(value) {
    var result = blankState();
    var lastVisited;
    if (!isObject(value) || (value.version !== 1 && value.version !== STATE_VERSION)) {
      throw new Error('Unsupported learning-state schema');
    }

    if (isObject(value.completed)) {
      Object.keys(value.completed).forEach(function (lessonId) {
        var completedAt = timestamp(value.completed[lessonId]);
        if (!isLessonId(lessonId) || completedAt === null) return;
        result.completed[lessonId] = completedAt;
        result.completionUpdated[lessonId] = completedAt;
      });
    }
    if (isObject(value.completionUpdated)) {
      Object.keys(value.completionUpdated).forEach(function (lessonId) {
        var updatedAt = timestamp(value.completionUpdated[lessonId]);
        var completedAt = result.completed[lessonId] || 0;
        if (!isLessonId(lessonId) || updatedAt === null) return;
        result.completionUpdated[lessonId] = Math.max(
          result.completionUpdated[lessonId] || 0,
          updatedAt
        );
        /* 修订晚于实体记录表示“删除”；不能在规范化时复活旧完成记录。 */
        if (updatedAt > completedAt) delete result.completed[lessonId];
      });
    }

    lastVisited = value.lastVisited;
    if (isObject(lastVisited)) lastVisited = lastVisited.lessonId;
    if (isLessonId(lastVisited)) {
      result.lastVisited = String(lastVisited);
      result.lastVisitedAt = timestamp(value.lastVisitedAt) || 1;
    }

    if (isObject(value.reading)) {
      Object.keys(value.reading).forEach(function (path) {
        var record = value.reading[path];
        var updatedAt;
        if (!safePath(path) || !isObject(record) ||
            (record.anchor !== null && typeof record.anchor !== 'string') ||
            !finiteNumber(record.offset) || !finiteNumber(record.ratio) ||
            record.ratio < 0 || record.ratio > 1) return;
        updatedAt = timestamp(record.updatedAt) || 1;
        result.reading[path] = {
          anchor: record.anchor || null,
          anchorText: typeof record.anchorText === 'string' ? record.anchorText : null,
          offset: record.offset,
          ratio: record.ratio,
          updatedAt: updatedAt
        };
        result.readingUpdated[path] = updatedAt;
      });
    }
    if (isObject(value.readingUpdated)) {
      Object.keys(value.readingUpdated).forEach(function (path) {
        var updatedAt = timestamp(value.readingUpdated[path]);
        var recordAt = result.reading[path] ? result.reading[path].updatedAt : 0;
        if (!safePath(path) || updatedAt === null) return;
        result.readingUpdated[path] = Math.max(
          result.readingUpdated[path] || 0,
          updatedAt
        );
        /* 修订晚于实体记录表示“删除”；保留 tombstone，移除旧阅读记录。 */
        if (updatedAt > recordAt) delete result.reading[path];
      });
    }
    return result;
  }

  function cloneState(value) {
    var result = blankState();
    Object.keys(value.completed).forEach(function (key) { result.completed[key] = value.completed[key]; });
    Object.keys(value.completionUpdated).forEach(function (key) {
      result.completionUpdated[key] = value.completionUpdated[key];
    });
    result.lastVisited = value.lastVisited;
    result.lastVisitedAt = value.lastVisitedAt;
    Object.keys(value.reading).forEach(function (key) {
      var record = value.reading[key];
      result.reading[key] = {
        anchor: record.anchor,
        anchorText: record.anchorText || null,
        offset: record.offset,
        ratio: record.ratio,
        updatedAt: record.updatedAt
      };
    });
    Object.keys(value.readingUpdated).forEach(function (key) {
      result.readingUpdated[key] = value.readingUpdated[key];
    });
    return result;
  }

  function sortedMap(value) {
    var result = {};
    Object.keys(value).sort().forEach(function (key) { result[key] = value[key]; });
    return result;
  }

  function serializeState(value) {
    return JSON.stringify({
      version: STATE_VERSION,
      completed: sortedMap(value.completed),
      completionUpdated: sortedMap(value.completionUpdated),
      lastVisited: value.lastVisited,
      lastVisitedAt: value.lastVisitedAt,
      reading: sortedMap(value.reading),
      readingUpdated: sortedMap(value.readingUpdated)
    });
  }

  function mergeStates(left, right) {
    var result = cloneState(left);
    var ids = Object.keys(left.completionUpdated).concat(Object.keys(right.completionUpdated));
    ids.forEach(function (lessonId) {
      var leftAt = left.completionUpdated[lessonId] || 0;
      var rightAt = right.completionUpdated[lessonId] || 0;
      var leftHas = Object.prototype.hasOwnProperty.call(left.completed, lessonId);
      var rightHas = Object.prototype.hasOwnProperty.call(right.completed, lessonId);
      if (rightAt < leftAt || (rightAt === leftAt && leftHas === rightHas)) return;
      result.completionUpdated[lessonId] = rightAt;
      /* 同修订冲突时固定让删除胜出，确保所有标签页最终一致。 */
      if (rightAt === leftAt ? leftHas && rightHas : rightHas) {
        result.completed[lessonId] = right.completed[lessonId];
      } else {
        delete result.completed[lessonId];
      }
    });
    if ((right.lastVisitedAt || 0) > (left.lastVisitedAt || 0) ||
        ((right.lastVisitedAt || 0) === (left.lastVisitedAt || 0) &&
         String(right.lastVisited || '') > String(left.lastVisited || ''))) {
      result.lastVisited = right.lastVisited;
      result.lastVisitedAt = right.lastVisitedAt || 0;
    }
    var paths = Object.keys(left.readingUpdated).concat(Object.keys(right.readingUpdated));
    paths.forEach(function (path) {
      var leftAt = left.readingUpdated[path] || 0;
      var rightAt = right.readingUpdated[path] || 0;
      var leftRecord = left.reading[path] || null;
      var rightRecord = right.reading[path] || null;
      var leftValue = JSON.stringify(leftRecord);
      var rightValue = JSON.stringify(rightRecord);
      if (rightAt < leftAt) return;
      if (rightAt === leftAt) {
        if (!!leftRecord !== !!rightRecord) {
          /* 同修订冲突时固定让删除胜出，确保所有标签页最终一致。 */
          result.readingUpdated[path] = rightAt;
          delete result.reading[path];
          return;
        }
        if (rightValue <= leftValue) return;
      }
      result.readingUpdated[path] = rightAt;
      if (rightRecord) result.reading[path] = rightRecord;
      else delete result.reading[path];
    });
    return result;
  }

  function createStorageAdapter() {
    var memory = blankState();

    function parseStored(raw) {
      if (raw === null) return null;
      try { return normalizeState(JSON.parse(raw)); } catch (error) { return null; }
    }

    function read() {
      try {
        var scoped = parseStored(window.localStorage.getItem(STORAGE_KEY));
        if (scoped) {
          memory = mergeStates(memory, scoped);
          return cloneState(memory);
        }
        var legacyKey = SCOPED_LEGACY_STORAGE_KEY;
        var legacy = parseStored(window.localStorage.getItem(legacyKey));
        if (!legacy) {
          legacyKey = UNSCOPED_LEGACY_STORAGE_KEY;
          legacy = parseStored(window.localStorage.getItem(legacyKey));
        }
        if (legacy) {
          memory = mergeStates(memory, legacy);
          try {
            window.localStorage.setItem(STORAGE_KEY, serializeState(memory));
            window.localStorage.removeItem(legacyKey);
          } catch (migrationError) {
            /* 保留 legacy；迁移失败不应丢掉已读出的进度。 */
          }
        }
      } catch (error) {
        /* localStorage 不可用时保留当前内存状态。 */
      }
      return cloneState(memory);
    }

    function write(value) {
      try {
        var durable = parseStored(window.localStorage.getItem(STORAGE_KEY));
        memory = mergeStates(memory, durable || blankState());
      } catch (error) {
        /* 仍可尝试本次写入。 */
      }
      memory = mergeStates(memory, value);
      try {
        window.localStorage.setItem(STORAGE_KEY, serializeState(memory));
      } catch (error) {
        /* 当前操作仍保存在内存中；后续写入会再次尝试持久化。 */
      }
      return cloneState(memory);
    }

    function mergeExternal(value) {
      memory = mergeStates(memory, value);
      try {
        var durableRaw = window.localStorage.getItem(STORAGE_KEY);
        var durable = parseStored(durableRaw);
        var serialized;
        memory = mergeStates(memory, durable || blankState());
        serialized = serializeState(memory);
        /* 已收敛时不重复写入，避免多标签页 storage 事件回声。 */
        if (serialized !== durableRaw) window.localStorage.setItem(STORAGE_KEY, serialized);
      } catch (error) {
        /* 当前标签仍保留合并结果；后续本地写入会再次尝试持久化。 */
      }
      return cloneState(memory);
    }

    function resetMemory() {
      memory = blankState();
      return cloneState(memory);
    }

    return {
      read: read,
      write: write,
      mergeExternal: mergeExternal,
      resetMemory: resetMemory
    };
  }

  var storage = createStorageAdapter();
  state = storage.read();

  function ready(callback) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', callback, { once: true });
    } else {
      callback();
    }
  }

  function siteRelativePath(href) {
    var page;
    var rootHref;
    if (!siteRoot) return null;
    try {
      page = new URL(href, window.location.href);
      page.hash = '';
      page.search = '';
      rootHref = siteRoot.href;
      if (page.href.indexOf(rootHref) !== 0) return null;
      return page.href.slice(rootHref.length) || 'index.html';
    } catch (error) {
      return null;
    }
  }

  function persist(nextState) {
    state = storage.write(nextState);
    renderLearningUi();
  }

  function ensureStatusRegion() {
    if (statusRegion && statusRegion.isConnected) return statusRegion;
    statusRegion = document.querySelector('[data-pwa-status-region]');
    if (!statusRegion) {
      statusRegion = document.createElement('div');
      statusRegion.className = 'pwa-status-region';
      statusRegion.setAttribute('data-pwa-status-region', '');
      statusRegion.setAttribute('aria-live', 'polite');
      statusRegion.setAttribute('aria-relevant', 'additions text');
      document.body.appendChild(statusRegion);
    }
    return statusRegion;
  }

  function removeStatus(id) {
    var region = ensureStatusRegion();
    var existing = region.querySelector('[data-pwa-status="' + id + '"]');
    if (existing) existing.remove();
  }

  function showStatus(id, message, action) {
    var region = ensureStatusRegion();
    var item = region.querySelector('[data-pwa-status="' + id + '"]');
    var text;
    var actions;
    var button;
    var close;

    if (!item) {
      item = document.createElement('div');
      item.className = 'pwa-status';
      item.setAttribute('data-pwa-status', id);
      item.setAttribute('role', 'status');
      region.appendChild(item);
    }

    item.innerHTML = '';
    text = document.createElement('span');
    text.className = 'pwa-status-message';
    text.textContent = message;
    item.appendChild(text);

    actions = document.createElement('span');
    actions.className = 'pwa-status-actions';
    if (action && typeof action.run === 'function') {
      button = document.createElement('button');
      button.type = 'button';
      button.className = 'pwa-status-action';
      button.textContent = action.label;
      button.addEventListener('click', function () {
        action.run(button);
      });
      actions.appendChild(button);
    }

    close = document.createElement('button');
    close.type = 'button';
    close.className = 'pwa-status-close';
    close.setAttribute('aria-label', '关闭提示');
    close.setAttribute('title', '关闭');
    close.textContent = '×';
    close.addEventListener('click', function () {
      item.remove();
    });
    actions.appendChild(close);
    item.appendChild(actions);
    return item;
  }

  function headingRoot() {
    return document.querySelector('main') || document.body;
  }

  function headingTextKey(heading) {
    return heading ? heading.textContent.replace(/\s+/g, ' ').trim().toLocaleLowerCase() : '';
  }

  function ensureHeadingAnchors() {
    var headings = headingRoot().querySelectorAll('h2');
    Array.prototype.forEach.call(headings, function (heading, index) {
      if (!heading.id) heading.id = 'sec-' + (index + 1);
    });
  }

  function anchorOffsetPx() {
    var rootStyle;
    var rem;
    var rootPx;
    try {
      rootStyle = window.getComputedStyle(document.documentElement);
      rem = parseFloat(rootStyle.getPropertyValue('--scroll-anchor-offset')) || 5;
      rootPx = parseFloat(rootStyle.fontSize) || 16;
      return rem * rootPx;
    } catch (error) {
      return 80;
    }
  }

  function readingSnapshot() {
    var doc = document.documentElement;
    var scrollY = window.scrollY || doc.scrollTop || 0;
    var maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
    var ratio = maxScroll > 0 ? Math.max(0, Math.min(1, scrollY / maxScroll)) : 0;
    var line = scrollY + anchorOffsetPx() + 8;
    var selected = null;
    var selectedTop = 0;
    var headings;

    ensureHeadingAnchors();
    headings = headingRoot().querySelectorAll('h1[id], h2[id], h3[id]');
    Array.prototype.forEach.call(headings, function (heading) {
      var top = heading.getBoundingClientRect().top + scrollY;
      if (top <= line && top >= selectedTop) {
        selected = heading;
        selectedTop = top;
      }
    });

    return {
      scrollY: scrollY,
      anchor: selected ? selected.id : null,
      anchorText: headingTextKey(selected),
      offset: selected ? scrollY - selectedTop : 0,
      ratio: ratio
    };
  }

  /* 更新流程会在发送 SKIP_WAITING 前调用此内部保存点。 */
  function saveReadingState() {
    var snapshot;
    var nextState;
    if (!currentPath || restoring) return;
    snapshot = readingSnapshot();
    state = storage.read();
    nextState = cloneState(state);
    if (snapshot.scrollY <= TOP_THRESHOLD) {
      if (Object.prototype.hasOwnProperty.call(nextState.reading, currentPath)) {
        delete nextState.reading[currentPath];
        nextState.readingUpdated[currentPath] = nextRevision(nextState.readingUpdated[currentPath]);
        state = storage.write(nextState);
      }
      return;
    }
    var updatedAt = nextRevision(nextState.readingUpdated[currentPath]);
    nextState.reading[currentPath] = {
      anchor: snapshot.anchor,
      anchorText: snapshot.anchorText,
      offset: snapshot.offset,
      ratio: snapshot.ratio,
      updatedAt: updatedAt
    };
    nextState.readingUpdated[currentPath] = updatedAt;
    state = storage.write(nextState);
  }

  function scheduleReadingSave() {
    if (restoring || saveTimer !== null) return;
    saveTimer = window.setTimeout(function () {
      saveTimer = null;
      saveReadingState();
    }, SAVE_DELAY);
  }

  function navigationIsBackForward() {
    var entries;
    try {
      if (window.performance && typeof window.performance.getEntriesByType === 'function') {
        entries = window.performance.getEntriesByType('navigation');
        if (entries && entries[0]) return entries[0].type === 'back_forward';
      }
      return !!(window.performance && window.performance.navigation &&
        window.performance.navigation.type === 2);
    } catch (error) {
      return false;
    }
  }

  function scrollToPosition(top) {
    try {
      window.scrollTo({ top: top, left: 0, behavior: 'auto' });
    } catch (error) {
      window.scrollTo(0, top);
    }
  }

  function clearCurrentReadingPosition() {
    var nextState;
    if (!currentPath || !Object.prototype.hasOwnProperty.call(state.reading, currentPath)) return;
    nextState = cloneState(state);
    delete nextState.reading[currentPath];
    nextState.readingUpdated[currentPath] = nextRevision(nextState.readingUpdated[currentPath]);
    state = storage.write(nextState);
  }

  function restoreReadingState() {
    var record;
    var doc;
    var maxScroll;
    var target = 0;
    var anchor;

    if (!currentPath || window.location.hash || navigationIsBackForward()) return;
    if ((window.scrollY || document.documentElement.scrollTop || 0) > TOP_THRESHOLD) return;
    record = state.reading[currentPath];
    if (!record) return;

    doc = document.documentElement;
    maxScroll = Math.max(0, doc.scrollHeight - window.innerHeight);
    if (record.anchor) {
      anchor = document.getElementById(record.anchor);
      if (anchor && record.anchorText && headingTextKey(anchor) !== record.anchorText) {
        anchor = null;
      }
    }
    if (!anchor && record.anchorText) {
      Array.prototype.some.call(
        headingRoot().querySelectorAll('h1, h2, h3'),
        function (heading) {
          if (headingTextKey(heading) !== record.anchorText) return false;
          anchor = heading;
          return true;
        }
      );
    }
    if (anchor) target = anchor.getBoundingClientRect().top + (window.scrollY || 0) + record.offset;
    else target = record.ratio * maxScroll;
    target = Math.max(0, Math.min(maxScroll, target));
    if (target <= TOP_THRESHOLD) return;

    restoring = true;
    scrollToPosition(target);
    window.setTimeout(function () {
      restoring = false;
      if ((window.scrollY || document.documentElement.scrollTop || 0) <= TOP_THRESHOLD) return;
      showStatus('reading-restored', '已恢复上次阅读位置', {
        label: '返回顶部',
        run: function () {
          scrollToPosition(0);
          clearCurrentReadingPosition();
          removeStatus('reading-restored');
        }
      });
    }, 80);
  }

  function completedCount() {
    var count = 0;
    lessons.forEach(function (lesson) {
      if (state.completed[lesson.lessonId]) count += 1;
    });
    return count;
  }

  function lessonHref(lesson) {
    var path;
    if (!siteRoot || !lesson) return '';
    path = lesson.href || lesson.url || ('lessons/' + lesson.file);
    try {
      return new URL(path, siteRoot).href;
    } catch (error) {
      return path;
    }
  }

  function continueTarget() {
    var lastIndex = -1;
    var target = null;

    if (!lessons.length) return null;
    if (state.lastVisited === null && completedCount() === 0) {
      return {
        href: siteRoot ? new URL('lessons/0001-ai-agent-learning-path-overview.html', siteRoot).href : '',
        title: '学习路径总览',
        lessonId: null,
        complete: true
      };
    }
    lessons.some(function (lesson, index) {
      if (lesson.lessonId === state.lastVisited) {
        lastIndex = index;
        return true;
      }
      return false;
    });

    if (lastIndex !== -1 && !state.completed[lessons[lastIndex].lessonId]) {
      target = lessons[lastIndex];
    }
    if (!target && lastIndex !== -1) {
      lessons.slice(lastIndex + 1).some(function (lesson) {
        if (!state.completed[lesson.lessonId]) {
          target = lesson;
          return true;
        }
        return false;
      });
    }
    if (!target) {
      lessons.some(function (lesson) {
        if (!state.completed[lesson.lessonId]) {
          target = lesson;
          return true;
        }
        return false;
      });
    }

    if (target) {
      return {
        href: lessonHref(target),
        title: target.title,
        lessonId: target.lessonId,
        complete: false
      };
    }
    return {
      href: siteRoot ? new URL('lessons/0001-ai-agent-learning-path-overview.html', siteRoot).href : '',
      title: '学习路径总览',
      lessonId: null,
      complete: true
    };
  }

  function updateLearningProgress(count, total) {
    var percent = total ? Math.round(count / total * 100) : 0;
    var nodes = document.querySelectorAll('[data-learning-progress]');
    Array.prototype.forEach.call(nodes, function (node) {
      var mode = node.getAttribute('data-learning-progress') || 'label';
      var strong = node.querySelector('strong');
      var detail = node.querySelector('span');
      node.setAttribute('data-completed', String(count));
      node.setAttribute('data-total', String(total));
      node.setAttribute('aria-label', '已完成 ' + count + '/' + total + ' 课');
      if (node.tagName === 'PROGRESS') {
        node.max = total;
        node.value = count;
      } else if (strong && detail) {
        strong.textContent = percent + '%';
        detail.textContent = count === 0 ? '尚未记录已完成课程' :
          '已完成 ' + count + ' / ' + total + ' 课';
      } else if (mode === 'completed' || mode === 'count') {
        node.textContent = String(count);
      } else if (mode === 'percent') {
        node.textContent = percent + '%';
      } else if (mode === 'fraction') {
        node.textContent = count + '/' + total;
      } else {
        node.textContent = '已完成 ' + count + ' / ' + total + ' 课';
      }
    });
  }

  function updateCourseBar(count, total) {
    var percent = total ? Math.round(count / total * 100) : 0;
    var hooks = document.querySelectorAll('[data-course-progress]');
    Array.prototype.forEach.call(hooks, function (hook) {
      var fill = hook.querySelector('.course-bar-track-fill');
      var cursor = hook.querySelector('.course-bar-track-cursor');
      var countNode = hook.parentNode && hook.parentNode.querySelector('[data-course-progress-count]');
      hook.setAttribute('aria-valuenow', String(count));
      hook.setAttribute('aria-valuemin', '0');
      hook.setAttribute('aria-valuemax', String(total));
      hook.setAttribute('aria-label', '已完成 ' + count + '/' + total + ' 课');
      hook.setAttribute('data-completed', String(count));
      hook.setAttribute('data-total', String(total));
      hook.classList.toggle('is-empty', count === 0);
      if (fill) fill.style.width = percent + '%';
      if (cursor) cursor.style.left = percent + '%';
      if (!countNode && hook.parentNode) {
        countNode = document.createElement('span');
        countNode.className = 'course-bar-progress-count';
        countNode.setAttribute('data-course-progress-count', '');
        hook.parentNode.insertBefore(countNode, hook);
      }
      if (countNode) {
        countNode.textContent = count + '/' + total;
        countNode.setAttribute('aria-label', '已完成 ' + count + '/' + total + ' 课');
      }
    });
  }

  function updateContinueLearning() {
    var target = continueTarget();
    var nodes;
    if (!target) return;
    nodes = document.querySelectorAll('[data-continue-learning]');
    Array.prototype.forEach.call(nodes, function (node) {
      var link = node.tagName === 'A' ? node : node.querySelector('a');
      var titleNode = node.querySelector('[data-continue-learning-title]');
      var mode = node.getAttribute('data-continue-learning') || 'label';
      var label = target.complete ? '查看学习路径总览' :
        '继续学习 · ' + target.lessonId + ' ' + target.title;

      if (link) {
        link.href = target.href;
        link.setAttribute('aria-label', label);
      } else if (node.tagName === 'BUTTON' && !node.hasAttribute('data-pwa-continue-bound')) {
        node.setAttribute('data-pwa-continue-bound', '');
        node.addEventListener('click', function () {
          window.location.href = node.getAttribute('data-continue-href');
        });
      }
      node.setAttribute('data-continue-href', target.href);
      node.setAttribute('data-continue-lesson', target.lessonId || 'overview');
      if (titleNode) {
        titleNode.textContent = label;
      } else if (node.tagName === 'A' && mode !== 'href') {
        node.textContent = label;
      } else if (node.tagName === 'BUTTON' && mode !== 'href') {
        node.textContent = label;
      } else if (!link && mode !== 'href') {
        node.textContent = label;
      } else if (link) {
        link.textContent = label;
      }
      Array.prototype.forEach.call(node.children, function (child) {
        if (child !== link && child.hasAttribute('aria-hidden')) {
          child.textContent = target.lessonId || '✓';
        }
      });
    });
  }

  function ensureCompletionButton() {
    var header;
    var wrapper;
    var button;
    if (!context || !context.isLesson || !isLessonId(context.lessonId)) return;
    header = document.querySelector('.lesson-header');
    if (!header) return;

    button = header.querySelector('[data-lesson-completion]');
    if (!button) {
      wrapper = document.createElement('div');
      wrapper.className = 'lesson-completion-control';
      button = document.createElement('button');
      button.type = 'button';
      button.className = 'lesson-completion-button';
      button.setAttribute('data-lesson-completion', context.lessonId);
      wrapper.appendChild(button);
      header.appendChild(wrapper);
    }

    if (!button.hasAttribute('data-pwa-completion-bound')) {
      button.setAttribute('data-pwa-completion-bound', '');
      button.addEventListener('click', function () {
        var lessonId = button.getAttribute('data-lesson-completion');
        var nextState = cloneState(state);
        var wasComplete = !!nextState.completed[lessonId];
        var updatedAt = nextRevision(nextState.completionUpdated[lessonId]);
        if (wasComplete) {
          delete nextState.completed[lessonId];
        } else {
          nextState.completed[lessonId] = updatedAt;
        }
        nextState.completionUpdated[lessonId] = updatedAt;
        persist(nextState);
        showStatus('lesson-completion', wasComplete ?
          lessonId + ' 已撤销完成' : lessonId + ' 已标记完成');
      });
    }
  }

  function updateCompletionButton() {
    var button;
    var isComplete;
    if (!context || !context.isLesson) return;
    button = document.querySelector('[data-lesson-completion="' + context.lessonId + '"]');
    if (!button) return;
    isComplete = !!state.completed[context.lessonId];
    button.classList.toggle('is-complete', isComplete);
    button.setAttribute('aria-pressed', isComplete ? 'true' : 'false');
    button.textContent = isComplete ? '撤销完成' : '标记本课完成';
    button.setAttribute('title', isComplete ? '将本课改为未完成' : '手动标记本课已完成');
  }

  function renderLearningUi() {
    var total;
    var count;
    if (!catalog || !lessons.length) return;
    ensureCompletionButton();
    updateCompletionButton();
    total = lessons.length;
    count = completedCount();
    updateLearningProgress(count, total);
    updateCourseBar(count, total);
    updateContinueLearning();
  }

  function recordLessonVisit() {
    var nextState;
    if (visitRecorded || !context || !context.isLesson || !isLessonId(context.lessonId)) return;
    visitRecorded = true;
    if (state.lastVisited === context.lessonId) return;
    nextState = cloneState(state);
    nextState.lastVisited = context.lessonId;
    nextState.lastVisitedAt = nextRevision(nextState.lastVisitedAt);
    state = storage.write(nextState);
  }

  function connectCatalog(attempt) {
    var available = window.CourseCatalog;
    try {
      if (available && typeof available.context === 'function' &&
          typeof available.lessons === 'function') {
        lessons = available.lessons();
        if (Array.isArray(lessons) && lessons.length) {
          catalog = available;
          context = catalog.context(window.location.pathname);
          recordLessonVisit();
          renderLearningUi();
          return;
        }
      }
    } catch (error) {
      lessons = [];
    }
    if (attempt < CATALOG_RETRIES) {
      window.setTimeout(function () { connectCatalog(attempt + 1); }, 100);
    }
  }

  function setupStorageSync() {
    window.addEventListener('storage', function (event) {
      var incoming;
      if (event.storageArea && event.storageArea !== window.localStorage) return;
      if (event.key !== null && event.key !== STORAGE_KEY) return;
      try {
        if (event.key === null || event.newValue === null) {
          storage.resetMemory();
          state = storage.read();
        } else {
          incoming = normalizeState(JSON.parse(event.newValue));
          state = storage.mergeExternal(incoming);
        }
        renderLearningUi();
      } catch (error) {
        /* 无效的外部状态不应覆盖当前已验证状态，也不应禁用后续持久化。 */
        renderLearningUi();
      }
    });
  }

  function setupReadingPosition() {
    window.addEventListener('scroll', scheduleReadingSave, { passive: true });
    window.addEventListener('resize', scheduleReadingSave, { passive: true });
    window.addEventListener('pagehide', saveReadingState);
    window.addEventListener('pageshow', function (event) {
      if (!event.persisted) return;
      visitRecorded = false;
      state = storage.read();
      recordLessonVisit();
      renderLearningUi();
    });
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') saveReadingState();
    });
    ensureHeadingAnchors();
    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        window.setTimeout(restoreReadingState, 40);
      });
    });
  }

  function setupConnectivityStatus() {
    function showOffline() {
      showStatus('connectivity', '当前可能离线');
    }
    function clearOffline() {
      removeStatus('connectivity');
    }
    window.addEventListener('offline', showOffline);
    window.addEventListener('online', clearOffline);
    if (navigator.onLine === false) showOffline();
  }

  function canRegisterWorker() {
    var hostname = window.location.hostname;
    var trustworthy = window.location.protocol === 'https:' || hostname === 'localhost' ||
      hostname === '127.0.0.1' || hostname === '[::1]';
    return BUILT_SITE && !!siteRoot && 'serviceWorker' in navigator && trustworthy;
  }

  function postCacheVisitedPage(reg) {
    var worker;
    var page;
    /* 已受控导航由 Service Worker 的 fetch 路径缓存；消息只补首次未受控页面。 */
    if (initiallyControlled || cacheVisitPending) return;
    worker = navigator.serviceWorker.controller || (reg && reg.active);
    if (!worker) return;
    page = new URL(window.location.href);
    page.hash = '';
    page.search = '';
    cacheVisitPending = true;
    worker.postMessage({ type: 'CACHE_VISITED_PAGE', url: page.href });
    clearTimeout(cacheVisitTimer);
    cacheVisitTimer = window.setTimeout(function () {
      cacheVisitPending = false;
      postCacheVisitedPage(registration);
    }, 4000);
  }

  function offerUpdate(worker) {
    if (!worker || worker.state === 'redundant') return;
    waitingWorker = worker;
    showStatus('update', '发现新版本', {
      label: '刷新更新',
      run: function (button) {
        var target = (registration && registration.waiting) || waitingWorker;
        if (!target || target.state === 'redundant') {
          removeStatus('update');
          return;
        }
        button.disabled = true;
        saveReadingState();
        refreshRequested = true;
        target.postMessage({ type: 'SKIP_WAITING' });
        clearTimeout(updateRecoveryTimer);
        updateRecoveryTimer = window.setTimeout(function () {
          refreshRequested = false;
          button.disabled = false;
          button.textContent = '重试更新';
        }, 12000);
      }
    });
  }

  function watchRegistration(reg) {
    registration = reg;

    function observeInstalling(worker) {
      if (!worker) return;
      function onStateChange() {
        if (worker.state === 'installed' && navigator.serviceWorker.controller) {
          offerUpdate(reg.waiting || worker);
        } else if (worker.state === 'redundant' && waitingWorker === worker) {
          waitingWorker = null;
          removeStatus('update');
        }
      }
      worker.addEventListener('statechange', onStateChange);
      onStateChange();
    }

    if (reg.waiting) offerUpdate(reg.waiting);
    observeInstalling(reg.installing);
    reg.addEventListener('updatefound', function () {
      observeInstalling(reg.installing);
    });
  }

  function setupWorker() {
    var workerUrl;
    if (!canRegisterWorker()) return;
    workerUrl = new URL('service-worker.js', siteRoot);

    navigator.serviceWorker.addEventListener('message', function (event) {
      if (!event.data || event.data.type !== 'CACHE_VISITED_PAGE_RESULT') return;
      clearTimeout(cacheVisitTimer);
      cacheVisitPending = false;
      if (event.data.ok === true) {
        initiallyControlled = true;
        return;
      }
      /* 临时网络或 Cache Storage 失败后继续补缓存，不把失败确认当作成功。 */
      cacheVisitTimer = window.setTimeout(function () {
        postCacheVisitedPage(registration);
      }, 4000);
    });

    navigator.serviceWorker.addEventListener('controllerchange', function () {
      if (reloadTriggered) return;
      clearTimeout(updateRecoveryTimer);
      waitingWorker = null;
      removeStatus('update');
      if (refreshRequested) {
        hadController = true;
        reloadTriggered = true;
        saveReadingState();
        window.location.reload();
        return;
      }
      if (!hadController) {
        hadController = true;
        if (registration) postCacheVisitedPage(registration);
        return;
      }
      showStatus('update-applied', '新版本已就绪', {
        label: '刷新使用',
        run: function (button) {
          button.disabled = true;
          saveReadingState();
          reloadTriggered = true;
          window.location.reload();
        }
      });
    });

    navigator.serviceWorker.register(workerUrl.href, { scope: appScopePath }).then(function (reg) {
      watchRegistration(reg);
      return navigator.serviceWorker.ready;
    }).then(function (reg) {
      registration = reg;
      postCacheVisitedPage(reg);
    }).catch(function () {
      /* PWA 是渐进增强：注册失败不打断课程阅读。 */
    });
  }

  ready(function () {
    ensureStatusRegion();
    setupConnectivityStatus();
    setupStorageSync();
    setupReadingPosition();
    setupWorker();
    connectCatalog(0);
    window.setTimeout(renderLearningUi, 250);
    window.setTimeout(renderLearningUi, 1000);
    window.addEventListener('load', renderLearningUi, { once: true });
  });
})();
