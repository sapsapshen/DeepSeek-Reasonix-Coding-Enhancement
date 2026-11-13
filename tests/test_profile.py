"""Tests for the Reasonix coding profile templates and installer."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import reasonix_profile


class TemplateTests(unittest.TestCase):
    def test_check_templates_accepts_the_shipped_profile(self) -> None:
        reasonix_profile.check_templates()

    def test_manifest_models_and_retired_keys_match_config(self) -> None:
        manifest = reasonix_profile.load_manifest()
        _, config = reasonix_profile.load_template_config()
        agent = config["agent"]
        for key in manifest["retired_agent_keys"]:
            self.assertNotIn(key, agent)
        self.assertNotIn("lsp", config)
        self.assertNotIn("prices", config)
        provider = config["providers"][0]
        self.assertEqual(provider["name"], "deepseek")
        self.assertEqual(provider["kind"], "openai")
        self.assertEqual(provider["base_url"], "https://api.deepseek.com")
        self.assertEqual(provider["vision_models"], ["deepseek-flash"])
        self.assertNotIn("api_key", provider)
        self.assertNotIn("price", provider)
        self.assertEqual(provider["effort"], "max")
        self.assertEqual(config["tools"]["shell"]["prefer"], "auto")

    def test_render_roundtrip_preserves_parsed_config(self) -> None:
        _, config = reasonix_profile.load_template_config()
        rendered = reasonix_profile.render_toml(config)
        self.assertEqual(tomllib.loads(rendered), config)

    def test_skill_commands_use_current_repositories(self) -> None:
        manifest = reasonix_profile.load_manifest()
        commands = reasonix_profile.skill_install_commands(manifest)
        self.assertEqual(len(commands), len(manifest["skills"]))
        for skill, command in zip(manifest["skills"], commands, strict=True):
            self.assertIn(skill["repository"], command)
            self.assertIn(f"--skill {skill['name']} ", command)
            self.assertIn("-a reasonix", command)

    def test_docs_name_the_same_skills_and_current_models(self) -> None:
        manifest = json.loads((ROOT / "templates" / "manifest.json").read_text(encoding="utf-8"))
        readme = (ROOT / "Readme.md").read_text(encoding="utf-8")
        handbook = (ROOT / "Reasonix-DeepSeek编程增强实施手册.md").read_text(encoding="utf-8")
        combined = readme + "\n" + handbook
        self.assertIn("deepseek-flash", combined)
        self.assertIn("deepseek-v4-pro", combined)
        self.assertIn("deepseek-v4-flash", combined)
        self.assertIn("finish_reason", readme)
        self.assertNotIn("5 种策略", readme)
        self.assertNotIn("5 策略", readme)
        self.assertIn("python reasonix_profile.py", handbook)
        self.assertIn("不会从进程环境变量", handbook)
        for skill in manifest["skills"]:
            self.assertIn(skill["name"], handbook)
            self.assertIn(skill["repository"], handbook)
        for retired in manifest["retired_skills"]:
            self.assertIn(retired["name"], handbook)


class HomeTests(unittest.TestCase):
    def test_reasonix_home_override_wins(self) -> None:
        home = reasonix_profile.default_home(
            platform_name="win32",
            environ={"REASONIX_HOME": "/tmp/custom-reasonix", "APPDATA": "C:/Users/example/AppData/Roaming"},
        )
        self.assertEqual(home, Path("/tmp/custom-reasonix"))

    def test_windows_home_uses_appdata(self) -> None:
        home = reasonix_profile.default_home(
            platform_name="win32",
            environ={"APPDATA": "C:/Users/example/AppData/Roaming"},
        )
        self.assertEqual(home, Path("C:/Users/example/AppData/Roaming/reasonix"))

    def test_windows_without_appdata_fails(self) -> None:
        with self.assertRaises(reasonix_profile.ProfileError):
            reasonix_profile.default_home(platform_name="win32", environ={})

    def test_posix_home_uses_dot_reasonix(self) -> None:
        home = reasonix_profile.default_home(platform_name="linux", environ={"HOME": "/home/example"})
        self.assertEqual(home, Path("/home/example/.reasonix"))

    def test_repo_directory_is_rejected(self) -> None:
        with self.assertRaises(reasonix_profile.ProfileError):
            reasonix_profile.plan_install(ROOT)


class InstallTests(unittest.TestCase):
    def test_apply_is_idempotent_and_does_not_write_env(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "reasonix"
            first = reasonix_profile.apply_install(home)
            self.assertTrue(any(item.action == "create" for item in first))
            config = (home / "config.toml").read_text(encoding="utf-8")
            self.assertEqual(config, (ROOT / "templates" / "config.toml").read_text(encoding="utf-8"))
            self.assertTrue((home / "commands" / "ship.md").is_file())
            self.assertTrue((home / "output-styles" / "deepseek-coding-max.md").is_file())
            self.assertFalse((home / ".env").exists())
            second = reasonix_profile.apply_install(home)
            self.assertTrue(all(item.action in {"unchanged", "skipped"} for item in second))
            self.assertFalse(list(home.glob("config.toml*.bak")))

    def test_merge_preserves_other_providers_and_redacts_reports(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "reasonix"
            home.mkdir()
            secret = "sk-test-secret-value"
            original = (
                'keep_me = true\n\n'
                '[[providers]]\n'
                'name = "other"\n'
                'kind = "openai"\n'
                'base_url = "https://example.invalid"\n'
                'model = "x"\n'
                f'api_key = "{secret}"\n\n'
                '[agent]\n'
                'temperature = 0.7\n'
                'custom_note = "leave-me"\n'
            )
            (home / "config.toml").write_text(original, encoding="utf-8")
            (home / "REASONIX.md").write_text("# local rules\n", encoding="utf-8")
            plan = reasonix_profile.format_report(reasonix_profile.plan_install(home))
            self.assertNotIn(secret, plan)
            actions = reasonix_profile.apply_install(home)
            report = reasonix_profile.format_report(actions)
            self.assertNotIn(secret, report)
            merged = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
            self.assertTrue(merged["keep_me"])
            self.assertEqual(merged["agent"]["custom_note"], "leave-me")
            self.assertEqual(merged["agent"]["temperature"], 0.0)
            names = [item["name"] for item in merged["providers"]]
            self.assertEqual(names, ["deepseek", "other"])
            other = merged["providers"][1]
            self.assertEqual(other["api_key"], secret)
            backup = (home / "config.toml.bak").read_text(encoding="utf-8")
            self.assertIn(secret, backup)
            self.assertEqual((home / "REASONIX.md").read_text(encoding="utf-8"), "# local rules\n")
            self.assertFalse((home / ".env").exists())

    def test_force_replaces_unmarked_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "reasonix"
            home.mkdir()
            (home / "REASONIX.md").write_text("# local rules\n", encoding="utf-8")
            reasonix_profile.apply_install(home, force=True)
            updated = (home / "REASONIX.md").read_text(encoding="utf-8")
            self.assertIn("inspect -> plan -> change -> verify -> summarize", updated)

    def test_merge_keeps_empty_tool_lists(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "reasonix"
            home.mkdir()
            (home / "config.toml").write_text("[tools]\nenabled = []\n", encoding="utf-8")
            reasonix_profile.apply_install(home)
            merged = tomllib.loads((home / "config.toml").read_text(encoding="utf-8"))
            self.assertEqual(merged["tools"]["enabled"], [])
            self.assertEqual(merged["tools"]["bash_timeout_seconds"], 300)

    def test_malformed_config_is_left_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "reasonix"
            home.mkdir()
            broken = "[[providers]\n"
            (home / "config.toml").write_text(broken, encoding="utf-8")
            with self.assertRaises(reasonix_profile.ProfileError):
                reasonix_profile.apply_install(home)
            self.assertEqual((home / "config.toml").read_text(encoding="utf-8"), broken)

    def test_check_command_succeeds(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(reasonix_profile.main(["--check"]), 0)

    def test_dry_run_does_not_create_home(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            home = Path(raw) / "missing"
            with contextlib.redirect_stdout(io.StringIO()):
                status = reasonix_profile.main(["--dry-run", "--home", str(home)])
            self.assertEqual(status, 0)
            self.assertFalse(home.exists())

    def test_conflicting_flags_fail(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(reasonix_profile.main(["--apply", "--dry-run"]), 2)
            self.assertEqual(reasonix_profile.main(["--check", "--apply"]), 2)


class RedactionTests(unittest.TestCase):
    def test_redact_hides_secret_assignments_without_touching_env_names(self) -> None:
        text = 'api_key = "sk-test-secret-value"\napi_key_env = "DEEPSEEK_API_KEY"\n'
        redacted = reasonix_profile.redact(text)
        self.assertNotIn("sk-test-secret-value", redacted)
        self.assertIn("DEEPSEEK_API_KEY", redacted)


if __name__ == "__main__":
    os.environ.pop("REASONIX_HOME", None)
    unittest.main()
