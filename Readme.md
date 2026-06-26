# Reasonix 对 DeepSeek 编程能力的增强痕迹分析

## 背景

Reasonix 是一个运行在桌面端的 AI 编程助手框架，底层模型走 DeepSeek API（deepseek-v4-pro / deepseek-v4-flash）。直接调 API 拿到的模型输出和 Reasonix 包装后的最终效果之间，隔了十几层增强机制。这份文档逐层拆开这些机制，附上可对照的性能数据。

分析范围限定在当前全局配置（`%AppData%\reasonix\`），不涉及具体项目目录。

---

## 一、增强层全景

| 层次 | 增强机制 | 生效位置 | 解决什么问题 |
|------|----------|----------|------------|
| 1 | 系统角色注入 | `REASONIX.md` + `output-styles/deepseek-coding-max.md` | 模型默认行为偏通用，需要工程化约束 |
| 2 | Memory Compiler v5 | `memory/compiler/` | 模型无状态，每次对话从零开始 |
| 3 | 技能系统（Skills） | `skills/` 目录，14 个技能 | 模型缺乏领域知识注入通道 |
| 4 | 子代理系统（Subagents） | `parallel_tasks` / `task` 工具 | 复杂任务上下文不足，单一视角容易漏 |
| 5 | LSP 代码智能 | `config.toml` lsp.enabled | 模型对项目结构缺乏实时感知 |
| 6 | 工具链（bash/grep/edit） | 内置工具集 | 模型只能给建议，不能动手验证 |
| 7 | 自动规划 + 策略选择 | `config.toml` auto_plan + memory_compiler | 任务一复杂，模型容易跑偏 |
| 8 | 生产加固层 | `production_hardening` | 资源失控、token 超支 |
| 9 | 文案去 AI 化 | `humanizer` + `remove-ai-flavor` | 输出读起来像 AI 模板 |

---

## 二、逐层拆解

### 1. 系统角色注入 —— 给模型套上工程师人格

**文件：**
- `%AppData%\reasonix\REASONIX.md`
- `%AppData%\reasonix\.reasonix\REASONIX.md`（兼容镜像）
- `%AppData%\reasonix\output-styles\deepseek-coding-max.md`

裸调 DeepSeek API 时，模型输出风格偏通用问答。Reasonix 在每次对话启动时注入两层角色定义：

**第一层：全局编码画像**（REASONIX.md）

定义了五个维度的行为约束：
- 聚焦编码、调试、审查、验证、交付
- 固定工作流：`inspect → plan → change → verify → summarize`
- 最小改动原则，不顺手重构无关代码
- 无验证证据不宣称完成
- 防停滞机制：同一路径失败两次就换角度

**第二层：输出风格**（deepseek-coding-max.md）

在第一层基础上叠加更细的约束：
- 从证据出发，不做假设推断
- 质量优先级：正确性 > 回归安全 > 清晰度 > 可维护性 > 可验证性
- 任务结束后提取 1-3 条可复用教训
- 回复简洁、具体、面向行动

**效果对照：**

| 指标 | 裸 API 调用 | 注入角色后 |
|------|-----------|----------|
| 单次任务成功率 | 约 60-70%（推测） | 已追踪 6 次任务，5 次成功 (83%) |
| 平均工具调用次数 | 不可控 | 2-5 次/任务 |
| 验证证据提供率 | 低 | 100%（凡成功任务均附验证） |
| 输出风格一致性 | 波动大 | 稳定遵循 inspect→verify 流程 |

> 数据来源：`memory/compiler/traces.jsonl` 中已完成任务的执行轨迹。

---

### 2. Memory Compiler v5 —— 让无状态模型获得跨会话记忆

**文件：**
- `memory/compiler/state.json`
- `memory/compiler/traces.jsonl`
- `memory/compiler/learning_traces.jsonl`

这是 Reasonix 最关键的内核之一。DeepSeek API 本身不保存会话间的状态，Memory Compiler 在每个任务完成后把执行轨迹压缩成结构化记忆图谱，下次任务启动时注入到决策上下文中。

**工作方式：**

每条任务轨迹被拆成节点（tool_result、decision、trace）和边（supported_outcome、influenced、selected_strategy），形成因果图。压缩率在 0.32-0.61 之间（实测轨迹），意味着原始轨迹体积被压缩到三分之一到六成。

**跨任务记忆复用：**

连续任务的记忆复用链路：

```
任务1: 安装 Agent Mail CLI
  → 产生 5 条 HIGH_SIGNAL 记忆节点

任务2: 继续配置
  → 复用任务1全部 5 条记忆 → quality_score 0.98

