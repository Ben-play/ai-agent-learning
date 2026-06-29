# 0003 - L03 变量、类型与数据结构

**日期**: 2026-06-26
**课程**: L03 变量、类型与数据结构
**状态**: 完成

## 关键知识点

1. **变量是引用**：Python 变量是标签（引用），不是盒子。多个变量可以指向同一个对象。
2. **可变 vs 不可变**：
   - 不可变：int/float/str/bool/tuple（可当 dict key）
   - 可变：list/dict/set（不可当 dict key）
3. **可变默认参数陷阱**：函数默认参数如果是可变对象，会共享状态。用 None 替代。
4. **四大容器**：
   - list：有序、可变（对话历史、工具列表）
   - dict：键值对（配置、LLM 响应）
   - tuple：不可变（坐标、版本号）
   - set：去重（已处理记录）
5. **推导式**：一行代码完成数据转换
6. **dict 深度操作**：
   - safe_get()：安全嵌套访问
   - defaultdict：自动默认值
   - ChainMap：多字典优先级合并

## Agent 开发关联

- LLM 响应是嵌套 dict，需要 safe_get() 安全访问
- Agent 配置用 ChainMap 实现优先级合并
- 工具调用去重用 set
- 对话历史管理用 list 切片

## 面试要点

- 可变 vs 不可变类型的区别
- 可变默认参数陷阱及解决方案
- defaultdict 和普通 dict 的区别
- isinstance 和 type 的区别
