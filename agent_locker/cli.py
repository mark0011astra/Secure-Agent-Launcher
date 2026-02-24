from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from .audit import iso_utc_now, write_audit_log
from .config import default_audit_log_path, default_policy_path, write_default_policy
from .policy import Policy, PolicyError, load_policy, normalize_path, save_policy
from .runner import CommandRunner, RunRequest


def positive_timeout(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timeout must be an integer") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("timeout must be greater than 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="secure-agent-locker", description="Safety-first launcher for agent CLIs.")
    parser.add_argument("--policy", type=Path, default=default_policy_path(), help="Policy JSON path.")
    parser.add_argument("--audit-log", type=Path, default=default_audit_log_path(), help="Audit log path.")

    subparsers = parser.add_subparsers(dest="subcommand", required=True)

    init_parser = subparsers.add_parser("init", help="Create a default policy file.")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing policy.")

    policy_parser = subparsers.add_parser("policy", help="Edit deny-path policy.")
    policy_sub = policy_parser.add_subparsers(dest="policy_cmd", required=True)
    policy_sub.add_parser("status", help="Show policy status.")
    policy_sub.add_parser("list", help="Show deny paths.")
    policy_sub.add_parser("on", help="Enable deny-path protection.")
    policy_sub.add_parser("off", help="Disable deny-path protection.")

    policy_add = policy_sub.add_parser("add", help="Add deny paths.")
    policy_add.add_argument("paths", nargs="+")

    policy_remove = policy_sub.add_parser("remove", help="Remove deny paths.")
    policy_remove.add_argument("paths", nargs="+")

    run_parser = subparsers.add_parser("run", help="Run an agent CLI with safety checks.")
    run_parser.add_argument("--execute", action="store_true", help="Actually execute command.")
    run_parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Working directory.")
    run_parser.add_argument("--timeout-sec", type=positive_timeout, default=None, help="Timeout for command execution.")
    run_parser.add_argument("command", nargs=argparse.REMAINDER, help="Command to launch after --")

    subparsers.add_parser("gui", help="Open simple GUI.")
    subparsers.add_parser("show", help="Print policy JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "init":
        write_default_policy(args.policy, overwrite=args.force)
        print(f"Policy ready: {args.policy}")
        return 0

    if args.subcommand == "gui":
        return run_gui(args.policy, args.audit_log)

    try:
        policy = load_policy(args.policy)
    except PolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.subcommand == "show":
        print(json.dumps(policy.to_dict(), indent=2))
        return 0

    if args.subcommand == "policy":
        return handle_policy_command(args, policy)

    if args.subcommand == "run":
        command = args.command
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            print("Command is required. Example: secure-agent-locker run -- codex", file=sys.stderr)
            return 2

        cwd = normalize_path(args.cwd)
        if not cwd.exists():
            print(f"Working directory was not found: {cwd}", file=sys.stderr)
            return 2
        if not cwd.is_dir():
            print(f"Working directory is not a directory: {cwd}", file=sys.stderr)
            return 2
        request = RunRequest(
            command=command,
            cwd=cwd,
            execute=bool(args.execute),
            timeout_sec=args.timeout_sec,
        )
        result = CommandRunner().run(request, policy)
        write_audit_log(
            args.audit_log,
            {
                "timestamp": iso_utc_now(),
                "command": command,
                "command_text": shlex.join(command),
                "cwd": str(cwd),
                "executed": result.executed,
                "reason": result.reason,
                "exit_code": result.exit_code,
                "blocked_paths": list(result.blocked_paths),
            },
        )
        print(result.message)
        if result.blocked_paths:
            for blocked in result.blocked_paths:
                print(f"blocked_path: {blocked}")
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.stderr:
            print(result.stderr, end="" if result.stderr.endswith("\n") else "\n", file=sys.stderr)
        return result.exit_code

    print("Unsupported command.", file=sys.stderr)
    return 2


def handle_policy_command(args: argparse.Namespace, policy: Policy) -> int:
    current = set(str(p) for p in policy.deny_paths)
    base_dir = args.policy.parent

    if args.policy_cmd == "status":
        print(f"enabled: {'on' if policy.enabled else 'off'}")
        print(f"deny_paths: {len(current)}")
        return 0

    if args.policy_cmd == "list":
        print(f"enabled: {'on' if policy.enabled else 'off'}")
        for path in sorted(current):
            print(path)
        return 0

    if args.policy_cmd in {"on", "off"}:
        updated = Policy(enabled=args.policy_cmd == "on", deny_paths=policy.deny_paths)
        save_policy(args.policy, updated)
        print(f"enabled: {'on' if updated.enabled else 'off'}")
        return 0

    if args.policy_cmd == "add":
        for raw in args.paths:
            current.add(str(normalize_path(raw, base_dir=base_dir)))
    elif args.policy_cmd == "remove":
        for raw in args.paths:
            current.discard(str(normalize_path(raw, base_dir=base_dir)))

    updated = Policy.from_dict(
        {
            "enabled": policy.enabled,
            "deny_paths": sorted(current),
        }
    )
    save_policy(args.policy, updated)
    print(f"enabled: {'on' if updated.enabled else 'off'}")
    for path in sorted(current):
        print(path)
    return 0


def run_gui(policy_path: Path, audit_log_path: Path) -> int:
    from .gui import launch_gui

    launch_gui(policy_path, audit_log_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
