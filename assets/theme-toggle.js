/**
 * 主题切换组件
 * - 支持深色/浅色切换
 * - 自动检测系统偏好
 * - localStorage 持久化
 * - 跟随系统偏好变化
 */
(function() {
  'use strict';

  const STORAGE_KEY = 'theme';
  const DARK = 'dark';
  const LIGHT = 'light';

  // 获取当前主题
  function getTheme() {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === DARK || stored === LIGHT) return stored;
    // 未设置过，检测系统偏好
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? DARK : LIGHT;
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

  // 应用主题
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    // 更新 meta theme-color（移动端浏览器状态栏）
    let meta = document.querySelector('meta[name="theme-color"]');
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
    localStorage.setItem(STORAGE_KEY, next);
    applyTheme(next);
  }

  // 初始化：尽早应用主题（防止闪烁）
  applyTheme(getTheme());

  // DOM 加载完成后注入按钮
  document.addEventListener('DOMContentLoaded', function() {
    btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'theme-toggle';
    btn.innerHTML =
      '<span class="icon-sun">' + SUN_SVG + '</span>' +
      '<span class="icon-moon">' + MOON_SVG + '</span>';
    btn.addEventListener('click', toggleTheme);
    document.body.appendChild(btn);
    updateButtonState(getTheme());
  });

  // 监听系统主题变化
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    // 只在用户没有手动设置过时才跟随系统
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches ? DARK : LIGHT);
    }
  });
})();
