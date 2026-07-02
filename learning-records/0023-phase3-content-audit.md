# Phase 3 内容深审（读内容 + 代码逻辑追踪）

## 背景
用户要求对刚生成的 Phase 3（L25–L38）再深审一遍，像 Phase 2 那样读内容层。上轮已过结构+交叉链接+代码 ast。这轮聚焦：**知识正确、代码 API 用法真对（用真 SDK 核字段名）、事实准确、Quiz、跨课一致、面试覆盖**。

## 方法
- **API surface 用真 SDK 核对**：装 openai 2.44/anthropic 0.115，introspect 确认 `chat.completions.parse`+`response_format`+`.parsed`/`.refusal`（L28）、`base_url` override 等。
- **派 3 个并行 reader 深读**（L25-29/L30-34/L35-38），当资深工程师追代码逻辑找茬。
- **铁律：P1 全部独立复核**（[[verify-strong-claims-search-not-found]]）——两个 P1 用 tiktoken/JSON-Schema 实证，一个用 Tavily 查 Anthropic 官方，一个读代码确认。

## reader 报告：4 P1 + 17 P2 + 25 P3。独立复核后修 4 P1 + 4 高价值 P2
读者容易过度声明（如把 Anthropic base_url 说成"必 404"，实则兼容 shim 存在），所以每条 P1 都自证。

### 修的 4 个 P1（全部独立确认真实）
1. **L36 `{"type": str.__name__}` 生成非法 JSON Schema**：`str.__name__`="str" 但 JSON Schema 要 "string"。实证确认。而且这段被当"框架底层原理"教。**已修**：加 `_JSON_TYPE={str:"string",int:"integer",float:"number",bool:"boolean"}` 映射（两个代码块都改）。
2. **L30 `count_tokens` 对 `content=None` 崩溃**：`enc.encode(None)` 实测抛 TypeError，而本课全是 tool 消息（content 常为 None）。**已修**：`enc.encode(m.get("content") or "")`。
3. **L38 `generate()` 双调模型 + 成本追踪未接线**：`run_tool_loop` return final_msg 但没 append，`finalize` 又对未更新的 messages 再调一次 → text 路径重复生成最终轮。**已修**：run_tool_loop 退出前 append 最终 msg；generate 的 text 路径直接返回 final_msg.content 不再调，json/stream 才走 finalize。
4. **L38 Anthropic base_url 标"OpenAI 兼容层"误导**（读者说必 404，我 Tavily 查 Anthropic 官方：`/v1/` 兼容端点**确实存在**但明确"有限兼容、full features 用 native"）→ **读者过度声明，降为 P2 处理**。**已修**：注释改"有限兼容（Extended Thinking 等用不了），生产更稳走 LiteLLM 网关（L32）"。

### 修的高价值 P2
5. **L27 回填漏 append 助手 tool_calls 消息**：OpenAI 要求 tool 结果前必须有对应的 tool_calls 消息，否则 400。照抄会报错，且这是 FC 基础课。**已修**：加 `messages.append(msg)` + "两个点"→"三个点"说明。
6. **L31 `wait_exponential(min=1,max=8)` 注释写"1→2→4→8s"实际是 2→4→8→8s**：tenacity 默认 multiplier=1 序列是 2,4,8…。**已修**：改 `multiplier=1,min=1,max=8` + "约 1→2→4→8s，实际以 tenacity 为准"。

## 没改的（真实但低 ROI，留作 polish 清单）
读者还提了 ~30 条 P2/P3：多厂商 vision 形状差异callout（L29 只给 OpenAI 形状）、`[DONE]` sentinel 是 OpenAI-specific（L26）、529 归给 OpenAI（L32 应属 Anthropic）、`gen_ai.tool.call.arguments` 非标准 span 属性（L33）、fill-ratio↔lost-in-middle 混淆（L30）、L34 §6 strict+optional 矛盾、MAX_TURNS 过度包装成生产级、L36 dispatch 没接 Pydantic 校验、cost tracker 全程"从略"……这些**属增强或措辞**，本轮 scope=修真错（P1+关键P2）。**系统性弱点**：整个 Phase 3 代码教 OpenAI SDK surface 却把 Anthropic 当同级一手源——续课可考虑要么 OpenAI-only、要么两家形状并列。

## 复核（改完必跑）
- 5 个改动文件 div 全平衡；改动代码全 ast.parse 通过；7 处 fix-needle 逐一确认在位。

**特别教训**：这轮 reader 又有过度声明（Anthropic base_url"必 404"、L30 摘要 bug 自己边说边撤回）→ **P1 必自证**再修，用 tiktoken/JSON-Schema/Tavily 各证一条。代码类 P1（type 名、encode None、双调用）尤其要亲自追逻辑。

**Why:** 用户要对刚生成的 Phase 3 深审找可优化点。
**How to apply:** 内容审 = 真 SDK 核 API + 并行 reader 追代码 + **P1 全部实证**（代码类追逻辑、事实类查官方）。改完必跑 div/ast/needle。续 Phase 4 若代码教多厂商，先定"OpenAI-only 还是两家并列"避免 base_url 类误导。
