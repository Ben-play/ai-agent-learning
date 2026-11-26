# Phase 9 · 按需进阶实验（选修）

配合[第九阶段 L80–L84](../../../lessons/0097-phase9-advanced-agent-outline.html#lesson-plan) 使用。先在已有客服证据问答或本地草稿流程里重现一个瓶颈，再选一个对照。没有需求就保留原方案，Phase 10 不依赖这些实验。

### 从可信课程仓库根运行

Pages 只发布课程和本页，不发布程序、合成夹具或报告。用已有的可信检出，或从[课程源码仓库](https://github.com/Ben-play/ai-agent-learning)取得与课程相同的版本，再从仓库根运行。验收用 Python 3.11+ 和 Node.js（建议 20+），不用 `-O`，无需安装项目依赖。

```bash
python -I -X utf8 scripts/check-course-examples.py --suite advanced
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/effort/main.py
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/tools/main.py
node code/phase9-advanced-agent/advanced-lab/gui/run.cjs worked
node code/phase9-advanced-agent/advanced-lab/gui/run.cjs transfer
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/coding/lab.py
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/recovery/checkpoint.py
```

### 实验各自证明什么

- **L80**：同一合成题集对照固定低、固定高与选择性投入。独立核对事实、来源、拒答与逐项账本；缺证没有生成，不代表先前取证免费。不是厂商线上跑分。
- **L81**：用固定的合成业务读工具比较小目录、全授权目录和按需加载。按实际序列化内容计字节，独立核对目录、定义和发现记录是否完整；漏发不能算节省。另查真实本地分发和预算，候选不等于能执行。
- **L82**：仅打开源码里的 `gui/preview.html`，检查可见预览、取消、迟到结果。Node 自检复用状态控制器，不等于浏览器验证；固定页已在本机无头 Chrome 中用临时配置验证按钮与 DOM 回显；未做人工视觉、键盘或外部站点验收，不使用账户或任何业务提交。
- **L83**：OpenHands SDK 固定版本只做源码对照，不下载或运行。实际测试的是本地惰性文本候选的改动范围和结果，不执行候选代码、不运行任意命令。
- **L84**：核心 40 分钟；[选做交接](../../../lessons/0096-L84-long-task-recovery.html#stage-practice-advanced-decision)约 10 分钟，另计。两臂以相同的任务、证据、审批和预算运行固定的新进程，教学基线不持久化停止，候选持久化；重启后前者写一行，后者零行。丢回包另验原回执与零重复 INSERT。这不是 Phase 8 性能对比，未验证生产身份、并发或远程取消，也可给出不采用的结论。

### 独立行为测试

```bash
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/effort/test_effort.py -v
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/tools/test_tools.py -v
node --test code/phase9-advanced-agent/advanced-lab/gui/controller.test.cjs
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/coding/test_lab.py -v
python -I -X utf8 code/phase9-advanced-agent/advanced-lab/recovery/test_recovery.py -v
```

交接归档应有：使用的夹具版本、原方案与候选、独立正负对照、实际影响、授权边界、维护成本和未测项。不要把合成指标、独立源码阅读或本地页面通过当作生产验收。
