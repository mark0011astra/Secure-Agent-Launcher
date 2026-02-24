from __future__ import annotations

import subprocess
import tempfile
import unittest
import os
from pathlib import Path

from agent_locker.policy import Policy
from agent_locker.runner import CommandRunner, RunRequest, TEST_MODE_ENV


class RunnerTestCase(unittest.TestCase):
    def test_dry_run_does_not_execute(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            calls: list[tuple[list[str], Path, int | None]] = []

            def fake_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
                calls.append((command, cwd, timeout_sec))
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            policy = Policy.from_dict({"enabled": True, "deny_paths": []})
            runner = CommandRunner(executor=fake_executor)
            result = runner.run(
                RunRequest(
                    command=["echo", "hello"],
                    cwd=tmp_path,
                    execute=False,
                    timeout_sec=None,
                ),
                policy,
            )

            self.assertEqual(result.reason, "dry_run")
            self.assertFalse(result.executed)
            self.assertEqual(calls, [])

    def test_execute_calls_injected_executor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            calls: list[tuple[list[str], Path, int | None]] = []

            def fake_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
                calls.append((command, cwd, timeout_sec))
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            policy = Policy.from_dict({"enabled": True, "deny_paths": []})
            runner = CommandRunner(executor=fake_executor)
            result = runner.run(
                RunRequest(
                    command=["echo", "hello"],
                    cwd=tmp_path,
                    execute=True,
                    timeout_sec=3,
                ),
                policy,
            )

            self.assertEqual(result.reason, "executed")
            self.assertTrue(result.executed)
            self.assertEqual(calls, [(["echo", "hello"], tmp_path, 3)])

    def test_policy_block_prevents_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            secret_dir = tmp_path / "secret"
            secret_dir.mkdir()
            secret_file = secret_dir / "token.txt"
            secret_file.write_text("x", encoding="utf-8")

            calls: list[tuple[list[str], Path, int | None]] = []

            def fake_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
                calls.append((command, cwd, timeout_sec))
                return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(secret_dir)]})
            runner = CommandRunner(executor=fake_executor)
            result = runner.run(
                RunRequest(
                    command=["cat", str(secret_file)],
                    cwd=tmp_path,
                    execute=True,
                    timeout_sec=None,
                ),
                policy,
            )

            self.assertEqual(result.reason, "blocked_by_policy")
            self.assertFalse(result.executed)
            self.assertEqual(calls, [])

    def test_test_mode_env_blocks_real_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            calls: list[tuple[list[str], Path, int | None]] = []

            def fake_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
                calls.append((command, cwd, timeout_sec))
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            policy = Policy.from_dict({"enabled": True, "deny_paths": []})
            runner = CommandRunner(executor=fake_executor)

            before = os.environ.get(TEST_MODE_ENV)
            os.environ[TEST_MODE_ENV] = "1"
            try:
                result = runner.run(
                    RunRequest(
                        command=["echo", "hello"],
                        cwd=tmp_path,
                        execute=True,
                        timeout_sec=None,
                    ),
                    policy,
                )
            finally:
                if before is None:
                    os.environ.pop(TEST_MODE_ENV, None)
                else:
                    os.environ[TEST_MODE_ENV] = before

            self.assertEqual(result.reason, "test_mode_block")
            self.assertFalse(result.executed)
            self.assertEqual(calls, [])

    def test_disabled_protection_allows_execution_for_denied_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            secret_dir = tmp_path / "secret"
            secret_dir.mkdir()
            secret_file = secret_dir / "token.txt"
            secret_file.write_text("x", encoding="utf-8")

            calls: list[tuple[list[str], Path, int | None]] = []

            def fake_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
                calls.append((command, cwd, timeout_sec))
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            policy = Policy.from_dict({"enabled": False, "deny_paths": [str(secret_dir)]})
            runner = CommandRunner(executor=fake_executor)
            result = runner.run(
                RunRequest(
                    command=["cat", str(secret_file)],
                    cwd=tmp_path,
                    execute=True,
                    timeout_sec=None,
                ),
                policy,
            )

            self.assertEqual(result.reason, "executed")
            self.assertTrue(result.executed)
            self.assertEqual(calls, [(["cat", str(secret_file)], tmp_path, None)])


if __name__ == "__main__":
    unittest.main()
