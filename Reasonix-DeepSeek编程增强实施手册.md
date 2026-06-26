# Reasonix DeepSeek 编程能力增强实施手册

> **用途：** 本文档供 AI Agent 读取并逐项执行。每步给出具体文件路径和内容，Agent 按顺序操作即可复现整套增强配置。

---

## 一、前提条件

- Reasonix 已安装（桌面端或 CLI）
- DeepSeek API Key 已配置（环境变量 `DEEPSEEK_API_KEY`）
- 操作系统：Windows（路径使用 `%AppData%`；macOS/Linux 对应 `~/.reasonix`）

---

## 二、核心配置文件

### 2.1 编辑 `config.toml`

**路径：** `%AppData%\reasonix\config.toml`

**操作：** 确保以下键值存在且正确。不存在则追加到文件末尾，存在则覆盖。

```toml
config_version = 3
default_model = "deepseek-pro"

[agent]
temperature = 0.0
auto_plan = "on"
memory_compiler = { enabled = true }
reasoning_language = "zh"
auto_plan_classifier = "deepseek-flash"
soft_compact_ratio = 0.55
compact_ratio = 0.78
compact_force_ratio = 0.9
planner_model = "deepseek-pro"
subagent_model = "deepseek-pro"
subagent_models = { review = "deepseek-pro", security_review = "deepseek-pro" }
subagent_effort = "high"
subagent_efforts = { review = "max", security_review = "max" }
output_style = "deepseek-coding-max"

[[providers]]
name = "deepseek-pro"
kind = "openai"
base_url = "https://api.deepseek.com"
model = "deepseek-v4-pro"
api_key_env = "DEEPSEEK_API_KEY"
context_window = 1000000
price = { cache_hit = 0.025, input = 3, output = 6, currency = "CNY" }
effort = "max"

[[providers]]
name = "deepseek-flash"
kind = "openai"
base_url = "https://api.deepseek.com"
model = "deepseek-v4-flash"
api_key_env = "DEEPSEEK_API_KEY"
context_window = 1000000
price = { cache_hit = 0.02, input = 1, output = 2, currency = "CNY" }
effort = "high"

[lsp]
enabled = true

[tools]
bash_timeout_seconds = 300

[tools.shell]
prefer = "powershell"

[sandbox]
bash = "enforce"
network = true
```

**验证：** 重启 Reasonix，确认默认模型显示为 `deepseek-pro`。

---

## 三、系统角色文件

### 3.1 全局编码画像

**路径：** `%AppData%\reasonix\REASONIX.md`

**操作：** 创建或覆盖此文件，写入以下内容。

```markdown
# Global DeepSeek Coding Profile

## Role
- Focus on coding, debugging, code review, verification, and engineering delivery.
- Reply in natural Chinese for Chinese users; keep code, commands, paths, APIs, and config names in English when clearer.
- Prioritize correctness, maintainability, compatibility, and verifiability.

## Standard Workflow
- Use the fixed workflow: `inspect -> plan -> change -> verify -> summarize`.
- Read the relevant code, tests, configs, logs, and failures before concluding or editing.
- For non-trivial work, state a short plan and then execute in small verified steps.

## Coding Rules
- Prefer the smallest sufficient change; avoid unrelated refactors.
- Reuse existing dependencies, patterns, and abstraction layers whenever practical.
- Stay sensitive to edge cases affecting correctness, security, stability, performance, or compatibility.
- Verify uncertain facts instead of guessing runtime state, API behavior, or tool results.

## Verification
- Run the narrowest useful validation first, then broaden validation when justified.
- Never claim completion without verification evidence.
- If verification is blocked, state the blocker, the unverified parts, and the residual risks.

## Learning Loop
- After each meaningful task, extract 1-3 reusable lessons.
- Suggest durable memory only for stable, cross-task, non-sensitive rules with long-term value.
- Do not store one-off details, temporary paths, temporary workarounds, secrets, or private data as long-term memory.

## Anti-Stall
- If the same path fails to advance twice, switch evidence sources or debugging angle.
- Prefer reproduction, logs, tests, comparisons, and isolation experiments over repeating the same attempt.
```

### 3.2 兼容镜像

**路径：** `%AppData%\reasonix\.reasonix\REASONIX.md`

