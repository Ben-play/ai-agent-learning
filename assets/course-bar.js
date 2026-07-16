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
    { file: '0029-phase2-ai-knowledge-outline.html', title: '第二阶段大纲', phase: '' },
    { file: '0044-phase3-api-engineering-outline.html', title: '第三阶段大纲', phase: '' },
    { file: '0004-L01-dev-environment-setup.html', title: '开发环境搭建', phase: '第一阶段', min: 15 },
    { file: '0005-L02-python-runtime-and-modules.html', title: 'Python 运行机制与模块系统', phase: '第一阶段', min: 35 },
    { file: '0006-L03-variables-types-data-structures.html', title: '变量、类型与数据结构', phase: '第一阶段', min: 40 },
    { file: '0008-L04-control-flow-and-prompt.html', title: '流程控制、字符串与 Prompt 构造', phase: '第一阶段', min: 35 },
    { file: '0009-L05-functions-and-parameters.html', title: '函数定义与参数', phase: '第一阶段', min: 25 },
    { file: '0010-L06-scope-closures-lambda.html', title: '作用域、闭包与 Lambda', phase: '第一阶段', min: 20 },
    { file: '0011-L07-classes-and-dataclass.html', title: '类、对象与 @dataclass', phase: '第一阶段', min: 20 },
    { file: '0012-L08-inheritance-and-call.html', title: '继承、多态与 __call__', phase: '第一阶段', min: 20 },
    { file: '0013-L09-files-json-dict.html', title: '文件、JSON 与 Dict 深度操作', phase: '第一阶段', min: 25 },
    { file: '0014-L10-exceptions-logging-context.html', title: '异常处理、日志与上下文管理器', phase: '第一阶段', min: 30 },
    { file: '0015-L11-decorators.html', title: '装饰器', phase: '第一阶段', min: 30 },
    { file: '0016-L12-generators-streaming.html', title: '生成器与 Streaming', phase: '第一阶段', min: 25 },
    { file: '0017-L13-type-hints.html', title: '类型提示系统', phase: '第一阶段', min: 20 },
    { file: '0018-L14-pydantic.html', title: 'Pydantic 数据验证', phase: '第一阶段', min: 30 },
    { file: '0019-L15-httpx.html', title: '用 httpx 发起 HTTP 请求', phase: '第一阶段', min: 30 },
    { file: '0020-L16-async-concurrency.html', title: 'async/await 与并发', phase: '第一阶段', min: 25 },
    { file: '0021-L17-llm-essence-and-parameters.html', title: 'LLM 本质与生成参数', phase: '第二阶段', min: 30 },
    { file: '0022-L18-tokenization.html', title: 'Token 与 Tokenization', phase: '第二阶段', min: 30 },
    { file: '0023-L19-hallucination.html', title: '幻觉全解（多因素视角）', phase: '第二阶段', min: 30 },
    { file: '0024-L20-reasoning-models.html', title: '推理能力与 Adaptive Thinking', phase: '第二阶段', min: 45 },
    { file: '0025-L21-model-capabilities.html', title: '模型能力边界与 Base vs Instruct', phase: '第二阶段', min: 35 },
    { file: '0026-L22-benchmarks-and-selection.html', title: '看懂 Benchmark 与模型选型', phase: '第二阶段', min: 35 },
    { file: '0027-L23-token-economics.html', title: 'Token 经济学与降本杠杆', phase: '第二阶段', min: 35 },
    { file: '0028-L24-phase2-capstone.html', title: 'Phase 2 综合实战项目', phase: '第二阶段', min: 45 },
    { file: '0030-L25-llm-api-basics.html', title: '主流 LLM API 上手', phase: '第三阶段', min: 20 },
    { file: '0031-L26-streaming.html', title: 'Streaming 流式输出', phase: '第三阶段', min: 35 },
    { file: '0032-L27-function-calling.html', title: 'Function Calling 原理', phase: '第三阶段', min: 35 },
    { file: '0033-L28-structured-outputs.html', title: 'Structured Outputs（约束解码）', phase: '第三阶段', min: 30 },
    { file: '0034-L29-multimodal-api.html', title: '多模态 API', phase: '第三阶段', min: 25 },
    { file: '0035-L30-context-window-management.html', title: 'Context Window 管理', phase: '第三阶段', min: 25 },
    { file: '0036-L31-error-handling-retry.html', title: '错误处理、退避与幂等', phase: '第三阶段', min: 40 },
    { file: '0037-L32-routing-fallback-gateway.html', title: '路由、Fallback 与 AI Gateway', phase: '第三阶段', min: 40 },
    { file: '0038-L33-observability.html', title: 'LLM 可观测性', phase: '第三阶段', min: 25 },
    { file: '0039-L34-tool-schema-design.html', title: 'Tool Schema 设计', phase: '第三阶段', min: 35 },
    { file: '0040-L35-function-calling-loop.html', title: '完整 Function Calling 循环', phase: '第三阶段', min: 35 },
    { file: '0041-L36-tool-robustness-registry.html', title: '工具健壮性与注册系统', phase: '第三阶段', min: 40 },
    { file: '0042-L37-cost-engineering.html', title: '成本工程：2026 降本优先级', phase: '第三阶段', min: 30 },
    { file: '0043-L38-phase3-capstone.html', title: 'Phase 3 综合实战', phase: '第三阶段', min: 45 },
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

  // 中：课程信息 —— 坐标读数 + 一根连续进度条（精装书页眉；无百分比数字）
  html += '<div class="course-bar-center">';
  if (isCourse) {
    // 阶段出现顺序 → 当前课属于第几阶段（1-based）
    var phaseOrder = [];
    COURSE.forEach(function(l) { if (phaseOrder.indexOf(l.phase) === -1) phaseOrder.push(l.phase); });
    var phaseNum = phaseOrder.indexOf(cur.phase) + 1;          // 第几阶段
    var overallPct = Math.round((courseIdx + 1) / TOTAL * 100); // 总进度（仅驱动进度条视觉，不显数字）

    // 坐标读数：第三阶段 · L30（中文阶段名 + 细竖线 + 课号；时长只在课页标题旁展示，此处不重复）
    html += '<span class="course-bar-coord" aria-label="第 ' + phaseNum + ' 阶段 · 第 ' + (courseIdx + 1) + ' 课，共 ' + TOTAL + ' 课">';
    html += '<span class="course-bar-phase-name">' + cur.phase + '</span>';
    html += '<span class="course-bar-coord-rule"></span>';
    html += '<span class="course-bar-num">L' + String(courseIdx + 1).padStart(2, '0') + '</span>';
    html += '</span>';

    html += '<span class="course-bar-title">' + cur.title + '</span>';

    // 一根连续进度条（整门课的顺序位置，非完成度）+ 游标，凹槽内发光
    html += '<div class="course-bar-track" role="progressbar" aria-valuenow="' + (courseIdx + 1) +
            '" aria-valuemin="1" aria-valuemax="' + TOTAL + '" aria-label="课程顺序位置：第 ' + (courseIdx + 1) + ' 课，共 ' + TOTAL + ' 课">';
    html += '<span class="course-bar-track-fill" style="width:' + overallPct + '%"></span>';
    html += '<span class="course-bar-track-cursor" style="left:' + overallPct + '%"></span>';
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
