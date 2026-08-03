/**
 * 交互测验 · 「即答即批」精致版（v4 · 无障碍加强版）
 *
 * 变化（相对 v3）：
 *   · radiogroup 通过生成的唯一 ID 与 .quiz-question 建立 aria-labelledby 关联
 *   · 真正的 roving tabindex：首个可聚焦选项 tabindex=0，其余为 -1；
 *     方向键 / Home / End 只移动焦点，不做选择；Enter/Space 走原生 click 判分
 *   · 通过生成的稳定 ID 将题目与 radiogroup、解析与已判分组关联
 *   · 判分结果不仅靠颜色：为作答项和揭示的正确答案追加仅供屏幕阅读器读取的状态文本，
 *     同时保留 aria-checked 仅表示用户实际选择的单个 radio
 *   · 避免重复播报：q-key/q-mark 装饰性符号 aria-hidden，动态结果只由 verdict 播报一次
 *   · 重试重置所有状态与 tabindex，并聚焦回第一个选项
 *
 * 不改任何课程 HTML —— 复用 DOM 契约：
 *   .quiz > .quiz-question / .quiz-options > button[data-answer="correct|wrong"] / .quiz-explanation
 */
(function () {
  'use strict';

  var CSS = `
  .quiz{
    --q-ok: var(--success, #16A34A);
    --q-ok-soft: color-mix(in srgb, var(--success,#16A34A) 12%, var(--card-bg,#fff));
    --q-no:#B4530E;
    --q-no-soft: color-mix(in srgb, #B4530E 10%, var(--card-bg,#fff));
    --q-amber: var(--accent-bright, #D97706);
    position:relative;
    margin:1.7rem 0;
    padding:1.25rem 1.3rem 1.15rem;
    border:1px solid var(--border, #D6D3D1);
    border-radius:var(--radius-lg, 14px);
    background:
      radial-gradient(140% 120% at 100% 0%, color-mix(in srgb, var(--q-amber) 5%, transparent), transparent 55%),
      var(--card-bg, #fff);
    box-shadow:var(--shadow-sm, 0 1px 2px rgba(0,0,0,.04));
  }
  .quiz::after{                       /* 卷角暗纹 */
    content:"";position:absolute;top:0;right:0;width:30px;height:30px;
    border-radius:0 var(--radius-lg,14px) 0 0;
    background:linear-gradient(225deg, color-mix(in srgb, var(--q-amber) 20%, transparent) 0 50%, transparent 50%);
    opacity:.45;pointer-events:none;
  }

  .quiz-question{
    display:flex;align-items:baseline;gap:.55rem;min-width:0;
    overflow-wrap:anywhere;word-break:break-word;
    font-weight:600;font-size:1rem;line-height:1.6;
    margin-bottom:.95rem;color:var(--fg, #1C1917);
  }
  .quiz-q{
    flex:none;display:inline-flex;align-items:center;justify-content:center;
    min-width:1.55rem;height:1.55rem;padding:0 .45rem;
    font:700 .72rem/1 var(--font-mono,monospace);
    color:#fff;background:var(--accent, #1A3A2A);
    border-radius:var(--radius-pill,999px);transform:translateY(1px);
  }

  .quiz-options{display:flex;flex-direction:column;gap:.5rem;margin:0;}

  .quiz-option{
    position:relative;display:flex;align-items:center;gap:.75rem;
    width:100%;text-align:left;overflow:hidden;
    padding:.75rem 1rem .75rem .9rem;
    font-size:.94rem;line-height:1.45;color:var(--fg-soft, #44403C);
    background:var(--card-bg,#fff);
    border:1.5px solid var(--border, #D6D3D1);
    border-radius:var(--radius-md,10px);
    cursor:pointer;
    transition:border-color .2s, background .2s, color .2s, transform .12s, box-shadow .2s;
  }
  /* 左侧强调条（判分后出现） */
  .quiz-option::before{
    content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
    background:transparent;transition:background .2s;
  }
  /* 字母徽章 A/B/C/D → 判分后变 ✓/✗ 容器 */
  .quiz-option .q-key{
    flex:none;display:inline-flex;align-items:center;justify-content:center;
    width:1.55rem;height:1.55rem;font:600 .8rem/1 var(--font-mono,monospace);
    color:var(--muted,#78716C);background:var(--bg-warm,#F3F0E8);
    border-radius:8px;transition:background .2s, color .2s, transform .25s cubic-bezier(.34,1.56,.64,1);
  }
  .quiz-option .q-text{flex:1 1 auto;min-width:0;overflow-wrap:anywhere;word-break:break-word;}
  .quiz-option .q-status{
    position:absolute;width:1px;height:1px;padding:0;margin:-1px;
    overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0;
  }
  /* 右侧箭头提示（未答时 hover 显现） */
  .quiz-option .q-mark{
    flex:none;margin-left:.25rem;font-size:1rem;color:var(--muted,#78716C);
    opacity:0;transform:translateX(-4px);transition:opacity .2s, transform .2s, color .2s;
  }

  .quiz:not(.graded) .quiz-option:hover{
    border-color:var(--q-amber);
    background:var(--accent-light, #FEF3C7);
    transform:translateY(-1px);
    box-shadow:var(--shadow-md,0 2px 8px rgba(0,0,0,.07));
  }
  .quiz:not(.graded) .quiz-option:hover .q-key{background:var(--q-amber);color:#fff;transform:scale(1.05);}
  .quiz:not(.graded) .quiz-option:hover .q-mark{opacity:.7;transform:none;}
  .quiz:not(.graded) .quiz-option:hover .q-mark::before{content:"→";}
  .quiz-option:focus-visible{outline:none;box-shadow:0 0 0 3px color-mix(in srgb, var(--q-amber) 42%, transparent);}

  /* ---------- 判分后 ---------- */
  .quiz.graded .quiz-option{cursor:default;}
  .quiz.graded .quiz-option:not(.correct):not(.wrong){opacity:.42;filter:saturate(.6);}

  .quiz-option.correct{border-color:color-mix(in srgb, var(--q-ok) 55%, var(--border));background:var(--q-ok-soft);color:var(--fg,#1C1917);}
  .quiz-option.correct::before{background:var(--q-ok);}
  .quiz-option.correct .q-key{background:var(--q-ok);color:#fff;}
  .quiz-option.correct .q-mark{opacity:1;transform:none;color:var(--q-ok);font-weight:700;}

  .quiz-option.wrong{border-color:color-mix(in srgb, var(--q-no) 55%, var(--border));background:var(--q-no-soft);color:var(--fg,#1C1917);}
  .quiz-option.wrong::before{background:var(--q-no);}
  .quiz-option.wrong .q-key{background:var(--q-no);color:#fff;}
  .quiz-option.wrong .q-mark{opacity:1;transform:none;color:var(--q-no);font-weight:700;}

  /* 页脚：结果语 + 再试一次（仅判分后出现） */
  .quiz-foot{
    display:none;align-items:center;gap:.9rem;margin-top:1rem;flex-wrap:wrap;
  }
  .quiz.graded .quiz-foot{display:flex;}
  .quiz-verdict{
    font-size:.92rem;font-weight:600;display:inline-flex;align-items:center;gap:.45rem;
    opacity:0;transform:translateX(-5px);transition:opacity .35s .05s, transform .35s .05s;
  }
  .quiz.graded .quiz-verdict{opacity:1;transform:none;}
  .quiz-verdict.ok{color:var(--q-ok);}
  .quiz-verdict.no{color:var(--q-no);}
  .quiz-retry{
    appearance:none;cursor:pointer;margin-left:auto;
    font:600 .82rem/1 var(--font-body,sans-serif);
    padding:.5rem .95rem;border-radius:var(--radius-pill,999px);
    color:var(--muted,#78716C);background:transparent;
    border:1.5px solid var(--border,#D6D3D1);
    transition:color .18s, border-color .18s, transform .12s;
  }
  .quiz-retry:hover{color:var(--fg,#1C1917);border-color:var(--q-amber);transform:translateY(-1px);}
  .quiz-retry::before{content:"↺ ";}

  /* 解析批注：默认收起，判分后滑入 */
  .quiz-explanation{
    display:block;overflow:hidden;
    max-height:0;opacity:0;margin-top:0;padding:0 0 0 .95rem;
    border-left:3px solid transparent;
    font-size:.92rem;line-height:1.7;color:var(--fg-soft,#44403C);
    transition:max-height .45s ease, opacity .35s ease, margin-top .35s ease;
  }
  .quiz.graded .quiz-explanation{
    max-height:60rem;opacity:1;margin-top:1rem;
    border-left-color:var(--exp-rule, var(--q-amber));
  }
  .quiz-explanation .exp-label{
    display:block;font:700 .72rem/1 var(--font-body,sans-serif);
    letter-spacing:.14em;text-transform:uppercase;
    color:var(--exp-rule, var(--q-amber));margin-bottom:.45rem;
  }

  @media (prefers-reduced-motion: reduce){ .quiz *{transition:none !important;} }
  `;
  var styleEl = document.createElement('style');
  styleEl.textContent = CSS;
  document.head.appendChild(styleEl);

  var LETTERS = ['A', 'B', 'C', 'D', 'E', 'F'];
  var uidCounter = 0;
  function uid(prefix) {
    var id;
    do {
      uidCounter += 1;
      id = prefix + '-' + uidCounter;
    } while (document.getElementById(id));
    return id;
  }

  document.querySelectorAll('.quiz').forEach(function (quiz) {
    var optWrap = quiz.querySelector('.quiz-options');
    if (!optWrap) return;
    var options = Array.prototype.slice.call(optWrap.querySelectorAll('button'));
    if (!options.length) return;
    var explanation = quiz.querySelector('.quiz-explanation');
    var question = quiz.querySelector('.quiz-question');

    // 生成/沿用稳定 ID，供 aria 关联使用
    if (question && !question.id) question.id = uid('quiz-question');
    if (explanation && !explanation.id) explanation.id = uid('quiz-explanation');

    optWrap.setAttribute('role', 'radiogroup');
    if (question) optWrap.setAttribute('aria-labelledby', question.id);

    options.forEach(function (btn, i) {
      btn.classList.add('quiz-option');
      btn.setAttribute('type', 'button');
      btn.setAttribute('role', 'radio');
      btn.setAttribute('aria-checked', 'false');
      if (!btn.id) btn.id = uid('quiz-option');
      // roving tabindex：仅第一个可聚焦，其余移出 Tab 顺序
      btn.setAttribute('tabindex', i === 0 ? '0' : '-1');
      var label = btn.innerHTML;
      btn.innerHTML =
        '<span class="q-key" aria-hidden="true">' + (LETTERS[i] || (i + 1)) + '</span>' +
        '<span class="q-text">' + label + '</span>' +
        '<span class="q-status"></span>' +
        '<span class="q-mark" aria-hidden="true"></span>';
    });

    if (explanation && !explanation.querySelector('.exp-label')) {
      var lab = document.createElement('span');
      lab.className = 'exp-label';
      lab.textContent = '解析';
      explanation.insertBefore(lab, explanation.firstChild);
    }

    // 页脚：结果语 + 再试一次
    var foot = document.createElement('div');
    foot.className = 'quiz-foot';
    var verdict = document.createElement('span');
    verdict.className = 'quiz-verdict';
    verdict.id = uid('quiz-verdict');
    verdict.setAttribute('role', 'status');
    verdict.setAttribute('aria-live', 'polite');
    var retryBtn = document.createElement('button');
    retryBtn.type = 'button';
    retryBtn.className = 'quiz-retry';
    retryBtn.textContent = '再试一次';
    foot.appendChild(verdict);
    foot.appendChild(retryBtn);
    if (explanation) quiz.insertBefore(foot, explanation);
    else quiz.appendChild(foot);

    function setOptionStatus(option, text) {
      option.querySelector('.q-status').textContent = text ? '，' + text : '';
    }

    function grade(picked) {
      if (quiz.classList.contains('graded')) return;
      quiz.classList.add('graded');
      var right = picked.getAttribute('data-answer') === 'correct';

      picked.classList.add(right ? 'correct' : 'wrong');
      picked.setAttribute('aria-checked', 'true');
      picked.querySelector('.q-key').textContent = right ? '✓' : '✗';
      setOptionStatus(picked, right ? '你的选择，正确' : '你的选择，错误');

      if (!right) {
        options.forEach(function (b) {
          if (b.getAttribute('data-answer') === 'correct') {
            b.classList.add('correct');
            b.querySelector('.q-key').textContent = '✓';
            setOptionStatus(b, '正确答案');
          }
        });
      }

      // 解析描述整个已判分组；选项自身的隐藏状态文字避免逐项重复播报解析。
      if (explanation) optWrap.setAttribute('aria-describedby', explanation.id);

      verdict.classList.add(right ? 'ok' : 'no');
      verdict.textContent = right
        ? '✓ 答对了，干得漂亮'
        : explanation
          ? '✗ 再想想 —— 正确答案已标出，看看解析'
          : '✗ 不对，正确答案已标出';

      if (explanation) {
        explanation.style.setProperty('--exp-rule', right ? 'var(--success, #16A34A)' : '#B4530E');
      }
    }

    function reset() {
      quiz.classList.remove('graded');
      options.forEach(function (b, i) {
        b.classList.remove('correct', 'wrong');
        b.setAttribute('aria-checked', 'false');
        b.removeAttribute('aria-describedby');
        b.querySelector('.q-key').textContent = LETTERS[i] || (i + 1);
        setOptionStatus(b, '');
        b.setAttribute('tabindex', i === 0 ? '0' : '-1');
      });
      optWrap.removeAttribute('aria-describedby');
      verdict.className = 'quiz-verdict';
      verdict.textContent = '';
      options[0].focus();
    }

    function moveFocus(from, to) {
      options[from].setAttribute('tabindex', '-1');
      options[to].setAttribute('tabindex', '0');
      options[to].focus();
    }

    options.forEach(function (btn, i) {
      btn.addEventListener('click', function () { grade(btn); });
      // 键盘：方向键 / Home / End 移动焦点（不判分），Enter/Space 由按钮原生触发 click 判分
      btn.addEventListener('keydown', function (e) {
        if (quiz.classList.contains('graded')) return;
        var nextIndex = null;
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') nextIndex = (i + 1) % options.length;
        else if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') nextIndex = (i - 1 + options.length) % options.length;
        else if (e.key === 'Home') nextIndex = 0;
        else if (e.key === 'End') nextIndex = options.length - 1;
        if (nextIndex !== null) {
          e.preventDefault();
          moveFocus(i, nextIndex);
        }
      });
    });
    retryBtn.addEventListener('click', reset);
  });
})();
