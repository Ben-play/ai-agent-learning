# 回到顶部按钮（共享组件）

给所有课程页加了「一键回到顶部」按钮，作为共享组件 `assets/back-to-top.js`，自注入 CSS+DOM，已挂到全部 15 个页面（课程/大纲/总览/审核报告）的脚本区。

## 设计
- 贴合课程暖色编辑风：森林绿(--accent)圆盘 + 白色向上箭头；hover 变琥珀(--accent-bright)并轻微上浮 + 箭头小幅"抬升"动画。
- **外圈 SVG 滚动进度环**：随页面滚动填充（stroke-dashoffset 驱动），按钮兼作阅读进度指示——这是本设计的记忆点。
- 滚动 >400px 才淡入(scale+translateY 弹入)；点击平滑滚顶，尊重 `prefers-reduced-motion`（改瞬时）。
- 定位 `bottom:5.5rem right:2rem`，叠在主题切换按钮(bottom:2rem)之上形成竖排；移动端同步收拢；不与右侧 TOC 冲突。
- 无障碍：真实 `<button>` + aria-label + title + focus-visible 环；键盘原生可用。深浅色走 token。

## 验证
- `node --check` 通过。
- 自建 DOM 模拟跑通完整行为：构建按钮 → 顶部隐藏 → 滚过 400px 显示 → 进度环 offset 随滚动百分比变化 → 回到顶部附近再隐藏 → 点击触发 `scrollTo({top:0,behavior:'smooth'})`。
- 15 个页面均已在 `theme-toggle.js` 之后加载该脚本；与既有 fixed 定位组件无重叠。

**Why:** 课程页较长，需要快速回顶；顺带用进度环增强阅读体验。
**How to apply:** 新页面只要在脚本区加 `<script src="../assets/back-to-top.js"></script>` 即可获得，无需其它改动。参见 [[0011-quiz-interaction-redesign]]（同为共享组件模式）。

## 配色优化（二次）
- 圆盘从纯森林绿平涂改为**森林绿渐变**(160deg，上浅下深)+**奶油色箭头**(#F8F6F1)+内高光，更有质感。
- 进度环轨道从冷灰 --border 改为**暖色 --accent-subtle**，让整体统一在暖调；环填充加了一层琥珀微光(drop-shadow)。
- hover 由"绿盘→琥珀盘"的突兀换色改为**保持绿盘 + 琥珀光晕环 + 轻抬**，更克制耐看。
- **修复深色模式对比度 bug**：原来 --accent 在深色下翻成浅薄荷，圆盘会变浅底配白箭头(几乎看不清)。新增 `[data-theme="dark"]` 与 `prefers-color-scheme:dark` 覆盖：深绿渐变盘 + **薄荷箭头**(#8FF0C4)，对比正确且好看。
- 验证：node --check + DOM 行为模拟复跑均通过(逻辑未动，仅 CSS)。
