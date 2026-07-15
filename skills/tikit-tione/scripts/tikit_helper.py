#!/usr/bin/env python3
"""Helpers for Tencent Cloud TI-ONE Tikit scripts."""

from __future__ import annotations

import argparse
import importlib.util
import inspect
import json
import os
import platform
import sys
import textwrap
import warnings
from typing import Any, Callable


SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _client_header() -> str:
    return """\
import os
from tikit.client import Client


client = Client(
    os.environ.get("TENCENTCLOUD_SECRET_ID"),
    os.environ.get("TENCENTCLOUD_SECRET_KEY"),
    os.environ.get("TENCENTCLOUD_REGION"),
)
"""


TEMPLATES: dict[str, str] = {
    "client": _client_header()
    + """

print(client)
""",
    "training": _client_header()
    + """

# Fill these placeholders from the current TI-ONE project.
task_name = "example-training-task"
code_package = "your-bucket/path/to/code-package/"
output_path = "your-bucket/path/to/output/"
startup_command = "python train.py"

# Verify exact Tikit class names and parameters against the installed version:
# python3 {skill_dir}/scripts/tikit_helper.py methods training
#
# Typical fields: framework/image, worker resource config, input data configs,
# output COS path, resource group, log config, VPC/subnet, max restart count.

print("Ready to create training task:")
print({{
    "task_name": task_name,
    "code_package": code_package,
    "output_path": output_path,
    "startup_command": startup_command,
}})

# Example shape only; replace with the exact signature for your Tikit version.
# resp = client.create_training_task(...)
# print(resp)
""",
    "notebook": _client_header()
    + """

# TI-ONE docs may still call development machines "notebook" in API names.
# Discover exact methods:
# python3 {skill_dir}/scripts/tikit_helper.py methods notebook

notebook_name = "example-dev-machine"
print("Ready to create/start/stop development machine:", notebook_name)

# resp = client.create_notebook(...)
# print(resp)
""",
    "data": _client_header()
    + """

# Tikit data operations cover datasets plus COS/HDFS/Hive movement.
# Discover exact methods:
# python3 {skill_dir}/scripts/tikit_helper.py methods dataset
# python3 {skill_dir}/scripts/tikit_helper.py methods cos
# python3 {skill_dir}/scripts/tikit_helper.py methods hdfs
# python3 {skill_dir}/scripts/tikit_helper.py methods hive

cos_path = "your-bucket/path/to/data/"
print("Ready to inspect or move data:", cos_path)

# resp = client.describe_cos_path(cos_path)  # Replace with exact installed method.
# print(resp)
""",
    "service": _client_header()
    + """

# Online model services are production-facing. Confirm resources and traffic
# before creating versions, stopping services, deleting services, or shifting weights.
# Discover exact methods:
# python3 {skill_dir}/scripts/tikit_helper.py methods service

service_name = "example-model-service"
model_path = "your-bucket/path/to/model/"
print("Ready to create or update service:", service_name, model_path)

# resp = client.create_model_service(...)
# print(resp)
""",
    "batch": _client_header()
    + """

# Batch tasks run offline processing or inference. Confirm one-off vs periodic
# execution and input/output data sources before submission.
# Discover exact methods:
# python3 {skill_dir}/scripts/tikit_helper.py methods batch

task_name = "example-batch-task"
input_path = "your-bucket/path/to/input/"
output_path = "your-bucket/path/to/output/"
print("Ready to create batch task:", task_name, input_path, output_path)

# resp = client.create_batch_task(...)
# print(resp)
""",
    "accelerate": _client_header()
    + """

# Model acceleration needs model format, tensor shape/config, optimization level,
# target GPU type, input model path, and output path.
# Discover exact methods:
# python3 {skill_dir}/scripts/tikit_helper.py methods accelerate
# python3 {skill_dir}/scripts/tikit_helper.py methods model

model_name = "example-model"
input_model_path = "your-bucket/path/to/model/"
output_path = "your-bucket/path/to/accelerated-model/"
print("Ready to create model acceleration task:", model_name, input_model_path, output_path)

# resp = client.create_model_accelerate_task(...)
# print(resp)
""",
}


