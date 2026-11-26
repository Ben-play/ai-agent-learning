/**
 * 统一课程目录
 * - 保留总览、大纲与正式课的线性顺序
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
    { file: '0042-L37-cost-engineering.html', title: '成本工程：负载驱动的成本决策', phase: '第三阶段' },
    { file: '0043-L38-phase3-capstone.html', title: 'Phase 3 综合实战：可验收的 Agent 客户端', phase: '第三阶段' },
    { file: '0045-phase4-prompt-context-outline.html', title: '第四阶段大纲', phase: '', outlineFor: '第四阶段' },
    { file: '0047-L39-testable-task-contract.html', title: '把请求写成可判定任务', phase: '第四阶段' },
    { file: '0048-L40-few-shot-counterexamples.html', title: 'Zero-shot、Few-shot 与反例', phase: '第四阶段' },
    { file: '0049-L41-prompt-versions-regression.html', title: 'Prompt 版本与回归', phase: '第四阶段' },
    { file: '0050-L42-context-evidence-budget.html', title: '证据选择、来源与上下文预算', phase: '第四阶段' },
    { file: '0051-L43-progressive-skill-disclosure.html', title: 'Skills 按需加载与权限边界', phase: '第四阶段' },
    { file: '0052-L44-project-acceptance-handoff.html', title: '项目验收与交接', phase: '第四阶段' },
    { file: '0063-phase5-agent-harness-outline.html', title: '第五阶段大纲', phase: '', outlineFor: '第五阶段' },
    { file: '0053-L45-function-workflow-agent.html', title: '先选函数、workflow 还是单 Agent', phase: '第五阶段' },
    { file: '0054-L46-bounded-agent-loop.html', title: '有界 Agent Loop', phase: '第五阶段' },
    { file: '0055-L47-typed-tool-contract.html', title: '小工具集、类型契约与执行校验', phase: '第五阶段' },
    { file: '0056-L48-context-notes-compaction.html', title: '上下文压缩与按需披露', phase: '第五阶段' },
    { file: '0057-L49-memory-lifecycle.html', title: '记忆的写入、纠正与删除', phase: '第五阶段' },
    { file: '0058-L50-approval-boundaries.html', title: '人工审批与明确禁止的动作', phase: '第五阶段' },
    { file: '0059-L51-approval-checkpoint-resume.html', title: '审批暂停、进程退出与恢复', phase: '第五阶段' },
    { file: '0060-L52-idempotent-draft-replay.html', title: '副作用已提交但响应丢失', phase: '第五阶段' },
    { file: '0061-L53-harness-regression.html', title: '用回归用例改进 Harness', phase: '第五阶段' },
    { file: '0062-L54-harness-acceptance.html', title: '阶段验收：固化框架无关契约', phase: '第五阶段' },
    { file: '0069-phase6-langgraph-mcp-outline.html', title: '第六阶段大纲', phase: '', outlineFor: '第六阶段' },
    { file: '0064-L55-langgraph-state-graph.html', title: '把手写 Harness 迁入最小状态图', phase: '第六阶段' },
    { file: '0065-L56-langgraph-durable-resume.html', title: 'LangGraph 中断、持久恢复与重放', phase: '第六阶段' },
    { file: '0066-L57-mcp-stdio.html', title: '先走本地 MCP stdio', phase: '第六阶段' },
    { file: '0067-L58-mcp-streamable-http.html', title: 'MCP Streamable HTTP 与 SSE', phase: '第六阶段' },
    { file: '0068-L59-mcp-skill-authority.html', title: 'Skill、Scope 和业务权限', phase: '第六阶段' },
    { file: '0080-phase7-data-rag-outline.html', title: '第七阶段大纲', phase: '', outlineFor: '第七阶段' },
    { file: '0070-L60-rag-data-access.html', title: '数据模型与行级访问', phase: '第七阶段' },
    { file: '0071-L61-rag-citation-chunks.html', title: '解析、清洗与可定位分块', phase: '第七阶段' },
    { file: '0072-L62-rag-lexical-retrieval.html', title: '先做授权词法检索', phase: '第七阶段' },
    { file: '0073-L63-rag-vector-retrieval.html', title: 'Embedding 与向量检索', phase: '第七阶段' },
    { file: '0074-L64-rag-hybrid-retrieval.html', title: '用失败题判断是否混合检索', phase: '第七阶段' },
    { file: '0075-L65-rag-reranking.html', title: '对同一候选集重排', phase: '第七阶段' },
    { file: '0076-L66-rag-cache-invalidation.html', title: '热缓存中的撤权、改版与删除', phase: '第七阶段' },
    { file: '0077-L67-rag-trust-boundary.html', title: '证据数据与执行权限', phase: '第七阶段' },
    { file: '0078-L68-rag-retrieval-evals.html', title: '检索评估：权限、召回与覆盖', phase: '第七阶段' },
    { file: '0079-L69-rag-generation-evals.html', title: '生成评估：引用、忠实度与拒答', phase: '第七阶段' },
    { file: '0091-phase8-agent-engineering-outline.html', title: '第八阶段大纲', phase: '', outlineFor: '第八阶段' },
    { file: '0081-L70-agent-telemetry.html', title: '贯通任务、试验与轨迹', phase: '第八阶段' },
    { file: '0082-L71-telemetry-privacy-alerts.html', title: '遥测最小化与可解释告警', phase: '第八阶段' },
    { file: '0083-L72-versioned-eval-datasets.html', title: '版本化任务集与重复试验', phase: '第八阶段' },
    { file: '0084-L73-evidence-outcome-scoring.html', title: '按证据和环境终态判分', phase: '第八阶段' },
    { file: '0085-L74-judge-calibration.html', title: '校准开放式质量评分', phase: '第八阶段' },
    { file: '0086-L75-tool-authority-bounds.html', title: '限制过度代理与工具权限', phase: '第八阶段' },
    { file: '0087-L76-agent-load-cost.html', title: '按负载比较降本方案', phase: '第八阶段' },
    { file: '0088-L77-offline-ci-gates.html', title: '把验收标准接入离线 CI', phase: '第八阶段' },
    { file: '0089-L78-agent-system-design.html', title: '在系统设计中说明取舍', phase: '第八阶段' },
    { file: '0090-L79-engineering-baseline-handoff.html', title: '交付可复核的工程基线', phase: '第八阶段' },
    { file: '0097-phase9-advanced-agent-outline.html', title: '第九阶段选修大纲', phase: '', outlineFor: '第九阶段' },
    { file: '0092-L80-reasoning-effort.html', title: '按任务选择推理投入', phase: '第九阶段' },
    { file: '0093-L81-tool-discovery.html', title: '工具搜索与受限聚合', phase: '第九阶段' },
    { file: '0094-L82-local-gui-preview.html', title: '本地 GUI 预览与取消', phase: '第九阶段' },
    { file: '0095-L83-coding-harness-boundaries.html', title: '编码 Agent 的工作区与验收', phase: '第九阶段' },
    { file: '0096-L84-long-task-recovery.html', title: '长任务的取消、重放与预算', phase: '第九阶段' },
    { file: '0106-phase10-framework-evolution-outline.html', title: '第十阶段大纲', phase: '', outlineFor: '第十阶段' },
    { file: '0098-L85-versioned-graph-state.html', title: '版本化状态与分支', phase: '第十阶段' },
    { file: '0099-L86-checkpoint-compatibility.html', title: '从同一批旧检查点比较恢复', phase: '第十阶段' },
    { file: '0100-L87-migration-fallback.html', title: '演练迁移失败与恢复路径', phase: '第十阶段' },
    { file: '0101-L88-architecture-decision.html', title: '记录架构决策：保留单 Agent 也有效', phase: '第十阶段' },
    { file: '0102-L89-bounded-worker-delegation.html', title: '单 Agent 与 Orchestrator–Worker 对照', phase: '第十阶段' },
    { file: '0103-L90-a2a-task-boundaries.html', title: 'A2A 的任务边界', phase: '第十阶段' },
    { file: '0104-L91-mcp-server-boundaries.html', title: 'MCP 服务端的只读权限边界', phase: '第十阶段' },
    { file: '0105-L92-hermes-source-comparison.html', title: '只读对照 Hermes 的状态与恢复边界', phase: '第十阶段' },
    { file: '0113-phase11-deployment-outline.html', title: '第十一阶段大纲', phase: '', outlineFor: '第十一阶段' },
    { file: '0107-L93-fastapi-persistent-state.html', title: '封装 FastAPI、Docker 与持久状态', phase: '第十一阶段' },
    { file: '0108-L94-deployment-promotion-gate.html', title: 'CI/CD：为部署设置晋级门禁', phase: '第十一阶段' },
    { file: '0109-L95-deployment-authority-audit.html', title: '限流、权限与最小化审计', phase: '第十一阶段' },
    { file: '0110-L96-canary-stop-conditions.html', title: '灰度指标与停止条件', phase: '第十一阶段' },
    { file: '0111-L97-rollback-pending-approvals.html', title: '回滚必须接住已存在的审批', phase: '第十一阶段' },
    { file: '0112-L98-incident-evaluation-iteration.html', title: '事故响应与评估驱动迭代', phase: '第十一阶段' }
  ];

  var PHASE_NUMBERS = {
    '第一阶段': 1,
    '第二阶段': 2,
    '第三阶段': 3,
    '第四阶段': 4,
    '第五阶段': 5,
    '第六阶段': 6,
    '第七阶段': 7,
    '第八阶段': 8,
    '第九阶段': 9,
    '第十阶段': 10,
    '第十一阶段': 11
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
      item.lessonId = 'L' + item.file.match(/-L(\d{2,3})-/)[1];
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