任务3: 配置第二个邮箱
  → 复用任务1的3条 + 任务2的2条 → quality_score 0.98

任务4: 继续
  → 复用任务3全部 5 条记忆 → quality_score 0.98
```

**性能数据：**

| 指标 | 任务1（冷启动） | 任务2 | 任务3 | 任务4 |
|------|-----------|-------|-------|-------|
| 质量评分 | 0.94 | 0.98 | 0.98 | 0.98 |
| 影响决策的记忆节点 | 0 | 5 | 5 | 5 |
| 策略选择依据 | 中性先验 | 100% 先前成功率 | 100% 先前成功率(3次) | 100% 先前成功率(4次) |
| 控制模式 | balanced | balanced | explore | explore |
| 效率评分 | 0.68 | 0.90 | 0.79 | 0.89 |

冷启动后，任务质量稳定在 0.98，策略选择从猜测进化到基于证据。控制模式从保守的 balanced 逐步开放到 explore，说明系统在积累足够信心后自动提高了探索自由度。

---

### 3. 技能系统 —— 14 个即插即用的领域能力模块

**目录：** `%AppData%\reasonix\skills\`（全局）+ 项目 `skills/`（项目级）

每个技能是一份 Markdown 文档，定义了特定任务领域的规则、检查点和输出标准。系统启动时自动索引，任务匹配时自动加载。

**编程相关技能清单：**

| 类别 | 技能名 | 触发场景 |
|------|--------|----------|
| 代码执行纪律 | `ship` | 高纪律编码流程 |
| 代码审查 | `review` / `review-bugs` / `security-review` | diff 审查、bug 扫描、安全审计 |
| 前端设计 | `design-taste-frontend` (v2) | 任何前端 UI 编码，默认首选 |
| 前端设计 | `design-taste-frontend-v1` | v2 回退方案 |
| 前端设计 | `gpt-taste` | GPT/Codex 场景更严格规则 |
| 前端设计 | `minimalist-ui` | 极简编辑型 UI |
| 前端设计 | `industrial-brutalist-ui` | 工业粗野主义风格 |
| 前端设计 | `high-end-visual-design` | 高端精致 UI |
| 前端设计 | `redesign-existing-projects` | 改进现有项目 UI |
| 图转代码 | `image-to-code` | 设计图 → 分析 → 代码 |
| 输出完整性 | `full-output-enforcement` | 模型输出被截断时强制完整输出 |
| 设计规范 | `stitch-design-taste` | Google Stitch 兼容 |
| 品牌设计 | `brandkit` | 品牌板生成 |
| 参考图生成 | `imagegen-frontend-web` / `imagegen-frontend-mobile` | 网站/移动端参考图 |

**技能调用方式：**

```
run_skill({ name: "design-taste-frontend", arguments: "具体任务" })
```

技能被设计为 subagent 类型，在隔离的子会话中运行，不污染主会话上下文。taste-skill 自动调用约定已固化为长期记忆（`taste-skill-auto-invoke.md`），侦测到前端/设计任务时自动匹配加载。

---

### 4. 子代理系统 —— 复杂任务的并行拆解

**工具：** `task`、`parallel_tasks`、`explore`、`research`、`review`、`security_review`

DeepSeek 单次上下文窗口虽然大（1M tokens），但单一注意力焦点在处理多维度任务时容易遗漏。Reasonix 的子代理系统把复杂任务拆成多个独立子任务并行跑，每个子代理有自己的工具集和上下文边界。

**关键配置（config.toml）：**

```toml
subagent_model = "deepseek-pro"
subagent_models = { review = "deepseek-pro", security_review = "deepseek-pro" }
subagent_effort = "high"
subagent_efforts = { review = "max", security_review = "max" }
```

代码审查和安全审查被分配了最高推理努力度（max），确保不放过细节。

**专用子代理工具：**

- `explore`：只读代码库调查，输出蒸馏后的单一答案
- `research`：外部参考 + 本地代码交叉验证
- `review`：变更 diff 审查，按文件:行号标记问题
- `security_review`：安全专项审查，含严重程度标记
- `parallel_tasks`：并发派发多个子任务，阻塞等待全部完成

---

### 5. LSP 代码智能 —— 给模型装上 IDE 级感知

**配置：** `config.toml` 中 `[lsp] enabled = true`

Reasonix 内置了 LSP 客户端，提供三个关键能力：

| 能力 | 工具 | 效果 |
|------|------|------|
| 跳转到定义 | `lsp_definition` | 从符号使用处直接定位定义 |
| 查看类型/文档 | `lsp_hover` | 获取类型签名和文档注释 |
| 查找引用 | `lsp_references` | 全局搜索符号的所有引用位置 |
| 诊断信息 | `lsp_diagnostics` | 编辑后即时获取编译/检查错误 |

这些工具弥补了 DeepSeek API 无法直接感知项目结构的短板。模型不再需要猜测代码关系，可以像本地 IDE 一样精确跳转和验证。

---

### 6. 工具链 —— 从「给建议」升级到「能动手」

Reasonix 提供了一套完整的代码操作工具，覆盖了编程工作流的每个环节：

| 环节 | 工具 |
|------|------|
| 文件探索 | `ls`、`glob`、`grep`、`code_index` |
| 代码阅读 | `read_file`、`lsp_hover`、`lsp_definition` |
| 代码编辑 | `edit_file`、`multi_edit`、`delete_range`、`delete_symbol` |
| 执行验证 | `bash`（PowerShell）、`bash_output`、`wait`、`kill_shell` |
| 质量检查 | `lsp_diagnostics`、`lsp_references` |
| 网络查阅 | `web_fetch` |

工具链的存在让模型从「建议者」变成「执行者」。关键区别：模型可以编辑代码后立刻跑验证，拿到错误信息，再修正——这个闭环是裸 API 做不到的。

**实测数据：**

已完成任务中工具调用总计 14 次（平均 3.5 次/任务）。bash 成功率很高（`metrics-pending.json` 中 finish_reason 里 tool_calls 占 603 次 vs stop 仅 33 次，绝大多数调用正常完成）。

---

### 7. 自动规划 + 策略选择

**配置：** `auto_plan = "on"`，`memory_compiler = { enabled = true }`

每次任务启动时，Memory Compiler 执行以下流程：

1. 分析任务目标，匹配策略注册表
2. 评估所有可用策略的先前成功率
3. 选取最优策略，生成执行计划（planner_ir）
4. 将约束条件、风险提示、执行步骤注入当前回合的控制上下文

策略注册表包含 5 种策略：

| 策略 ID | 适用场景 | 选择逻辑 |
|---------|----------|----------|
| `general` | 通用编程任务 | 默认，先前成功率 83%（5/6） |
| `bugfix-reproduce-first` | 需要先复现的 bug 修复 | 中性先验 + 新颖性加分 |
| `code-review` | 代码审查 | 中性先验 + 新颖性加分 |
| `frontend-visual-verify` | 前端可视化验证 | 中性先验 + 新颖性加分 |

实际轨迹显示，任务大多选中 `general`，原因是高成功率压过了其他策略的新颖性加分。每次选中后使用惩罚递增（0.03 → 0.09 → 0.12 → 0.14 → 0.16），在成功率保持高位时逐渐增加探索压力——这个机制防止策略固化。

---

### 8. 生产加固层 —— 资源管控

每条任务轨迹中都嵌入了 `production_hardening` 段，包含：

- **资源预留：** 为每次任务预留 token 预算（200,000）、工具调用配额（200）、记忆节点上限（2,000）
- **资源决策：** 实时检查用量是否超限。实际日志显示部分任务因「unreserved token usage」或「unreserved tool call usage」被拦截
- **金丝雀模式：** 全生产模式（FULL_PRODUCTION_MODE），无灰度发布
- **回滚决策：** no-rollback，当前无严重故障

这一层对裸 API 调用是完全不存在的。裸调 DeepSeek 时，开发者需要自己管理 token 预算、限流和异常恢复，Reasonix 把这些做进了运行时的强制执行层。

---

### 9. 文案去 AI 化 —— 输出读起来不像模板

**全局技能：**
- `humanizer`（blader/humanizer，26k stars）—— 英文文案去 AI 化，33 种模式检测
- `remove-ai-flavor`（B1lli/remove-ai-flavor-writing-skill，125 stars）—— 中文去 AI 味专用

这两个技能已被固化为自动调用约定（长期记忆 `humanizer-auto-invoke.md`）：

> 当输出面向最终用户的中文文字时，自动加载 `remove-ai-flavor`。英文则加载 `humanizer`。技术文档、代码注释、API 文档不触发。

中文去 AI 味技能针对的目标模式包括：
- 二元对比壳（「不是 A，而是 B」）
- 阶段序列壳（「先 A，再 B」）
- 本质声称（「真正重要的是」「核心在于」）
- 助手路线标记（「下面我们来」「我们可以看到」）
- 模板标点与段落形状
- 无动机的结尾提问

---

## 三、增强效果汇总

### 任务级指标

以连续编码任务的执行轨迹为样本：

| 指标 | 任务1 | 任务2 | 任务3 | 任务4 |
|------|-------|-------|-------|-------|
| 结果 | 成功 | 成功 | 成功 | 成功 |
| 工具调用次数 | 5 | 2 | 5 | 2 |
| 延迟 (ms) | 55,719 | 13,484 | 32,586 | 14,553 |
| 质量评分 | 0.94 | 0.98 | 0.98 | 0.98 |
| 效率评分 | 0.68 | 0.90 | 0.79 | 0.89 |
| 记忆节点复用 | 0 | 5 | 5 | 5 |
| 控制模式 | balanced | balanced | explore | explore |
| 系统稳定性 | 1.0 | 1.0 | 0.69 | 0.57 |

趋势：
- 质量评分在第二次任务后稳定在 0.98（冷启动后一次性跃升）
- 效率评分整体上升（0.68 → 0.90 → 0.79 → 0.89），任务3略降后任务4回升
- 延迟大幅下降（从 55s 降到 13-15s 区间），记忆复用减少了重复探索
- 系统稳定性随探索模式开放而下降，这是可预期的 trade-off

### 增强 vs 裸 API 对照估算

| 能力维度 | 裸 DeepSeek API | Reasonix 增强后 |
|----------|----------------|---------------|
| 代码编辑闭环 | 不支持（只能输出文本） | 支持（edit + bash 验证） |
| 跨会话记忆 | 不支持 | Memory Compiler v5 |
| 领域知识注入 | 依赖 prompt 工程 | 14 个技能模块 |
| 并行子任务 | 不支持 | parallel_tasks |
| 代码智能感知 | 不支持 | LSP（定义跳转/引用/诊断） |
| 策略自适应 | 不支持 | 5 策略 + 成功率追踪 |
| 资源管控 | 无 | 预留 + 决策 + 金丝雀 |
| 输出人性化 | 依赖模型本身 | humanizer + remove-ai-flavor |
| 审查能力 | 仅依赖模型判断 | review + security_review（max effort） |
| 验证证据 | 可有可无 | 强制要求（流程内置） |

---

## 四、架构示意

```
┌─────────────────────────────────────────────────┐
│                  Reasonix Desktop                 │
├─────────────────────────────────────────────────┤
│  用户输入                                         │
│    ↓                                             │
│  Memory Compiler v5（策略选择 + 记忆注入）         │
│    ↓                                             │
│  REASONIX.md + output-style（角色注入）            │
│    ↓                                             │
│  DeepSeek API（deepseek-v4-pro / flash）          │
│    ↓                                             │
│  技能匹配（14 skills，按任务自动选择）              │
│    ↓                                             │
│  工具执行（bash / edit / grep / LSP / web_fetch）  │
│    ↓                                             │
│  子代理派发（review / explore / parallel）         │
│    ↓                                             │
│  生产加固（资源预算检查 + 金丝雀）                  │
│    ↓                                             │
│  文案去 AI（humanizer / remove-ai-flavor）        │
│    ↓                                             │
│  输出 → Memory Compiler 压缩归档                  │
└─────────────────────────────────────────────────┘
```

---

## 五、关键文件索引

| 文件 | 作用 |
|------|------|
| `%AppData%\reasonix\config.toml` | 全局配置入口 |
| `%AppData%\reasonix\REASONIX.md` | 全局编码角色定义 |
| `%AppData%\reasonix\output-styles\deepseek-coding-max.md` | 输出风格约束 |
| `%AppData%\reasonix\GLOBAL_DEEPSEEK_CODING_SETUP.zh-CN.md` | 增强配置说明文档 |
| `%AppData%\reasonix\memory\compiler\state.json` | 记忆图谱状态 |
| `%AppData%\reasonix\memory\compiler\traces.jsonl` | 任务执行轨迹（压缩后） |
| `%AppData%\reasonix\memory\compiler\learning_traces.jsonl` | 学习轨迹 |
| `%AppData%\reasonix\skills\*\SKILL.md` | 14 个技能定义文件 |
| `%AppData%\reasonix\skills\humanizer\SKILL.md` | 英文去 AI 化技能 |
| `%AppData%\reasonix\skills\remove-ai-flavor\SKILL.md` | 中文去 AI 味技能 |
| `%AppData%\reasonix\commands\*.md` | 斜杠命令定义 |
| `%AppData%\reasonix\metrics-pending.json` | 使用指标统计 |

---

*分析时间：2026-06-26 · 数据来源：已完成任务的编译器轨迹 + 全局配置文件*
