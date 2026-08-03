/**
 * 统一课程目录
 * - 保留总览、大纲与 L01–L38 的线性顺序
 * - 集中计算相邻页、阶段大纲与正式课坐标
 * - 对外只暴露 context(pathname) 和 lessons()
 */
(function() {
  'use strict';

  var ITEMS = [
    { file: '0001-ai-agent-learning-path-overview.html', title: '学习路径总览', phase: '' },
    { file: '0002-phase1-python-outline.html', title: '第一阶段大纲', phase: '', outlineFor: '第一阶段' },
    { file: '0004-L01-dev-environment-setup.html', title: '开发环境搭建', phase: '第一阶段' },
    { file: '0005-L02-python-runtime-and-modules.html', title: 'Python 运行机制与模块系统', phase: '第一阶段' },
    { file: '0006-L03-variables-types-data-structures.html', title: '变量、类型与数据结构', phase: '第一阶段' },
    { file: '0008-L04-control-flow-and-prompt.html', title: '流程控制、字符串与 Prompt 构造', phase: '第一阶段' },
    { file: '0009-L05-functions-and-parameters.html', title: '函数定义与参数', phase: '第一阶段' },
    { file: '0010-L06-scope-closures-lambda.html', title: '作用域、闭包与 Lambda', phase: '第一阶段' },
    { file: '0011-L07-classes-and-dataclass.html', title: '类、对象与 @dataclass', phase: '第一阶段' },
    { file: '0012-L08-inheritance-and-call.html', title: '继承、多态与 __call__', phase: '第一阶段' },
    { file: '0013-L09-files-json-dict.html', title: '文件、JSON 与 JSON Lines', phase: '第一阶段' },
    { file: '0014-L10-exceptions-logging-context.html', title: '异常处理、日志与上下文管理器', phase: '第一阶段' },
    { file: '0015-L11-decorators.html', title: '装饰器 — Agent 框架的基石', phase: '第一阶段' },
    { file: '0016-L12-generators-streaming.html', title: '生成器与 Streaming 模式', phase: '第一阶段' },
    { file: '0017-L13-type-hints.html', title: '类型提示系统', phase: '第一阶段' },
    { file: '0018-L14-pydantic.html', title: 'Pydantic 数据验证', phase: '第一阶段' },
    { file: '0019-L15-httpx.html', title: '用 httpx 发起 HTTP 请求', phase: '第一阶段' },
    { file: '0020-L16-async-concurrency.html', title: 'async/await 与并发', phase: '第一阶段' },
    { file: '0029-phase2-ai-knowledge-outline.html', title: '第二阶段大纲', phase: '', outlineFor: '第二阶段' },
    { file: '0021-L17-llm-essence-and-parameters.html', title: 'LLM 本质与生成参数', phase: '第二阶段' },
    { file: '0022-L18-tokenization.html', title: 'Token 与 Tokenization 深入', phase: '第二阶段' },
    { file: '0023-L19-hallucination.html', title: '幻觉全解', phase: '第二阶段' },
    { file: '0024-L20-reasoning-models.html', title: '推理能力与 Adaptive Thinking', phase: '第二阶段' },
    { file: '0025-L21-model-capabilities.html', title: '模型能力边界与 Base vs Instruct', phase: '第二阶段' },
    { file: '0026-L22-benchmarks-and-selection.html', title: '看懂 Benchmark 与模型选型', phase: '第二阶段' },
    { file: '0027-L23-token-economics.html', title: 'Token 经济学与降本杠杆', phase: '第二阶段' },
    { file: '0028-L24-phase2-capstone.html', title: 'Phase 2 综合实战：模型对比 · 幻觉测试 · 成本核算', phase: '第二阶段' },
    { file: '0044-phase3-api-engineering-outline.html', title: '第三阶段大纲', phase: '', outlineFor: '第三阶段' },
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
    { file: '0043-L38-phase3-capstone.html', title: 'Phase 3 综合实战：多模型 Agent 客户端', phase: '第三阶段' }
  ];

  var PHASE_NUMBERS = {
    '第一阶段': 1,
    '第二阶段': 2,
    '第三阶段': 3
  };
  var OUTLINES = {};
  var LESSONS = [];

  function freeze(value) {
    return Object.freeze(value);
  }

  function copy(item) {
    var result;
    if (!item) return null;
    result = {};
    Object.keys(item).forEach(function(key) {
      result[key] = item[key];
    });
    return result;
  }

  function expose(item) {
    return item ? freeze(copy(item)) : null;
  }

  function currentFile(pathname) {
    var path = String(pathname || '');
    var parts;
    var file;
    if (!path) return ITEMS[0].file;
    path = path.split('#')[0].split('?')[0].replace(/\\/g, '/');
    parts = path.split('/').filter(Boolean);
    try {
      parts = parts.map(function(part) { return decodeURIComponent(part); });
    } catch (error) {
      return '';
    }
    if (parts.length > 1 && parts[parts.length - 2].toLocaleLowerCase() !== 'lessons') return '';
    file = parts[parts.length - 1] || '';
    return file;
  }

  ITEMS.forEach(function(item) {
    if (item.outlineFor) OUTLINES[item.outlineFor] = item;
    if (item.phase) {
      item.lessonIndex = LESSONS.length;
      item.lessonId = 'L' + item.file.match(/-L(\d{2})-/)[1];
      item.phaseNumber = PHASE_NUMBERS[item.phase];
      LESSONS.push(item);
    }
  });

  function context(pathname) {
    var file = currentFile(pathname);
    var index = -1;
    var item;
    var result;

    ITEMS.some(function(candidate, candidateIndex) {
      if (candidate.file === file) {
        index = candidateIndex;
        return true;
      }
      return false;
    });
    if (index === -1) return null;

    item = ITEMS[index];
    result = {
      current: expose(item),
      prev: expose(index > 0 ? ITEMS[index - 1] : null),
      next: expose(index < ITEMS.length - 1 ? ITEMS[index + 1] : null),
      outline: expose(item.phase ? OUTLINES[item.phase] :
        (item.outlineFor ? item : OUTLINES['第一阶段'])),
      isLesson: !!item.phase,
      lessonId: item.lessonId || null,
      phase: item.phase || '',
      phaseNumber: item.phase ? PHASE_NUMBERS[item.phase] : null,
      lessonIndex: typeof item.lessonIndex === 'number' ? item.lessonIndex : -1,
      total: LESSONS.length
    };
    return freeze(result);
  }

  function lessons() {
    return freeze(LESSONS.map(expose));
  }

  window.CourseCatalog = freeze({
    context: context,
    lessons: lessons
  });
})();
