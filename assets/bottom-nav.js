/**
 * 底部课程导航
 * - 卡片式上一课/下一课
 * - 显示课程标题
 * - 回到大纲按钮
 */
(function() {
  'use strict';

  const LESSONS = [
    { file: '0001-ai-agent-learning-path-overview.html', title: '学习路径总览', phase: '' },
    { file: '0002-phase1-python-outline.html', title: '第一阶段大纲', phase: '' },
    { file: '0029-phase2-ai-knowledge-outline.html', title: '第二阶段大纲', phase: '' },
    { file: '0044-phase3-api-engineering-outline.html', title: '第三阶段大纲', phase: '' },
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
    { file: '0016-L12-generators-streaming.html', title: '生成器与 Streaming', phase: '第一阶段' },
    { file: '0017-L13-type-hints.html', title: '类型提示系统', phase: '第一阶段' },
    { file: '0018-L14-pydantic.html', title: 'Pydantic 数据验证', phase: '第一阶段' },
    { file: '0019-L15-httpx.html', title: '用 httpx 发起 HTTP 请求', phase: '第一阶段' },
    { file: '0020-L16-async-concurrency.html', title: 'async/await 与并发', phase: '第一阶段' },
    { file: '0021-L17-llm-essence-and-parameters.html', title: 'LLM 本质与生成参数', phase: '第二阶段' },
    { file: '0022-L18-tokenization.html', title: 'Token 与 Tokenization', phase: '第二阶段' },
    { file: '0023-L19-hallucination.html', title: '幻觉全解（校准视角）', phase: '第二阶段' },
    { file: '0024-L20-reasoning-models.html', title: '推理模型与 Extended Thinking', phase: '第二阶段' },
    { file: '0025-L21-model-capabilities.html', title: '模型能力边界与 Base vs Instruct', phase: '第二阶段' },
    { file: '0026-L22-benchmarks-and-selection.html', title: '看懂 Benchmark 与模型选型', phase: '第二阶段' },
    { file: '0027-L23-token-economics.html', title: 'Token 经济学与降本杠杆', phase: '第二阶段' },
    { file: '0028-L24-phase2-capstone.html', title: 'Phase 2 综合实战项目', phase: '第二阶段' },
    { file: '0030-L25-llm-api-basics.html', title: '主流 LLM API 上手', phase: '第三阶段' },
    { file: '0031-L26-streaming.html', title: 'Streaming 流式输出', phase: '第三阶段' },
    { file: '0032-L27-function-calling.html', title: 'Function Calling 原理', phase: '第三阶段' },
    { file: '0033-L28-structured-outputs.html', title: 'Structured Outputs（约束解码）', phase: '第三阶段' },
    { file: '0034-L29-multimodal-api.html', title: '多模态 API', phase: '第三阶段' },
    { file: '0035-L30-context-window-management.html', title: 'Context Window 管理', phase: '第三阶段' },
    { file: '0036-L31-error-handling-retry.html', title: '错误处理、退避与幂等', phase: '第三阶段' },
    { file: '0037-L32-routing-fallback-gateway.html', title: '路由、Fallback 与 AI Gateway', phase: '第三阶段' },
    { file: '0038-L33-observability.html', title: 'LLM 可观测性', phase: '第三阶段' },
    { file: '0039-L34-tool-schema-design.html', title: 'Tool Schema 设计', phase: '第三阶段' },
    { file: '0040-L35-function-calling-loop.html', title: '完整 Function Calling 循环', phase: '第三阶段' },
    { file: '0041-L36-tool-robustness-registry.html', title: '工具健壮性与注册系统', phase: '第三阶段' },
    { file: '0042-L37-cost-engineering.html', title: '成本工程：2026 降本优先级', phase: '第三阶段' },
    { file: '0043-L38-phase3-capstone.html', title: 'Phase 3 综合实战', phase: '第三阶段' },
  ];

  const currentFile = window.location.pathname.split('/').pop();
  const idx = LESSONS.findIndex(l => l.file === currentFile);
  if (idx === -1) return;

  const prev = idx > 0 ? LESSONS[idx - 1] : null;
  const next = idx < LESSONS.length - 1 ? LESSONS[idx + 1] : null;
  const cur = LESSONS[idx];

  let html = '<div class="bottom-nav-inner">';

  // 上一课
  html += '<div class="bottom-nav-side">';
  if (prev) {
    html += '<a href="' + prev.file + '" class="bottom-nav-card bottom-nav-prev">';
    html += '<span class="bottom-nav-label">← 上一课</span>';
    html += '<span class="bottom-nav-title">' + prev.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  // 中间：回到大纲（按当前课程所属阶段选对应大纲页）
  var outlineFile = '0002-phase1-python-outline.html';
  if (cur && cur.phase === '第二阶段') outlineFile = '0029-phase2-ai-knowledge-outline.html';
  else if (cur && cur.phase === '第三阶段') outlineFile = '0044-phase3-api-engineering-outline.html';
  html += '<div class="bottom-nav-center">';
  html += '<a href="' + outlineFile + '" class="bottom-nav-outline">';
  html += '<span class="bottom-nav-outline-icon">☰</span>';
  html += '<span class="bottom-nav-outline-text">大纲</span>';
  html += '</a>';
  html += '</div>';

  // 下一课
  html += '<div class="bottom-nav-side">';
  if (next) {
    html += '<a href="' + next.file + '" class="bottom-nav-card bottom-nav-next">';
    html += '<span class="bottom-nav-label">下一课 →</span>';
    html += '<span class="bottom-nav-title">' + next.title + '</span>';
    html += '</a>';
  }
  html += '</div>';

  html += '</div>';

  const nav = document.createElement('nav');
  nav.className = 'bottom-nav';
  nav.innerHTML = html;

  // 插入到 body 末尾（footer 之前）
  var footer = document.querySelector('footer');
  if (footer) {
    document.body.insertBefore(nav, footer);
  } else {
    document.body.appendChild(nav);
  }
})();
