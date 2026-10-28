#!/usr/bin/env python3
"""Install, run, inspect, and troubleshoot a user-owned Xray or sing-box proxy."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GITHUB_RELEASE_API = "https://api.github.com/repos/XTLS/Xray-core/releases/latest"
SUPPORTED_PROVIDERS = ("xray", "sing-box")
DEFAULT_HEALTH_URL = "https://example.com"
DEFAULT_SINGBOX_LISTEN_PORT = 1080


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    default_config: Path
    bin_env: tuple[str, ...]
    config_env: tuple[str, ...]
    run_prefix: tuple[str, ...]
    test_prefix: tuple[str, ...]


PROVIDER_SPECS = {
    "xray": ProviderSpec(
        name="xray",
        default_config=Path("~/.config/xray/config.json"),
        bin_env=("MANAGE_PROXY_XRAY_BIN", "XRAY_BIN"),
        config_env=("MANAGE_PROXY_XRAY_CONFIG", "XRAY_CONFIG"),
        run_prefix=("run", "-config"),
        test_prefix=("run", "-test", "-config"),
    ),
    "sing-box": ProviderSpec(
        name="sing-box",
        default_config=Path("~/.config/sing-box/config.json"),
        bin_env=("MANAGE_PROXY_SINGBOX_BIN", "SINGBOX_BIN"),
        config_env=("MANAGE_PROXY_SINGBOX_CONFIG", "SINGBOX_CONFIG"),
        run_prefix=("run", "-c"),
        test_prefix=("check", "-c"),
    ),
}


class ProxyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Endpoint:
    host: str
    port: int
    protocol: str
    tag: str

    @property
    def http_url(self) -> str:
        return f"http://{format_host(self.host)}:{self.port}"

    @property
    def socks_url(self) -> str:
        return f"socks5h://{format_host(self.host)}:{self.port}"


@dataclass(frozen=True)
class Runtime:
    provider: str
    binary: Path
    config: Path
    asset_dir: Path
    state_dir: Path
    pid_file: Path
    log_file: Path

    @property
    def spec(self) -> ProviderSpec:
        return PROVIDER_SPECS[self.provider]


def eprint(message: str) -> None:
    print(message, file=sys.stderr)


def expand_path(value: str | os.PathLike[str]) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(str(value)))).resolve(strict=False)


def format_host(host: str) -> str:
    return f"[{host}]" if ":" in host and not host.startswith("[") else host


def state_root(provider: str) -> Path:
    explicit = os.environ.get("MANAGE_PROXY_STATE_DIR")
    if explicit:
        return expand_path(explicit)
    xdg_state = os.environ.get("XDG_STATE_HOME")
    base = expand_path(xdg_state) if xdg_state else Path.home() / ".local/state"
    return base / "manage-proxy" / provider


def first_env(names: tuple[str, ...]) -> str | None:
    for name in names:
        value = os.environ.get(name)
        if value:
            return value
    return None


def find_binary(provider: str) -> Path:
    explicit = first_env(PROVIDER_SPECS[provider].bin_env)
    if explicit:
        return expand_path(explicit)

    discovered = shutil.which(provider)
    if discovered:
        return expand_path(discovered)

    return Path.home() / ".local/bin" / provider


def build_runtime(provider: str) -> Runtime:
    spec = PROVIDER_SPECS[provider]
    binary = find_binary(provider)
    config = expand_path(first_env(spec.config_env) or str(spec.default_config))
    explicit_asset = os.environ.get("MANAGE_PROXY_XRAY_ASSET_DIR") or os.environ.get(
        "XRAY_LOCATION_ASSET"
    )
    if explicit_asset:
        asset_dir = expand_path(explicit_asset)
    else:
        asset_dir = binary.resolve(strict=False).parent
    root = state_root(provider)
    return Runtime(
        provider=provider,
        binary=binary,
        config=config,
        asset_dir=asset_dir,
        state_dir=root,
        pid_file=root / f"{provider}.pid",
        log_file=root / f"{provider}.log",
    )


def require_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise ProxyError(
            f"unsupported provider: {provider!r}; supported: {', '.join(SUPPORTED_PROVIDERS)}"
        )


def require_singbox(provider: str, action: str) -> None:
    if provider != "sing-box":
        raise ProxyError(f"{action} is supported for the sing-box provider only")


def load_json_config(config: Path) -> dict[str, Any]:
    try:
        with config.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ProxyError(f"config not found: {config}") from exc
    except PermissionError as exc:
        raise ProxyError(f"config is not readable: {config}") from exc
    except json.JSONDecodeError as exc:
        raise ProxyError(f"cannot parse config as JSON: {config}: {exc}") from exc

    if not isinstance(data, dict):
        raise ProxyError(f"config root must be an object: {config}")
    return data


def normalize_client_host(listen: str) -> str:
    override = os.environ.get("MANAGE_PROXY_HOST")
    if override:
        return override
    if listen in {"", "0.0.0.0", "::", "[::]"}:
        return "127.0.0.1"
    if listen == "localhost":
        return "127.0.0.1"
    return listen.strip("[]")


def discover_endpoint(config: Path, provider: str) -> Endpoint:
    port_override = os.environ.get("MANAGE_PROXY_PORT")
    host_override = os.environ.get("MANAGE_PROXY_HOST")
    if port_override:
        try:
            port = int(port_override)
        except ValueError as exc:
            raise ProxyError("MANAGE_PROXY_PORT must be an integer") from exc
        return Endpoint(host_override or "127.0.0.1", port, "mixed", "override")

    data = load_json_config(config)
    candidates: list[tuple[int, Endpoint]] = []
    protocol_priority = {"mixed": 0, "http": 1, "socks": 2}
    for inbound in data.get("inbounds", []):
        if not isinstance(inbound, dict):
            continue
        if provider == "sing-box":
            protocol = str(inbound.get("type", ""))
            raw_port = inbound.get("listen_port")
        else:
            protocol = str(inbound.get("protocol", ""))
            raw_port = inbound.get("port")
        if protocol not in protocol_priority:
            continue
        try:
            port = int(raw_port)
        except (TypeError, ValueError):
            continue
        if not 1 <= port <= 65535:
            continue
        listen = str(inbound.get("listen", "0.0.0.0"))
        host = normalize_client_host(listen)
        tag = str(inbound.get("tag", ""))
        loopback_priority = 0 if host in {"127.0.0.1", "::1"} else 1
        rank = loopback_priority * 10 + protocol_priority[protocol]
        candidates.append((rank, Endpoint(host, port, protocol, tag)))

    if not candidates:
        raise ProxyError(
            "no mixed, http, or socks inbound found; set MANAGE_PROXY_HOST and "
            "MANAGE_PROXY_PORT to override discovery"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def process_environment(runtime: Runtime) -> dict[str, str]:
    env = os.environ.copy()
    if runtime.provider == "xray":
        env["XRAY_LOCATION_ASSET"] = str(runtime.asset_dir)
    return env


def binary_command(runtime: Runtime, prefix: tuple[str, ...], config: Path) -> list[str]:
    return [str(runtime.binary), *prefix, str(config)]


def xray_command(runtime: Runtime, *, test: bool = False) -> list[str]:
    prefix = runtime.spec.test_prefix if test else runtime.spec.run_prefix
    return binary_command(runtime, prefix, runtime.config)


def run_config_test(runtime: Runtime, config: Path | None = None) -> subprocess.CompletedProcess[str]:
    command = binary_command(runtime, runtime.spec.test_prefix, config or runtime.config)
    return subprocess.run(
        command,
        env=process_environment(runtime),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=20,
    )


def read_pid(pid_file: Path) -> int | None:
    try:
        value = pid_file.read_text(encoding="utf-8").strip()
        return int(value)
    except (FileNotFoundError, ValueError, OSError):
        return None


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def process_cmdline(pid: int) -> list[str]:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return []
    return [part.decode(errors="replace") for part in raw.split(b"\0") if part]


def managed_process_status(runtime: Runtime) -> tuple[str, int | None]:
    pid = read_pid(runtime.pid_file)
    if pid is None:
        return "stopped", None
    if not pid_alive(pid):
        return "stale", pid

    cmdline = process_cmdline(pid)
    if not cmdline:
        return "unknown", pid
    try:
        command_binary = expand_path(cmdline[0])
        expected_binary = runtime.binary.resolve(strict=False)
    except OSError:
        return "foreign", pid
    resolved_args = {str(expand_path(arg)) for arg in cmdline[1:] if arg.startswith("/")}
    if command_binary != expected_binary or str(runtime.config) not in resolved_args:
        return "foreign", pid
    return "running", pid


def remove_stale_pid(runtime: Runtime) -> None:
    status, _ = managed_process_status(runtime)
    if status == "stale":
        runtime.pid_file.unlink(missing_ok=True)


def port_open(endpoint: Endpoint, timeout_seconds: float = 0.5) -> bool:
    try:
        with socket.create_connection((endpoint.host, endpoint.port), timeout=timeout_seconds):
            return True
    except OSError:
        return False


def tail_log(path: Path, lines: int) -> list[str]:
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        return []
    return content[-lines:]


def ensure_prerequisites(runtime: Runtime) -> Endpoint:
    if not runtime.binary.is_file() or not os.access(runtime.binary, os.X_OK):
        raise ProxyError(
            f"{runtime.provider} binary is missing or not executable: {runtime.binary}; run install"
        )
    if not runtime.config.is_file():
        raise ProxyError(f"{runtime.provider} config not found: {runtime.config}")
    endpoint = discover_endpoint(runtime.config, runtime.provider)
    try:
        result = run_config_test(runtime)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProxyError(f"{runtime.provider} configuration check could not run: {exc}") from exc
    if result.returncode != 0:
        detail = result.stdout.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ProxyError(f"{runtime.provider} configuration check failed{suffix}")
    return endpoint


def command_start(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    endpoint = ensure_prerequisites(runtime)
    runtime.state_dir.mkdir(parents=True, exist_ok=True)
    remove_stale_pid(runtime)
    status, pid = managed_process_status(runtime)
    if status == "running":
        print(f"{runtime.provider} is already running (pid {pid}, {endpoint.host}:{endpoint.port})")
        return 0
    if status in {"foreign", "unknown"}:
        raise ProxyError(
            f"refusing to overwrite {runtime.pid_file}: pid {pid} is not a verified managed {runtime.provider} process"
        )

    try:
        with runtime.log_file.open("a", encoding="utf-8") as log_handle:
            process = subprocess.Popen(
                xray_command(runtime),
                env=process_environment(runtime),
                stdin=subprocess.DEVNULL,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                text=True,
            )
    except OSError as exc:
        raise ProxyError(f"failed to start {runtime.provider}: {exc}") from exc

    temporary_pid = runtime.pid_file.with_suffix(".pid.tmp")
    temporary_pid.write_text(f"{process.pid}\n", encoding="utf-8")
    os.replace(temporary_pid, runtime.pid_file)

    deadline = time.monotonic() + 6
    while time.monotonic() < deadline:
        if process.poll() is not None:
            runtime.pid_file.unlink(missing_ok=True)
            lines = tail_log(runtime.log_file, 12)
            if lines:
                eprint("\n".join(lines))
            raise ProxyError(f"{runtime.provider} exited during startup with code {process.returncode}")
        if port_open(endpoint):
            print(
                f"{runtime.provider} started (pid {process.pid}, endpoint {endpoint.host}:{endpoint.port}, "
                f"log {runtime.log_file})"
            )
            return 0
        time.sleep(0.2)

    try:
        os.kill(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    runtime.pid_file.unlink(missing_ok=True)
    raise ProxyError(
        f"{runtime.provider} did not listen on {endpoint.host}:{endpoint.port} within 6 seconds; "
        f"inspect {runtime.log_file}"
    )


def command_stop(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    status, pid = managed_process_status(runtime)
    if status in {"stopped", "stale"}:
        runtime.pid_file.unlink(missing_ok=True)
        print(f"{runtime.provider} is not running")
        return 0
    if status != "running" or pid is None:
        raise ProxyError(
            f"refusing to stop pid {pid}: it is not a verified managed {runtime.provider} process ({status})"
        )

    try:
        os.kill(pid, signal.SIGTERM)
    except OSError as exc:
        raise ProxyError(f"failed to signal managed {runtime.provider} pid {pid}: {exc}") from exc
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not pid_alive(pid):
            runtime.pid_file.unlink(missing_ok=True)
            print(f"{runtime.provider} stopped (pid {pid})")
            return 0
        time.sleep(0.2)

    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and pid_alive(pid):
        time.sleep(0.1)
    runtime.pid_file.unlink(missing_ok=True)
    print(f"{runtime.provider} was force-stopped after the graceful timeout (pid {pid})")
    return 0


def command_restart(args: argparse.Namespace) -> int:
    command_stop(args)
    return command_start(args)


def current_proxy_environment(endpoint: Endpoint) -> str:
    expected = {endpoint.http_url, endpoint.socks_url}
    configured = {
        value
        for key in ("http_proxy", "https_proxy", "all_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
        if (value := os.environ.get(key))
    }
    if not configured:
        return "unset"
    return "configured" if configured.issubset(expected) else "different"


def command_status(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    print(f"provider: {runtime.provider}")
    print(f"binary: {runtime.binary}")
    print(f"config: {runtime.config}")
    print(f"state: {runtime.state_dir}")

    if not runtime.binary.is_file():
        print("binary_status: missing")
        return 1
    try:
        version = subprocess.run(
            [str(runtime.binary), "version"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
        ).stdout.splitlines()[0]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        version = "unknown"
    print(f"version: {version}")

    endpoint: Endpoint | None = None
    try:
        endpoint = discover_endpoint(runtime.config, runtime.provider)
        print(f"endpoint: {endpoint.protocol}://{endpoint.host}:{endpoint.port} ({endpoint.tag or 'untagged'})")
        print(f"listener: {'open' if port_open(endpoint) else 'closed'}")
        print(f"shell_environment: {current_proxy_environment(endpoint)}")
    except ProxyError as exc:
        print(f"endpoint_error: {exc}")

    status, pid = managed_process_status(runtime)
    print(f"process: {status}" + (f" (pid {pid})" if pid else ""))
    return 0 if status == "running" and endpoint and port_open(endpoint) else 1


def proxy_url(endpoint: Endpoint) -> str:
    if endpoint.protocol == "socks":
        return endpoint.socks_url
    return endpoint.http_url


def curl_health(endpoint: Endpoint, url: str, timeout_seconds: float) -> tuple[bool, str]:
    curl = shutil.which("curl")
    if not curl:
        return False, "curl is required for an end-to-end proxy health check"
    result = subprocess.run(
        [
            curl,
            "--silent",
            "--show-error",
            "--location",
            "--output",
            os.devnull,
            "--write-out",
            "%{http_code}",
            "--max-time",
            str(timeout_seconds),
            "--proxy",
            proxy_url(endpoint),
            url,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    code = result.stdout.strip()
    if result.returncode == 0 and len(code) == 3 and code[0] in {"2", "3"}:
        return True, f"HTTP {code}"
    detail = result.stderr.strip().splitlines()
    message = detail[-1] if detail else f"curl exit {result.returncode}, HTTP {code or '000'}"
    if result.returncode == 97 or "SOCKS5" in message.upper():
        message = f"proxy handshake failed; check upstream protocol and credentials ({message})"
    else:
        message = (
            "proxy request failed after the local endpoint was reachable; check upstream "
            f"connectivity, protocol, credentials, and proxy logs ({message})"
        )
    return False, message


def command_check(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    endpoint = ensure_prerequisites(runtime)
    status, pid = managed_process_status(runtime)
    if not port_open(endpoint):
        raise ProxyError(
            f"local proxy endpoint is closed: {endpoint.host}:{endpoint.port} "
            f"(managed process status {status}, pid {pid})"
        )
    if status != "running":
        eprint(
            f"warning: proxy listener is open but no verified managed {runtime.provider} process is recorded "
            f"(status {status}, pid {pid})"
        )

    if args.timeout <= 0:
        raise ProxyError("--timeout must be greater than zero")

    url = args.url or os.environ.get("MANAGE_PROXY_HEALTH_URL") or DEFAULT_HEALTH_URL
    healthy, detail = curl_health(endpoint, url, args.timeout)
    if not healthy:
        raise ProxyError(detail)
    print(f"proxy healthy: {endpoint.host}:{endpoint.port} -> {url} ({detail})")
    return 0


def command_doctor(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    failures = 0

    if runtime.binary.is_file() and os.access(runtime.binary, os.X_OK):
        print(f"[ok] {runtime.provider} binary: {runtime.binary}")
    else:
        print(f"[fail] {runtime.provider} binary: {runtime.binary}")
        failures += 1

    if runtime.config.is_file() and os.access(runtime.config, os.R_OK):
        print(f"[ok] {runtime.provider} config: {runtime.config}")
    else:
        print(f"[fail] {runtime.provider} config: {runtime.config}")
        failures += 1

    endpoint: Endpoint | None = None
    if failures == 0:
        try:
            endpoint = discover_endpoint(runtime.config, runtime.provider)
            print(f"[ok] proxy endpoint: {endpoint.protocol}://{endpoint.host}:{endpoint.port}")
        except ProxyError as exc:
            print(f"[fail] proxy endpoint: {exc}")
            failures += 1

        try:
            result = run_config_test(runtime)
            if result.returncode == 0:
                print("[ok] configuration check")
            else:
                detail = result.stdout.strip().splitlines()
                print(f"[fail] configuration check: {detail[-1] if detail else 'unknown error'}")
                failures += 1
        except (OSError, subprocess.TimeoutExpired) as exc:
            print(f"[fail] configuration check: {exc}")
            failures += 1

    if runtime.provider == "sing-box":
        nodes_path = nodes_file(runtime)
        if nodes_path.is_file():
            try:
                count = len(load_nodes(runtime))
                print(f"[ok] nodes file: {nodes_path} ({count} nodes)")
            except ProxyError as exc:
                print(f"[fail] nodes file: {exc}")
                failures += 1
        else:
            print(f"[info] nodes file missing: {nodes_path} (node switching unavailable)")

    if shutil.which("curl"):
        print("[ok] curl available")
    else:
        print("[fail] curl missing")
        failures += 1

    status, pid = managed_process_status(runtime)
    print(f"[info] managed process: {status}" + (f" (pid {pid})" if pid else ""))
    if endpoint:
        print(f"[info] local listener: {'open' if port_open(endpoint) else 'closed'}")
    print(f"[info] log: {runtime.log_file}")
    return 1 if failures else 0


def command_logs(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    if args.lines <= 0:
        raise ProxyError("--lines must be greater than zero")
    lines = tail_log(runtime.log_file, args.lines)
    if not lines:
        print(f"no {runtime.provider} log output at {runtime.log_file}")
        return 0
    print("\n".join(lines))
    return 0


def command_env(args: argparse.Namespace) -> int:
    runtime = build_runtime(args.provider)
    endpoint = discover_endpoint(runtime.config, runtime.provider)
    if endpoint.protocol == "socks":
        http_proxy = endpoint.socks_url
        all_proxy = endpoint.socks_url
    elif endpoint.protocol == "http":
        http_proxy = endpoint.http_url
        all_proxy = endpoint.http_url
    else:
        http_proxy = endpoint.http_url
        all_proxy = endpoint.socks_url

    values = {
        "http_proxy": http_proxy,
        "https_proxy": http_proxy,
        "all_proxy": all_proxy,
    }
    for key, value in values.items():
        print(f"export {key}={shlex.quote(value)}")
    print("")
    for upper, lower in (("HTTP_PROXY", "http_proxy"), ("HTTPS_PROXY", "https_proxy"), ("ALL_PROXY", "all_proxy")):
        print(f'export {upper}="${lower}"')
    print("")
    print("export no_proxy='127.0.0.1,localhost,::1'")
    print('export NO_PROXY="$no_proxy"')
    return 0


def nodes_file(runtime: Runtime) -> Path:
    explicit = os.environ.get("MANAGE_PROXY_NODES_FILE")
    if explicit:
        return expand_path(explicit)
    return runtime.state_dir / "nodes.json"


def load_nodes(runtime: Runtime) -> list[dict[str, Any]]:
    path = nodes_file(runtime)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProxyError(
            f"nodes file not found: {path}; populate it from the subscription parser "
            f"(or set MANAGE_PROXY_NODES_FILE)"
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise ProxyError(f"cannot read nodes file {path}: {exc}") from exc
    if not isinstance(data, list) or not data or not all(isinstance(n, dict) for n in data):
        raise ProxyError(f"nodes file must be a non-empty JSON array of objects: {path}")
    return data


def singbox_outbound(node: dict[str, Any]) -> dict[str, Any]:
    node_type = node.get("type", "anytls")
    if node_type != "anytls":
        raise ProxyError(f"unsupported node protocol for sing-box config generation: {node_type!r}")
    server = node.get("server")
    port = node.get("port")
    password = node.get("password")
    if not server or not port or not password:
        raise ProxyError("node entry is missing server, port, or password")
    params = node.get("params") if isinstance(node.get("params"), dict) else {}
    tls: dict[str, Any] = {
        "enabled": True,
        "server_name": params.get("sni") or server,
        "insecure": params.get("insecure") == "1",
    }
    fingerprint = params.get("fp")
    if fingerprint:
        tls["utls"] = {"enabled": True, "fingerprint": fingerprint}
    return {
        "type": "anytls",
        "tag": "proxy",
        "server": server,
        "server_port": int(port),
        "password": password,
        "tls": tls,
    }


def current_listen_port(runtime: Runtime) -> int:
    override = os.environ.get("MANAGE_PROXY_PORT")
    if override:
        try:
            return int(override)
        except ValueError as exc:
            raise ProxyError("MANAGE_PROXY_PORT must be an integer") from exc
    try:
        data = load_json_config(runtime.config)
        for inbound in data.get("inbounds", []):
            if not isinstance(inbound, dict):
                continue
            raw = inbound.get("listen_port", inbound.get("port"))
            if isinstance(raw, int) and 1 <= raw <= 65535:
                return raw
    except ProxyError:
        pass
    return DEFAULT_SINGBOX_LISTEN_PORT


def build_singbox_config(node: dict[str, Any], listen_port: int) -> dict[str, Any]:
    return {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [
            {
                "type": "mixed",
                "tag": "mixed-in",
                "listen": "127.0.0.1",
                "listen_port": listen_port,
            }
        ],
        "outbounds": [singbox_outbound(node), {"type": "direct", "tag": "direct"}],
        "route": {"final": "proxy"},
    }


def write_config_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.chmod(0o600)
    os.replace(temporary, path)


def command_nodes(args: argparse.Namespace) -> int:
    require_singbox(args.provider, "node listing")
    runtime = build_runtime(args.provider)
    nodes = load_nodes(runtime)
    print(f"nodes file: {nodes_file(runtime)}")
    for index, node in enumerate(nodes):
        node_type = str(node.get("type", "anytls"))
        name = str(node.get("name", ""))[:60]
        print(f"{index:3d}  {node_type:<8} {name:<62} port={node.get('port')}")
    return 0


def command_use(args: argparse.Namespace) -> int:
    require_singbox(args.provider, "node switching")
    runtime = build_runtime(args.provider)
    nodes = load_nodes(runtime)
    if not 0 <= args.index < len(nodes):
        raise ProxyError(f"node index out of range: 0..{len(nodes) - 1}")
    node = nodes[args.index]
    listen_port = current_listen_port(runtime)
    candidate = build_singbox_config(node, listen_port)

    runtime.state_dir.mkdir(parents=True, exist_ok=True)
    temp_config = runtime.state_dir / "config.candidate.json"
    write_config_atomic(temp_config, candidate)
    try:
        result = run_config_test(runtime, temp_config)
    except (OSError, subprocess.TimeoutExpired) as exc:
        temp_config.unlink(missing_ok=True)
        raise ProxyError(f"generated config could not be validated: {exc}") from exc
    if result.returncode != 0:
        temp_config.unlink(missing_ok=True)
        detail = result.stdout.strip().splitlines()
        suffix = f": {detail[-1]}" if detail else ""
        raise ProxyError(f"generated config failed validation{suffix}")
    runtime.config.parent.mkdir(parents=True, exist_ok=True)
    os.replace(temp_config, runtime.config)
    runtime.config.chmod(0o600)

    name = str(node.get("name", ""))[:60]
    status, _ = managed_process_status(runtime)
    if status == "running":
        print(f"switched to node {args.index} ({name}); restarting managed process")
        command_stop(args)
        return command_start(args)
    print(f"config switched to node {args.index} ({name}); managed process is {status}, run start to apply")
    return 0


def github_request(url: str) -> urllib.request.Request:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "manage-proxy-skill",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.Request(url, headers=headers)


def release_asset_name() -> str:
    if platform.system() != "Linux":
        raise ProxyError("v1 installation supports Linux only")
    machine = platform.machine().lower()
    if machine in {"x86_64", "amd64"}:
        return "Xray-linux-64.zip"
    if machine in {"aarch64", "arm64"}:
        return "Xray-linux-arm64-v8a.zip"
    raise ProxyError(f"unsupported Linux architecture for v1 installation: {machine}")


def fetch_latest_release() -> tuple[str, str, str]:
    try:
        with urllib.request.urlopen(github_request(GITHUB_RELEASE_API), timeout=30) as response:
            release = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise ProxyError(f"failed to query XTLS GitHub release API: {exc}") from exc

    tag = release.get("tag_name")
    wanted = release_asset_name()
    for asset in release.get("assets", []):
        if asset.get("name") != wanted:
            continue
        url = asset.get("browser_download_url")
        digest = asset.get("digest")
        if not isinstance(tag, str) or not isinstance(url, str):
            break
        if not isinstance(digest, str) or not digest.startswith("sha256:"):
            raise ProxyError("GitHub release asset does not provide an official SHA-256 digest")
        return tag, url, digest.removeprefix("sha256:")
    raise ProxyError(f"release asset not found: {wanted}")


def download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "manage-proxy-skill"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, destination.open("wb") as output:
            shutil.copyfileobj(response, output)
    except (OSError, urllib.error.URLError) as exc:
        raise ProxyError(f"download failed: {exc}") from exc


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_extract_xray(archive: Path, destination: Path) -> None:
    allowed = {"xray", "geoip.dat", "geosite.dat", "LICENSE", "README.md"}
    try:
        with zipfile.ZipFile(archive) as package:
            names = set(package.namelist())
            if "xray" not in names:
                raise ProxyError("downloaded Xray archive does not contain the xray executable")
            for name in names:
                path = Path(name)
                if path.is_absolute() or ".." in path.parts:
                    raise ProxyError(f"unsafe path in Xray archive: {name}")
                if name in allowed:
                    package.extract(name, destination)
    except zipfile.BadZipFile as exc:
        raise ProxyError("downloaded Xray asset is not a valid ZIP archive") from exc


def switch_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() and not link.is_symlink():
        raise ProxyError(f"refusing to replace non-symlink binary: {link}")
    temporary = link.with_name(f".{link.name}.tmp-{os.getpid()}")
    temporary.unlink(missing_ok=True)
    temporary.symlink_to(target)
    os.replace(temporary, link)


def command_install(args: argparse.Namespace) -> int:
    if args.provider != "xray":
        raise ProxyError(
            "install automates the xray provider only; install sing-box manually from the "
            "official SagerNet/sing-box release"
        )
    existing = find_binary(args.provider)
    if existing.is_file() and os.access(existing, os.X_OK) and not args.upgrade:
        print(f"Xray is already installed: {existing}; use --upgrade to install the latest release")
        return 0

    tag, official_url, expected_digest = fetch_latest_release()
    prefix = args.download_prefix or os.environ.get("MANAGE_PROXY_DOWNLOAD_PREFIX")
    download_url = f"{prefix.rstrip('/')}/{official_url}" if prefix else official_url
    install_root = expand_path(
        os.environ.get("MANAGE_PROXY_INSTALL_ROOT") or "~/.local/share/xray"
    )
    bin_dir = expand_path(os.environ.get("MANAGE_PROXY_BIN_DIR") or "~/.local/bin")
    install_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=".manage-proxy-", dir=install_root) as tmp:
        temporary = Path(tmp)
        archive = temporary / "xray.zip"
        stage = temporary / "stage"
        stage.mkdir()
        print(f"downloading {tag} from {download_url}")
        download_file(download_url, archive)
        actual_digest = sha256_file(archive)
        if actual_digest != expected_digest:
            raise ProxyError(
                f"SHA-256 mismatch: expected {expected_digest}, received {actual_digest}"
            )
        safe_extract_xray(archive, stage)
        executable = stage / "xray"
        executable.chmod(0o755)

        target = install_root / tag
        if target.exists():
            if not (target / "xray").is_file():
                raise ProxyError(f"existing install directory is incomplete: {target}")
        else:
            os.replace(stage, target)
        switch_symlink(bin_dir / "xray", target / "xray")

    result = subprocess.run(
        [str(bin_dir / "xray"), "version"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=10,
    )
    first_line = result.stdout.splitlines()[0] if result.stdout else "version unavailable"
    if result.returncode != 0:
        raise ProxyError(f"installed Xray failed to run: {first_line}")
    print(f"installed: {first_line}")
    print(f"binary: {bin_dir / 'xray'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Install, run, inspect, and troubleshoot a user-owned proxy service."
    )
    parser.add_argument(
        "--provider",
        default=os.environ.get("MANAGE_PROXY_PROVIDER", "xray"),
        help=f"proxy provider (supports: {', '.join(SUPPORTED_PROVIDERS)})",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    install = subparsers.add_parser("install", help="install the latest official Xray release")
    install.add_argument("--upgrade", action="store_true", help="install latest even if Xray exists")
    install.add_argument(
        "--download-prefix",
        help="explicit URL prefix for a download accelerator; official SHA-256 is still required",
    )
    install.set_defaults(handler=command_install)

    subparsers.add_parser("doctor", help="check installation and configuration prerequisites").set_defaults(
        handler=command_doctor
    )
    subparsers.add_parser("start", help="start the managed proxy process").set_defaults(
        handler=command_start
    )
    subparsers.add_parser("stop", help="stop the verified managed proxy process").set_defaults(
        handler=command_stop
    )
    subparsers.add_parser("restart", help="restart the managed proxy process").set_defaults(
        handler=command_restart
    )
    subparsers.add_parser("status", help="show process, listener, and shell environment status").set_defaults(
        handler=command_status
    )

    check = subparsers.add_parser("check", help="run an end-to-end request through the proxy")
    check.add_argument("--url", help=f"health URL (default: {DEFAULT_HEALTH_URL})")
    check.add_argument("--timeout", type=float, default=10, help="curl timeout in seconds")
    check.set_defaults(handler=command_check)

    logs = subparsers.add_parser("logs", help="print recent managed proxy logs")
    logs.add_argument("--lines", type=int, default=50, help="number of lines")
    logs.set_defaults(handler=command_logs)

    subparsers.add_parser("env", help="print Bash proxy exports derived from the proxy config").set_defaults(
        handler=command_env
    )

    nodes = subparsers.add_parser("nodes", help="list available nodes (sing-box only)")
    nodes.set_defaults(handler=command_nodes)

    use = subparsers.add_parser("use", help="switch the sing-box config to a node by index")
    use.add_argument("index", type=int, help="node index from the nodes command")
    use.set_defaults(handler=command_use)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        require_provider(args.provider)
        return int(args.handler(args))
    except ProxyError as exc:
        eprint(f"error: {exc}")
        return 1
    except KeyboardInterrupt:
        eprint("interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
