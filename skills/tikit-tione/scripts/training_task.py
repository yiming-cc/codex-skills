#!/usr/bin/env python3
"""Submit and inspect TI-ONE training tasks with small, reusable commands."""

from __future__ import annotations

import argparse
import json
import os
import time
import warnings
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
DEFAULT_IMAGE_URL = os.environ.get("TIONE_DEFAULT_IMAGE_URL")
DEFAULT_IMAGE_TYPE = os.environ.get("TIONE_DEFAULT_IMAGE_TYPE", "CCR")
DEFAULT_REGISTRY_REGION = os.environ.get("TIONE_DEFAULT_REGISTRY_REGION")
DEFAULT_REGISTRY_ID = os.environ.get("TIONE_DEFAULT_REGISTRY_ID")
DEFAULT_INPUT_COS = env_list("TIONE_DEFAULT_INPUT_COS")
DEFAULT_INPUT_COSFS = env_list("TIONE_DEFAULT_INPUT_COSFS")
DEFAULT_INPUT_DATASET = env_list("TIONE_DEFAULT_INPUT_DATASET")
DEFAULT_INPUT_CFS = env_list("TIONE_DEFAULT_INPUT_CFS", "TIONE_INPUT_CFS_ROOT")

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
        raise SystemExit(
            "tikit is not installed. Retry with: "
            "uv run --with tikit python <this-script> <args>"
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


def data_configs(args: argparse.Namespace) -> list[Any] | None:
    require_tikit()
    from tikit.models import TrainingDataConfig

    configs: list[TrainingDataConfig] = []
    for value in args.input_cos or []:
        source, target = parse_pair(value, "--input-cos")
        configs.append(TrainingDataConfig.new_mount_cos(source, target))
    for value in args.input_cosfs or []:
        source, target = parse_pair(value, "--input-cosfs")
        configs.append(TrainingDataConfig.new_mount_cosfs(source, target))
    for value in args.input_dataset or []:
        dataset_id, target = parse_pair(value, "--input-dataset")
        configs.append(TrainingDataConfig.new_dataset_mount(dataset_id, target))
    for value in args.input_cfs or []:
        cfs_id, source, target = parse_cfs(value)
        configs.append(TrainingDataConfig.new_mount_cfs(cfs_id, source, target))
    return configs or None


def effective_enable_rdma(args: argparse.Namespace) -> bool:
    if args.enable_rdma is not None:
        return args.enable_rdma
    return args.workers > 1


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


def print_plan(args: argparse.Namespace, framework_kind: str) -> None:
    print(f"name: {args.name}")
    print(f"framework: {framework_kind}")
    print(f"resource_group: {args.resource_group_id}")
    print(f"network: {args.vpc_id}/{args.subnet_id}")
    print(f"resource: {args.gpu_type} gpu={args.gpu or RESOURCE_PROFILES.get(args.gpu_type, {}).get('gpu', 8)} workers={args.workers}")
    print(f"enable_rdma: {effective_enable_rdma(args)}")
    if args.code_package_path:
        print(f"code: {args.code_package_path}")
    if args.cos_output:
        print(f"output: {args.cos_output}")
    mounts = []
    for attr, label in (
        ("input_cos", "cos"),
        ("input_cosfs", "cosfs"),
        ("input_dataset", "dataset"),
        ("input_cfs", "cfs"),
    ):
        for value in getattr(args, attr, None) or []:
            mounts.append(f"{label}:{value}")
    if mounts:
        print("mounts:")
        for mount in mounts:
            print(f"- {mount}")
    print(f"cmd: {args.cmd}")


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
    print_plan(args, framework_kind)
    if not args.yes:
        print("dry_run: add --yes to submit")
        return 0
    validate_live_submit(args)
    resp = client().create_training_task(
        name=args.name,
        framework=framework,
        cos_output=args.cos_output,
        worker_resource=resource_config(args),
        code_package_path=args.code_package_path,
        input_data_config=data_configs(args),
        worker_start_cmd=args.cmd,
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
    print(f"submitted: {data.get('Id', 'unknown')}")
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
        print("dry_run: add --yes to submit")
        return 0
    return submit(args, system_framework(args), "system:PYTORCH/" + DEFAULT_FRAMEWORK)


def cmd_submit_system(args: argparse.Namespace) -> int:
    if not args.yes:
        print_plan(args, f"system:{args.framework_name}/{args.framework_env}")
        print("dry_run: add --yes to submit")
        return 0
    return submit(args, system_framework(args), f"system:{args.framework_name}/{args.framework_env}")


def cmd_submit_custom(args: argparse.Namespace) -> int:
    if not args.image_url:
        raise SystemExit("missing --image-url or TIONE_DEFAULT_IMAGE_URL")
    if not args.yes:
        print_plan(args, f"custom:{args.image_type}/{args.image_url}")
        print("dry_run: add --yes to submit")
        return 0
    return submit(args, custom_framework(args), f"custom:{args.image_type}/{args.image_url}")


def cmd_status(args: argparse.Namespace) -> int:
    data = normalize(client().describe_training_task(args.task_id)).get("TrainingTaskDetail", {})
    print(f"id: {data.get('Id', args.task_id)}")
    print(f"name: {data.get('Name', '')}")
    print(f"status: {data.get('Status', '')}")
    if data.get("Message"):
        print(f"message: {data['Message']}")
    if data.get("RuntimeInSeconds") is not None:
        print(f"runtime_s: {data['RuntimeInSeconds']}")
    return 0


def add_common_submit_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--name", required=True)
    parser.add_argument("--cmd", required=True)
    parser.add_argument("--gpu-type", default=DEFAULT_GPU_TYPE, choices=sorted(RESOURCE_PROFILES))
    parser.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
    parser.add_argument("--gpu", type=float)
    parser.add_argument("--cpu", type=float)
    parser.add_argument("--memory", type=float, help="GB")
    parser.add_argument("--resource-group-id", default=DEFAULT_RESOURCE_GROUP_ID)
    parser.add_argument("--vpc-id", default=DEFAULT_VPC_ID)
    parser.add_argument("--subnet-id", default=DEFAULT_SUBNET_ID)
    parser.add_argument("--code-package-path")
    parser.add_argument("--cos-output")
    parser.add_argument("--input-cos", action="append", default=DEFAULT_INPUT_COS, help="COS_PATH:TARGET_PATH")
    parser.add_argument("--input-cosfs", action="append", default=DEFAULT_INPUT_COSFS, help="COS_PATH:TARGET_PATH")
    parser.add_argument("--input-dataset", action="append", default=DEFAULT_INPUT_DATASET, help="DATASET_ID:TARGET_PATH")
    parser.add_argument("--input-cfs", action="append", default=DEFAULT_INPUT_CFS, help="CFS_ID:SOURCE_PATH:TARGET_PATH")
    parser.add_argument("--remark")
    parser.add_argument("--log-enable", action="store_true")
    parser.add_argument("--log-logset-id")
    parser.add_argument("--log-topic-id")
    parser.add_argument("--enable-rdma", action=argparse.BooleanOptionalAction, default=None)
    parser.add_argument("--restart-limit", type=int, default=0)
    parser.add_argument("--yes", action="store_true", help="Submit the task. Without this flag, only print the plan.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    smoke = sub.add_parser("submit-smoke", help="Submit a short built-in no-op GPU training task.")
    smoke.add_argument("--name")
    smoke.add_argument("--gpu-type", default=DEFAULT_GPU_TYPE, choices=sorted(RESOURCE_PROFILES))
    smoke.add_argument("--workers", type=int, default=DEFAULT_WORKERS)
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
    smoke.add_argument("--input-cos", action="append", default=DEFAULT_INPUT_COS)
    smoke.add_argument("--input-cosfs", action="append", default=DEFAULT_INPUT_COSFS)
    smoke.add_argument("--input-dataset", action="append", default=DEFAULT_INPUT_DATASET)
    smoke.add_argument("--input-cfs", action="append", default=DEFAULT_INPUT_CFS)
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

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