def cmd_check(_: argparse.Namespace) -> int:
    print(f"python: {sys.version.split()[0]} ({platform.platform()})")
    print(f"skill_dir: {SKILL_DIR}")

    spec = importlib.util.find_spec("tikit")
    if not spec:
        print("tikit: not installed")
        print("install_hint: pip3 install -U tikit")
        return 1

    print(f"tikit: found at {spec.origin}")
    try:
        import tikit  # type: ignore

        version = getattr(tikit, "__version__", "unknown")
        print(f"tikit_version: {version}")
    except Exception as exc:  # pragma: no cover - environment dependent.
        print(f"tikit_import_error: {type(exc).__name__}: {exc}")
        return 2

    for name in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_REGION"):
        value = os.environ.get(name)
        state = "set" if value else "unset"
        print(f"env:{name}: {state}")
    return 0


def cmd_methods(args: argparse.Namespace) -> int:
    spec = importlib.util.find_spec("tikit")
    if not spec:
        print("tikit is not installed; cannot inspect Client methods.", file=sys.stderr)
        return 1

    from tikit.client import Client  # type: ignore

    pattern = (args.pattern or "").lower()
    names = []
    for name, value in inspect.getmembers(Client):
        if name.startswith("_"):
            continue
        if pattern and pattern not in name.lower():
            continue
        if callable(value):
            try:
                sig = str(inspect.signature(value))
            except Exception:
                sig = "(...)"
            names.append(f"{name}{sig}")

    if not names:
        print("No matching public Client methods found.")
        return 1
    print("\n".join(sorted(names)))
    return 0


def _normalize(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "to_json_string"):
        try:
            return json.loads(obj.to_json_string())
        except Exception:
            return str(obj)
    if isinstance(obj, list):
        return [_normalize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: _normalize(value) for key, value in obj.items()}
    if hasattr(obj, "__dict__"):
        return {
            key.lstrip("_"): _normalize(value)
            for key, value in obj.__dict__.items()
            if not key.startswith("__")
        }
    return str(obj)


def _items(data: Any) -> list[Any]:
    if not isinstance(data, dict):
        return []
    for value in data.values():
        if isinstance(value, list):
            return value
    return []


def _total(data: Any, items: list[Any]) -> int:
    if isinstance(data, dict):
        for key in ("TotalCount", "Total", "Count"):
            value = data.get(key)
            if isinstance(value, int):
                return value
    return len(items)


