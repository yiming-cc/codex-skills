#!/usr/bin/env python3
"""Submit and inspect TI-ONE training tasks with small, reusable commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any


def load_local_env_defaults() -> None:
    """Load non-secret defaults from references/local_env.sh if present."""
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(skill_dir, "references", "local_env.sh")
    if not os.path.exists(env_path):
        return
    secret_words = ("SECRET", "TOKEN", "PASSWORD", "COOKIE", "CREDENTIAL")
    with open(env_path, encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip("'\"")
            if not key or any(word in key.upper() for word in secret_words):
                continue
            os.environ.setdefault(key, value)


def env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return float(value)


def env_list(*names: str) -> list[str]:
    for name in names:
        value = os.environ.get(name)
        if value:
            return [item.strip() for item in value.split(",") if item.strip()]
    return []


load_local_env_defaults()

DEFAULT_RESOURCE_GROUP_ID = os.environ.get("TIONE_RESOURCE_GROUP_ID")
DEFAULT_VPC_ID = os.environ.get("TIONE_VPC_ID")
DEFAULT_SUBNET_ID = os.environ.get("TIONE_SUBNET_ID")
DEFAULT_FRAMEWORK_NAME = os.environ.get("TIONE_DEFAULT_FRAMEWORK_NAME", "PYTORCH")
DEFAULT_FRAMEWORK = os.environ.get(
    "TIONE_DEFAULT_FRAMEWORK_ENV", "torch1.9-py3.8-cuda11.1-gpu"
)
DEFAULT_MODE = os.environ.get("TIONE_DEFAULT_MODE", "DDP")
DEFAULT_WORKERS = int(os.environ.get("TIONE_DEFAULT_WORKERS", "1"))
DEFAULT_GPU_TYPE = os.environ.get("TIONE_DEFAULT_GPU_TYPE", "N50p-72G")
DEFAULT_RUN_USER = os.environ.get("TIONE_DEFAULT_RUN_USER", "image-default")
DEFAULT_IMAGE_URL = os.environ.get("TIONE_DEFAULT_IMAGE_URL")
DEFAULT_IMAGE_TYPE = os.environ.get("TIONE_DEFAULT_IMAGE_TYPE", "CCR")
DEFAULT_REGISTRY_REGION = os.environ.get("TIONE_DEFAULT_REGISTRY_REGION")
DEFAULT_REGISTRY_ID = os.environ.get("TIONE_DEFAULT_REGISTRY_ID")
DEFAULT_INPUT_COS = env_list("TIONE_DEFAULT_INPUT_COS")
DEFAULT_INPUT_COSFS = env_list("TIONE_DEFAULT_INPUT_COSFS")
DEFAULT_INPUT_DATASET = env_list("TIONE_DEFAULT_INPUT_DATASET")
DEFAULT_INPUT_CFS = env_list("TIONE_DEFAULT_INPUT_CFS")

TRANSIENT_STATUSES = {"SUBMITTING", "CREATING", "PENDING", "RUNNING"}
SUCCESS_STATUSES = {"SUCCEED"}
FAILURE_STATUSES = {"FAILED", "STOPPED"}
KNOWN_STATUSES = TRANSIENT_STATUSES | SUCCESS_STATUSES | FAILURE_STATUSES

RESOURCE_PROFILES = {
    "N50p-72G": {
        "cpu": env_float("TIONE_N50P_8GPU_CPU", 252),
        "memory": env_float("TIONE_N50P_8GPU_MEMORY", 720),
        "gpu": env_float("TIONE_N50P_8GPU_GPU", 8),
    },
    "GPU-HCCPNV6": {
        "cpu": env_float("TIONE_HCCPNV6_8GPU_CPU", 120),
        "memory": env_float("TIONE_HCCPNV6_8GPU_MEMORY", 1200),
        "gpu": env_float("TIONE_HCCPNV6_8GPU_GPU", 8),
    },
}


def require_tikit() -> None:
    try:
        import tikit  # noqa: F401
    except ModuleNotFoundError as exc:
        control_python = os.environ.get("TIONE_CONTROL_PYTHON", "/usr/bin/python3")
        raise SystemExit(
            "tikit is unavailable in this interpreter. Run this public control-plane tool with "
            f"the image-provided interpreter, for example: {control_python} <this-script> <args>. "
            "Do not install Tikit into a project environment."
        ) from exc


def normalize(obj: Any) -> Any:
    if hasattr(obj, "to_json_string"):
        return json.loads(obj.to_json_string())
    if isinstance(obj, list):
        return [normalize(item) for item in obj]
    if isinstance(obj, dict):
        return {key: normalize(value) for key, value in obj.items()}
    if hasattr(obj, "__dict__"):
        return {
            key.lstrip("_"): normalize(value)
            for key, value in obj.__dict__.items()
            if not key.startswith("__")
        }
    return obj


def client() -> Any:
    require_tikit()
    from tikit.client import Client

    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID")
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY")
    region = os.environ.get("TENCENTCLOUD_REGION") or os.environ.get("REGION")
    token = os.environ.get("TENCENTCLOUD_SESSION_TOKEN")
    if not (secret_id and secret_key and region):
        raise SystemExit("missing env: TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY/TENCENTCLOUD_REGION")
    warnings.filterwarnings("ignore", category=UserWarning)
    return Client(secret_id, secret_key, region, token=token)


def resource_config(args: argparse.Namespace) -> Any:
    require_tikit()
    from tikit.models import ResourceConfigInfo

    profile = RESOURCE_PROFILES.get(args.gpu_type, {})
    cpu = args.cpu if args.cpu is not None else profile.get("cpu")
    memory = args.memory if args.memory is not None else profile.get("memory")
    gpu = args.gpu if args.gpu is not None else profile.get("gpu", 8)
    if cpu is None or memory is None:
        raise SystemExit(f"missing --cpu/--memory for gpu type {args.gpu_type}")
    return ResourceConfigInfo.new_prepaid(
        cpu=cpu,
        memory=memory,
        gpu=gpu,
        gpu_type=args.gpu_type,
        instance_num=args.workers,
    )


def parse_pair(value: str, label: str) -> tuple[str, str]:
    parts = value.split(":", 1)
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise argparse.ArgumentTypeError(f"{label} must be SOURCE:TARGET")
    return parts[0], parts[1]


def parse_cfs(value: str) -> tuple[str, str, str]:
    parts = value.split(":", 2)
    if len(parts) != 3 or not all(parts):
        raise argparse.ArgumentTypeError("CFS mount must be CFS_ID:SOURCE_PATH:TARGET_PATH")
    return parts[0], parts[1], parts[2]


def effective_data_inputs(args: argparse.Namespace) -> dict[str, list[str]]:
    defaults = {
        "input_cos": DEFAULT_INPUT_COS,
        "input_cosfs": DEFAULT_INPUT_COSFS,
        "input_dataset": DEFAULT_INPUT_DATASET,
        "input_cfs": DEFAULT_INPUT_CFS,
    }
    effective: dict[str, list[str]] = {}
    targets: dict[str, tuple[str, str]] = {}
    for attr, default_values in defaults.items():
        explicit = getattr(args, attr, None)
        values = list(explicit if explicit is not None else ([] if args.no_default_inputs else default_values))
        deduplicated = []
        seen_values = set()
        for value in values:
            if value in seen_values:
                continue
            seen_values.add(value)
            if attr == "input_cfs":
                cfs_id, source, target = parse_cfs(value)
                source_identity = f"{cfs_id}:{source}"
            else:
                source_identity, target = parse_pair(value, "--" + attr.replace("_", "-"))
            previous = targets.get(target)
            identity = (attr, source_identity)
            if previous is not None and previous != identity:
                raise SystemExit(
                    f"conflicting data mounts for target {target}: "
                    f"{previous[0]}:{previous[1]} and {attr}:{source_identity}"
                )
            targets[target] = identity
            deduplicated.append(value)
        effective[attr] = deduplicated
    return effective


def data_configs(args: argparse.Namespace) -> list[Any] | None:
    require_tikit()
    from tikit.models import TrainingDataConfig

    inputs = effective_data_inputs(args)
    configs: list[TrainingDataConfig] = []
    for value in inputs["input_cos"]:
        source, target = parse_pair(value, "--input-cos")
        configs.append(TrainingDataConfig.new_mount_cos(source, target))
    for value in inputs["input_cosfs"]:
        source, target = parse_pair(value, "--input-cosfs")
        configs.append(TrainingDataConfig.new_mount_cosfs(source, target))
    for value in inputs["input_dataset"]:
        dataset_id, target = parse_pair(value, "--input-dataset")
        configs.append(TrainingDataConfig.new_dataset_mount(dataset_id, target))
    for value in inputs["input_cfs"]:
        cfs_id, source, target = parse_cfs(value)
        configs.append(TrainingDataConfig.new_mount_cfs(cfs_id, source, target))
    return configs or None


def effective_enable_rdma(args: argparse.Namespace) -> bool:
    if args.enable_rdma is not None:
        return args.enable_rdma
    return args.workers > 1


def effective_start_cmd(args: argparse.Namespace) -> str:
    if args.run_user == "image-default":
        return args.cmd
    if args.run_user == "root":
        return (
            'if [ "$(id -u)" -ne 0 ]; then '
            'echo "TI-ONE task must run as root" >&2; exit 1; fi; '
            + args.cmd
        )
    raise ValueError(f"unsupported run user: {args.run_user}")


def system_framework(args: argparse.Namespace) -> Any:
    require_tikit()
    from tikit.models import FrameworkInfo

    return FrameworkInfo.new_system_framework(
        framework_name=args.framework_name,
        framework_environment=args.framework_env,
        training_mode=args.mode,
    )


def custom_framework(args: argparse.Namespace) -> Any:
    require_tikit()
    from tikit.models import FrameworkInfo

    username = os.environ.get(args.image_user_env) if args.image_user_env else None
    password = os.environ.get(args.image_password_env) if args.image_password_env else None
    return FrameworkInfo.new_custom(
        training_mode=args.mode,
        image_type=args.image_type,
        image_url=args.image_url,
        registry_region=args.registry_region,
        registry_id=args.registry_id,
        user_name=username,
        passwd=password,
    )


def build_plan(args: argparse.Namespace, framework_kind: str) -> dict[str, Any]:
    inputs = effective_data_inputs(args)
    mounts = []
    for attr, label in (
        ("input_cos", "cos"),
        ("input_cosfs", "cosfs"),
        ("input_dataset", "dataset"),
        ("input_cfs", "cfs"),
    ):
        mounts.extend(f"{label}:{value}" for value in inputs[attr])
    return {
        "name": args.name,
        "framework": framework_kind,
        "resource_group_id": args.resource_group_id,
        "vpc_id": args.vpc_id,
        "subnet_id": args.subnet_id,
        "resource": {
            "gpu_type": args.gpu_type,
            "gpu": args.gpu or RESOURCE_PROFILES.get(args.gpu_type, {}).get("gpu", 8),
            "cpu": args.cpu or RESOURCE_PROFILES.get(args.gpu_type, {}).get("cpu"),
            "memory": args.memory or RESOURCE_PROFILES.get(args.gpu_type, {}).get("memory"),
            "workers": args.workers,
        },
        "run_user": args.run_user,
        "enable_rdma": effective_enable_rdma(args),
        "code_package_path": args.code_package_path,
        "cos_output": args.cos_output,
        "mounts": mounts,
        "cmd": effective_start_cmd(args),
    }


def print_plan(args: argparse.Namespace, framework_kind: str) -> dict[str, Any]:
    plan = build_plan(args, framework_kind)
    if args.plan_format == "json":
        print(json.dumps(plan, ensure_ascii=False, sort_keys=True))
        return plan
    print(f"name: {plan['name']}")
    print(f"framework: {plan['framework']}")
    print(f"resource_group: {plan['resource_group_id']}")
    print(f"network: {plan['vpc_id']}/{plan['subnet_id']}")
    resource = plan["resource"]
    print(f"resource: {resource['gpu_type']} gpu={resource['gpu']} workers={resource['workers']}")
    print(f"run_user: {plan['run_user']}")
    print(f"enable_rdma: {plan['enable_rdma']}")
    if plan["code_package_path"]:
        print(f"code: {plan['code_package_path']}")
    if plan["cos_output"]:
        print(f"output: {plan['cos_output']}")
    if plan["mounts"]:
        print("mounts:")
        for mount in plan["mounts"]:
            print(f"- {mount}")
    if args.receipt:
        print(f"receipt: {args.receipt}")
    print(f"cmd: {plan['cmd']}")
    return plan


def print_dry_run(args: argparse.Namespace) -> None:
    stream = sys.stderr if args.plan_format == "json" else sys.stdout
    print("dry_run: add --yes to submit", file=stream)


def plan_hash(plan: dict[str, Any]) -> str:
    payload = json.dumps(plan, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def existing_receipt(args: argparse.Namespace, plan: dict[str, Any]) -> str | None:
    if not args.receipt:
        return None
    path = Path(args.receipt)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    expected_hash = plan_hash(plan)
    if data.get("plan_hash") != expected_hash:
        raise SystemExit(f"receipt plan mismatch: {path}")
    task_id = data.get("task_id")
    if not task_id:
        raise SystemExit(f"receipt has no task_id: {path}")
    return str(task_id)


def write_receipt(args: argparse.Namespace, plan: dict[str, Any], task_id: str) -> None:
    if not args.receipt:
        return
    path = Path(args.receipt)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "submitted_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "task_id": task_id,
        "name": args.name,
        "plan_hash": plan_hash(plan),
        "plan": plan,
    }
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")
        temp_path = f.name
    os.replace(temp_path, path)


def validate_live_submit(args: argparse.Namespace) -> None:
    if not args.yes:
        return
    missing = [
        name
        for name, value in (
            ("resource_group_id", args.resource_group_id),
            ("vpc_id", args.vpc_id),
            ("subnet_id", args.subnet_id),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "missing required live-submit fields: "
            + ", ".join(missing)
            + ". Set TIONE_RESOURCE_GROUP_ID/TIONE_VPC_ID/TIONE_SUBNET_ID "
            "or pass the corresponding CLI flags."
        )


def submit(args: argparse.Namespace, framework: Any, framework_kind: str) -> int:
    plan = print_plan(args, framework_kind)
    if not args.yes:
        print_dry_run(args)
        return 0
    validate_live_submit(args)
    task_id = existing_receipt(args, plan)
    if task_id:
        print(f"existing receipt: {task_id}")
        return 0
    resp = client().create_training_task(
        name=args.name,
        framework=framework,
        cos_output=args.cos_output,
        worker_resource=resource_config(args),
        code_package_path=args.code_package_path,
        input_data_config=data_configs(args),
        worker_start_cmd=effective_start_cmd(args),
        resource_group_id=args.resource_group_id,
        remark=args.remark,
        log_enable=args.log_enable,
        log_logset_id=args.log_logset_id,
        log_topic_id=args.log_topic_id,
        vpc_id=args.vpc_id,
        sub_net_id=args.subnet_id,
        enable_rdma=effective_enable_rdma(args),
        restart_limit=args.restart_limit,
    )
    data = normalize(resp)
    task_id = str(data.get("Id", "unknown"))
    if task_id == "unknown":
        raise SystemExit(f"training task response has no Id: {data}")
    write_receipt(args, plan, task_id)
    print(f"submitted: {task_id}")
    return 0


def cmd_submit_smoke(args: argparse.Namespace) -> int:
    if args.name is None:
        args.name = "codex-smoke-test-" + time.strftime("%Y%m%d-%H%M%S")
    args.framework_name = DEFAULT_FRAMEWORK_NAME
    args.framework_env = DEFAULT_FRAMEWORK
    args.mode = "DDP"
    args.cmd = "bash -lc 'echo codex-smoke-test; date; hostname; nvidia-smi -L || true; sleep 20; echo done'"
    args.code_package_path = None
    args.cos_output = None
    args.remark = args.remark or "codex smoke test: short no-op job"
    if not args.yes:
        print_plan(args, "system:PYTORCH/" + DEFAULT_FRAMEWORK)
        print_dry_run(args)
        return 0
    return submit(args, system_framework(args), "system:PYTORCH/" + DEFAULT_FRAMEWORK)


def cmd_submit_system(args: argparse.Namespace) -> int:
    if not args.yes:
        print_plan(args, f"system:{args.framework_name}/{args.framework_env}")
        print_dry_run(args)
        return 0
    return submit(args, system_framework(args), f"system:{args.framework_name}/{args.framework_env}")


def cmd_submit_custom(args: argparse.Namespace) -> int:
    if not args.image_url:
        raise SystemExit("missing --image-url or TIONE_DEFAULT_IMAGE_URL")
    if not args.yes:
        print_plan(args, f"custom:{args.image_type}/{args.image_url}")
        print_dry_run(args)
        return 0
    return submit(args, custom_framework(args), f"custom:{args.image_type}/{args.image_url}")


def training_task_detail(task_id: str) -> dict[str, Any]:
    return normalize(client().describe_training_task(task_id)).get("TrainingTaskDetail", {})


def cmd_status(args: argparse.Namespace) -> int:
    data = training_task_detail(args.task_id)
    print(f"id: {data.get('Id', args.task_id)}")
    print(f"name: {data.get('Name', '')}")
    print(f"status: {data.get('Status', '')}")
    if data.get("Message"):
        print(f"message: {data['Message']}")
    if data.get("RuntimeInSeconds") is not None:
        print(f"runtime_s: {data['RuntimeInSeconds']}")
    return 0


def cmd_wait(args: argparse.Namespace) -> int:
    last_status = None
    while True:
        data = training_task_detail(args.task_id)
        status = str(data.get("Status", ""))
        if status != last_status:
            print(f"id: {data.get('Id', args.task_id)} status: {status}", flush=True)
            last_status = status
        if status in FAILURE_STATUSES:
            print(f"failure: {data.get('FailureReason') or data.get('Message') or status}")
            return 1
        if status not in KNOWN_STATUSES:
            raise SystemExit(f"unknown TI-ONE training task status: {status!r}")
        if args.until == "started" and status in {"RUNNING", "SUCCEED"}:
            return 0
        if args.until == "terminal" and status == "SUCCEED":
            return 0
        time.sleep(args.poll_seconds)


def add_common_submit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", required=True)
    parser.add_argument("--cmd", required=True)
    parser.add_argument("--gpu-type", default=DEFAULT_GPU_TYPE, choices=sorted(RESOURCE_PROFILES))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--run-user", default=DEFAULT_RUN_USER, choices=("image-default", "root"))
    parser.add_argument("--gpu", type=float)
    parser.add_argument("--cpu", type=float)
    parser.add_argument("--memory", type=float, help="GB")
    parser.add_argument("--resource-group-id", default=DEFAULT_RESOURCE_GROUP_ID)
    parser.add_argument("--vpc-id", default=DEFAULT_VPC_ID)
    parser.add_argument("--subnet-id", default=DEFAULT_SUBNET_ID)
    parser.add_argument("--code-package-path")
    parser.add_argument("--cos-output")
    parser.add_argument("--input-cos", action="append", help="COS_PATH:TARGET_PATH")
    parser.add_argument("--input-cosfs", action="append", help="COS_PATH:TARGET_PATH")
    parser.add_argument("--input-dataset", action="append", help="DATASET_ID:TARGET_PATH")
    parser.add_argument("--input-cfs", action="append", help="CFS_ID:SOURCE_PATH:TARGET_PATH")
    parser.add_argument(
        "--no-default-inputs",
        action="store_true",
        help="Do not use image-level default data mounts; explicit --input-* values still apply.",
    )
    parser.add_argument("--remark")
    parser.add_argument("--log-enable", action="store_true")
    parser.add_argument("--log-logset-id")
    parser.add_argument("--log-topic-id")
    parser.add_argument("--enable-rdma", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--restart-limit", type=int, default=0)
    parser.add_argument("--plan-format", choices=("text", "json"), default="text")
    parser.add_argument("--receipt", help="Atomic JSON task receipt used to make submission idempotent.")
    parser.add_argument("--yes", action="store_true", help="Submit the task. Without this flag, only print the plan.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("submit-smoke", help="Submit a short built-in no-op GPU training task.")
    smoke.add_argument("--name")
    smoke.add_argument("--gpu-type", default=DEFAULT_GPU_TYPE, choices=sorted(RESOURCE_PROFILES))
    smoke.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    smoke.add_argument("--run-user", default=DEFAULT_RUN_USER, choices=("image-default", "root"))
    smoke.add_argument("--gpu", type=float)
    smoke.add_argument("--cpu", type=float)
    smoke.add_argument("--memory", type=float, help="GB")
    smoke.add_argument("--resource-group-id", default=DEFAULT_RESOURCE_GROUP_ID)
    smoke.add_argument("--vpc-id", default=DEFAULT_VPC_ID)
    smoke.add_argument("--subnet-id", default=DEFAULT_SUBNET_ID)
    smoke.add_argument("--remark")
    smoke.add_argument("--log-enable", action="store_true")
    smoke.add_argument("--log-logset-id")
    smoke.add_argument("--log-topic-id")
    smoke.add_argument("--enable-rdma", action=argparse.BooleanOptionalAction, default=None)
    smoke.add_argument("--restart-limit", type=int, default=0)
    smoke.add_argument("--input-cos", action="append")
    smoke.add_argument("--input-cosfs", action="append")
    smoke.add_argument("--input-dataset", action="append")
    smoke.add_argument("--input-cfs", action="append")
    smoke.add_argument("--no-default-inputs", action="store_true")
    smoke.add_argument("--plan-format", choices=("text", "json"), default="text")
    smoke.add_argument("--receipt")
    smoke.add_argument("--yes", action="store_true")
    smoke.set_defaults(func=cmd_submit_smoke)

    system = sub.add_parser("submit-system", help="Submit with a TI-ONE built-in framework image.")
    add_common_submit_args(system)
    system.add_argument("--framework-name", default=DEFAULT_FRAMEWORK_NAME)
    system.add_argument("--framework-env", default=DEFAULT_FRAMEWORK)
    system.add_argument("--mode", default=DEFAULT_MODE)
    system.set_defaults(func=cmd_submit_system)

    custom = sub.add_parser("submit-custom", help="Submit with a custom image.")
    add_common_submit_args(custom)
    custom.add_argument("--image-url", default=DEFAULT_IMAGE_URL)
    custom.add_argument("--image-type", default=DEFAULT_IMAGE_TYPE, choices=("CCR", "TCR", "CUSTOM"))
    custom.add_argument("--registry-region", default=DEFAULT_REGISTRY_REGION)
    custom.add_argument("--registry-id", default=DEFAULT_REGISTRY_ID)
    custom.add_argument("--image-user-env", help="Environment variable containing registry username.")
    custom.add_argument("--image-password-env", help="Environment variable containing registry password.")
    custom.add_argument("--mode", default=DEFAULT_MODE)
    custom.set_defaults(func=cmd_submit_custom)

    status = sub.add_parser("status", help="Print concise status for one training task.")
    status.add_argument("task_id")
    status.set_defaults(func=cmd_status)

    wait = sub.add_parser("wait", help="Wait for a training task to start or reach a terminal state.")
    wait.add_argument("task_id")
    wait.add_argument("--until", choices=("started", "terminal"), default="started")
    wait.add_argument("--poll-seconds", type=int, default=30)
    wait.set_defaults(func=cmd_wait)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
