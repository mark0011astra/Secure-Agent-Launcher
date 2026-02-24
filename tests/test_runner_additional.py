from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_locker.policy import Policy, normalize_path
from agent_locker import runner as runner_mod
from agent_locker.runner import CommandRunner, RunRequest, extract_candidate_paths, find_blocked_paths, resolve_executable


class RunnerAdditionalTestCase(unittest.TestCase):
    def test_empty_command_returns_invalid_request(self) -> None:
        policy = Policy.from_dict({"enabled": True, "deny_paths": []})
        runner = CommandRunner()

        result = runner.run(
            RunRequest(
                command=[],
                cwd=Path.cwd(),
                execute=True,
                timeout_sec=None,
            ),
            policy,
        )

        self.assertEqual(result.reason, "invalid_request")
        self.assertEqual(result.exit_code, 2)
        self.assertFalse(result.executed)

    def test_executor_file_not_found_maps_to_command_not_found(self) -> None:
        policy = Policy.from_dict({"enabled": True, "deny_paths": []})

        def fake_executor(_command: list[str], _cwd: Path, _timeout_sec: int | None) -> subprocess.CompletedProcess:
            raise FileNotFoundError("missing")

        runner = CommandRunner(executor=fake_executor)
        result = runner.run(
            RunRequest(
                command=["missing-cmd"],
                cwd=Path.cwd(),
                execute=True,
                timeout_sec=None,
            ),
            policy,
        )

        self.assertEqual(result.reason, "command_not_found")
        self.assertEqual(result.exit_code, 127)
        self.assertIn("missing", result.message)

    def test_executor_timeout_preserves_partial_streams(self) -> None:
        policy = Policy.from_dict({"enabled": True, "deny_paths": []})

        def fake_executor(_command: list[str], _cwd: Path, _timeout_sec: int | None) -> subprocess.CompletedProcess:
            raise subprocess.TimeoutExpired(cmd=["sleep", "5"], timeout=5, output="partial-out", stderr="partial-err")

        runner = CommandRunner(executor=fake_executor)
        result = runner.run(
            RunRequest(
                command=["sleep", "5"],
                cwd=Path.cwd(),
                execute=True,
                timeout_sec=5,
            ),
            policy,
        )

        self.assertEqual(result.reason, "timeout")
        self.assertEqual(result.exit_code, 124)
        self.assertTrue(result.executed)
        self.assertEqual(result.stdout, "partial-out")
        self.assertEqual(result.stderr, "partial-err")

    def test_find_blocked_paths_deduplicates_and_sorts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            alpha = tmp_path / "alpha"
            beta = tmp_path / "beta"
            alpha.mkdir()
            beta.mkdir()

            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(alpha), str(beta)]})
            blocked = find_blocked_paths(
                ["cat", str(beta / "b.txt"), str(alpha / "a.txt"), str(alpha / "a.txt")],
                tmp_path,
                policy,
            )

            self.assertEqual(
                blocked,
                sorted({str((alpha / "a.txt").resolve(strict=False)), str((beta / "b.txt").resolve(strict=False))}),
            )

    def test_find_blocked_paths_checks_executable_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            blocked_executable = normalize_path(tmp_path / "bin" / "tool")
            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(blocked_executable.parent)]})

            with mock.patch.object(runner_mod, "resolve_executable", return_value=blocked_executable):
                blocked = find_blocked_paths(["tool"], tmp_path, policy)

            self.assertEqual(blocked, [str(blocked_executable)])

    def test_resolve_executable_with_path_separator_returns_normalized_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            raw = Path(temp_dir) / "bin" / "tool"
            resolved = resolve_executable(str(raw))
            self.assertEqual(resolved, normalize_path(raw))

    def test_extract_candidate_paths_with_mixed_args(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            args = ["--verbose", "config=./app.yaml", "README.md", "../deploy.sh", "token=abc123", "plain"]

            extracted = extract_candidate_paths(args, cwd)

            self.assertEqual(
                extracted,
                [
                    normalize_path("./app.yaml", base_dir=cwd),
                    normalize_path("README.md", base_dir=cwd),
                    normalize_path("../deploy.sh", base_dir=cwd),
                ],
            )

    def test_extract_candidate_paths_skips_tokens_that_fail_normalization(self) -> None:
        cwd = Path.cwd()

        def fake_normalize(path: str | Path, base_dir: Path | None = None) -> Path:
            if str(path) == "bad.txt":
                raise OSError("bad path")
            return normalize_path(path, base_dir=base_dir)

        with mock.patch.object(runner_mod, "normalize_path", side_effect=fake_normalize):
            extracted = extract_candidate_paths(["bad.txt", "good.txt"], cwd)

        self.assertEqual(extracted, [normalize_path("good.txt", base_dir=cwd)])

    def test_extract_candidate_paths_reads_option_value_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cwd = Path(temp_dir)
            extracted = extract_candidate_paths(["--config", "settings.toml", "--policy=./policy.json"], cwd)
            self.assertEqual(
                extracted,
                [
                    normalize_path("settings.toml", base_dir=cwd),
                    normalize_path("./policy.json", base_dir=cwd),
                ],
            )

    def test_find_blocked_paths_checks_environment_assignment_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            tmp_path = Path(temp_dir)
            deny = tmp_path / "secret"
            deny.mkdir()
            policy = Policy.from_dict({"enabled": True, "deny_paths": [str(deny)]})
            blocked = find_blocked_paths(
                ["TOKEN_FILE=./secret/token.env", "python3", "-c", "print('ok')"],
                tmp_path,
                policy,
            )
            self.assertEqual(blocked, [str((deny / "token.env").resolve(strict=False))])


if __name__ == "__main__":
    unittest.main()
