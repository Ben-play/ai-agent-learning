/**
 * 内容增强工具 · content-tools.js
 *
 * 渐进式、幂等地增强既有静态内容，不要求逐页手改：
 * 1) Callout：为装饰性图标注入 aria-hidden 图标，并为 .interview-box 注入真实
 *    DOM 标签「面试覆盖：」（供屏幕阅读器朗读），不改动作者原文本节点。
 * 2) 代码块：为每个未被包裹的 <pre> 包一层技术块外壳，加可见标签
 *    （默认「代码示例」，若显式指定 data-lang/data-label 则用其值）+ 复制按钮
 *    （带 aria-label 与 polite 状态播报），保留代码文本与可选中性不变。
 * 3) 横向滚动：为表格与 pre 增加安全滚动容器；仅在真正发生横向溢出时才
 *    赋予 tabindex/aria-label，并在 resize 时重新判定。
 * 4) 全程可重复执行（DOMContentLoaded 多次触发 / 热重载）不会产生嵌套包裹。
 *
 * 无构建、无外部依赖，可直接以 file:// 打开页面执行。
 */
(function () {
  'use strict';

  var DEFAULT_CODE_LABEL = '技术示例';
  var INTERVIEW_LABEL = '面试覆盖：';
  var EXERCISE_LABEL = '练习：';
  var TASK_LABEL = '实战任务';

  function ready(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  /* ---------- 1) Callout 图标 / interview-box 标签 ---------- */

  var CALLOUT_ICONS = {
    tip: '💡',
    info: 'ℹ️',
    warning: '⚠️',
    'why-box': '❓',
    'exercise-box': '✏️',
    'best-practice-point': '✓'
  };

  function enhanceCallouts(root) {
    Object.keys(CALLOUT_ICONS).forEach(function (cls) {
      var nodes = root.querySelectorAll('.' + cls + ':not([data-icon-injected])');
      nodes.forEach(function (el) {
        el.setAttribute('data-icon-injected', '1');
        var icon = document.createElement('span');
        icon.className = 'callout-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = CALLOUT_ICONS[cls] + ' ';
        el.insertBefore(icon, el.firstChild);
      });
    });

    var labelledCallouts = [
      { selector: '.interview-box', icon: '🎯 ', label: INTERVIEW_LABEL },
      { selector: '.exercise', icon: '🏋️ ', label: EXERCISE_LABEL },
      { selector: '.task-box', icon: '🎯 ', label: TASK_LABEL }
    ];
    labelledCallouts.forEach(function (config) {
      var nodes = root.querySelectorAll(config.selector + ':not([data-label-injected])');
      nodes.forEach(function (el) {
        el.setAttribute('data-label-injected', '1');
        var icon = document.createElement('span');
        icon.className = 'callout-icon';
        icon.setAttribute('aria-hidden', 'true');
        icon.textContent = config.icon;
        var label = document.createElement('span');
        label.className = 'callout-label';
        label.textContent = config.label;
        el.insertBefore(label, el.firstChild);
        el.insertBefore(icon, el.firstChild);
      });
    });
  }

  /* ---------- 2) 代码块增强 ---------- */

  function getClipboardText(preEl) {
    // 保留原始文本（含空白/换行），不做任何裁剪
    return preEl.textContent;
  }

  function fallbackCopy(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '-1000px';
    ta.style.left = '-1000px';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, text.length);
    var ok = false;
    try {
      ok = document.execCommand('copy');
    } catch (e) {
      ok = false;
    }
    document.body.removeChild(ta);
    return ok;
  }

  function copyText(text) {
    // file:// 下 navigator.clipboard 常不可用/被拒绝，需健壮回退
    if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text).catch(function () {
        return fallbackCopy(text);
      });
    }
    return Promise.resolve(fallbackCopy(text));
  }

  function makeStatusEl() {
    var status = document.createElement('span');
    status.className = 'copy-status';
    status.setAttribute('role', 'status');
    status.setAttribute('aria-live', 'polite');
    return status;
  }

  var COPY_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
      '<rect x="8" y="8" width="11" height="11" rx="2"></rect>' +
      '<path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"></path>' +
    '</svg>';
  var CHECK_ICON =
    '<svg viewBox="0 0 24 24" aria-hidden="true">' +
      '<path d="m5 12 4 4L19 6"></path>' +
    '</svg>';

  function enhanceCodeBlocks(root) {
    var pres = root.querySelectorAll('pre:not([data-tech-enhanced])');
    pres.forEach(function (pre) {
      // 已被包裹过（重复执行场景）则跳过，避免嵌套
      if (pre.closest('.tech-block')) {
        pre.setAttribute('data-tech-enhanced', '1');
        return;
      }
      pre.setAttribute('data-tech-enhanced', '1');

      var label = pre.getAttribute('data-label') || pre.getAttribute('data-lang') || DEFAULT_CODE_LABEL;

      var wrapper = document.createElement('div');
      wrapper.className = 'tech-block';

      var head = document.createElement('div');
      head.className = 'tech-block-head';

      var labelEl = document.createElement('span');
      labelEl.className = 'tech-block-label';
      labelEl.textContent = label;

      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'copy-btn';
      btn.setAttribute('aria-label', '复制技术示例');
      btn.setAttribute('title', '复制');
      btn.innerHTML = COPY_ICON;

      var toast = document.createElement('span');
      toast.className = 'copy-toast';
      toast.setAttribute('aria-hidden', 'true');

      var action = document.createElement('span');
      action.className = 'copy-action';
      action.appendChild(toast);
      action.appendChild(btn);

      var status = makeStatusEl();

      head.appendChild(labelEl);
      head.appendChild(action);
      head.appendChild(status);

      var parent = pre.parentNode;
      parent.insertBefore(wrapper, pre);
      wrapper.appendChild(head);
      wrapper.appendChild(pre);

      btn.addEventListener('click', function () {
        var text = getClipboardText(pre);
        copyText(text).then(function (ok) {
          if (ok === false) {
            status.textContent = '复制失败，请手动选择复制';
            return;
          }
          btn.classList.add('copied');
          btn.setAttribute('aria-label', '已复制');
          btn.setAttribute('title', '已复制');
          btn.innerHTML = CHECK_ICON;
          toast.textContent = '已复制';
          toast.classList.add('show');
          status.textContent = '已复制到剪贴板';
          setTimeout(function () {
            btn.classList.remove('copied');
            btn.setAttribute('aria-label', '复制技术示例');
            btn.setAttribute('title', '复制');
            btn.innerHTML = COPY_ICON;
            toast.classList.remove('show');
          }, 1800);
        });
      });
    });
  }

  /* ---------- 3) 横向滚动容器（表格 + 未被技术块包裹的独立场景） ---------- */

  function wrapForScroll(el, extraClass) {
    if (el.closest('.scroll-region')) return el.parentNode;
    var wrap = document.createElement('div');
    wrap.className = 'scroll-region' + (extraClass ? ' ' + extraClass : '');
    var parent = el.parentNode;
    parent.insertBefore(wrap, el);
    wrap.appendChild(el);
    return wrap;
  }

  function ensureScrollWrappers(root) {
    // 表格：直接包裹（表格外层没有其它专门壳）
    var tables = root.querySelectorAll('table:not([data-scroll-wrapped])');
    tables.forEach(function (table) {
      table.setAttribute('data-scroll-wrapped', '1');
      wrapForScroll(table, 'table-scroll-region');
    });

    // pre：横向滚动由 pre 自身承担，因此焦点与滚动落在同一元素；
    // tech-block/head 保持静止，避免键盘横向滚动时工具栏一起移动。
    var pres = root.querySelectorAll('pre:not([data-scroll-wrapped])');
    pres.forEach(function (pre) {
      pre.setAttribute('data-scroll-wrapped', '1');
      pre.classList.add('scroll-region');
    });
  }

  function updateOverflowState(root) {
    var regions = root.querySelectorAll('.scroll-region');
    regions.forEach(function (region) {
      // .scroll-region 本身就是实际的横向滚动器：表格场景是外层 wrapper，
      // 代码场景是 pre 本身。必须比较滚动器自身尺寸，不能比较内层 table
      // （table 的 scrollWidth/clientWidth 相等，即使其 wrapper 已经溢出）。
      var overflowing = region.scrollWidth > region.clientWidth + 1;
      if (overflowing) {
        if (!region.hasAttribute('tabindex')) {
          region.setAttribute('tabindex', '0');
          var isTable = !!region.querySelector('table');
          region.setAttribute('aria-label', isTable ? '表格内容，可横向滚动查看' : '代码内容，可横向滚动查看');
        }
        region.setAttribute('role', 'region');
        region.setAttribute('data-scrollable', '1');
      } else {
        region.removeAttribute('tabindex');
        region.removeAttribute('role');
        region.removeAttribute('aria-label');
        region.removeAttribute('data-scrollable');
      }
    });
  }

  var resizeTimer = null;
  function onResize() {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(function () {
      updateOverflowState(document);
    }, 150);
  }

  function onDetailsToggle(event) {
    var details = event.target;
    if (!details || details.tagName !== 'DETAILS') return;

    // closed <details> 中的 pre 在 DOMContentLoaded 时没有可测布局；展开后的下一帧
    // 仅重算该 details 内的滚动区，避免为一次局部交互扫描整页。
    requestAnimationFrame(function () {
      updateOverflowState(details);
    });
  }

  /* ---------- 4) 打印时展开可运行自检 ---------- */

  function installPrintDetailsHandlers() {
    // 脚本被重复加载时复用同一控制器，避免重复监听器覆盖首次 beforeprint 的状态。
    var controllerKey = '__aiCourseBpPrintController';
    if (window[controllerKey]) return;

    var controller = {
      checkStates: null
    };

    controller.beforePrint = function () {
      // 某些浏览器会为一次打印流程重复派发 beforeprint；只捕获首次状态。
      if (controller.checkStates !== null) return;

      controller.checkStates = [];
      var checks = document.querySelectorAll('details.bp-check');
      checks.forEach(function (details) {
        controller.checkStates.push({ element: details, open: details.open });
        if (!details.open) details.open = true;
      });
    };

    controller.afterPrint = function () {
      if (controller.checkStates === null) return;

      // 按快照恢复每个面板，而不是假定打印期间状态没有其它变化。
      controller.checkStates.forEach(function (state) {
        state.element.open = state.open;
      });
      controller.checkStates = null;
    };

    window[controllerKey] = controller;
    window.addEventListener('beforeprint', controller.beforePrint);
    window.addEventListener('afterprint', controller.afterPrint);
  }

  function run() {
    enhanceCallouts(document);
    enhanceCodeBlocks(document);
    ensureScrollWrappers(document);
    updateOverflowState(document);
  }

  ready(function () {
    run();
    installPrintDetailsHandlers();
    window.addEventListener('resize', onResize);
    // toggle 不会在所有浏览器中可靠冒泡；捕获阶段委托保证动态/既有 details 均可处理。
    document.addEventListener('toggle', onDetailsToggle, true);
  });
})();
