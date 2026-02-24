from __future__ import annotations

import shlex
import shutil
import sys
from pathlib import Path


def _launcher_prefix() -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable]

    launcher = shutil.which("agent-locker")
    if launcher:
        return [launcher]

    return [sys.executable, "-m", "agent_locker.cli"]


def build_launcher_command_line(
    policy_path: Path,
    audit_log_path: Path,
    cwd: Path,
    command: list[str],
) -> str:
    launcher_command = [
        *_launcher_prefix(),
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
    ]
    return shlex.join(launcher_command)
