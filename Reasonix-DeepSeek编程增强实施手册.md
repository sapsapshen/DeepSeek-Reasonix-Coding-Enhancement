# Reasonix DeepSeek 编程能力增强实施手册

> 版本 2.0.0 · 核对日期 2026-11-13。给人和 Agent 按顺序执行。文件正文以 `templates/` 为准，本手册不再复制第二份正文。

## 1. 前提

- 已安装 Reasonix 1.x 或 2.x。两边使用同一个 Reasonix home。
- 本机有 Python 3.11 或更高版本。
- 密钥放在 `<Reasonix home>/.env`：

```dotenv
DEEPSEEK_API_KEY=sk-...
```

Reasonix 不会从进程环境变量、项目 `.env` 或系统钥匙串读取 provider 密钥。只在 shell 里 `export DEEPSEEK_API_KEY` 不会让当前版本发出请求。安装器不读写 `.env`，也不把密钥写进 `config.toml`。

Reasonix home：

| 系统 | 路径 |
| --- | --- |
| macOS / Linux | `~/.reasonix` |
| Windows | `%APPDATA%\reasonix` |

临时安装或测试时设置 `REASONIX_HOME`。设置之后，配置、状态和缓存都留在该目录下。

## 2. 检查模板

在本仓库根目录执行。若系统里的命令名是 `python3`，下面的 `python` 换成 `python3`。

```bash
python reasonix_profile.py --check
```

通过时打印 `templates ok`。这一步不接触 Reasonix home。

## 3. 预览

```bash
python reasonix_profile.py
```

指定目录：

```bash
python reasonix_profile.py --home "$REASONIX_HOME"
```

预览只打印动作和技能安装命令，不创建目录。报告里的密钥样式字符串会被打码。

## 4. 写入本机配置

```bash
python reasonix_profile.py --apply
```

写入这些路径：

| 仓库模板 | Reasonix home 中的位置 |
| --- | --- |
| `templates/config.toml` | `config.toml` |
| `templates/REASONIX.md` | `REASONIX.md` |
| `templates/output-styles/deepseek-coding-max.md` | `output-styles/deepseek-coding-max.md` |
| `templates/commands/ship.md` | `commands/ship.md` |
| `templates/commands/learn.md` | `commands/learn.md` |
| `templates/commands/review-bugs.md` | `commands/review-bugs.md` |

`REASONIX.md` 从 Reasonix home 作为用户级常驻指令加载，然后再加载项目里的 `REASONIX.md` / `AGENTS.md` / `CLAUDE.md`。项目文件更深，冲突时项目规则优先。本安装器不改当前项目里的指令文件。

v1.8.1 之后不再需要把同一份文件复制到 `<home>/.reasonix/`。那个嵌套目录不是文档中的加载路径，本版本停止写入它。

已有文件的规则：

- `config.toml` 不存在：原样复制模板，注释保留。
- `config.toml` 已存在且能解析：先备份为 `config.toml.bak`，再更新托管键。其他 provider、未知键、已有 `api_key` 保留。名为 `deepseek` 的 provider 整段换成模板。
- `config.toml` 解析失败：报错并保持原字节。
- Markdown 带有 `reasonix-coding-profile` 标记：更新到当前模板。
- Markdown 没有标记：跳过。确认要替换时加 `--force`。
- 再次执行且内容已一致：不写新备份。

托管键包括 `default_model`、`[agent]` 里的温度、推理语言、压缩比例、规划模型、子代理模型与 effort、`output_style`，以及 bash 超时、`tools.shell.prefer`、`sandbox.bash` 和 `sandbox.network`。

当前模板的要点：

