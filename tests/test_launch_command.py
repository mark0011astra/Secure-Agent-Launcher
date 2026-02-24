from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from agent_locker.launch_command import build_launcher_command_line
from agent_locker.policy import Policy, save_policy


class LaunchCommandTestCase(unittest.TestCase):
    @mock.patch("agent_locker.launch_command.shutil.which", return_value=None)
    def test_build_launcher_command_line_round_trips_with_shlex(self, _mock_which: mock.Mock) -> None:
        policy_path = Path("/tmp/policy with space.json")
        audit_log_path = Path("/tmp/audit log.jsonl")
        cwd = Path("/tmp/project with space")
        command = ["codex", "--model", "gpt-5", "--prompt", "hello world"]

        line = build_launcher_command_line(
            policy_path=policy_path,
            audit_log_path=audit_log_path,
            cwd=cwd,
            command=command,
        )
        parsed = shlex.split(line)

        self.assertEqual(
            parsed,
            [
                sys.executable,
                "-m",
                "agent_locker.cli",
                "--policy",
                str(policy_path),
                "--audit-log",
                str(audit_log_path),
                "run",
                "--execute",
                "--cwd",
                str(cwd),
                "--",
                *command,
            ],
        )

    @mock.patch("agent_locker.launch_command.shutil.which", return_value="/usr/local/bin/agent-locker")
    def test_build_launcher_command_line_prefers_installed_command(self, _mock_which: mock.Mock) -> None:
        line = build_launcher_command_line(
            policy_path=Path("/tmp/policy.json"),
            audit_log_path=Path("/tmp/audit.log"),
            cwd=Path("/tmp/project"),
            command=["codex"],
        )
        parsed = shlex.split(line)

        self.assertEqual(parsed[0], "/usr/local/bin/agent-locker")
        self.assertEqual(parsed[1:7], ["--policy", "/tmp/policy.json", "--audit-log", "/tmp/audit.log", "run", "--execute"])

    def test_generated_command_uses_latest_policy_at_execution_time(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            policy_path = root / "policy.json"
            audit_log_path = root / "audit.log"
            secret_dir = root / "secret"
            secret_dir.mkdir()
            secret_file = secret_dir / "token.txt"
            secret_file.write_text("top-secret", encoding="utf-8")

            save_policy(
                policy_path,
                Policy.from_dict(
                    {
                        "enabled": True,
                        "deny_paths": [],
                    }
                ),
            )

            nested_command = [
                sys.executable,
                "-c",
                "import pathlib,sys;print(pathlib.Path(sys.argv[1]).read_text())",
                str(secret_file),
            ]
            line = build_launcher_command_line(
                policy_path=policy_path,
                audit_log_path=audit_log_path,
                cwd=root,
                command=nested_command,
            )

            # Update policy after command generation.
            save_policy(
                policy_path,
                Policy.from_dict(
                    {
                        "enabled": True,
                        "deny_paths": [str(secret_dir)],
                    }
                ),
            )

            repo_root = Path(__file__).resolve().parents[1]
            completed = subprocess.run(
                shlex.split(line),
                cwd=repo_root,
                text=True,
                capture_output=True,
            )

            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("blocked_path:", completed.stdout)
            self.assertNotIn("top-secret", completed.stdout)

            audit_lines = audit_log_path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(audit_lines), 1)
            audit_entry = json.loads(audit_lines[0])
            self.assertEqual(audit_entry["reason"], "blocked_by_policy")


if __name__ == "__main__":
    unittest.main()
