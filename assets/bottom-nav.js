/**
 * 课程导航
 * - 桌面端：页脚卡片式上一课 / 大纲 / 下一课
 * - 手机端：固定返回 / 上一课 / 目录 / 下一课 Dock
 * - 所有课程目标来自 CourseCatalog，保持 file:// 与 Pages 子路径兼容
 */
(function() {
  'use strict';

  var context;
  var prev;
  var next;
  var outline;
  var fallback;
  var html;
  var nav;
  var footer;

  function mobileIcon(path) {
    return '<span class="mobile-course-icon" aria-hidden="true">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + path + '</svg></span>';
  }

  if (!window.CourseCatalog) return;
  context = window.CourseCatalog.context(window.location.pathname);
  if (!context) return;

  prev = context.prev;
  next = context.next;
  outline = context.outline;
  fallback = context.isLesson && outline ? outline.file : '../index.html';

  html = '<div class="bottom-nav-inner">';

  html += '<div class="bottom-nav-side">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="bottom-nav-card bottom-nav-prev">';
    html += '<span class="bottom-nav-label">← 上一课</span>';
    html += '<span class="bottom-nav-title">' + prev.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '<div class="bottom-nav-center">';
  if (outline) {
    html += '<a href="' + outline.file + '" class="bottom-nav-outline" aria-label="查看本阶段课程大纲">';
    html += '<span class="bottom-nav-outline-icon" aria-hidden="true">☰</span>';
    html += '<span class="bottom-nav-outline-text">大纲</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '<div class="bottom-nav-side">';
  if (next) {
    html += '<a href="' + next.file + '" class="bottom-nav-card bottom-nav-next">';
    html += '<span class="bottom-nav-label">下一课 →</span>';
    html += '<span class="bottom-nav-title">' + next.title + '</span>';
    html += '</a>';
  }
  html += '</div>';
  html += '</div>';

  html += '<div class="mobile-course-nav" data-mobile-course-nav>';
  html += '<a href="' + fallback + '" class="mobile-course-action" data-course-back aria-label="返回上一页面；无浏览历史时返回课程大纲">';
  html += mobileIcon('<path d="M15 18l-6-6 6-6"></path>');
  html += '<span>返回</span>';
  html += '</a>';

  if (prev) {
    html += '<a href="' + prev.file + '" class="mobile-course-action" aria-label="上一课：' + prev.title + '">';
    html += mobileIcon('<path d="M19 12H5"></path><path d="M11 18l-6-6 6-6"></path>') + '<span>上一课</span></a>';
  } else {
    html += '<span class="mobile-course-action is-disabled" aria-disabled="true">';
    html += mobileIcon('<path d="M19 12H5"></path><path d="M11 18l-6-6 6-6"></path>') + '<span>上一课</span></span>';
  }

  html += '<button type="button" class="mobile-course-action" data-mobile-toc-toggle aria-controls="toc" aria-expanded="false">';
  html += mobileIcon('<path d="M4 6h16"></path><path d="M4 12h16"></path><path d="M4 18h16"></path>') + '<span>目录</span></button>';

  if (next) {
    html += '<a href="' + next.file + '" class="mobile-course-action" aria-label="下一课：' + next.title + '">';
    html += mobileIcon('<path d="M5 12h14"></path><path d="M13 6l6 6-6 6"></path>') + '<span>下一课</span></a>';
  } else {
    html += '<span class="mobile-course-action is-disabled" aria-disabled="true">';
    html += mobileIcon('<path d="M5 12h14"></path><path d="M13 6l6 6-6 6"></path>') + '<span>下一课</span></span>';
  }
  html += '</div>';

  nav = document.createElement('nav');
  nav.className = 'bottom-nav';
  nav.setAttribute('aria-label', '课程导航');
  nav.innerHTML = html;

  footer = document.querySelector('footer');
  if (footer) {
    document.body.insertBefore(nav, footer);
  } else {
    document.body.appendChild(nav);
  }
})();
