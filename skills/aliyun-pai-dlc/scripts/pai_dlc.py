#!/usr/bin/env python3
"""Small, auditable wrapper around the Alibaba Cloud PAI CLI.

The wrapper owns local defaults and credential loading. The cloud API remains
implemented by the installed ``pai`` binary, so its request and response shape
can be inspected with ``--dry-run`` and ``-o json``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import sys
from typing import Any


SKILL_DIR = Path(__file__).resolve().parents[1]
LOCAL_ENV = SKILL_DIR / "references" / "local_env.sh"


def parse_shell_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        raw_value = raw_value.strip()
        try:
            parsed = shlex.split(raw_value, comments=True, posix=True)
        except ValueError as exc:
            raise RuntimeError(f"invalid env file {path}: {exc}") from None
        values[key] = parsed[0] if parsed else ""
    return values


def check_private_path(path: Path) -> None:
    if not path.is_absolute() or path.is_symlink():
        raise RuntimeError(f"private credential file must be an absolute regular file: {path}")
    try:
        parent = path.parent.stat()
        info = path.stat()
    except FileNotFoundError:
        raise RuntimeError(f"credential file does not exist: {path}") from None
    if path.parent.is_symlink() or parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
        raise RuntimeError(f"credential directory is not owner-only: {path.parent}")
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise RuntimeError(f"credential file is not owner-only: {path}")


def load_credentials() -> None:
    if LOCAL_ENV.exists():
        for key, value in parse_shell_env(LOCAL_ENV).items():
            os.environ.setdefault(key, value)

    env_file = os.environ.get("ALIYUN_PAI_CREDENTIAL_ENV_FILE")
    if env_file:
        path = Path(env_file).expanduser()
        check_private_path(path)
        for key, value in parse_shell_env(path).items():
            os.environ.setdefault(key, value)

    json_file = os.environ.get("ALIYUN_PAI_CREDENTIAL_JSON_FILE")
    if json_file:
        path = Path(json_file).expanduser()
        check_private_path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise RuntimeError("credential JSON must contain an object")
        allowed = {"access_key_id", "access_key_secret", "security_token"}
        if set(payload) - allowed or not payload.get("access_key_id") or not payload.get("access_key_secret"):
            raise RuntimeError("credential JSON must contain access_key_id and access_key_secret")
        os.environ.setdefault("PAI_ACCESS_KEY_ID", str(payload["access_key_id"]))
        os.environ.setdefault("PAI_ACCESS_KEY_SECRET", str(payload["access_key_secret"]))
        if payload.get("security_token"):
            os.environ.setdefault("PAI_SECURITY_TOKEN", str(payload["security_token"]))


def env_value(name: str, fallback: str | None = None) -> str | None:
    value = os.environ.get(name)
    return value if value not in (None, "") else fallback


def env_int(name: str, fallback: int | None = None) -> int | None:
    value = env_value(name)
    if value is None:
        return fallback
    try:
        return int(value)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer") from None


def pai_binary() -> str:
    configured = os.environ.get("PAI_CLI_BIN", "pai")
    resolved = shutil.which(configured) if not os.path.isabs(configured) else configured
    if not resolved or not os.access(resolved, os.X_OK):
        raise RuntimeError(f"PAI CLI not found or not executable: {configured}")
    return resolved


def child_env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("PAI_REGION", "cn-beijing")
    return env


def run_pai(arguments: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
    command = [pai_binary(), *arguments]
    return subprocess.run(
        command,
        env=child_env(),
        text=True,
        capture_output=capture,
        check=False,
    )


def decode_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text.strip()


def print_process(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)


def credential_source() -> str:
    if os.environ.get("PAI_ACCESS_KEY_ID") and os.environ.get("PAI_ACCESS_KEY_SECRET"):
        return "PAI_ACCESS_KEY_ID/PAI_ACCESS_KEY_SECRET"
    if os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_ID") and os.environ.get("ALIBABA_CLOUD_ACCESS_KEY_SECRET"):
        return "ALIBABA_CLOUD_ACCESS_KEY_ID/ALIBABA_CLOUD_ACCESS_KEY_SECRET"
    if os.environ.get("ALIYUN_PAI_CREDENTIAL_JSON_FILE"):
        return "private JSON file"
    if os.environ.get("ALIYUN_PAI_CREDENTIAL_ENV_FILE"):
        return "private env file"
    config_dir = Path(os.environ.get("PAI_CONFIG_DIR", Path.home() / ".pai")).expanduser()
    if (config_dir / "config.json").exists():
        return "PAI CLI config"
    return "missing"


def command_check(_: argparse.Namespace) -> int:
    report: dict[str, Any] = {
        "pai_cli": None,
        "version": None,
        "region": env_value("PAI_REGION"),
        "workspace_id": env_value("PAI_WORKSPACE_ID"),
        "resource_id": env_value("ALIYUN_DLC_RESOURCE_ID"),
        "credential_source": credential_source(),
        "config_dir": str(Path(os.environ.get("PAI_CONFIG_DIR", Path.home() / ".pai")).expanduser()),
    }
    configured = os.environ.get("PAI_CLI_BIN", "pai")
    resolved = shutil.which(configured) if not os.path.isabs(configured) else configured
    if resolved and os.access(resolved, os.X_OK):
        report["pai_cli"] = resolved
        result = run_pai(["--version"], capture=True)
        report["version"] = (result.stdout or result.stderr).strip()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["pai_cli"] else 2


def resource_id(args: argparse.Namespace) -> str:
    value = args.resource_id or env_value("ALIYUN_DLC_RESOURCE_ID")
    if not value:
        raise RuntimeError("resource quota ID is required. Pass --resource-id or set ALIYUN_DLC_RESOURCE_ID")
    return value


def workspace_id(args: argparse.Namespace) -> str | None:
    return args.workspace_id or env_value("PAI_WORKSPACE_ID")


def run_json_command(arguments: list[str]) -> tuple[int, Any]:
    result = run_pai(arguments + ["-o", "json"], capture=True)
    payload = decode_json(result.stdout or "")
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr)
    return result.returncode, payload


def command_resources(args: argparse.Namespace) -> int:
    quota = resource_id(args)
    scope = {"region": env_value("PAI_REGION"), "workspace_id": workspace_id(args), "resource_id": quota}
    result: dict[str, Any] = {"scope": scope}
    errors: dict[str, Any] = {}

    code, payload = run_json_command(["resource", "quota", "get", quota])
    result["quota"] = payload
    if code:
        errors["quota"] = payload

    workload_args = ["resource", "quota", "workloads", quota, "--workload-type", "dlc"]
    if args.self_only:
        workload_args.append("--self-only")
    else:
        workload_args.append("--all-users")
    code, payload = run_json_command(workload_args)
    result["dlc_workloads"] = payload
    if code:
        errors["dlc_workloads"] = payload

    if args.users:
        user_args = ["resource", "quota", "user-usage", quota, "--sort-by", "UsedGPU", "--order", "desc"]
        if workspace_id(args):
            user_args.extend(["--workspace-id", workspace_id(args)])
        code, payload = run_json_command(user_args)
        result["user_usage"] = payload
        if code:
            errors["user_usage"] = payload

    if errors:
        result["errors"] = errors
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


def add_scope_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--workspace-id")
    parser.add_argument("--resource-id")


def add_submit_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name")
    parser.add_argument("--command")
    parser.add_argument("--job-type", default=None)
    parser.add_argument("--image", default=None)
    parser.add_argument("--worker-count", type=int, default=None)
    parser.add_argument("--worker-spec", default=None)
    parser.add_argument("--cpu", default=None)
    parser.add_argument("--memory", default=None)
    parser.add_argument("--gpu", default=None)
    parser.add_argument("--gpu-type", default=None)
    parser.add_argument("--shared-memory", default=None)
    parser.add_argument("--data-source", action="append", default=None)
    parser.add_argument("--code-source", default=None)
    parser.add_argument("--code-branch", default=None)
    parser.add_argument("--code-commit", default=None)
    parser.add_argument("--code-mount-path", default=None)
    parser.add_argument("--thirdparty-lib", action="append", default=None)
    parser.add_argument("--thirdparty-lib-dir", default=None)
    parser.add_argument("--env", action="append", default=None)
    parser.add_argument("--priority", type=int, default=None)
    parser.add_argument("--scheduling-strategy", default=None)
    parser.add_argument("--success-policy", default=None)
    parser.add_argument("--max-running-time-minutes", type=int, default=None)
    parser.add_argument("--accessibility", default=None)
    parser.add_argument("--description", default=None)
    parser.add_argument("--from-file", default=None)
    parser.add_argument("--body-json", default=None)
    parser.add_argument("--receipt", default=None)
    parser.add_argument("--live", action="store_true")
    add_scope_arguments(parser)


def append_option(command: list[str], flag: str, value: Any) -> None:
    if value is not None and value != "":
        command.extend([flag, str(value)])


def build_submit_command(args: argparse.Namespace, *, live: bool) -> list[str]:
    if args.from_file and args.body_json:
        raise RuntimeError("--from-file and --body-json are mutually exclusive")

    command = ["dlc", "job", "submit"]
    if args.from_file:
        command.extend(["--from-file", args.from_file])
    elif args.body_json:
        command.extend(["--body-json", args.body_json])
    else:
        if not args.name or not args.command:
            raise RuntimeError("--name and --command are required for scalar submission")
        image = args.image or env_value("ALIYUN_DLC_DEFAULT_IMAGE")
        if not image:
            raise RuntimeError("image is required. Pass --image or set ALIYUN_DLC_DEFAULT_IMAGE")
        append_option(command, "--name", args.name)
        append_option(command, "--job-type", args.job_type or env_value("ALIYUN_DLC_DEFAULT_JOB_TYPE", "PyTorchJob"))
        append_option(command, "--image", image)
        append_option(command, "--command", args.command)
        append_option(command, "--workspace-id", workspace_id(args))

        if args.worker_spec:
            conflicting = [args.resource_id, args.cpu, args.memory, args.gpu, args.gpu_type, args.shared_memory]
            if any(value not in (None, "") for value in conflicting):
                raise RuntimeError("--worker-spec cannot be combined with quota resource flags")
            append_option(command, "--worker-spec", args.worker_spec)
            append_option(command, "--worker-count", args.worker_count or env_int("ALIYUN_DLC_DEFAULT_WORKER_COUNT", 1))
        else:
            append_option(command, "--resource-id", args.resource_id or env_value("ALIYUN_DLC_RESOURCE_ID"))
            append_option(command, "--worker-count", args.worker_count or env_int("ALIYUN_DLC_DEFAULT_WORKER_COUNT", 1))
            append_option(command, "--cpu", args.cpu or env_value("ALIYUN_DLC_DEFAULT_CPU"))
            append_option(command, "--memory", args.memory or env_value("ALIYUN_DLC_DEFAULT_MEMORY"))
            append_option(command, "--gpu", args.gpu or env_value("ALIYUN_DLC_DEFAULT_GPU"))
            append_option(command, "--gpu-type", args.gpu_type)
            append_option(command, "--shared-memory", args.shared_memory or env_value("ALIYUN_DLC_DEFAULT_SHARED_MEMORY"))

        for value in args.data_source or []:
            append_option(command, "--data-source", value)
        for value in args.thirdparty_lib or []:
            append_option(command, "--thirdparty-lib", value)
        append_option(command, "--code-source", args.code_source)
        append_option(command, "--code-branch", args.code_branch)
        append_option(command, "--code-commit", args.code_commit)
        append_option(command, "--code-mount-path", args.code_mount_path)
        append_option(command, "--thirdparty-lib-dir", args.thirdparty_lib_dir)
        for value in args.env or []:
            append_option(command, "--env", value)
        append_option(command, "--priority", args.priority)
        append_option(command, "--scheduling-strategy", args.scheduling_strategy)
        append_option(command, "--success-policy", args.success_policy)
        append_option(command, "--max-running-time-minutes", args.max_running_time_minutes)
        append_option(command, "--accessibility", args.accessibility)
        append_option(command, "--description", args.description)

    if live:
        command.extend(["--result-envelope", "-o", "json"])
    else:
        command.append("--dry-run")
    return command


def extract_job_id(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("job_id", "JobId", "id", "Id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for value in payload.values():
            found = extract_job_id(value)
            if found:
                return found
    if isinstance(payload, list):
        for value in payload:
            found = extract_job_id(value)
            if found:
                return found
    return None


def write_receipt(path_value: str | None, command: list[str], result: subprocess.CompletedProcess[str]) -> None:
    if not path_value:
        return
    path = Path(path_value).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "command": command,
        "returncode": result.returncode,
        "job_id": extract_job_id(decode_json(result.stdout or "")),
        "stdout": result.stdout or "",
    }
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def command_submit(args: argparse.Namespace, *, force_dry_run: bool = False) -> int:
    live = bool(args.live) and not force_dry_run
    command = build_submit_command(args, live=live)
    result = run_pai(command, capture=True)
    print_process(result)
    if live:
        write_receipt(args.receipt, command, result)
    return result.returncode


def command_job_get(args: argparse.Namespace) -> int:
    result = run_pai(["dlc", "job", "get", args.job_id, "-o", "json"], capture=False)
    print_process(result)
    return result.returncode


def command_job_logs(args: argparse.Namespace) -> int:
    command = ["dlc", "job", "logs", args.job_id, "--tail", str(args.tail)]
    if args.pod:
        command.extend(["--pod", args.pod])
    if args.follow:
        command.append("--follow")
    result = run_pai(command, capture=False)
    print_process(result)
    return result.returncode


def command_job_events(args: argparse.Namespace) -> int:
    command = ["dlc", "job", "events", args.job_id, "--max", str(args.max_events)]
    if args.pod:
        command.extend(["--pod", args.pod])
    result = run_pai(command, capture=False)
    print_process(result)
    return result.returncode


def command_job_wait(args: argparse.Namespace) -> int:
    command = ["dlc", "job", "wait", args.job_id, "--for", args.wait_for,
               "--interval", str(args.interval), "--timeout", str(args.timeout)]
    result = run_pai(command, capture=False)
    print_process(result)
    return result.returncode


def command_job_list(args: argparse.Namespace) -> int:
    command = ["dlc", "job", "list"]
    if workspace_id(args):
        command.extend(["--workspace-id", workspace_id(args)])
    if args.status:
        command.extend(["--status", args.status])
    if args.display_name:
        command.extend(["--display-name", args.display_name])
    command.extend(["--since", args.since, "-o", "json"])
    result = run_pai(command, capture=False)
    print_process(result)
    return result.returncode


def command_stop(args: argparse.Namespace) -> int:
    if not args.live:
        print("stop requires --live", file=sys.stderr)
        return 2
    result = run_pai(["dlc", "job", "stop", args.job_id, "--yes"], capture=False)
    print_process(result)
    return result.returncode


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PAI DLC CLI helper")
    sub = parser.add_subparsers(dest="operation", required=True)

    check = sub.add_parser("check")
    check.set_defaults(handler=command_check)

    resources = sub.add_parser("resources")
    add_scope_arguments(resources)
    resources.add_argument("--self-only", action="store_true")
    resources.add_argument("--users", action="store_true")
    resources.set_defaults(handler=command_resources)

    dry_run = sub.add_parser("dry-run")
    add_submit_arguments(dry_run)
    dry_run.set_defaults(handler=lambda args: command_submit(args, force_dry_run=True))

    submit = sub.add_parser("submit")
    add_submit_arguments(submit)
    submit.set_defaults(handler=command_submit)

    status = sub.add_parser("status")
    status.add_argument("job_id")
    status.set_defaults(handler=command_job_get)

    logs = sub.add_parser("logs")
    logs.add_argument("job_id")
    logs.add_argument("--pod")
    logs.add_argument("--tail", type=int, default=2000)
    logs.add_argument("--follow", action="store_true")
    logs.set_defaults(handler=command_job_logs)

    events = sub.add_parser("events")
    events.add_argument("job_id")
    events.add_argument("--pod")
    events.add_argument("--max", dest="max_events", type=int, default=2000)
    events.set_defaults(handler=command_job_events)

    wait = sub.add_parser("wait")
    wait.add_argument("job_id")
    wait.add_argument("--for", dest="wait_for", default="Succeeded")
    wait.add_argument("--interval", type=int, default=10)
    wait.add_argument("--timeout", type=int, default=3600)
    wait.set_defaults(handler=command_job_wait)

    listing = sub.add_parser("list")
    add_scope_arguments(listing)
    listing.add_argument("--status")
    listing.add_argument("--display-name")
    listing.add_argument("--since", default="7d")
    listing.set_defaults(handler=command_job_list)

    stop = sub.add_parser("stop")
    stop.add_argument("job_id")
    stop.add_argument("--live", action="store_true")
    stop.set_defaults(handler=command_stop)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        load_credentials()
        args = make_parser().parse_args(argv)
        return int(args.handler(args))
    except (RuntimeError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
