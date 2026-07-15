#!/usr/bin/env python3
"""Print concise TI-ONE training task status, pod names, and recent logs."""

from __future__ import annotations

import argparse
import json
import os
import re
import warnings
from typing import Any


DEFAULT_FILTERS = (
    "failed",
    "error",
    "exception",
    "traceback",
    "no such",
    "not found",
    "no module",
    "command not found",
    "exit status",
    "start command",
)


def require_tikit() -> None:
    try:
        import tikit  # noqa: F401
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "tikit is not installed. Retry with: "
            "uv run --with tikit python <this-script> <args>"
        ) from exc


def client() -> Any:
    require_tikit()
    from tikit.client import Client

    secret_id = os.environ.get("TENCENTCLOUD_SECRET_ID")
    secret_key = os.environ.get("TENCENTCLOUD_SECRET_KEY")
    region = os.environ.get("TENCENTCLOUD_REGION") or os.environ.get("REGION")
    token = os.environ.get("TENCENTCLOUD_SESSION_TOKEN")
    if not (secret_id and secret_key and region):
        raise SystemExit(
            "missing env: TENCENTCLOUD_SECRET_ID/TENCENTCLOUD_SECRET_KEY/"
            "TENCENTCLOUD_REGION"
        )
    warnings.filterwarnings("ignore", category=UserWarning)
    return Client(secret_id, secret_key, region, token=token)


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


def scrub(text: str) -> str:
    secret_names = (
        "TENCENTCLOUD_SECRET_ID",
        "TENCENTCLOUD_SECRET_KEY",
        "TENCENTCLOUD_SESSION_TOKEN",
    )
    for name in secret_names:
        value = os.environ.get(name)
        if value:
            text = text.replace(value, f"<{name}>")
    text = re.sub(
        r"(PASSWORD|TOKEN|SECRET|KEY|CREDENTIALS_URL)=([^|\s]+)",
        r"\1=<redacted>",
        text,
        flags=re.IGNORECASE,
    )
    return text


def extract_pods(pods_obj: Any) -> list[str]:
    text = str(pods_obj)
    return sorted(set(re.findall(r"(train-[a-zA-Z0-9\-]+-master-\d+)", text)))


def task_detail(data: Any) -> dict[str, Any]:
    normalized = normalize(data)
    if isinstance(normalized, dict):
        detail = normalized.get("TrainingTaskDetail")
        if isinstance(detail, dict):
            return detail
    return {}


def log_lines(logs_obj: Any) -> list[str]:
    text = scrub(str(logs_obj))
    return [line for line in text.splitlines() if line.strip()]


def print_filtered(lines: list[str], filters: tuple[str, ...], raw: bool) -> None:
    if raw:
        for line in lines:
            print(line)
        return
    for line in lines:
        lower = line.lower()
        if any(pattern in lower for pattern in filters):
            print(line[:1600])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task_ids", nargs="+")
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--raw", action="store_true", help="Print all returned log lines.")
    parser.add_argument(
        "--filter",
        action="append",
        dest="filters",
        help="Case-insensitive substring filter. Can be repeated.",
    )
    parser.add_argument("--order", default="DESC", choices=("ASC", "DESC"))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    api = client()
    filters = tuple(args.filters) if args.filters else DEFAULT_FILTERS
    for task_id in args.task_ids:
        print(f"\nTASK {task_id}")
        try:
            detail = task_detail(api.describe_training_task(task_id))
            if detail:
                print(f"name: {detail.get('Name', '')}")
                print(f"status: {detail.get('Status', '')}")
                if detail.get("Message"):
                    print(f"message: {detail['Message']}")
                if detail.get("RuntimeInSeconds") is not None:
                    print(f"runtime_s: {detail['RuntimeInSeconds']}")
        except Exception as exc:
            print(f"describe_task_error: {type(exc).__name__}: {scrub(str(exc))}")
        try:
            pods = extract_pods(api.describe_training_task_pods(task_id))
            print("pods: " + (", ".join(pods) if pods else "none"))
            for pod in pods:
                print(f"\nPOD {pod}")
                logs = api.describe_train_logs(
                    pod_name=pod,
                    limit=args.limit,
                    order=args.order,
                )
                print_filtered(log_lines(logs), filters, args.raw)
        except Exception as exc:
            print(f"logs_error: {type(exc).__name__}: {scrub(str(exc))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
