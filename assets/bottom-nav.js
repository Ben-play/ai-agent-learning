/**
 * 底部课程导航
 * - 卡片式上一课/下一课
 * - 显示课程标题
 * - 回到大纲按钮
 */
(function() {
  'use strict';

  const LESSONS = [
    { file: '0001-ai-agent-learning-path-overview.html', title: '学习路径总览', phase: '' },
    { file: '0002-phase1-python-outline.html', title: '第一阶段大纲', phase: '' },
    { file: '0004-L01-dev-environment-setup.html', title: '开发环境搭建', phase: '第一阶段' },
    { file: '0005-L02-python-runtime-and-modules.html', title: 'Python 运行机制与模块系统', phase: '第一阶段' },
    { file: '0006-L03-variables-types-data-structures.html', title: '变量、类型与数据结构', phase: '第一阶段' },
  ];

  const currentFile = window.location.pathname.split('/').pop();
  const idx = LESSONS.findIndex(l => l.file === currentFile);
  if (idx === -1) return;

  const prev = idx > 0 ? LESSONS[idx - 1] : null;
  const next = idx < LESSONS.length - 1 ? LESSONS[idx + 1] : null;

  let html = '<div class="bottom-nav-inner">';

  // 上一课
  html += '<div class="bottom-nav-side">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="bottom-nav-card bottom-nav-prev">';
    html += '<span class="bottom-nav-label">← 上一课</span>';
    html += '<span class="bottom-nav-title">' + prev.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  // 中间：回到大纲
  html += '<div class="bottom-nav-center">';
  html += '<a href="0002-phase1-python-outline.html" class="bottom-nav-outline">';
  html += '<span class="bottom-nav-outline-icon">☰</span>';
  html += '<span class="bottom-nav-outline-text">大纲</span>';
  html += '</a>';
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

  const nav = document.createElement('nav');
  nav.className = 'bottom-nav';
  nav.innerHTML = html;

  // 插入到 body 末尾（footer 之前）
  var footer = document.querySelector('footer');
  if (footer) {
    document.body.insertBefore(nav, footer);
  } else {
    document.body.appendChild(nav);
  }
})();
