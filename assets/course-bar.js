/**
 * 统一课程导航栏
 * - 粘性定位
 * - 上一课 / 课程列表 / 下一课
 * - 进度指示
 * - 无下拉框，用胶囊按钮
 */
(function() {
  'use strict';

  var context;
  var cur;
  var prev;
  var next;
  var html;
  var completed = 0;
  var completedPct;
  var bar;

  if (!window.CourseCatalog) return;
  context = window.CourseCatalog.context(window.location.pathname);
  if (!context) return;

  cur = context.current;
  prev = context.prev;
  next = context.next;

  // 构建 HTML
  html = '<div class="course-bar-inner">';

  // 左：上一课
  html += '<div class="course-bar-side course-bar-left">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="course-bar-nav" title="' + prev.title + '">';
    html += '<span class="course-bar-nav-arrow">←</span>';
    html += '<span class="course-bar-nav-label">' + prev.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  // 中：课程信息 —— 坐标读数 + 一根连续进度条（精装书页眉；无百分比数字）
  html += '<div class="course-bar-center">';
  if (context.isLesson) {
    // 坐标读数：第三阶段 · L30（中文阶段名 + 细竖线 + 课号；时长只在课页标题旁展示，此处不重复）
    html += '<span class="course-bar-coord" aria-label="第 ' + context.phaseNumber + ' 阶段 · 第 ' +
            (context.lessonIndex + 1) + ' 课，共 ' + context.total + ' 课">';
    html += '<span class="course-bar-phase-name">' + context.phase + '</span>';
    html += '<span class="course-bar-coord-rule"></span>';
    html += '<span class="course-bar-num">' + context.lessonId + '</span>';
    html += '</span>';

    html += '<span class="course-bar-title">' + cur.title + '</span>';

    // 完成度由学习状态模块渐进更新；模块未加载时稳健显示 0/38。
    completedPct = Math.round(completed / context.total * 100);
    html += '<div class="course-bar-track is-empty" role="progressbar" aria-valuenow="' + completed +
            '" aria-valuemin="0" aria-valuemax="' + context.total + '" aria-label="已完成 ' +
            completed + '/' + context.total + ' 课" data-course-progress="completed" data-completed="' +
            completed + '" data-total="' + context.total + '">';
    html += '<span class="course-bar-track-fill" style="width:' + completedPct + '%"></span>';
    html += '<span class="course-bar-track-cursor" style="left:' + completedPct + '%"></span>';
    html += '</div>';
  } else {
    html += '<span class="course-bar-title">' + cur.title + '</span>';
  }
  html += '</div>';

  // 右：下一课
  html += '<div class="course-bar-side course-bar-right">';
  if (next) {
    html += '<a href="' + next.file + '" class="course-bar-nav" title="' + next.title + '">';
    html += '<span class="course-bar-nav-label">' + next.title + '</span>';
    html += '<span class="course-bar-nav-arrow">→</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '</div>';

  bar = document.createElement('div');
  bar.className = 'course-bar';
  bar.innerHTML = html;
  document.body.insertBefore(bar, document.body.firstChild);
})();
