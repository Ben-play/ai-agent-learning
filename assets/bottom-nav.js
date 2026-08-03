/**
 * 底部课程导航
 * - 卡片式上一课/下一课
 * - 显示课程标题
 * - 回到大纲按钮
 */
(function() {
  'use strict';

  var context;
  var prev;
  var next;
  var outline;
  var html;
  var nav;
  var footer;

  if (!window.CourseCatalog) return;
  context = window.CourseCatalog.context(window.location.pathname);
  if (!context) return;

  prev = context.prev;
  next = context.next;
  outline = context.outline;
  html = '<div class="bottom-nav-inner">';

  // 上一课
  html += '<div class="bottom-nav-side">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="bottom-nav-card bottom-nav-prev">';
    html += '<span class="bottom-nav-label">← 上一课</span>';
    html += '<span class="bottom-nav-title">' + prev.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  // 中间：回到大纲（目录统一提供当前页面所属阶段的大纲）
  html += '<div class="bottom-nav-center">';
  if (outline) {
    html += '<a href="' + outline.file + '" class="bottom-nav-outline" aria-label="查看本阶段课程大纲（紧凑目录入口）">';
    html += '<span class="bottom-nav-outline-icon" aria-hidden="true">☰</span>';
    html += '<span class="bottom-nav-outline-text">大纲</span>';
    html += '</a>';
  }
  html += '</div>';

  // 下一课
  html += '<div class="bottom-nav-side">';
  if (next) {
    html += '<a href="' + next.file + '" class="bottom-nav-card bottom-nav-next">';
    html += '<span class="bottom-nav-label">下一课 →</span>';
    html += '<span class="bottom-nav-title">' + next.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '</div>';

  nav = document.createElement('nav');
  nav.className = 'bottom-nav';
  nav.setAttribute('aria-label', '课程页脚导航（上一课 / 大纲 / 下一课）');
  nav.innerHTML = html;

  // 插入到 body 末尾（footer 之前）
  footer = document.querySelector('footer');
  if (footer) {
    document.body.insertBefore(nav, footer);
  } else {
    document.body.appendChild(nav);
  }
})();