def _resource_units(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "?"
    if value % 100 == 0:
        return f"{value / 100:g}"
    return str(value)


def _gpu_detail_map(resource: dict[str, Any]) -> dict[str, float]:
    details = resource.get("GpuDetailSet") or []
    result: dict[str, float] = {}
    for item in details:
        if not isinstance(item, dict):
            continue
        name = item.get("Name")
        value = item.get("Value")
        if name and isinstance(value, (int, float)):
            result[str(name)] = value / 100 if value % 100 == 0 else float(value)
    return result


def _gpu_detail_text(
    total_res: dict[str, Any], used_res: dict[str, Any], avail_res: dict[str, Any]
) -> str:
    total = _gpu_detail_map(total_res)
    used = _gpu_detail_map(used_res)
    avail = _gpu_detail_map(avail_res)
    names = sorted(set(total) | set(used) | set(avail))
    if not names:
        return ""
    parts = []
    for name in names:
        parts.append(
            f"{name} {used.get(name, 0):g}/{total.get(name, 0):g} "
            f"avail {avail.get(name, 0):g}"
        )
    return "; ".join(parts)


def _env(name: str) -> str | None:
    value = os.environ.get(name)
    return value if value else None


def _scrub(text: str) -> str:
    for name in ("TENCENTCLOUD_SECRET_ID", "TENCENTCLOUD_SECRET_KEY", "TENCENTCLOUD_SESSION_TOKEN"):
        value = os.environ.get(name)
        if value:
            text = text.replace(value, f"<{name}>")
    return text


def _brief_name(item: Any, *keys: str) -> str:
    if not isinstance(item, dict):
        return str(item)
    for key in keys:
        value = item.get(key)
        if value:
            return str(value)
    return "unknown"


def cmd_resources(args: argparse.Namespace) -> int:
    spec = importlib.util.find_spec("tikit")
    if not spec:
        print("tikit: not installed")
        return 1

    secret_id = _env("TENCENTCLOUD_SECRET_ID")
    secret_key = _env("TENCENTCLOUD_SECRET_KEY")
    region = _env("TENCENTCLOUD_REGION") or _env("REGION")
    token = _env("TENCENTCLOUD_SESSION_TOKEN")
    if not (secret_id and secret_key and region):
        print("missing env: TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY/TENCENTCLOUD_REGION")
        return 2

    from tikit.client import Client  # type: ignore

    warnings.filterwarnings("ignore", category=UserWarning)
    client = Client(secret_id, secret_key, region, token=token)
    print(f"region: {region}")

    def call(label: str, fn: Callable[[], Any]) -> tuple[int, list[Any]]:
        try:
            data = _normalize(fn())
        except Exception as exc:
            print(f"{label}: error {type(exc).__name__}: {_scrub(str(exc))}")
            return 0, []
        items = _items(data)
        return _total(data, items), items

    total, groups = call("resource_groups", lambda: client.describe_resource_groups(offset=0, limit=args.limit))
    print(f"resource_groups: {total}")
    for item in groups[: args.limit]:
        if not isinstance(item, dict):
            continue
        total_res = item.get("TotalResource") or {}
        used_res = item.get("UsedResource") or {}
        avail_res = item.get("AvailableResource") or {}
        print(
            "- "
            f"{_brief_name(item, 'ResourceGroupName', 'Name')} "
            f"{_brief_name(item, 'ResourceGroupId', 'Id')} "
            f"gpu {_resource_units(used_res.get('Gpu'))}/{_resource_units(total_res.get('Gpu'))} "
            f"avail {_resource_units(avail_res.get('Gpu'))} "
            f"inst {item.get('FreeInstance', '?')}/{item.get('TotalInstance', '?')} "
            f"sched {'yes' if item.get('HasSchedulableNode') else 'no'}"
        )
        gpu_detail = _gpu_detail_text(total_res, used_res, avail_res)
        if gpu_detail:
            print(f"  gpu_by_type: {gpu_detail}")

    total, tasks = call("training_tasks", lambda: client.describe_training_tasks(offset=0, limit=args.limit))
    running = sum(1 for item in tasks if isinstance(item, dict) and item.get("Status") == "RUNNING")
    print(f"training_tasks: {total} running={running}")
    for item in tasks[: args.limit]:
        if isinstance(item, dict):
            print(f"- {item.get('Status', '?')} {_brief_name(item, 'Name', 'TaskName')} {_brief_name(item, 'Id', 'TaskId')}")

    total, notebooks = call("notebooks", lambda: client.describe_notebooks(offset=0, limit=args.limit))
    running = sum(1 for item in notebooks if isinstance(item, dict) and str(item.get("Status", "")).lower() == "running")
    print(f"notebooks: {total} running={running}")
    for item in notebooks[: args.limit]:
        if isinstance(item, dict):
            print(f"- {item.get('Status', '?')} {_brief_name(item, 'Name', 'NotebookName')} {_brief_name(item, 'Id', 'NotebookId')}")

    dataset_total, _ = call("datasets", lambda: client.describe_datasets(offset=0, limit=1))
    service_total, _ = call("services", lambda: client.describe_model_services(offset=0, limit=1))
    batch_total, _ = call("batch_tasks", lambda: client.describe_batch_tasks(offset=0, limit=1))
    acc_total, _ = call("model_accelerate_tasks", lambda: client.describe_model_accelerate_tasks(offset=0, limit=1))
    print(f"other: datasets={dataset_total} services={service_total} batch={batch_total} accel={acc_total}")
    return 0


def cmd_render(args: argparse.Namespace) -> int:
    template = TEMPLATES[args.kind].format(skill_dir=SKILL_DIR)
    print(textwrap.dedent(template).strip())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Check local Python/Tikit environment.")
    check.set_defaults(func=cmd_check)

    methods = sub.add_parser("methods", help="List public tikit.client.Client methods.")
    methods.add_argument("pattern", nargs="?", help="Optional case-insensitive name filter.")
    methods.set_defaults(func=cmd_methods)

    resources = sub.add_parser("resources", help="Print a concise read-only TI-ONE resource summary.")
    resources.add_argument("--limit", type=int, default=5, help="Maximum items to print per resource type.")
    resources.set_defaults(func=cmd_resources)

    render = sub.add_parser("render", help="Render a starter Tikit Python script.")
    render.add_argument("kind", choices=sorted(TEMPLATES))
    render.set_defaults(func=cmd_render)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func: Callable[[argparse.Namespace], int] = args.func
    return func(args)


if __name__ == "__main__":
    raise SystemExit(main())
