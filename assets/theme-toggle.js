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
    const btn = document.createElement('button');
    btn.className = 'theme-toggle';
    btn.setAttribute('aria-label', '切换深色/浅色模式');
    btn.setAttribute('title', '切换深色/浅色模式');
    btn.innerHTML = '<span class="icon-sun">☀️</span><span class="icon-moon">🌙</span>';
    btn.addEventListener('click', toggleTheme);
    document.body.appendChild(btn);
  });

  // 监听系统主题变化
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
    // 只在用户没有手动设置过时才跟随系统
    if (!localStorage.getItem(STORAGE_KEY)) {
      applyTheme(e.matches ? DARK : LIGHT);
    }
  });
})();
