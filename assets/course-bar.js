/**
 * 统一课程导航栏
 * - 粘性定位
 * - 上一课 / 课程列表 / 下一课
 * - 进度指示
 * - 无下拉框，用胶囊按钮
 */
(function() {
  'use strict';

  const LESSONS = [
    { file: '0001-ai-agent-learning-path-overview.html', title: '学习路径总览', phase: '' },
    { file: '0002-phase1-python-outline.html', title: '第一阶段大纲', phase: '' },
    { file: '0004-L01-dev-environment-setup.html', title: '开发环境搭建', phase: '第一阶段' },
    { file: '0005-L02-python-runtime-and-modules.html', title: 'Python 运行机制与模块系统', phase: '第一阶段' },
    { file: '0006-L03-variables-types-data-structures.html', title: '变量、类型与数据结构', phase: '第一阶段' },
    { file: '0008-L04-control-flow-and-prompt.html', title: '流程控制、字符串与 Prompt 构造', phase: '第一阶段' },
    { file: '0009-L05-functions-and-parameters.html', title: '函数定义与参数', phase: '第一阶段' },
    { file: '0010-L06-scope-closures-lambda.html', title: '作用域、闭包与 Lambda', phase: '第一阶段' },
    { file: '0011-L07-classes-and-dataclass.html', title: '类、对象与 @dataclass', phase: '第一阶段' },
    { file: '0012-L08-inheritance-and-call.html', title: '继承、多态与 __call__', phase: '第一阶段' },
    { file: '0013-L09-files-json-dict.html', title: '文件、JSON 与 Dict 深度操作', phase: '第一阶段' },
    { file: '0014-L10-exceptions-logging-context.html', title: '异常处理、日志与上下文管理器', phase: '第一阶段' },
    { file: '0015-L11-decorators.html', title: '装饰器', phase: '第一阶段' },
  ];

  const COURSE = LESSONS.filter(l => l.phase);
  const TOTAL = COURSE.length;
  const currentFile = window.location.pathname.split('/').pop();
  const idx = LESSONS.findIndex(l => l.file === currentFile);
  if (idx === -1) return;

  const cur = LESSONS[idx];
  const courseIdx = COURSE.findIndex(l => l.file === currentFile);
  const isCourse = courseIdx !== -1;
  const prev = idx > 0 ? LESSONS[idx - 1] : null;
  const next = idx < LESSONS.length - 1 ? LESSONS[idx + 1] : null;

  // 构建 HTML
  let html = '<div class="course-bar-inner">';

  // 左：上一课
  html += '<div class="course-bar-side course-bar-left">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="course-bar-nav" title="' + prev.title + '">';
    html += '<span class="course-bar-nav-arrow">←</span>';
    html += '<span class="course-bar-nav-label">' + (prev.phase ? prev.title : prev.title) + '</span>';
    html += '</a>';
  }
  html += '</div>';

  // 中：课程信息
  html += '<div class="course-bar-center">';
  if (isCourse) {
    html += '<span class="course-bar-num">L' + String(courseIdx + 1).padStart(2, '0') + '</span>';
    html += '<span class="course-bar-title">' + cur.title + '</span>';
    // 进度点
    html += '<div class="course-bar-dots">';
    COURSE.forEach(function(_, i) {
      var cls = i < courseIdx ? 'done' : (i === courseIdx ? 'active' : '');
      html += '<span class="course-bar-dot ' + cls + '"></span>';
    });
    html += '</div>';
  } else {
    html += '<span class="course-bar-title">' + cur.title + '</span>';
  }
  html += '</div>';

  // 右：下一课
  html += '<div class="course-bar-side course-bar-right">';
  if (next) {
    html += '<a href="' + next.file + '" class="course-bar-nav" title="' + next.title + '">';
    html += '<span class="course-bar-nav-label">' + (next.phase ? next.title : next.title) + '</span>';
    html += '<span class="course-bar-nav-arrow">→</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '</div>';

  const bar = document.createElement('div');
  bar.className = 'course-bar';
  bar.innerHTML = html;
  document.body.insertBefore(bar, document.body.firstChild);
})();