**操作：** 将 3.1 的文件内容完整复制到此路径（兼容不同 Runtime 对 home 目录的解析差异）。

### 3.3 输出风格约束

**路径：** `%AppData%\reasonix\output-styles\deepseek-coding-max.md`

**操作：** 创建目录 `output-styles`（如不存在），写入以下内容。

```markdown
# DeepSeek Coding Max

Use a high-discipline coding style optimized for engineering delivery.

## Working Style
- Start from evidence, not assumptions.
- For substantial work, follow `inspect -> plan -> change -> verify -> summarize`.
- Keep changes as small as correctness allows.
- Prefer explicit root-cause reasoning over trial-and-error edits.

## Quality Bar
- Prioritize correctness, regression safety, clarity, maintainability, and validation.
- Preserve surrounding conventions unless the task explicitly asks for change.
- Check meaningful edge cases that affect users, data, stability, performance, or security.
- Prefer solutions with a clear verification path.

## Learning
- At the end of substantial tasks, summarize root cause, fix strategy, verification evidence, and reusable lessons.
- Promote only stable, non-sensitive, cross-task lessons into durable memory candidates.

## Response Shape
- Be concise, concrete, and action-oriented.
- Final answers should emphasize outcome, validation, remaining risk, and lessons when relevant.
```

**验证：** 重启 Reasonix，发送一条编程任务，观察回复是否遵循 `inspect → plan → change → verify → summarize` 流程。

---

## 四、斜杠命令

### 4.1 ship 命令（高纪律编码流程）

**路径：** `%AppData%\reasonix\commands\ship.md`

```markdown
---
description: High-discipline coding execution flow
argument-hint: <task>
---
Execute this coding task with a strict engineering workflow.

Task: $ARGUMENTS

Requirements:
1. Read the relevant code, tests, configs, and logs first.
2. For non-trivial work, state a short plan before editing.
3. Make the smallest correct change and avoid unrelated refactors.
4. Run targeted validation first, then widen validation only when needed.
5. Finish with:
   - change summary
   - verification evidence
   - remaining risks
   - 1-3 reusable lessons

If durable memory candidates appear, list them separately.
```

### 4.2 learn 命令

**路径：** `%AppData%\reasonix\commands\learn.md`

```markdown
---
description: Extract reusable lessons from the current task
argument-hint: [task]
---
Extract 1-3 reusable, cross-task lessons from the current task. Focus on:
- Root cause patterns
- Fix strategies that worked
- Verification approaches that caught issues
- Anti-patterns to avoid

Output each lesson as a candidate for durable memory. Do not include secrets, one-off paths, or temporary workarounds.
```

### 4.3 review-bugs 命令

**路径：** `%AppData%\reasonix\commands\review-bugs.md`

```markdown
---
description: Review the current changes with a bug-finding mindset
argument-hint: [focus-area]
---
Review the current diff with a focus on finding bugs. For each issue found, report:
- File and line
- Severity (critical / high / medium / low)
- Root cause
- Fix suggestion
```

### 4.4 兼容镜像

将以上三个文件同步复制到 `%AppData%\reasonix\.reasonix\commands\` 目录。

---

## 五、技能安装

### 5.1 前端品味技能集（taste-skill，13 个技能）

```bash
reasonix install-capability --source https://github.com/Leonxlnx/taste-skill --kind skill
```

安装后确认以下技能出现在 `/skills` 列表中：
- `design-taste-frontend`（默认前端首选）
- `design-taste-frontend-v1`（v2 回退）
- `gpt-taste`
- `high-end-visual-design`
- `minimalist-ui`
- `industrial-brutalist-ui`
- `image-to-code`
- `redesign-existing-projects`
- `full-output-enforcement`
- `stitch-design-taste`
- `imagegen-frontend-web`
- `imagegen-frontend-mobile`
- `brandkit`

### 5.2 文案去 AI 化技能

```bash
reasonix install-capability --source https://github.com/blader/humanizer --kind skill
reasonix install-capability --source https://github.com/B1lli/remove-ai-flavor-writing-skill --kind skill
```

安装后确认：
- `humanizer` 出现在技能列表（英文去 AI 化）
- `remove-ai-flavor` 出现在技能列表（中文去 AI 味）

### 5.3 技能自动调用约定（长期记忆）

**路径：** `%AppData%\reasonix\projects\<project-hash>\memory\` 下创建记忆文件。

**操作：** 在 Reasonix 中执行以下自然语言指令，让 Memory Compiler 自动记录：

> 记住以下约定：当任务涉及前端/UI/设计编码时，自动调用 design-taste-frontend 技能。当输出面向最终用户的中文文案时，自动调用 remove-ai-flavor 技能。英文文案则自动调用 humanizer 技能。技术文档和代码注释不需要去 AI 化。

或者直接创建记忆文件（如果 Memory Compiler 不可用）：

**taste-skill 自动调用：**
```yaml
触发条件: 前端/UI/设计编码任务
动作: run_skill({ name: "design-taste-frontend", arguments: "<任务描述>" })
```

**去 AI 化自动调用：**
```yaml
触发条件: 输出面向用户的中文文字
动作: run_skill({ name: "remove-ai-flavor", arguments: "<待处理文本>" })

