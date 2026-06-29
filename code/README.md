# 代码练习目录

本目录存放所有课程的代码练习和实战项目。

## 目录结构

```
code/
├── phase1-python/              # 阶段 1：Python 基础与软件工程素养
│   ├── part-a-basics/          # Part A：基础夯实（L01-L10）
│   │   ├── L01-dev-env/        # 环境搭建
│   │   ├── L02-python-runtime/ # Python 运行机制
│   │   ├── L03-variables/      # 变量与数据类型
│   │   ├── L04-operators/      # 运算符与表达式
│   │   ├── L05-strings/        # 字符串基础
│   │   ├── L06-regex/          # 正则表达式
│   │   ├── L07-flow-control/   # 条件与循环
│   │   ├── L08-comprehensions/ # 推导式
│   │   ├── L09-seq-types/      # 列表/元组/集合
│   │   └── L10-dicts/          # 字典与数据结构选型
│   ├── part-b-advanced/        # Part B：进阶特性（L11-L18）
│   │   ├── L11-functions/      # 函数定义与参数
│   │   ├── L12-scope-lambda/   # 作用域与 Lambda
│   │   ├── L13-oop-basics/     # 类与对象
│   │   ├── L14-oop-advanced/   # 继承/多态/魔术方法
│   │   ├── L15-files-json/     # 文件读写与 JSON
│   │   ├── L16-exceptions/     # 异常处理与上下文管理器
│   │   ├── L17-decorators/     # 装饰器
│   │   └── L18-generators/     # 生成器/迭代器/闭包
│   └── part-c-agent-core/      # Part C：Agent 核心技能（L19-L22）
│       ├── L19-type-hints/     # 类型提示系统
│       ├── L20-pydantic/       # Pydantic 数据验证
│       ├── L21-async/          # async/await 与并发
│       └── L22-engineering/    # Git/测试/设计模式
├── phase2-database/            # 阶段 2：数据库基础
├── phase3-data-pipeline/       # 阶段 3：数据处理管线
├── phase4-ai-basics/           # 阶段 4：AI 知识基础
├── phase5-llm-api/             # 阶段 5：LLM 原理与 API
├── phase6-prompt-engineering/  # 阶段 6：Prompt Engineering
├── phase7-vector-rag/          # 阶段 7：向量数据库与 RAG
├── phase8-agent-architecture/  # 阶段 8：Agent 架构设计
├── phase9-frameworks/          # 阶段 9：主流框架与多智能体
├── phase10-testing/            # 阶段 10：调试、测试与评估
├── phase11-optimization/       # 阶段 11：工程优化
└── phase12-deployment/         # 阶段 12：生产部署与安全攻防
```

## 使用规范

- 每个课程文件夹内放该课的练习代码和 `README.md`（记录练习内容）
- 文件命名清晰，如 `exercise1_greet.py`、`weather_tool.py`
- 运行前确保已激活虚拟环境：`source .venv/bin/activate`
- 阶段 2-12 的目录在开始对应阶段时再创建具体内容