- `default_model = "deepseek/deepseek-v4-pro"`
- provider 名 `deepseek`，`kind = "openai"`，`base_url = "https://api.deepseek.com"`
- `models = ["deepseek-flash", "deepseek-v4-pro"]`
- `vision_models` 只有 `deepseek-flash`。Pro 收到图片后不会描述图片，列进视觉模型会让图片被静默丢掉
- `effort = "max"`
- `compact_ratio = 0.85`。2026-06 的 `soft_compact_ratio` 和 `compact_force_ratio` 不再写入；当前文档把 `compact_ratio` 当作自动压缩的触发比例
- `tools.shell.prefer = "auto"`。2026-06 手册把所有系统都写成 PowerShell，会让 macOS 和 Linux 偏离本机 shell
- `bash_timeout_seconds = 300`
- 不写 `prices`、`config_version`、`[lsp]`、`auto_plan`、`memory_compiler`

官方规范同时给出 Anthropic Messages 路线：`kind = "anthropic"`，`base_url = "https://api.deepseek.com/anthropic"`。模板跟随仓库里的 `reasonix.example.toml`，使用 OpenAI 兼容路线。两条路线都指向同一套模型 ID。

`subagent_models` 同时写了 `security-review` 和 `security_review`。内置技能名是带连字符的 `security-review`，旧文档和规范示例里出现过下划线形式。两份键都指向 `deepseek/deepseek-v4-pro`，effort 都是 `max`。

## 5. 写入密钥后的人工确认

编辑 `<Reasonix home>/.env`，保存 `DEEPSEEK_API_KEY`。文件权限按本机习惯收紧。然后重启 Reasonix，或新开一个会话。

确认：

1. 默认模型是 `deepseek/deepseek-v4-pro`。
2. `/effort` 能看到 DeepSeek 的 `high` 与 `max`。
3. 斜杠命令 `/ship`、`/learn`、`/review-bugs` 出现在命令列表中。
4. `/memory instructions` 能看到 home 里的 `REASONIX.md`。

## 6. 安装外部技能

Reasonix 扫描 `<Reasonix home>/skills/<name>/SKILL.md`，也扫描 `npx skills add ... -a reasonix` 落到的 `.reasonix/skills`、`.agents/skills` 等目录。2026-06 的 `reasonix install-capability --source ... --kind skill` 不是当前文档中的命令。会话里的内置技能名叫 `install-capability`，它通过 `install_source` 做安装计划。下面的命令是现在跨 Agent 的安装方式。

先装默认前端技能：

```bash
npx skills add https://github.com/Leonxlnx/taste-skill --skill design-taste-frontend -a reasonix
```

`design-taste-frontend` 是 taste-skill 仓库里保留的唯一技能，版本线已到 v2。旧的分项搬到了独立仓库，安装名不变。

```bash
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill high-end-visual-design -a reasonix
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill minimalist-ui -a reasonix
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill industrial-brutalist-ui -a reasonix
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill gpt-taste -a reasonix
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill stitch-design-taste -a reasonix
npx skills add https://github.com/Leonxlnx/taste-skill-classics --skill design-taste-frontend-v1 -a reasonix
```

这些 classic 技能的上游 frontmatter 带有 `disable-model-invocation: true`。当前 Reasonix 会遵守该字段：模型不能自动调用，用户仍可用 `/技能名` 调用。需要某个风格时显式点名。

图像与品牌技能：

```bash
npx skills add https://github.com/Leonxlnx/imagegen-skills --skill imagegen-frontend-web -a reasonix
npx skills add https://github.com/Leonxlnx/imagegen-skills --skill imagegen-frontend-mobile -a reasonix
npx skills add https://github.com/Leonxlnx/imagegen-skills --skill brandkit -a reasonix
npx skills add https://github.com/Leonxlnx/imagegen-skills --skill image-to-code -a reasonix
```

文案：

```bash
npx skills add https://github.com/blader/humanizer --skill humanizer -a reasonix
npx skills add https://github.com/b1lli/remove-ai-flavor-writing-skill --skill remove-ai-flavor -a reasonix
```

`humanizer` 处理英文。`remove-ai-flavor` 处理面向读者的中文。代码、命令、配置名和 API 文档保持原样。

