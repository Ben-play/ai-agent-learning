/**
 * 「回到顶部」组件 · 带滚动进度环
 *
 * - 森林绿圆形按钮 + 向上箭头，风格贴合课程暖色编辑风
 * - 外圈 SVG 环随页面滚动进度填充（按钮兼作阅读进度指示）
 * - 滚动超过阈值才淡入；点击平滑滚回顶部（尊重 prefers-reduced-motion）
 * - 叠放在主题切换按钮之上，移动端同步收拢；不与右侧 TOC 冲突
 * - 无障碍：真实 <button> + aria-label + title；键盘原生可用
 * - 自注入样式与 DOM，作为共享组件被各页面 <script> 引入即可
 */
(function () {
  'use strict';

  var SHOW_AT = 400;      // 滚动超过多少 px 才显示
  var R = 20;             // 进度环半径
  var CIRC = 2 * Math.PI * R;

  var CSS = `
  .to-top{
    /* 与主题切换共用同一套 offset/size token，二者堆叠时用 --control-size + --control-gap 精确算出叠放高度，
       避免各自硬编码数字导致间距在响应式断点上跑偏；同时叠加安全区，兼容刘海屏/手势条 */
    position:fixed;
    right:calc(var(--control-offset-x, 2rem) + var(--safe-x, env(safe-area-inset-right, 0px)));
    bottom:calc(var(--control-offset-y, 2rem) + var(--safe-y, env(safe-area-inset-bottom, 0px)) + var(--control-size, 3rem) + var(--control-gap, .85rem));
    width:var(--control-size, 3rem); height:var(--control-size, 3rem); z-index:60;
    display:grid; place-items:center;
    border:none; padding:0; cursor:pointer;
    background:transparent;
    opacity:0; transform:translateY(12px) scale(.85);
    pointer-events:none;
    transition:opacity .35s ease, transform .35s cubic-bezier(.34,1.56,.64,1);
  }
  .to-top.show{ opacity:1; transform:none; pointer-events:auto; }

  /* 进度环 */
  .to-top svg{ position:absolute; inset:0; width:100%; height:100%; transform:rotate(-90deg); }
  .to-top .ring-track{ fill:none; stroke:var(--accent-subtle, #E8E4DA); stroke-width:2.5; }
  .to-top .ring-fill{
    fill:none; stroke:var(--accent-bright, #D97706); stroke-width:2.5; stroke-linecap:round;
    stroke-dasharray:${CIRC.toFixed(2)};
    stroke-dashoffset:${CIRC.toFixed(2)};
    filter:drop-shadow(0 0 2px color-mix(in srgb, var(--accent-bright,#D97706) 45%, transparent));
    transition:stroke-dashoffset .1s linear;
  }
  /* 中央圆盘 + 箭头 —— 浅色默认为"纸片"感（浅底 + 森林绿箭头 + 细边），不再是深色块 */
  .to-top .disc{
    position:relative; z-index:1;
    width:2.35rem; height:2.35rem; border-radius:50%;
    display:grid; place-items:center;
    background:linear-gradient(160deg, var(--tt-disc-hi, #FFFFFF), var(--tt-disc-lo, #F1EDE3));
    color:var(--tt-arrow, #1A3A2A);
    box-shadow:0 0 0 1.5px var(--tt-edge, var(--border, #D6D3D1)),
               var(--shadow-md, 0 2px 8px rgba(0,0,0,.12)),
               inset 0 1px 0 color-mix(in srgb, #fff 60%, transparent);
    transition:background .2s, color .2s, transform .2s, box-shadow .25s;
  }
  .to-top .disc svg{ position:static; width:1.05rem; height:1.05rem; transform:none; stroke:currentColor; }
  /* hover：浅色下"填"成森林绿盘 + 奶油箭头（浅→彩的满足感）+ 琥珀光晕 + 轻抬 */
  .to-top:hover .disc{
    background:linear-gradient(160deg, var(--tt-hi-hover, #234A34), var(--tt-lo-hover, #16301F));
    color:var(--tt-arrow-hover, #F8F6F1);
    transform:translateY(-2px);
    box-shadow:0 0 0 1.5px transparent,
               var(--shadow-lg, 0 4px 16px rgba(0,0,0,.2)),
               0 0 0 4px color-mix(in srgb, var(--accent-bright,#D97706) 22%, transparent),
               inset 0 1px 0 color-mix(in srgb, #fff 20%, transparent);
  }
  .to-top:hover .arrow{ animation:tt-bob .7s ease infinite; }
  .to-top:focus-visible{ outline:none; }
  .to-top:focus-visible .disc{ box-shadow:0 0 0 3px color-mix(in srgb, var(--accent-bright,#D97706) 55%, transparent); }

  /* 深色模式：静止态本就用深盘，浅→彩的逻辑反过来 —— 深绿盘 + 薄荷箭头（对比正确） */
  [data-theme="dark"] .to-top{
    --tt-disc-hi:#1F3A2B; --tt-disc-lo:#14251B; --tt-arrow:#8FF0C4; --tt-edge:#2E4B3A;
    --tt-hi-hover:#264A35; --tt-lo-hover:#193322; --tt-arrow-hover:#B8F5D6;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]) .to-top{
      --tt-disc-hi:#1F3A2B; --tt-disc-lo:#14251B; --tt-arrow:#8FF0C4; --tt-edge:#2E4B3A;
      --tt-hi-hover:#264A35; --tt-lo-hover:#193322; --tt-arrow-hover:#B8F5D6;
    }
  }

  @keyframes tt-bob{ 0%,100%{transform:translateY(0)} 50%{transform:translateY(-2.5px)} }

  @media (min-width:641px) and (max-width:900px){
    .to-top{
      right:calc(var(--control-offset-x-tablet, 1.5rem) + var(--safe-x, env(safe-area-inset-right, 0px)));
      bottom:calc(var(--control-offset-y-tablet, 1.6rem) + var(--safe-y, env(safe-area-inset-bottom, 0px)) + var(--control-size-tablet, 2.8rem) + var(--control-gap, .85rem));
      width:var(--control-size-tablet, 2.8rem); height:var(--control-size-tablet, 2.8rem);
    }
    .to-top .disc{ width:2.15rem; height:2.15rem; }
  }
  @media (max-width:640px){
    .to-top{
      right:calc(var(--control-offset-x-phone, 1.2rem) + var(--safe-x, env(safe-area-inset-right, 0px)));
      bottom:calc(var(--mobile-course-nav-inset, 0px) + var(--control-offset-y-phone, 1.2rem) + max(var(--control-size-phone, 2.6rem), var(--tap-target, 44px)) + var(--control-gap, .85rem));
      width:max(var(--control-size-phone, 2.6rem), var(--tap-target, 44px)); height:max(var(--control-size-phone, 2.6rem), var(--tap-target, 44px));
    }
    .to-top .disc{ width:2rem; height:2rem; }
  }
  @media print{
    .to-top{ display:none !important; }
  }
  @media (prefers-reduced-motion:reduce){
    .to-top, .to-top .disc, .to-top .ring-fill{ transition:none; }
    .to-top:hover .arrow{ animation:none; }
  }
  `;
  var style = document.createElement('style');
  style.textContent = CSS;
  document.head.appendChild(style);

  function build() {
    var btn = document.createElement('button');
    btn.className = 'to-top';
    btn.type = 'button';
    btn.setAttribute('aria-label', '回到顶部');
    btn.setAttribute('title', '回到顶部');
    btn.innerHTML =
      '<svg viewBox="0 0 44 44" aria-hidden="true">' +
        '<circle class="ring-track" cx="22" cy="22" r="' + R + '"></circle>' +
        '<circle class="ring-fill" cx="22" cy="22" r="' + R + '"></circle>' +
      '</svg>' +
      '<span class="disc">' +
        '<svg class="arrow" viewBox="0 0 24 24" fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' +
          '<path d="M12 19V5M5 12l7-7 7 7"></path>' +
        '</svg>' +
      '</span>';

    var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    btn.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    });
    document.body.appendChild(btn);

    var fill = btn.querySelector('.ring-fill');
    var ticking = false;

    function update() {
      ticking = false;
      var doc = document.documentElement;
      var scrolled = window.scrollY || doc.scrollTop;
      var max = (doc.scrollHeight - window.innerHeight) || 1;
      var pct = Math.min(1, Math.max(0, scrolled / max));
      fill.style.strokeDashoffset = (CIRC * (1 - pct)).toFixed(2);
      btn.classList.toggle('show', scrolled > SHOW_AT);
    }
    function onScroll() {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    }
    window.addEventListener('scroll', onScroll, { passive: true });
    window.addEventListener('resize', onScroll, { passive: true });
    update();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', build);
  } else {
    build();
  }
})();
