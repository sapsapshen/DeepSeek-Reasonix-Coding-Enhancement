# Reasonix 对 DeepSeek 编程能力的增强

这个仓库记录 Reasonix 如何把 DeepSeek 收成一套可复现的编程配置，并提供可检查、可安装的模板。分析样本来自 2026-06-26 的本机轨迹。安装步骤对齐 2026-11-13 的 Reasonix `studio` 文档和 DeepSeek 官方价格页。

模板在 `templates/`。安装与检查入口是 `reasonix_profile.py`。逐步操作见 [实施手册](Reasonix-DeepSeek编程增强实施手册.md)。

## 当前模型与配置

Reasonix 的活跃线是 2.x（`studio`）。1.x（`main-v2`）仍在维护，两边共用同一个 Reasonix home：

| 系统 | Reasonix home |
| --- | --- |
| macOS / Linux | `~/.reasonix` |
| Windows | `%APPDATA%\reasonix` |

`REASONIX_HOME` 会覆盖上表。provider 密钥只放在 `<Reasonix home>/.env` 的 `DEEPSEEK_API_KEY`。`config.toml` 里只写变量名 `api_key_env`。

当前官方模型 ID：

| 用途 | 模型 ID | 2026-11-13 实际服务的版本 |
| --- | --- | --- |
| 编程执行、规划、审查 | `deepseek-v4-pro` | DeepSeek-V4-Pro-0813 |
| 低成本默认与分类 | `deepseek-flash` | DeepSeek-V4.1-Flash-1017 |

`deepseek-v4-flash` 仍被 API 接受，但是旧 Flash 的兼容别名，请求由 V4.1 Flash 处理并按 Flash 计费。本配置不再把它写成模型 ID。

上下文长度仍是 1M。本配置不手写 `max_output_tokens`，沿用 Reasonix 的自动预算。思考默认开启，执行 provider 的 `effort` 设为 `max`。`review` 与 `security-review` 的子代理 effort 也是 `max`。

价格以 DeepSeek 文档为准（2026-11-13，每百万 token，美元，高峰）。低谷是高峰的一半。高峰时段为周一至周五 UTC 01:00–04:00 与 06:00–10:00，中国法定节假日全天按低谷。

| 模型 | 缓存命中 | 缓存未命中 | 输出 |
| --- | ---: | ---: | ---: |
| `deepseek-v4-pro` | 0.044 | 1.32 | 3.96 |
| `deepseek-flash` | 0.006 | 0.30 | 1.20 |

模板不写 `prices`。Reasonix 会冻结官方价目；手写价目会被当成自定义费率。2026-06 手册里的人民币 3/6 与 1/2 已经对不上这张价目表。

## 安装

需要 Python 3.11 及以上，只用标准库。系统里如果没有 `python` 命令，改用 `python3`。

```bash
python reasonix_profile.py --check
python reasonix_profile.py --dry-run
python reasonix_profile.py --apply
```

`--apply` 写入 Reasonix home 中的：

- `config.toml` 的托管键
- `REASONIX.md`
- `output-styles/deepseek-coding-max.md`
- `commands/ship.md`、`learn.md`、`review-bugs.md`

已有 `config.toml` 会先备份，再合并托管键。其他 provider、未知键和已有密钥保留。没有管理标记的 `REASONIX.md` 或命令文件会跳过，`--force` 才覆盖。安装器不创建、不修改 `.env`。

技能仍由各自仓库发布。手册列出当前的 `npx skills add ... -a reasonix` 命令。Reasonix 已内置 `explore`、`locate`、`research`、`review`、`security-review`、`test` 和 `install-capability`，不必再安装。

## 增强层在当前版本里的位置

