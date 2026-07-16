/**
 * 总览页 · 阶段折叠/展开
 * - button.phase-header 是真实可聚焦的按钮，点击时切换所属 .phase 的 collapsed class
 *   （驱动 style.css 里已有的折叠视觉），并同步 aria-expanded
 * - 仅总览页（0001）引入，其余页面无 .phase-header 时什么也不做
 */
(function () {
  'use strict';

  var headers = document.querySelectorAll('.phase-header');
  if (!headers.length) return;

  headers.forEach(function (btn) {
    btn.addEventListener('click', function () {
      var phase = btn.closest('.phase');
      if (!phase) return;
      var collapsed = phase.classList.toggle('collapsed');
      btn.setAttribute('aria-expanded', String(!collapsed));
    });
  });
})();
