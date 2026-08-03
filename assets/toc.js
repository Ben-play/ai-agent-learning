/**
 * 响应式课程目录
 * - 桌面端：固定侧边 TOC + 当前章节高亮
 * - 手机端：由课程 Dock 打开的可访问底部抽屉
 */
(function () {
  'use strict';

  var toc = document.getElementById('toc');
  if (!toc) return;

  var main = document.querySelector('main') || document.body;
  var phoneQuery = window.matchMedia('(max-width: 640px)');
  var toggle = null;
  var backdrop = null;
  var closeButton = null;
  var sheetOpen = false;
  var previousFocus = null;
  var scrollY = 0;

  function courseBarOffset() {
    var bar = document.querySelector('.course-bar');
    if (bar) return Math.ceil(bar.getBoundingClientRect().height);
    return 80;
  }

  function focusableElements() {
    return Array.prototype.slice.call(toc.querySelectorAll(
      'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
    )).filter(function (element) {
      return !element.hidden && element.getAttribute('aria-hidden') !== 'true';
    });
  }

  function unlockPage() {
    document.documentElement.classList.remove('mobile-toc-open');
    document.body.style.removeProperty('position');
    document.body.style.removeProperty('top');
    document.body.style.removeProperty('width');
    window.scrollTo(0, scrollY);
  }

  function closeSheet(restoreFocus) {
    if (!sheetOpen) return;
    sheetOpen = false;
    toc.classList.remove('is-mobile-open');
    toc.removeAttribute('role');
    toc.removeAttribute('aria-modal');
    if (backdrop) {
      backdrop.classList.remove('is-open');
      backdrop.hidden = true;
    }
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    unlockPage();
    if (restoreFocus !== false && previousFocus && previousFocus.focus) previousFocus.focus();
  }

  function openSheet() {
    var focusable;
    if (!phoneQuery.matches || !toggle || toggle.disabled || sheetOpen) return;
    sheetOpen = true;
    previousFocus = document.activeElement;
    scrollY = window.scrollY || document.documentElement.scrollTop || 0;
    document.documentElement.classList.add('mobile-toc-open');
    document.body.style.position = 'fixed';
    document.body.style.top = '-' + scrollY + 'px';
    document.body.style.width = '100%';
    toc.classList.add('is-mobile-open');
    toc.setAttribute('role', 'dialog');
    toc.setAttribute('aria-modal', 'true');
    if (backdrop) {
      backdrop.hidden = false;
      backdrop.classList.add('is-open');
    }
    toggle.setAttribute('aria-expanded', 'true');
    focusable = focusableElements();
    (toc.querySelector('a.active') || focusable[0] || toc).focus();
  }

  function setupMobileSheet() {
    toggle = document.querySelector('[data-mobile-toc-toggle]');
    if (!toggle) return;

    closeButton = toc.querySelector('[data-mobile-toc-close]');
    backdrop = document.querySelector('[data-mobile-toc-backdrop]');
    if (!backdrop) {
      backdrop = document.createElement('button');
      backdrop.type = 'button';
      backdrop.className = 'mobile-toc-backdrop';
      backdrop.setAttribute('data-mobile-toc-backdrop', '');
      backdrop.setAttribute('aria-label', '关闭课程目录');
      backdrop.hidden = true;
      document.body.appendChild(backdrop);
    }

    toggle.addEventListener('click', openSheet);
    if (closeButton) closeButton.addEventListener('click', function () { closeSheet(true); });
    backdrop.addEventListener('click', function () { closeSheet(true); });
    toc.addEventListener('click', function (event) {
      var link = event.target.closest('a');
      if (link) closeSheet(link.getAttribute('href').charAt(0) === '#');
    });
    toc.addEventListener('keydown', function (event) {
      var focusable;
      var first;
      var last;
      if (!sheetOpen) return;
      if (event.key === 'Escape') {
        event.preventDefault();
        closeSheet(true);
        return;
      }
      if (event.key !== 'Tab') return;
      focusable = focusableElements();
      if (!focusable.length) return;
      first = focusable[0];
      last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });

    function onBreakpointChange(event) {
      if (!event.matches) closeSheet(false);
    }
    if (typeof phoneQuery.addEventListener === 'function') {
      phoneQuery.addEventListener('change', onBreakpointChange);
    } else if (typeof phoneQuery.addListener === 'function') {
      phoneQuery.addListener(onBreakpointChange);
    }
  }

  function setupScrollSpy(headings, links) {
    var currentIdx = -1;
    var ticking = false;

    function setActive(idx) {
      if (idx === currentIdx) return;
      currentIdx = idx;
      links.forEach(function (link, index) {
        if (index === idx) {
          link.classList.add('active');
          link.setAttribute('aria-current', 'location');
        } else {
          link.classList.remove('active');
          link.removeAttribute('aria-current');
        }
      });
    }

    function computeActive() {
      var doc = document.documentElement;
      var atBottom = window.innerHeight + window.scrollY >= doc.scrollHeight - 2;
      var position = courseBarOffset() + 8;
      var index = 0;
      var i;
      if (atBottom) {
        setActive(headings.length - 1);
        return;
      }
      for (i = 0; i < headings.length; i += 1) {
        if (headings[i].getBoundingClientRect().top <= position) index = i;
      }
      setActive(index);
    }

    function scheduleCompute() {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(function () {
        computeActive();
        ticking = false;
      });
    }

    window.addEventListener('scroll', scheduleCompute, { passive: true });
    window.addEventListener('resize', scheduleCompute, { passive: true });
    window.addEventListener('hashchange', scheduleCompute);

    if ('IntersectionObserver' in window) {
      var observer = new IntersectionObserver(scheduleCompute, {
        rootMargin: '-' + courseBarOffset() + 'px 0px -60% 0px',
        threshold: 0
      });
      headings.forEach(function (heading) { observer.observe(heading); });
    }

    requestAnimationFrame(function () { requestAnimationFrame(computeActive); });
    if (window.location.hash) window.setTimeout(computeActive, 50);
  }

  function build() {
    var headings = Array.prototype.slice.call(main.querySelectorAll('h2'));
    var nav;
    var header;
    var title;
    var links = [];
    var context;
    var outline;

    toggle = document.querySelector('[data-mobile-toc-toggle]');
    if (headings.length < 2) {
      toc.hidden = true;
      if (toggle) {
        toggle.disabled = true;
        toggle.setAttribute('aria-disabled', 'true');
      }
      return;
    }
    toc.hidden = false;

    header = document.createElement('div');
    header.className = 'toc-mobile-header';
    title = document.createElement('strong');
    title.className = 'toc-mobile-title';
    title.textContent = '本课目录';
    closeButton = document.createElement('button');
    closeButton.type = 'button';
    closeButton.className = 'toc-mobile-close';
    closeButton.setAttribute('data-mobile-toc-close', '');
    closeButton.setAttribute('aria-label', '关闭课程目录');
    closeButton.textContent = '×';
    header.appendChild(title);
    header.appendChild(closeButton);

    nav = document.createElement('nav');
    nav.setAttribute('aria-label', '本课目录');
    title = document.createElement('div');
    title.className = 'toc-title';
    title.textContent = '本课目录';
    nav.appendChild(title);

    if (window.CourseCatalog && typeof window.CourseCatalog.context === 'function') {
      context = window.CourseCatalog.context(window.location.pathname);
      outline = context && context.outline;
      if (outline) {
        var outlineLink = document.createElement('a');
        outlineLink.className = 'toc-outline-link';
        outlineLink.href = outline.file;
        outlineLink.textContent = '查看本阶段大纲';
        nav.appendChild(outlineLink);
      }
    }

    headings.forEach(function (heading, index) {
      var link;
      if (!heading.id) heading.id = 'sec-' + (index + 1);
      link = document.createElement('a');
      link.href = '#' + heading.id;
      link.textContent = heading.textContent.trim();
      nav.appendChild(link);
      links.push(link);
    });

    toc.innerHTML = '';
    toc.tabIndex = -1;
    toc.appendChild(header);
    toc.appendChild(nav);
    setupScrollSpy(headings, links);
    setupMobileSheet();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build, { once: true });
  } else {
    build();
  }
})();
