/**
 * 侧边目录（TOC）
 * - 自动从 <main> 内的 <h2> 生成锚点目录，注入到 <aside class="toc" id="toc">
 * - 固定在右侧，滚动高亮当前章节；窄屏自动隐藏
 * - .toc 在 style.css 中无样式，故本脚本自带极简样式
 */
(function () {
  'use strict';

  var toc = document.getElementById('toc');
  if (!toc) return;

  var main = document.querySelector('main') || document.body;
  var headings = Array.prototype.slice.call(main.querySelectorAll('h2'));
  if (headings.length < 2) return;   // 章节太少就不显示

  var css = [
    '.toc { position: fixed; top: 50%; right: 1rem; transform: translateY(-50%);',
    '  max-width: 220px; max-height: 70vh; overflow-y: auto; padding: 0.75rem 0.9rem;',
    '  font-size: 0.82rem; line-height: 1.5; border-radius: 12px;',
    '  background: var(--card-bg, rgba(255,255,255,0.9)); backdrop-filter: blur(6px);',
    '  border: 1px solid var(--border, #e5e7eb); box-shadow: 0 4px 16px rgba(0,0,0,0.08);',
    '  z-index: 50; }',
    '.toc-title { font-weight: 700; font-size: 0.72rem; letter-spacing: 0.05em;',
    '  text-transform: uppercase; color: var(--muted, #6b7280); margin-bottom: 0.5rem; }',
    '.toc a { display: block; padding: 0.2rem 0; color: var(--muted, #6b7280);',
    '  text-decoration: none; border-left: 2px solid transparent; padding-left: 0.6rem;',
    '  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }',
    '.toc a:hover { color: var(--accent-bright, #4f46e5); }',
    '.toc a.active { color: var(--accent-bright, #4f46e5); border-left-color: var(--accent-bright, #4f46e5); font-weight: 600; }',
    '@media (max-width: 1100px) { .toc { display: none; } }'
  ].join('\n');
  var style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // 给每个 h2 补 id（若无），并构建目录
  var links = [];
  var html = '<div class="toc-title">本课目录</div>';
  headings.forEach(function (h, i) {
    if (!h.id) h.id = 'sec-' + (i + 1);
    html += '<a href="#' + h.id + '">' + h.textContent.trim() + '</a>';
  });
  toc.innerHTML = html;
  links = Array.prototype.slice.call(toc.querySelectorAll('a'));

  // 滚动高亮（scroll-spy）
  function onScroll() {
    var pos = window.scrollY + 120;
    var currentIdx = 0;
    for (var i = 0; i < headings.length; i++) {
      if (headings[i].offsetTop <= pos) currentIdx = i;
    }
    links.forEach(function (a, i) {
      a.classList.toggle('active', i === currentIdx);
    });
  }

  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
})();
