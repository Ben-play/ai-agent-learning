# 大纲 v4.1 结构修复

对 v4 大纲进行结构审查后的修复。

## 修复内容

1. **死链修复** — 3 个指向不存在文件的链接已修复
2. **Phase 1 精简** — 从 22 课压缩到 15 课，Part A 从 10 课压缩到 4 课（快速复习）
3. **Phase 4 实战化** — 去掉 PyTorch 实战，改为 API 对比模型选型
4. **Phase 6 去重叠** — 恢复为纯 Prompt Engineering，Context Engineering 统一在 Phase 8
5. **Phase 8 精简** — Memory 合并为子模块，聚焦 Loop + Harness + Context Engineering
6. **Phase 9 精简** — 框架重点 2-3 个，不再罗列所有框架
7. **Phase 9.5 新增** — 高级能力（Extended Thinking/Computer Use/Agentic Coding）作为选修
8. **Phase 10+11 合并** — 测试+评估+优化合并，消除可观测性重复
9. **时间估算** — 每个阶段标注预计时间，总计约 18-24 周
10. **版本号更新** — v4 → v4.1

## 审查发现的原则

- 学习记录说用户有基础 → Phase 1 不应该太慢
- MISSION 说"Out of scope: 深度学习理论研究" → Phase 4 不应该做 PyTorch 实战
- Context Engineering 不应该在两个阶段重复讲
- 可观测性不应该在两个阶段重复讲
- 框架不需要全学，重点 2-3 个就够

**Why:** 结构问题会影响学习效率和体验
**How to apply:** 每次大纲大改后做一次结构审查
