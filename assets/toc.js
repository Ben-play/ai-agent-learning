/**
 * 侧边目录（TOC）
 * - 从 <main> 内的 <h2> 生成锚点目录，注入到 <aside class="toc" id="toc" aria-label="页面目录">
 * - 视觉样式统一维护在 style.css（.toc / .toc-title / .toc nav a 等规则）
 * - 当前章节判定：getBoundingClientRect + sticky 顶栏偏移量为主，IntersectionObserver 兜底
 *   （覆盖迟加载内容改变高度的情况），hashchange/resize 均重新计算，rAF 节流滚动事件
 */
(function () {
  'use strict';

  var toc = document.getElementById('toc');
  if (!toc) return;

  var main = document.querySelector('main') || document.body;

  function build() {
    var headings = Array.prototype.slice.call(main.querySelectorAll('h2'));
    if (headings.length < 2) { toc.hidden = true; return; } // 章节太少就不显示
    toc.hidden = false;

    var nav = document.createElement('nav');
    nav.setAttribute('aria-label', '本课目录');

    var title = document.createElement('div');
    title.className = 'toc-title';
    title.textContent = '本课目录';
    nav.appendChild(title);

    var links = [];
    headings.forEach(function (h, i) {
      if (!h.id) h.id = 'sec-' + (i + 1);
      var a = document.createElement('a');
      a.href = '#' + h.id;
      a.textContent = h.textContent.trim();
      nav.appendChild(a);
      links.push(a);
    });

    toc.innerHTML = '';
    toc.appendChild(nav);

    setupScrollSpy(headings, links);
  }

  function setupScrollSpy(headings, links) {
    var rootPx = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    var offsetRem = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue('--scroll-anchor-offset')
    ) || 5; // 变量按 rem 定义，兜底 5rem
    var offset = offsetRem * rootPx;

    var currentIdx = -1;
    var ticking = false;

    function setActive(idx) {
      if (idx === currentIdx) return;
      currentIdx = idx;
      links.forEach(function (a, i) {
        if (i === idx) {
          a.classList.add('active');
          a.setAttribute('aria-current', 'location');
        } else {
          a.classList.remove('active');
          a.removeAttribute('aria-current');
        }
      });
    }

    function computeActive() {
      var doc = document.documentElement;
      var atBottom = window.innerHeight + window.scrollY >= doc.scrollHeight - 2;
      if (atBottom) {
        setActive(headings.length - 1);
        return;
      }
      var pos = offset + 8;
      var idx = 0;
      for (var i = 0; i < headings.length; i++) {
        if (headings[i].getBoundingClientRect().top <= pos) idx = i;
      }
      setActive(idx);
    }

    function onScrollOrResize() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        computeActive();
        ticking = false;
      });
    }

    window.addEventListener('scroll', onScrollOrResize, { passive: true });
    window.addEventListener('resize', onScrollOrResize);
    window.addEventListener('hashchange', onScrollOrResize);

    // IntersectionObserver 兜底：迟加载内容（图片/字体）改变布局高度时也能重新判定
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function () { onScrollOrResize(); }, {
        rootMargin: '-' + Math.round(offset) + 'px 0px -60% 0px',
        threshold: 0,
      });
      headings.forEach(function (h) { io.observe(h); });
    }

    // 首屏：等一帧布局稳定后再计算一次，兼容首次渲染时机不定的情况
    requestAnimationFrame(function () {
      requestAnimationFrame(computeActive);
    });

    // 带 hash 进入时，滚动就位后重新计算高亮
    if (window.location.hash) {
      setTimeout(computeActive, 50);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();
