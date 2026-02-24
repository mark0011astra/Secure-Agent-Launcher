from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from agent_locker import cli
from agent_locker.config import write_default_policy
from agent_locker.policy import load_policy
from agent_locker.runner import RunResult


class CliTestCase(unittest.TestCase):
    def test_init_creates_policy(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli.main(["--policy", str(policy_path), "init"])

            self.assertEqual(exit_code, 0)
            self.assertTrue(policy_path.exists())
            self.assertIn("Policy ready:", stdout.getvalue())

    def test_show_prints_json_payload(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            write_default_policy(policy_path, overwrite=True)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli.main(["--policy", str(policy_path), "show"])

            self.assertEqual(exit_code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertIn("enabled", payload)
            self.assertIn("deny_paths", payload)

    def test_run_without_command_returns_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            audit_log_path = Path(temp_dir) / "audit.log"
            write_default_policy(policy_path, overwrite=True)

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "--audit-log",
                        str(audit_log_path),
                        "run",
                        "--execute",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("Command is required", stderr.getvalue())

    def test_run_with_invalid_timeout_returns_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            write_default_policy(policy_path, overwrite=True)

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    cli.main(
                        [
                            "--policy",
                            str(policy_path),
                            "run",
                            "--timeout-sec",
                            "0",
                            "--",
                            "echo",
                            "ok",
                        ]
                    )
            self.assertEqual(exc.exception.code, 2)
            self.assertIn("timeout must be greater than 0", stderr.getvalue())

    def test_run_with_missing_working_directory_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy_path = root / "policy.json"
            write_default_policy(policy_path, overwrite=True)
            missing_dir = root / "missing-dir"

            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "run",
                        "--execute",
                        "--cwd",
                        str(missing_dir),
                        "--",
                        "echo",
                        "ok",
                    ]
                )

            self.assertEqual(exit_code, 2)
            self.assertIn("Working directory was not found", stderr.getvalue())

    def test_run_executes_runner_and_writes_audit_log(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            audit_log_path = Path(temp_dir) / "audit.log"
            workdir = Path(temp_dir) / "work"
            workdir.mkdir()
            write_default_policy(policy_path, overwrite=True)

            fake_result = RunResult(
                executed=True,
                exit_code=7,
                reason="executed",
                message="Command executed.",
                stdout="stdout-line\n",
                stderr="stderr-line\n",
                blocked_paths=(),
            )

            with mock.patch.object(cli.CommandRunner, "run", return_value=fake_result) as run_mock:
                stdout = io.StringIO()
                stderr = io.StringIO()
                with redirect_stdout(stdout), redirect_stderr(stderr):
                    exit_code = cli.main(
                        [
                            "--policy",
                            str(policy_path),
                            "--audit-log",
                            str(audit_log_path),
                            "run",
                            "--execute",
                            "--cwd",
                            str(workdir),
                            "--",
                            "codex",
                            "--model",
                            "gpt-5",
                        ]
                    )

            self.assertEqual(exit_code, 7)
            run_mock.assert_called_once()
            self.assertIn("Command executed.", stdout.getvalue())
            self.assertIn("stdout-line", stdout.getvalue())
            self.assertIn("stderr-line", stderr.getvalue())

            audit_lines = audit_log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(audit_lines), 1)
            audit_entry = json.loads(audit_lines[0])
            self.assertEqual(audit_entry["reason"], "executed")
            self.assertEqual(audit_entry["executed"], True)
            self.assertEqual(audit_entry["command"], ["codex", "--model", "gpt-5"])

    def test_policy_on_and_off_persist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            write_default_policy(policy_path, overwrite=True)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                off_code = cli.main(["--policy", str(policy_path), "policy", "off"])
            self.assertEqual(off_code, 0)
            self.assertFalse(load_policy(policy_path).enabled)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                on_code = cli.main(["--policy", str(policy_path), "policy", "on"])
            self.assertEqual(on_code, 0)
            self.assertTrue(load_policy(policy_path).enabled)

    def test_policy_add_relative_path_resolves_from_policy_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy_dir = root / "policy-home"
            policy_dir.mkdir()
            policy_path = policy_dir / "policy.json"
            write_default_policy(policy_path, overwrite=True)

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                exit_code = cli.main(["--policy", str(policy_path), "policy", "add", "./secrets"])

            self.assertEqual(exit_code, 0)
            loaded = load_policy(policy_path)
            self.assertIn((policy_dir / "secrets").resolve(strict=False), loaded.deny_paths)

    def test_gui_subcommand_delegates_to_run_gui(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            policy_path = Path(temp_dir) / "policy.json"
            audit_log_path = Path(temp_dir) / "audit.log"

            with mock.patch.object(cli, "run_gui", return_value=0) as run_gui_mock:
                exit_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "--audit-log",
                        str(audit_log_path),
                        "gui",
                    ]
                )

            self.assertEqual(exit_code, 0)
            run_gui_mock.assert_called_once_with(policy_path, audit_log_path)

    def test_run_result_changes_when_policy_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy_path = root / "policy.json"
            audit_log_path = root / "audit.log"
            secret_dir = root / "secret"
            secret_dir.mkdir()
            secret_file = secret_dir / "token.txt"
            secret_file.write_text("sensitive-data", encoding="utf-8")
            write_default_policy(policy_path, overwrite=True)

            command = [
                sys.executable,
                "-c",
                "import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())",
                str(secret_file),
            ]

            first_stdout = io.StringIO()
            first_stderr = io.StringIO()
            with redirect_stdout(first_stdout), redirect_stderr(first_stderr):
                first_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "--audit-log",
                        str(audit_log_path),
                        "run",
                        "--execute",
                        "--cwd",
                        str(root),
                        "--",
                        *command,
                    ]
                )

            self.assertEqual(first_code, 0)
            self.assertIn("sensitive-data", first_stdout.getvalue())

            policy_add_stdout = io.StringIO()
            with redirect_stdout(policy_add_stdout):
                policy_add_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "policy",
                        "add",
                        str(secret_dir),
                    ]
                )
            self.assertEqual(policy_add_code, 0)

            second_stdout = io.StringIO()
            second_stderr = io.StringIO()
            with redirect_stdout(second_stdout), redirect_stderr(second_stderr):
                second_code = cli.main(
                    [
                        "--policy",
                        str(policy_path),
                        "--audit-log",
                        str(audit_log_path),
                        "run",
                        "--execute",
                        "--cwd",
                        str(root),
                        "--",
                        *command,
                    ]
                )

            self.assertNotEqual(second_code, 0)
            self.assertIn("blocked_path:", second_stdout.getvalue())
            self.assertNotIn("sensitive-data", second_stdout.getvalue())

            audit_lines = audit_log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(audit_lines), 2)
            first_audit = json.loads(audit_lines[0])
            second_audit = json.loads(audit_lines[1])
            self.assertEqual(first_audit["reason"], "executed")
            self.assertEqual(second_audit["reason"], "blocked_by_policy")
            self.assertTrue(second_audit["blocked_paths"])


if __name__ == "__main__":
    unittest.main()
