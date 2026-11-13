#!/usr/bin/env python3
"""Install and check the Reasonix DeepSeek coding profile.

The profile templates live in ``templates/``. This tool copies the managed
Markdown into a Reasonix home and merges ``config.toml`` without writing
secrets. Pass ``--apply`` to change disk; the default is a dry run.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROFILE_MARKER = "reasonix-coding-profile"
MANAGED_PATHS: tuple[tuple[str, ...], ...] = (
    ("default_model",),
    ("agent", "temperature"),
    ("agent", "reasoning_language"),
    ("agent", "compact_ratio"),
    ("agent", "planner_model"),
    ("agent", "subagent_model"),
    ("agent", "subagent_effort"),
    ("agent", "subagent_models"),
    ("agent", "subagent_efforts"),
    ("agent", "output_style"),
    ("tools", "bash_timeout_seconds"),
    ("tools", "shell", "prefer"),
    ("sandbox", "bash"),
    ("sandbox", "network"),
)
MARKDOWN_FILES: tuple[str, ...] = (
    "REASONIX.md",
    "output-styles/deepseek-coding-max.md",
    "commands/ship.md",
    "commands/learn.md",
    "commands/review-bugs.md",
)
SECRET_VALUE = re.compile(r"sk-[A-Za-z0-9_\-]{6,}")
SECRET_ASSIGNMENT = re.compile(
    r"(?i)(?:^|\n)\s*(?:export\s+)?(?:api_key|secret|token|password)\s*=\s*\S+"
)


class ProfileError(Exception):
    """A profile check or install cannot continue."""


@dataclass(frozen=True)
class Action:
    """One planned or completed file operation."""

    path: str
    action: str
    detail: str


def repo_root() -> Path:
    """Return the repository root that contains this module."""
    return Path(__file__).resolve().parent


def templates_dir() -> Path:
    """Return the canonical template directory."""
    return repo_root() / "templates"


def load_manifest() -> dict[str, Any]:
    """Load ``templates/manifest.json``."""
    path = templates_dir() / "manifest.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"无法读取 {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ProfileError("templates/manifest.json 必须是 JSON 对象")
    return data


def load_template_config() -> tuple[str, dict[str, Any]]:
    """Return the template config text and its parsed TOML."""
    path = templates_dir() / "config.toml"
    try:
        text = path.read_text(encoding="utf-8")
        parsed = tomllib.loads(text)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"无法解析 {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ProfileError("templates/config.toml 必须是 TOML 表")
    return text, parsed


def default_home(
    platform_name: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the Reasonix home without creating it.

    ``REASONIX_HOME`` wins. Otherwise Windows uses ``%APPDATA%\\reasonix`` and
    other platforms use ``~/.reasonix``.
    """
    env = os.environ if environ is None else environ
    override = env.get("REASONIX_HOME", "").strip()
    if override:
        return Path(override).expanduser()
    platform = sys.platform if platform_name is None else platform_name
    if platform.startswith("win"):
        appdata = env.get("APPDATA", "").strip()
        if not appdata:
            raise ProfileError("Windows 上未设置 APPDATA，请改用 REASONIX_HOME")
        return Path(appdata) / "reasonix"
    home = env.get("HOME", "").strip()
    base = Path(home).expanduser() if home else Path.home()
    return base / ".reasonix"


def skill_install_commands(manifest: Mapping[str, Any] | None = None) -> list[str]:
    """Return the ``npx skills add`` commands for skills this profile installs."""
    data = load_manifest() if manifest is None else manifest
    commands: list[str] = []
    skills = data.get("skills", [])
    if not isinstance(skills, list):
        raise ProfileError("manifest.skills 必须是数组")
    for item in skills:
        if not isinstance(item, dict) or item.get("install") is not True:
            continue
        name = item.get("name")
        repository = item.get("repository")
        if not isinstance(name, str) or not isinstance(repository, str):
            raise ProfileError("可安装技能必须包含 name 和 repository")
        commands.append(f"npx skills add {repository} --skill {name} -a reasonix")
    return commands


