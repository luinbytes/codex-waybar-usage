"""Alias, fallback, and Waybar JSON checks for the Grok rename."""

import importlib.util
import inspect
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "cursor_usage.json"
SCRIPT = ROOT / "grok-waybar.py"
SHIM = ROOT / "codex-waybar.py"

ENV_KEYS = (
    "GROK_WAYBAR_SIGNAL",
    "CODEX_WAYBAR_SIGNAL",
    "GROK_WAYBAR_HITBOX_RIGHT",
    "CODEX_WAYBAR_HITBOX_RIGHT",
    "GROK_WAYBAR_THEME",
    "CODEX_WAYBAR_THEME",
    "GROK_WAYBAR_LAUNCH",
    "CODEX_WAYBAR_LAUNCH",
    "GROK_USAGE_TIMEOUT",
    "CODEX_WAYBAR_TIMEOUT",
    "GROK_WAYBAR_LAYER_SHELL",
    "CODEX_WAYBAR_LAYER_SHELL",
    "GROK_WAYBAR_PRELOADED",
    "CODEX_WAYBAR_PRELOADED",
    "CODEX_BIN",
    "GROK_WAYBAR_FIXTURE",
)


def load_module():
    spec = importlib.util.spec_from_file_location("grok_waybar", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RenameCompatTest(unittest.TestCase):
    def setUp(self):
        self.module = load_module()
        self.saved = {key: os.environ.get(key) for key in ENV_KEYS}
        for key in ENV_KEYS:
            os.environ.pop(key, None)
        self.module._DEPRECATIONS_LOGGED.clear()

    def tearDown(self):
        for key, value in self.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_new_config_key_wins_over_legacy(self):
        os.environ["GROK_WAYBAR_SIGNAL"] = "4"
        os.environ["CODEX_WAYBAR_SIGNAL"] = "9"
        stderr = StringIO()
        with redirect_stderr(stderr):
            value = self.module.env_int(
                "GROK_WAYBAR_SIGNAL", 13, 0, 31, legacy="CODEX_WAYBAR_SIGNAL"
            )
        self.assertEqual(value, 4)
        self.assertEqual(stderr.getvalue(), "")

    def test_legacy_config_key_is_accepted_once(self):
        os.environ["CODEX_WAYBAR_HITBOX_RIGHT"] = "120"
        stderr = StringIO()
        with redirect_stderr(stderr):
            first = self.module.env_int(
                "GROK_WAYBAR_HITBOX_RIGHT",
                88,
                0,
                10_000,
                legacy="CODEX_WAYBAR_HITBOX_RIGHT",
            )
            second = self.module.env_int(
                "GROK_WAYBAR_HITBOX_RIGHT",
                88,
                0,
                10_000,
                legacy="CODEX_WAYBAR_HITBOX_RIGHT",
            )
        self.assertEqual(first, 120)
        self.assertEqual(second, 120)
        note = stderr.getvalue().strip().splitlines()
        self.assertEqual(
            note,
            [
                "grok-waybar-usage: CODEX_WAYBAR_HITBOX_RIGHT is deprecated; use GROK_WAYBAR_HITBOX_RIGHT"
            ],
        )

    def test_missing_keys_use_default_without_a_note(self):
        stderr = StringIO()
        with redirect_stderr(stderr):
            value = self.module.env_int(
                "GROK_USAGE_TIMEOUT", 12, 1, 60, legacy="CODEX_WAYBAR_TIMEOUT"
            )
        self.assertEqual(value, 12)
        self.assertEqual(stderr.getvalue(), "")

    def test_theme_and_launch_fall_back(self):
        os.environ["CODEX_WAYBAR_THEME"] = "/tmp/legacy-colors.toml"
        os.environ["CODEX_WAYBAR_LAUNCH"] = "echo legacy"
        stderr = StringIO()
        with redirect_stderr(stderr):
            theme = self.module.theme_file()
            launch = self.module.env_get(
                "GROK_WAYBAR_LAUNCH", legacy="CODEX_WAYBAR_LAUNCH"
            )
        self.assertEqual(theme, Path("/tmp/legacy-colors.toml"))
        self.assertEqual(launch, "echo legacy")
        self.assertIn("CODEX_WAYBAR_THEME", stderr.getvalue())
        self.assertIn("CODEX_WAYBAR_LAUNCH", stderr.getvalue())

    def test_codex_cli_contract_stays_codex(self):
        source = inspect.getsource(self.module.request_rate_limits)
        self.assertIn("account/rateLimits/read", source)
        self.assertIn("CODEX_WAYBAR_TIMEOUT", source)
        self.assertNotIn("GROK_WAYBAR", source)
        cursor_source = inspect.getsource(self.module.request_cursor_usage)
        self.assertIn('legacy="CODEX_WAYBAR_TIMEOUT"', cursor_source)
        self.assertEqual(self.module.codex_argv(), ["codex", "app-server", "--stdio"])
        os.environ["CODEX_BIN"] = "/opt/codex"
        self.assertEqual(
            self.module.codex_argv(), ["/opt/codex", "app-server", "--stdio"]
        )
        payload = {
            "rateLimitsByLimitId": {
                "codex": {
                    "secondary": {"usedPercent": 15, "windowDurationMins": 10080}
                }
            }
        }
        windows = self.module.normalize_windows(payload)
        self.assertEqual(windows[0]["used_percent"], 15)

    def test_waybar_json_emits_new_and_old_classes(self):
        windows = self.module.windows_from_cursor(json.loads(FIXTURE.read_text()))
        output = self.module.waybar_output(windows)
        self.assertEqual(output["text"], "[USG 85%]")
        self.assertEqual(output["alt"], "grok")
        self.assertEqual(output["tooltip"], "Grok weekly: 85% left")
        self.assertEqual(output["class"], ["active", "grok-usage", "codex-usage"])
        hidden = self.module.waybar_output([])
        self.assertEqual(hidden["text"], "[USG --]")
        self.assertEqual(hidden["alt"], "grok")
        self.assertEqual(
            hidden["class"], ["inactive", "grok-usage", "codex-usage"]
        )
        self.assertEqual(hidden["tooltip"], "Grok usage unavailable")

    def test_stylesheet_and_gtk_css_keep_old_selectors(self):
        css = (ROOT / "waybar.css").read_text()
        for selector in (
            "#custom-grok-usage",
            "#custom-codex-usage",
            "#custom-codex-usage.active",
            "#custom-codex-usage.inactive",
            "#custom-codex-usage.warning",
        ):
            self.assertIn(selector, css)
        theme = self.module.theme_css(self.module.load_theme())
        self.assertIn(".grok-card", theme)
        self.assertIn(".codex-card", theme)
        self.assertEqual(
            self.module.paired_css_classes("grok-over"), ["grok-over", "codex-over"]
        )

    def test_both_entry_points_print_the_same_fixture_json(self):
        expected = None
        for script in (SCRIPT, SHIM):
            result = subprocess.run(
                [sys.executable, str(script), "--fixture", str(FIXTURE)],
                check=True,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.stderr, "")
            payload = json.loads(result.stdout)
            self.assertEqual(
                payload,
                {
                    "text": "[USG 85%]",
                    "alt": "grok",
                    "class": ["active", "grok-usage", "codex-usage"],
                    "tooltip": "Grok weekly: 85% left",
                },
            )
            if expected is None:
                expected = result.stdout
            else:
                self.assertEqual(result.stdout, expected)

    def test_cursor_timeout_accepts_the_legacy_name(self):
        os.environ["CODEX_WAYBAR_TIMEOUT"] = "9"
        stderr = StringIO()
        with redirect_stderr(stderr):
            value = self.module.env_int(
                "GROK_USAGE_TIMEOUT", 12, 1, 60, legacy="CODEX_WAYBAR_TIMEOUT"
            )
        self.assertEqual(value, 9)
        self.assertIn(
            "CODEX_WAYBAR_TIMEOUT is deprecated; use GROK_USAGE_TIMEOUT",
            stderr.getvalue(),
        )

    def test_missing_cursor_db_prints_inactive_json(self):
        with tempfile.TemporaryDirectory() as home:
            env = os.environ.copy()
            env["HOME"] = home
            env["XDG_CONFIG_HOME"] = str(Path(home) / ".config")
            env.pop("GROK_WAYBAR_FIXTURE", None)
            result = subprocess.run(
                [sys.executable, str(SHIM)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
        self.assertEqual(
            json.loads(result.stdout),
            {
                "text": "[USG --]",
                "alt": "grok",
                "class": ["inactive", "grok-usage", "codex-usage"],
                "tooltip": "Grok usage unavailable",
            },
        )
        self.assertIn("Cursor is not signed in", result.stderr)

    def test_shim_is_only_an_alias(self):
        text = SHIM.read_text()
        self.assertIn("grok-waybar.py", text)
        self.assertNotIn("api2.cursor.sh", text)
        self.assertNotIn("account/rateLimits/read", text)
        config = (ROOT / "waybar.jsonc").read_text()
        self.assertIn("custom/grok-usage", config)
        self.assertIn("custom/codex-usage", config)
        self.assertIn("grok-waybar.py", config)
        self.assertIn("codex-waybar-usage/codex-waybar.py", config)

    def test_install_keeps_the_old_exec_path(self):
        with tempfile.TemporaryDirectory() as home:
            home_path = Path(home)
            config = home_path / ".config"
            data = home_path / ".local" / "share"
            cache = home_path / ".cache"
            state = home_path / ".local" / "state"
            runtime = home_path / "runtime"
            bin_dir = home_path / "bin"
            for directory in (config, data, cache, state, runtime, bin_dir):
                directory.mkdir(parents=True)
            runtime.chmod(0o700)
            # systemctl --user talks to the real user bus and ignores HOME.
            log_path = home_path / "systemctl.log"
            systemctl = bin_dir / "systemctl"
            systemctl.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$SYSTEMCTL_LOG"\n'
                "exit 0\n",
                encoding="utf-8",
            )
            systemctl.chmod(0o755)
            env = os.environ.copy()
            env["HOME"] = home
            env["XDG_CONFIG_HOME"] = str(config)
            env["XDG_DATA_HOME"] = str(data)
            env["XDG_CACHE_HOME"] = str(cache)
            env["XDG_STATE_HOME"] = str(state)
            env["XDG_RUNTIME_DIR"] = str(runtime)
            env["SYSTEMCTL_LOG"] = str(log_path)
            env.pop("DBUS_SESSION_BUS_ADDRESS", None)
            env["PATH"] = os.pathsep.join(
                [str(bin_dir), env.get("PATH", "/usr/bin:/bin")]
            )
            self.assertEqual(
                Path(shutil.which("systemctl", path=env["PATH"])), systemctl
            )
            old_unit = config / "systemd/user/codex-waybar-popup.service"
            old_unit.parent.mkdir(parents=True)
            old_unit.write_text(
                "[Service]\nExecStart=/old/codex-waybar.py --popup\n",
                encoding="utf-8",
            )
            subprocess.run(
                ["bash", str(ROOT / "install.sh"), "--no-enable"],
                check=True,
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            new_script = home_path / ".local/share/grok-waybar-usage/grok-waybar.py"
            old_script = home_path / ".local/share/codex-waybar-usage/codex-waybar.py"
            unit = config / "systemd/user/grok-waybar-popup.service"
            alias = config / "systemd/user/codex-waybar-popup.service"
            self.assertTrue(new_script.is_file())
            self.assertTrue(old_script.is_symlink())
            self.assertIn("Alias=codex-waybar-popup.service", unit.read_text())
            self.assertIn(
                ".local/share/grok-waybar-usage/grok-waybar.py --popup",
                unit.read_text(),
            )
            self.assertTrue(alias.is_symlink())
            self.assertEqual(os.readlink(alias), "grok-waybar-popup.service")
            result = subprocess.run(
                [sys.executable, str(old_script), "--fixture", str(FIXTURE)],
                check=True,
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(json.loads(result.stdout)["alt"], "grok")
            self.assertIn("codex-usage", json.loads(result.stdout)["class"])
            self.assertEqual(
                log_path.read_text(encoding="utf-8").splitlines(),
                ["--user disable --now codex-waybar-popup.service"],
            )


if __name__ == "__main__":
    unittest.main()
