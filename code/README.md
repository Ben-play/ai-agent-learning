# 代码练习目录

本目录保存课程示例与阶段级离线综合项目。课件仍以 `../lessons/` 中的 L01–L16 为 Phase 1 线性学习入口；这里的项目不增加课号或课时。

## 当前目录

```text
code/
└── phase1-python/
    ├── part-a-basics/
    │   ├── agent-hello/              # L01/L02 使用的锁定 uv 包项目
    │   └── my-first-agent/           # 入门练习草稿
    └── phase1-practices-capstone/     # Phase 1 非编号离线综合验收
```

## Phase 1 综合项目

`phase1-practices-capstone/` 使用 Pydantic v2、`httpx.MockTransport`、asyncio、pytest 与 mypy，离线组合验证：

- 稳定包接口与显式状态所有权；
- 执行前验证、失败安全注册和有界动作；
- 单一重试 owner、真实异步流关闭与按项批次隔离；
- 异常根因、脱敏日志和原子 JSON 持久化；
- “重试整个批次”“只导出 Schema 不实例验证”两个故意失败的反事实。

运行方式见 [`phase1-python/phase1-practices-capstone/README.md`](phase1-python/phase1-practices-capstone/README.md)。对应的阶段决策压缩页位于 [`../best-practices/phase1-python-engineering-practices.html`](../best-practices/phase1-python-engineering-practices.html)。

## 使用规范

- 项目使用自己的 `pyproject.toml` 与 `uv.lock`，从项目根运行 `uv run --offline --locked ...`；
- `.venv`、缓存、日志和运行生成文件不进入版本控制；
- 验收只使用占位敏感值，不要求真实 API Key 或网络；
- 新阶段开始时再按真实课程结构创建对应代码目录，不预先维护虚构课号。