def check_templates() -> None:
    """Raise ``ProfileError`` when the shipped templates disagree with the manifest."""
    manifest = load_manifest()
    version = manifest.get("profile_version")
    if not isinstance(version, str) or not version:
        raise ProfileError("manifest.profile_version 缺失")
    text, config = load_template_config()
    _reject_secrets(text, "templates/config.toml")
    if f"profile_version: {version}" not in text:
        raise ProfileError("config.toml 的 profile_version 与 manifest 不一致")
    if PROFILE_MARKER not in text:
        raise ProfileError("config.toml 缺少管理标记")
    for path in MANAGED_PATHS:
        _require_path(config, path)
    agent = config.get("agent", {})
    if not isinstance(agent, dict):
        raise ProfileError("[agent] 必须是表")
    for key in manifest.get("retired_agent_keys", []):
        if key in agent:
            raise ProfileError(f"模板仍包含已退役键 agent.{key}")
    if "lsp" in config or "prices" in config or "price" in config or "config_version" in config:
        raise ProfileError("模板包含不应写入的 lsp、价格或 config_version")
    provider = _deepseek_provider(config)
    models = manifest.get("models", {})
    if not isinstance(models, dict):
        raise ProfileError("manifest.models 必须是对象")
    expected_models = [models.get("provider_default"), models.get("executor")]
    if provider.get("models") != expected_models:
        raise ProfileError("provider.models 与 manifest.models 不一致")
    if provider.get("api_key_env") != "DEEPSEEK_API_KEY":
        raise ProfileError("provider 必须只声明 DEEPSEEK_API_KEY 的变量名")
    if "api_key" in provider:
        raise ProfileError("模板 provider 不能写入 api_key")
    if config.get("default_model") != f"deepseek/{models.get('executor')}":
        raise ProfileError("default_model 必须指向执行模型")
    for relative in MARKDOWN_FILES:
        path = templates_dir() / relative
        try:
            body = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ProfileError(f"缺少模板 {relative}: {exc}") from exc
        _reject_secrets(body, relative)
        if f"{PROFILE_MARKER} {version}" not in body:
            raise ProfileError(f"{relative} 缺少版本标记")
        if relative.startswith("commands/") and "$ARGUMENTS" not in body:
            raise ProfileError(f"{relative} 没有 $ARGUMENTS")
        if relative.startswith("commands/") and not body.startswith("---\n"):
            raise ProfileError(f"{relative} 缺少前置信息")
    workflow = "inspect -> plan -> change -> verify -> summarize"
    for relative in ("REASONIX.md", "output-styles/deepseek-coding-max.md"):
        body = (templates_dir() / relative).read_text(encoding="utf-8")
        if workflow not in body:
            raise ProfileError(f"{relative} 缺少固定工作流")
    if not skill_install_commands(manifest):
        raise ProfileError("manifest 没有可安装技能")


def plan_install(home: Path, force: bool = False) -> list[Action]:
    """Describe what ``--apply`` would change. This function does not write."""
    check_templates()
    target = _validate_home(home)
    actions: list[Action] = []
    config_path = target / "config.toml"
    template_text, template_config = load_template_config()
    actions.extend(_plan_config(config_path, template_text, template_config))
    for relative in MARKDOWN_FILES:
        actions.append(_plan_markdown(target / relative, templates_dir() / relative, force))
    env_path = target / ".env"
    if _env_has_named_key(env_path, "DEEPSEEK_API_KEY"):
        actions.append(Action(str(env_path), "unchanged", "DEEPSEEK_API_KEY 已存在，安装器不会读写密钥"))
    elif env_path.exists():
        actions.append(Action(str(env_path), "unchanged", "未找到 DEEPSEEK_API_KEY，请自行写入 <Reasonix home>/.env"))
    else:
        actions.append(Action(str(env_path), "skipped", "没有 .env。请创建它并写入 DEEPSEEK_API_KEY，安装器不会代写"))
    return actions


