from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from .policy import Policy, normalize_path

TEST_MODE_ENV = "AGENT_LOCKER_TEST_MODE"
PATH_OPTION_NAMES = {
    "-C",
    "-c",
    "-f",
    "-o",
    "--cd",
    "--config",
    "--config-file",
    "--config-path",
    "--cwd",
    "--directory",
    "--file",
    "--input",
    "--log-file",
    "--output",
    "--path",
    "--policy",
    "--project",
    "--root",
    "--settings",
    "--workdir",
}
PATH_SUFFIX_HINTS = (
    ".cfg",
    ".conf",
    ".crt",
    ".csr",
    ".env",
    ".ini",
    ".json",
    ".key",
    ".md",
    ".pem",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
)


Executor = Callable[[list[str], Path, int | None], subprocess.CompletedProcess]


@dataclass(frozen=True)
class RunRequest:
    command: list[str]
    cwd: Path
    execute: bool
    timeout_sec: int | None


@dataclass(frozen=True)
class RunResult:
    executed: bool
    exit_code: int
    reason: str
    message: str
    stdout: str
    stderr: str
    blocked_paths: tuple[str, ...]


def _result(
    *,
    reason: str,
    message: str,
    executed: bool,
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
    blocked_paths: tuple[str, ...] = (),
) -> RunResult:
    return RunResult(
        executed=executed,
        exit_code=exit_code,
        reason=reason,
        message=message,
        stdout=stdout,
        stderr=stderr,
        blocked_paths=blocked_paths,
    )


def default_executor(command: list[str], cwd: Path, timeout_sec: int | None) -> subprocess.CompletedProcess:
    return subprocess.run(
        command,
        cwd=str(cwd),
        timeout=timeout_sec,
        capture_output=True,
        text=True,
        check=False,
    )


class CommandRunner:
    def __init__(self, executor: Executor = default_executor):
        self.executor = executor

    def run(self, request: RunRequest, policy: Policy) -> RunResult:
        if not request.command:
            return _result(
                reason="invalid_request",
                message="Command is required.",
                executed=False,
                exit_code=2,
            )

        blocked_paths = tuple(find_blocked_paths(request.command, request.cwd, policy))
        if blocked_paths:
            return _result(
                reason="blocked_by_policy",
                message="Command blocked by deny policy.",
                executed=False,
                exit_code=25,
                blocked_paths=blocked_paths,
            )

        if not request.execute:
            return _result(
                reason="dry_run",
                message="Dry run only. Use --execute to allow execution.",
                executed=False,
                exit_code=0,
            )

        if os.getenv(TEST_MODE_ENV, "") == "1":
            return _result(
                reason="test_mode_block",
                message=f"Execution blocked because {TEST_MODE_ENV}=1.",
                executed=False,
                exit_code=26,
            )

        try:
            completed = self.executor(request.command, request.cwd, request.timeout_sec)
        except FileNotFoundError as exc:
            return _result(
                reason="command_not_found",
                message=str(exc),
                executed=False,
                exit_code=127,
            )
        except subprocess.TimeoutExpired as exc:
            return _result(
                reason="timeout",
                message=f"Command timed out after {exc.timeout} seconds.",
                executed=True,
                exit_code=124,
                stdout=exc.stdout or "",
                stderr=exc.stderr or "",
            )

        return _result(
            reason="executed",
            message="Command executed.",
            executed=True,
            exit_code=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )


def find_blocked_paths(command: list[str], cwd: Path, policy: Policy) -> list[str]:
    blocked: set[str] = set()

    executable: str | None = None
    args_start = 1
    for idx, token in enumerate(command):
        if _is_env_assignment(token):
            for candidate in _resolve_candidate_paths(token, cwd):
                _add_blocked_candidate(blocked, candidate, policy)
            continue
        executable = token
        args_start = idx + 1
        break

    if executable is not None:
        _add_blocked_candidate(blocked, resolve_executable(executable), policy)

    for candidate in extract_candidate_paths(command[args_start:], cwd):
        _add_blocked_candidate(blocked, candidate, policy)

    return sorted(blocked)


def _add_blocked_candidate(blocked: set[str], candidate: Path | None, policy: Policy) -> None:
    if candidate is None:
        return
    if policy.is_denied(candidate):
        blocked.add(str(candidate))


def resolve_executable(binary: str) -> Path | None:
    if "/" in binary:
        return normalize_path(binary)
    resolved = shutil.which(binary)
    if resolved is None:
        return None
    return normalize_path(resolved)


def extract_candidate_paths(args: list[str], cwd: Path) -> list[Path]:
    paths: list[Path] = []
    expect_option_value_path = False
    for arg in args:
        if not arg:
            continue
        if expect_option_value_path:
            expect_option_value_path = False
            paths.extend(_resolve_candidate_paths(arg, cwd))
            continue
        if arg.startswith("-"):
            option, has_value, option_value = arg.partition("=")
            if has_value:
                if _option_expects_path(option) or _looks_like_path(option_value):
                    paths.extend(_resolve_candidate_paths(option_value, cwd))
                continue
            if _option_expects_path(arg):
                expect_option_value_path = True
            continue
        paths.extend(_resolve_candidate_paths(arg, cwd))
    return paths


def _resolve_candidate_paths(arg: str, cwd: Path) -> list[Path]:
    resolved: list[Path] = []
    for token in _extract_path_tokens(arg):
        try:
            resolved.append(normalize_path(token, base_dir=cwd))
        except OSError:
            continue
    return resolved


def _extract_path_tokens(arg: str) -> list[str]:
    tokens: list[str] = []
    if "=" in arg:
        _, right = arg.split("=", 1)
        if _looks_like_path(right):
            tokens.append(right)
    elif _looks_like_path(arg):
        tokens.append(arg)
    return tokens


def _looks_like_path(value: str) -> bool:
    if not value:
        return False
    if value.startswith(("~", "/", "./", "../")):
        return True
    if value.endswith("/") or value.endswith("\\"):
        return True
    if value.endswith(PATH_SUFFIX_HINTS):
        return True
    # Covers drive-style paths such as C:\path\to\file.
    if len(value) >= 3 and value[1:3] in {":\\", ":/"}:
        return True
    # Bare directory/file forms that include separators.
    if "/" in value or "\\" in value:
        return True
    return False


def _option_expects_path(option_name: str) -> bool:
    return option_name in PATH_OPTION_NAMES


def _is_env_assignment(token: str) -> bool:
    if "=" not in token:
        return False
    left, _ = token.split("=", 1)
    if not left:
        return False
    return re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", left) is not None