| 层 | 2026-06 观察 | 2026-11 配置里怎么落地 |
| --- | --- | --- |
| 角色与输出风格 | `REASONIX.md` 与 `deepseek-coding-max` | 写到 Reasonix home。`output_style = "deepseek-coding-max"` |
| 跨会话记忆 | Memory Compiler v5 轨迹 | `[agent].memory_compiler` 已退役，升级时会被删掉。现行层是 Context Engine v2：常驻指令走 `REASONIX.md`，事实记忆走 `/memory` |
| 技能 | 一份 14 项清单 | 内置技能直接可用。外部技能按手册中的新仓库安装 |
| 子代理 | `task` / `parallel_tasks` | 仍可用。审查模型由 `subagent_models` 指向 `deepseek/deepseek-v4-pro` |
| LSP | 定义、悬停、引用、诊断 | 这些工具仍在工具契约里。当前示例配置没有 `[lsp] enabled`，模板不写这个开关 |
| 工具执行 | bash、编辑、搜索 | 保留。Shell 使用 `prefer = "auto"`，由本机选择 bash 或 PowerShell |
| 自动规划 | `auto_plan = "on"` | `auto_plan` 与 `auto_plan_classifier` 已被忽略，升级时从用户配置删除。规划改走 Plan 模式和 `balanced` / `delivery` preset |
| 资源约束 | 轨迹里的 `production_hardening` | 那是 6 月轨迹里的运行时字段，不是当前 `config.toml` 的可写段 |
| 去 AI 味 | humanizer 与 remove-ai-flavor | 仓库仍在，安装源见手册。技术文档和代码注释不默认改写 |

固定工作流仍是 `inspect -> plan -> change -> verify -> summarize`。角色文件要求最小改动、没有验证证据不宣称完成，同一路径失败两次就换证据来源。

## 2026-06-26 轨迹快照

下面的数字只描述当天已经完成的编译器轨迹，不是当前版本的基准。样本是连续四次编码任务，另有一条「已追踪 6 次、成功 5 次」的汇总，两者范围不同。

| 指标 | 任务1 | 任务2 | 任务3 | 任务4 |
| --- | --- | --- | --- | --- |
| 结果 | 成功 | 成功 | 成功 | 成功 |
| 工具调用次数 | 5 | 2 | 5 | 2 |
| 延迟 (ms) | 55,719 | 13,484 | 32,586 | 14,553 |
| 质量评分 | 0.94 | 0.98 | 0.98 | 0.98 |
| 效率评分 | 0.68 | 0.90 | 0.79 | 0.89 |
| 记忆节点复用 | 0 | 5 | 5 | 5 |
| 控制模式 | balanced | balanced | explore | explore |
| 系统稳定性 | 1.0 | 1.0 | 0.69 | 0.57 |

四次任务的工具调用合计 14 次，平均 3.5 次。`metrics-pending.json` 里 `finish_reason` 为 `tool_calls` 的 603 次、`stop` 的 33 次，只说明模型那一次选择了继续调用工具，不能当成 bash 成功率。

轨迹里能对上名字的策略是四条：`general`、`bugfix-reproduce-first`、`code-review`、`frontend-visual-verify`。`general` 的先前成功率写成 5/6。选择惩罚从 0.03 增加到 0.16 的记录仍属于这次快照。压缩率 0.32–0.61 也只属于这些轨迹。

6 月清单把内置命令、内置审查技能和外部 taste 技能合在一起数成「14 个」。这个数对不上分项，现行清单以实施手册为准。`ship` 是本配置提供的斜杠命令。`review` 与 `security-review` 现在随 Reasonix 内置。

当时的 Memory Compiler 文件出现在两个位置：全局 `<Reasonix home>/memory/compiler/`，以及 `<Reasonix home>/projects/<project-hash>/memory/compiler/`。新的安装不要再创建这套目录。旧的 Memory v5 记录块仍然可读。

## 参考

- Reasonix 配置路径与密钥：<https://github.com/esengine/DeepSeek-Reasonix/blob/studio/docs/CONFIG_PATHS.md>
- Reasonix 配置契约：<https://github.com/esengine/DeepSeek-Reasonix/blob/studio/docs/SPEC.md>
- 记忆层迁移说明：<https://github.com/esengine/DeepSeek-Reasonix/blob/studio/docs/SESSION_MEMORY_RETRIEVAL.md>
- DeepSeek 模型与价格：<https://api-docs.deepseek.com/quick_start/pricing/>

文档版本：2.0.0 · 模板核对日期：2026-11-13
