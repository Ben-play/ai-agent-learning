# Part B 剩余课程全部落地（L06–L11）

一次性把 Part B（Python 进阶特性）L05 之后的 6 节课全部从大纲落地为完整可交互课程。至此 Phase 1 的 Part A（L01–L04）+ Part B（L05–L11）共 11 节内容课全部写完，仅剩 Part C（L12–L16）。

## 本批新增课程
| 文件 | 课 | 核心 |
|------|-----|------|
| 0010 | L06 作用域、闭包与 Lambda | LEGB、闭包(nonlocal)、lambda+高阶函数；练习=闭包 Agent 计数器 |
| 0011 | L07 类、对象与 @dataclass | class/classmethod/staticmethod、@dataclass/field/frozen、dataclass vs Pydantic；练习=Message/ToolCall/AgentState |
| 0012 | L08 继承、多态与 __call__ | super、ABC、__call__(工具核心模式)、多态、组合优于继承；练习=BaseTool 可调用基类 |
| 0013 | L09 文件、JSON 与 Dict 深度操作 | with open/pathlib、json dump(s)/load(s)、JSON Lines 流解析容错、orjson；练习=解析流式响应 |
| 0014 | L10 异常处理、日志与上下文管理器 | try/except/else/finally、自定义异常+raise from、logging、@contextmanager、tenacity；练习=API 调用上下文管理器 |
| 0015 | L11 装饰器 | 装饰器=闭包+高阶、functools.wraps、带参三层、@tool 从签名生成 Schema；练习=手写 @tool |

## 设计要点
- **Agent 主线贯穿**：闭包→装饰器→@tool 一条线，L11 收官时把"函数签名(L05)+类型注解(L13)+docstring→工具 Schema"闭环，明确指向 L14 Pydantic。L11 末尾加了"Part B 完成"里程碑提示。
- **课程间交叉引用**：可变默认值(L03/L05)、解包(L05)、字符串(L04)、生成器(L12) 等前后链接。

## 验证（按审核清单）
- **代码全部先跑通再落地**：开工前用一个集中脚本验证了 6 节课的所有核心代码(闭包计数器、@dataclass+frozen 的 FrozenInstanceError、ABC+__call__、JSON Lines 容错解析、异常链+上下文管理器+重试+logging、@tool 用 inspect 提取 schema)——Python 3.14 全通过，无一节带错误代码。
- **结构验证**：6 节课 HTML 标签全平衡、每节 2 道 Quiz 各恰 1 正确答案、5 脚本齐全、进度条 37%→69% 递进。
- **导航**：L01→L11 在 bottom-nav/course-bar 连续无跳号；6 节课均 3/3 登记(两个 nav + 大纲链接)；nav node --check 通过。
- 注：tenacity/orjson 环境未装，课程作为"真实工具"引用(RESOURCES 有链接)，验证时用 stdlib 等价实现确认模式正确。

**Why:** 用户要求"继续生成 Part B 后面的课程"。
**How to apply:** Part B 完结。下一步 Part C（L12 生成器/Streaming、L13 类型提示、L14 Pydantic、L15 httpx、L16 async）。写 L13/L14 时记得承接 L11 埋的 @tool→Schema 线，L14 用 Pydantic 深化。参见 [[0010-l05-lesson-authored]]。