不再单独安装的旧名字：

| 旧技能 | 现状 |
| --- | --- |
| `redesign-existing-projects` | 作者已并入 `design-taste-frontend`，现有页面会在浏览器里先核对再改 |
| `full-output-enforcement` | 作者已移除。后续项目见 <https://github.com/Leonxlnx/unlazy>，本配置不默认安装 |

安装后执行 `/skills`，核对上述名字已经出现。内置的 `review` 和 `security-review` 不需要这组命令。

## 7. 记忆约定

Context Engine v2 把常驻规则和背景事实分开。必须每次都在上下文里的规则放在 `REASONIX.md`。可以变旧的偏好放在记忆事实里。

全局事实、用户偏好和反馈都要人确认。Auto 和 YOLO 不会跳过这个确认。因此安装器不往 `memory/` 里写猜测格式的事实文件。

若要把技能约定存成记忆，在 Reasonix 里明确要求保存，例如：

> 记住这条全局反馈：前端或 UI 实现任务调用 design-taste-frontend。面向读者的中文使用 remove-ai-flavor，面向读者的英文使用 humanizer。技术文档、代码注释和 API 说明不改写文风。classic 风格技能只在被点名时调用。

保存后用 `/memory` 查看 id、scope 和 revision。用 `/memory instructions` 查看常驻指令的实际加载顺序。

2026-06 手册要求检查 `projects/<hash>/memory/compiler/traces.jsonl` 里的 `strategy_used`。那个目录属于已退役的 Memory Compiler v5。升级后的新任务不会因为写过 `memory_compiler = { enabled = true }` 就继续产生它。旧轨迹块仍可阅读。

## 8. 生效后的行为核对

1. 提一个小的编程任务。回复按 `inspect -> plan -> change -> verify -> summarize` 推进，结束时给出实际跑过的验证。
2. 连续两个相关任务。第二个任务是否用到记忆，以 `/memory recall` 的记录为准。
3. 要求做前端页面时，看是否加载了 `design-taste-frontend`。classic 技能被点名后才应出现。
4. 让它改一段给读者看的中文，再看 `remove-ai-flavor` 有没有被调用。
5. 打开一次带图的任务。图片应走 `deepseek-flash` 的视觉能力；纯文本编程任务保持 `deepseek-v4-pro`。
6. 首次使用 provider 自带搜索时，Reasonix 会出示 DeepSeek Search 的费用确认。当前公开价格是每 1000 次成功请求 0.75 美元。不同意就保持关闭。

## 9. 与 2026-06 手册的差异

| 2026-06 写法 | 现在 |
| --- | --- |
| 两个 provider，模型 `deepseek-v4-pro` 与 `deepseek-v4-flash` | 一个 provider，模型 `deepseek-v4-pro` 与 `deepseek-flash` |
| 人民币单价写进配置 | 不写价格，避免把过期价目冻成自定义费率 |
| `config_version = 3` | 不代写。路径文档中的示例是 `config_version = 1`，交给 Reasonix 自己的迁移 |
| `auto_plan` 与 Memory Compiler v5 | 升级时移除。规划用 Plan 模式；记忆用 Context Engine v2 |
| 全部系统 `prefer = "powershell"` | `prefer = "auto"` |
| 嵌套 `.reasonix` 镜像 | 不再复制 |
| 14 个技能加一条 `install-capability` 命令 | 内置技能直接用；外部技能按第 6 节的新仓库安装 |
| 策略表写「5 种」但只列出 4 条 | 快照里对得上名字的是四条，见 README |

LSP 工具 `lsp_definition`、`lsp_hover`、`lsp_references`、`lsp_diagnostics` 仍在 Reasonix 工具契约中。当前示例没有 `[lsp]` 开关，所以模板不写它。

## 10. 本地测试

```bash
python -m unittest discover -s tests -v
```

测试使用临时目录，不会修改本机真实的 Reasonix home。