触发条件: 输出面向用户的英文文字
动作: run_skill({ name: "humanizer", arguments: "<待处理文本>" })
```

---

## 六、Memory Compiler v5 配置

### 6.1 确认已启用

在 `config.toml` 中确认：
```toml
[agent]
memory_compiler = { enabled = true }
```

### 6.2 验证记忆图谱工作

发送一条编程任务，完成后检查以下目录是否生成了轨迹文件：

```
%AppData%\reasonix\projects\<project-hash>\memory\compiler\
  ├── state.json
  ├── traces.jsonl
  └── learning_traces.jsonl
```

`state.json` 应包含 HIGH_SIGNAL 记忆节点，`traces.jsonl` 应包含策略选择记录（含 selected_strategy、outcome、quality_score 等字段）。

---

## 七、完整文件清单

实施完成后，以下文件应全部就位：

| # | 文件 | 类型 |
|---|------|------|
| 1 | `%AppData%\reasonix\config.toml` | 配置 |
| 2 | `%AppData%\reasonix\REASONIX.md` | 角色注入 |
| 3 | `%AppData%\reasonix\.reasonix\REASONIX.md` | 兼容镜像 |
| 4 | `%AppData%\reasonix\output-styles\deepseek-coding-max.md` | 输出风格 |
| 5 | `%AppData%\reasonix\.reasonix\output-styles\deepseek-coding-max.md` | 兼容镜像 |
| 6 | `%AppData%\reasonix\commands\ship.md` | 命令 |
| 7 | `%AppData%\reasonix\commands\learn.md` | 命令 |
| 8 | `%AppData%\reasonix\commands\review-bugs.md` | 命令 |
| 9 | `%AppData%\reasonix\.reasonix\commands\ship.md` | 兼容镜像 |
| 10 | `%AppData%\reasonix\.reasonix\commands\learn.md` | 兼容镜像 |
| 11 | `%AppData%\reasonix\.reasonix\commands\review-bugs.md` | 兼容镜像 |
| 12 | `%AppData%\reasonix\skills\humanizer\SKILL.md` | 技能 |
| 13 | `%AppData%\reasonix\skills\remove-ai-flavor\SKILL.md` | 技能 |
| 14 | `%AppData%\reasonix\skills\design-taste-frontend\SKILL.md` | 技能 |
| 15 | `%AppData%\reasonix\skills\*` (其余 12 个 taste-skill) | 技能 |
| 16 | `%AppData%\reasonix\projects\<hash>\memory\compiler\state.json` | 记忆 |
| 17 | `%AppData%\reasonix\projects\<hash>\memory\compiler\traces.jsonl` | 记忆 |

---

## 八、效果验证

逐项检查以下行为是否生效：

1. **角色注入生效：** 任意编程问题，回复是否先 inspect 再给出方案？是否在完成后附验证证据？
2. **Memory Compiler 生效：** 执行两个相关任务，第二个任务是否引用了第一个任务的经验？
3. **技能自动调用生效：** 请求「做一个 landing page」，是否自动加载了 `design-taste-frontend`？
4. **去 AI 化生效：** 输出中文文案时是否避免了「不是…而是…」「先…再…」「真正重要的是…」等句式？
5. **策略选择生效：** 检查 `traces.jsonl`，是否每轮都有 `strategy_used` 字段且后续任务的选择依据从「中性先验」进化为「先前成功率」？

---

*文档版本：1.0 · 最后更新：2026-06-26*