def apply_install(home: Path, force: bool = False) -> list[Action]:
    """Create or update the profile in ``home`` and return the actions taken."""
    check_templates()
    target = _validate_home(home)
    target.mkdir(parents=True, exist_ok=True)
    actions: list[Action] = []
    template_text, template_config = load_template_config()
    actions.extend(_apply_config(target / "config.toml", template_text, template_config))
    for relative in MARKDOWN_FILES:
        actions.append(_apply_markdown(target / relative, templates_dir() / relative, force))
    env_path = target / ".env"
    if env_path.exists():
        detail = (
            "DEEPSEEK_API_KEY 已存在"
            if _env_has_named_key(env_path, "DEEPSEEK_API_KEY")
            else "未找到 DEEPSEEK_API_KEY"
        )
        actions.append(Action(str(env_path), "unchanged", detail + "，安装器没有修改 .env"))
    else:
        actions.append(Action(str(env_path), "skipped", "没有写入 .env"))
    return actions


def format_report(actions: Sequence[Action]) -> str:
    """Render actions for a terminal. Secret-shaped values are redacted."""
    lines = [f"{item.action:10} {item.path}  {item.detail}" for item in actions]
    lines.extend(skill_install_commands())
    return redact("\n".join(lines))


def redact(text: str) -> str:
    """Hide secret-shaped substrings before they reach a log or terminal."""
    redacted = SECRET_VALUE.sub("sk-[redacted]", text)
    return SECRET_ASSIGNMENT.sub(
        lambda match: match.group(0).split("=", 1)[0] + "=[redacted]",
        redacted,
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line and return a process status."""
    parser = argparse.ArgumentParser(description="检查或安装 Reasonix DeepSeek 编程增强配置")
    parser.add_argument("--check", action="store_true", help="只检查仓库模板，不接触 Reasonix home")
    parser.add_argument("--dry-run", action="store_true", help="只打印计划。省略 --apply 时这是默认行为")
    parser.add_argument("--apply", action="store_true", help="写入 Reasonix home")
    parser.add_argument("--home", type=Path, help="Reasonix home，默认按平台解析")
    parser.add_argument("--force", action="store_true", help="覆盖没有管理标记的同名文件")
    args = parser.parse_args(None if argv is None else list(argv))
    if args.apply and args.dry_run:
        print("error: --apply 和 --dry-run 不能同时使用", file=sys.stderr)
        return 2
    if args.check and (args.apply or args.dry_run or args.home is not None or args.force):
        print("error: --check 只检查仓库模板，不能和安装参数一起用", file=sys.stderr)
        return 2
    try:
        if args.check:
            check_templates()
            print(f"templates ok  profile_version={load_manifest()['profile_version']}")
            return 0
        home = args.home if args.home is not None else default_home()
        actions = apply_install(home, force=args.force) if args.apply else plan_install(home, force=args.force)
    except ProfileError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(format_report(actions))
    return 0


def _reject_secrets(text: str, label: str) -> None:
    if SECRET_VALUE.search(text) or SECRET_ASSIGNMENT.search(text):
        raise ProfileError(f"{label} 含有密钥样式的内容，已拒绝")


def _require_path(data: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            raise ProfileError("模板缺少 " + ".".join(path))
        current = current[key]
    return current


def _deepseek_provider(config: Mapping[str, Any]) -> dict[str, Any]:
    providers = config.get("providers")
    if not isinstance(providers, list):
        raise ProfileError("模板缺少 [[providers]]")
    found = [item for item in providers if isinstance(item, dict) and item.get("name") == "deepseek"]
    if len(found) != 1:
        raise ProfileError("模板必须恰好有一个名为 deepseek 的 provider")
    return found[0]


def _validate_home(home: Path) -> Path:
    if not str(home):
        raise ProfileError("Reasonix home 为空")
    try:
        resolved = home.expanduser().resolve()
    except OSError as exc:
        raise ProfileError(f"无法解析 Reasonix home: {exc}") from exc
    repo = repo_root().resolve()
    if resolved == Path(resolved.anchor):
        raise ProfileError("拒绝把文件系统根目录当作 Reasonix home")
    if resolved == repo or resolved.is_relative_to(repo) or repo.is_relative_to(resolved):
        raise ProfileError("拒绝把本仓库或其父目录当作 Reasonix home")
    return resolved


def _plan_config(path: Path, template_text: str, template_config: Mapping[str, Any]) -> list[Action]:
    if not path.exists():
        return [Action(str(path), "create", "写入模板 config.toml")]
    try:
        existing_text = path.read_text(encoding="utf-8")
        existing = tomllib.loads(existing_text)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProfileError(f"现有 config.toml 无法解析，未修改: {exc}") from exc
    if not isinstance(existing, dict):
        raise ProfileError("现有 config.toml 不是 TOML 表，未修改")
    if existing_text == template_text or existing == template_config:
        return [Action(str(path), "unchanged", "config.toml 已与模板一致")]
    merged = merge_config(existing, template_config)
    if merged == existing:
        return [Action(str(path), "unchanged", "托管键已是目标值")]
    return [Action(str(path), "update", "合并托管键并保留其余 provider 与未知键；原文件会备份")]


def _apply_config(path: Path, template_text: str, template_config: Mapping[str, Any]) -> list[Action]:
    planned = _plan_config(path, template_text, template_config)
    action = planned[0]
    if action.action == "create":
        _atomic_write(path, template_text)
        return planned
    if action.action != "update":
        return planned
    existing_text = path.read_text(encoding="utf-8")
    existing = tomllib.loads(existing_text)
    if not isinstance(existing, dict):
        raise ProfileError("现有 config.toml 不是 TOML 表，未修改")
    backup = _backup_path(path)
    backup.write_text(existing_text, encoding="utf-8")
    rendered = render_toml(merge_config(existing, template_config))
    _reject_secrets_in_rendered_delta(existing_text, rendered)
    _atomic_write(path, rendered)
    return [Action(str(backup), "backup", "原 config.toml"), action]


def _reject_secrets_in_rendered_delta(previous: str, rendered: str) -> None:
    """Allow secrets that were already on disk, and reject secrets this tool added."""
    previous_hits = set(SECRET_VALUE.findall(previous))
    for hit in SECRET_VALUE.findall(rendered):
        if hit not in previous_hits:
            raise ProfileError("合并结果出现了模板中没有、原配置中也没有的密钥，已拒绝写入")


def _plan_markdown(path: Path, source: Path, force: bool) -> Action:
    body = source.read_text(encoding="utf-8")
    if not path.exists():
        return Action(str(path), "create", "写入托管文件")
    current = path.read_text(encoding="utf-8")
    if current == body:
        return Action(str(path), "unchanged", "内容已是当前模板")
    if PROFILE_MARKER in current or force:
        return Action(str(path), "update", "用当前模板替换托管文件")
    return Action(str(path), "skipped", "目标已存在且没有管理标记；保留原文件。确认后可加 --force")


def _apply_markdown(path: Path, source: Path, force: bool) -> Action:
    planned = _plan_markdown(path, source, force)
    if planned.action in {"create", "update"}:
        path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, source.read_text(encoding="utf-8"))
    return planned


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _backup_path(path: Path) -> Path:
    primary = path.with_name(path.name + ".bak")
    if not primary.exists():
        return primary
    stamp = 1
    while True:
        candidate = path.with_name(f"{path.name}.{stamp}.bak")
        if not candidate.exists():
            return candidate
        stamp += 1


def _env_has_named_key(path: Path, name: str) -> bool:
    if not path.is_file():
        return False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ProfileError(f"无法读取 {path}: {exc}") from exc
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        key, separator, value = line.partition("=")
        if separator and key.strip() == name and value.strip().strip("\"'"):
            return True
    return False


def merge_config(existing: Mapping[str, Any], template: Mapping[str, Any]) -> dict[str, Any]:
    """Copy ``existing`` and set the managed keys from ``template``.

    Providers other than ``deepseek`` stay in place. The ``deepseek`` provider
    entry is replaced by the template entry. Unknown keys are kept.
    """
    if not isinstance(existing, dict):
        raise ProfileError("现有配置不是表")
    merged = copy.deepcopy(dict(existing))
    template_dict = dict(template)
    for path in MANAGED_PATHS:
        _set_path(merged, path, copy.deepcopy(_require_path(template_dict, path)))
    providers = merged.get("providers", [])
    if providers is None:
        providers = []
    if not isinstance(providers, list) or any(not isinstance(item, dict) for item in providers):
        raise ProfileError("现有 [[providers]] 无法合并，未修改配置")
    replacement = copy.deepcopy(_deepseek_provider(template_dict))
    kept = [item for item in providers if item.get("name") != "deepseek"]
    merged["providers"] = [replacement, *kept]
    return merged


def _set_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def render_toml(data: Mapping[str, Any]) -> str:
    """Render a parsed config back to TOML.

    The first install copies the commented template. A merge uses this renderer,
    so comments from an older user file live only in the backup.
    """
    lines = [
        "# reasonix-coding-profile: managed",
        "# profile_version: regenerated",
        "# Generated by reasonix_profile.py. The previous file was backed up.",
        "",
    ]
    _emit_table_body(lines, "", dict(data))
    rendered = "\n".join(lines).rstrip() + "\n"
    reparsed = tomllib.loads(rendered)
    if reparsed != data:
        raise ProfileError("生成的 config.toml 往返解析后与合并结果不一致，已拒绝写入")
    return rendered


def _emit_table_body(lines: list[str], prefix: str, table: dict[str, Any]) -> None:
    scalars: dict[str, Any] = {}
    children: dict[str, dict[str, Any]] = {}
    arrays: dict[str, list[Any]] = {}
    for key, value in table.items():
        if isinstance(value, dict):
            children[key] = value
        elif isinstance(value, list) and value and all(isinstance(item, dict) for item in value):
            arrays[key] = value
        else:
            scalars[key] = value
    if prefix:
        lines.append(_format_table_header(prefix, array=False))
    for key, value in scalars.items():
        lines.append(f"{_format_key(key)} = {_render_value(value)}")
    if prefix or scalars:
        lines.append("")
    for key, child in children.items():
        child_prefix = f"{prefix}.{key}" if prefix else key
        _emit_table_body(lines, child_prefix, child)
    for key, items in arrays.items():
        array_prefix = f"{prefix}.{key}" if prefix else key
        for item in items:
            lines.append(_format_table_header(array_prefix, array=True))
            for item_key, item_value in item.items():
                lines.append(f"{_format_key(item_key)} = {_render_value(item_value)}")
            lines.append("")


def _render_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        rendered = format(value, ".12g")
        if "." not in rendered and "e" not in rendered and "E" not in rendered:
            rendered += ".0"
        return rendered
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, list):
        return "[" + ", ".join(_render_value(item) for item in value) + "]"
    if isinstance(value, dict):
        parts = [f"{_format_key(key)} = {_render_value(item)}" for key, item in value.items()]
        return "{ " + ", ".join(parts) + " }"
    raise ProfileError(f"无法写成 TOML 的值类型: {type(value).__name__}")


def _format_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_]+", key):
        return key
    escaped = key.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _format_table_header(prefix: str, array: bool) -> str:
    header = ".".join(_format_key(part) for part in prefix.split("."))
    return f"[[{header}]]" if array else f"[{header}]"


if __name__ == "__main__":
    sys.exit(main())
