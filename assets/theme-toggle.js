/**
 * 主题切换组件
 * - 支持深色/浅色切换
 * - 自动检测系统偏好
 * - 安全 localStorage 持久化（受限环境降级为内存）
 * - 跟随系统偏好变化
 */
(function() {
  'use strict';

  if (window.__aiCourseThemeToggleInitialized) return;
  window.__aiCourseThemeToggleInitialized = true;

  const script = document.currentScript;
  const scriptUrl = script && script.src;
  let siteRoot = null;
  try { siteRoot = scriptUrl ? new URL('../', scriptUrl) : null; } catch (error) { /* 特殊 URL 降级。 */ }
  const scopePath = siteRoot ? siteRoot.pathname : 'local';
  const storageScope = encodeURIComponent(scopePath);
  const STORAGE_KEY = 'ai-course:theme:v1:' + storageScope;
  const LEGACY_STORAGE_KEY = 'theme';
  const MIGRATION_KEY = 'ai-course:theme:migrated:' + storageScope;
  const LEGACY_SEEN_KEY = 'ai-course:theme:legacy-seen:' + storageScope;
  const DARK = 'dark';
  const LIGHT = 'light';
  let memoryTheme = null;
  let memoryOnly = false;

  function isTheme(value) {
    return value === DARK || value === LIGHT;
  }

  function rememberLegacy(value) {
    window.localStorage.setItem(LEGACY_SEEN_KEY, isTheme(value) ? value : '');
  }

  function changedLegacyTheme() {
    var legacy = window.localStorage.getItem(LEGACY_STORAGE_KEY);
    var seen = window.localStorage.getItem(LEGACY_SEEN_KEY);
    if (seen === null) {
      rememberLegacy(legacy);
      return null;
    }
    if (legacy === seen) return null;
    rememberLegacy(legacy);
    return isTheme(legacy) ? legacy : null;
  }

  function readStoredTheme() {
    let value;
    let legacyChange;
    if (memoryOnly && isTheme(memoryTheme)) {
      try {
        window.localStorage.setItem(STORAGE_KEY, memoryTheme);
        window.localStorage.setItem(MIGRATION_KEY, '1');
        memoryOnly = window.localStorage.getItem(STORAGE_KEY) !== memoryTheme;
      } catch (recoveryError) {
        memoryOnly = true;
      }
      /* 未持久化的最新用户选择优先于存储中的旧值。 */
      if (memoryOnly) return memoryTheme;
    }
    try {
      value = window.localStorage.getItem(STORAGE_KEY);
      legacyChange = changedLegacyTheme();
      if (isTheme(legacyChange)) {
        memoryTheme = legacyChange;
        memoryOnly = true;
        try {
          window.localStorage.setItem(STORAGE_KEY, legacyChange);
          window.localStorage.setItem(MIGRATION_KEY, '1');
          memoryOnly = window.localStorage.getItem(STORAGE_KEY) !== legacyChange;
        } catch (migrationError) { /* 当前标签仍使用内存值。 */ }
        return legacyChange;
      }
      if (isTheme(value)) {
        memoryTheme = value;
        memoryOnly = false;
        try { window.localStorage.setItem(MIGRATION_KEY, '1'); } catch (migrationError) { /* best effort */ }
        return value;
      }
      if (window.localStorage.getItem(MIGRATION_KEY) !== '1') {
        value = window.localStorage.getItem(LEGACY_STORAGE_KEY);
        if (isTheme(value)) {
          memoryTheme = value;
          try {
            window.localStorage.setItem(STORAGE_KEY, value);
            window.localStorage.setItem(MIGRATION_KEY, '1');
            rememberLegacy(value);
            memoryOnly = window.localStorage.getItem(STORAGE_KEY) !== value;
          } catch (migrationError) {
            memoryOnly = true;
          }
          return value;
        }
      }
      if (memoryOnly && isTheme(memoryTheme)) return memoryTheme;
      memoryTheme = null;
      return null;
    } catch (error) {
      memoryOnly = true;
      return memoryTheme;
    }
  }

  function writeStoredTheme(theme) {
    memoryTheme = theme;
    memoryOnly = true;
    try {
      window.localStorage.setItem(STORAGE_KEY, theme);
      window.localStorage.setItem(MIGRATION_KEY, '1');
      memoryOnly = window.localStorage.getItem(STORAGE_KEY) !== theme;
    } catch (error) { /* 当前选择仍保存在内存中，后续读取会重试存储。 */ }
  }

  function systemTheme() {
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
  }

  // 获取当前主题
  function getTheme() {
    const stored = readStoredTheme();
    if (stored === DARK || stored === LIGHT) return stored;
    return systemTheme();
  }

  // 纯 CSS/SVG 图标：不依赖任何 emoji 字体或远程资源，深浅色下都能稳定渲染
  var SUN_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<circle cx="12" cy="12" r="4"></circle>' +
      '<path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"></path>' +
    '</svg>';
  var MOON_SVG =
    '<svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
      '<path d="M20 14.5A8.5 8.5 0 1 1 9.5 4a7 7 0 0 0 10.5 10.5Z"></path>' +
    '</svg>';

  var btn = null;
  var boundButton = null;

  // 应用主题
  function applyTheme(theme) {
    let meta;
    document.documentElement.setAttribute('data-theme', theme);
    // 更新 meta theme-color（移动端浏览器状态栏）
    meta = document.querySelector('meta[name="theme-color"]');
    if (!meta) {
      meta = document.createElement('meta');
      meta.name = 'theme-color';
      document.head.appendChild(meta);
    }
    meta.content = theme === DARK ? '#1A1A1E' : '#F8F6F1';
    if (btn) updateButtonState(theme);
  }

  // 更新按钮的可访问性文案：动态说明「点击后会切到哪个模式」，并暴露当前状态
  function updateButtonState(theme) {
    var next = theme === DARK ? LIGHT : DARK;
    var nextLabel = next === DARK ? '深色' : '浅色';
    var currentLabel = theme === DARK ? '深色' : '浅色';
    btn.setAttribute('aria-label', '切换到' + nextLabel + '模式（当前：' + currentLabel + '模式）');
    btn.setAttribute('title', '切换到' + nextLabel + '模式');
    // aria-pressed 反映“深色模式当前是否已启用”这一状态，而非按钮本身的按下动作
    btn.setAttribute('aria-pressed', theme === DARK ? 'true' : 'false');
  }

  // 切换主题
  function toggleTheme() {
    const current = getTheme();
    const next = current === DARK ? LIGHT : DARK;
    writeStoredTheme(next);
    applyTheme(next);
  }

  function buildButton() {
    btn = document.querySelector('.theme-toggle[data-theme-toggle]');
    if (!btn) {
      btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'theme-toggle';
      btn.setAttribute('data-theme-toggle', '');
      btn.innerHTML =
        '<span class="icon-sun">' + SUN_SVG + '</span>' +
        '<span class="icon-moon">' + MOON_SVG + '</span>';
      document.body.appendChild(btn);
    }
    if (boundButton !== btn) {
      btn.setAttribute('data-theme-toggle-bound', '');
      btn.addEventListener('click', toggleTheme);
      boundButton = btn;
    }
    updateButtonState(getTheme());
  }

  // 初始化：尽早应用主题（防止闪烁）
  applyTheme(getTheme());

  // DOM 加载完成后注入按钮
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildButton, { once: true });
  } else {
    buildButton();
  }

  // 监听系统主题变化；只在用户没有手动设置过时跟随系统
  if (window.matchMedia) {
    var media = window.matchMedia('(prefers-color-scheme: dark)');
    var onSystemThemeChange = function(e) {
      if (readStoredTheme() !== DARK && readStoredTheme() !== LIGHT) {
        applyTheme(e.matches ? DARK : LIGHT);
      }
    };
    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', onSystemThemeChange);
    } else if (typeof media.addListener === 'function') {
      media.addListener(onSystemThemeChange);
    }
  }

  // 同源多标签页主题同步；只接受 localStorage，并以持久化 scoped 值为准。
  window.addEventListener('storage', function(event) {
    var stored;
    if (event.storageArea && event.storageArea !== window.localStorage) return;
    if (event.key !== null && event.key !== STORAGE_KEY && event.key !== LEGACY_STORAGE_KEY) return;
    if (event.key === LEGACY_STORAGE_KEY &&
        (event.newValue === DARK || event.newValue === LIGHT)) {
      /* 兼容尚未升级的旧标签页：同步它的明确用户操作，并收敛到 scoped 键。 */
      memoryTheme = event.newValue;
      memoryOnly = true;
      try {
        window.localStorage.setItem(STORAGE_KEY, event.newValue);
        window.localStorage.setItem(MIGRATION_KEY, '1');
        rememberLegacy(event.newValue);
        memoryOnly = window.localStorage.getItem(STORAGE_KEY) !== event.newValue;
      } catch (error) { /* 当前标签仍使用内存值。 */ }
      applyTheme(event.newValue);
      return;
    }
    stored = readStoredTheme();
    applyTheme(stored === DARK || stored === LIGHT ? stored : systemTheme());
  });

  // 从 bfcache 恢复时重新对齐持久化主题和按钮状态。
  window.addEventListener('pageshow', function() {
    applyTheme(getTheme());
  });
})();
