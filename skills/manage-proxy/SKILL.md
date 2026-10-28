---
name: manage-proxy
description: Install, start, stop, restart, inspect, and troubleshoot user-owned proxy clients, including process state, local listeners, configuration validity, logs, shell proxy exports, and end-to-end connectivity. Use when Codex needs to manage a proxy service, diagnose whether a proxy is actually usable, generate shell proxy settings, or install Xray from official XTLS releases. Supports two providers on Linux - xray and sing-box (including subscription node listing and switching for sing-box); other providers such as Clash are future extensions.
---

# Manage Proxy

Use the bundled CLI as the single management entry point. Resolve it relative to this `SKILL.md` instead of assuming the current project directory:

```bash
SKILL_DIR="<directory containing this SKILL.md>"
python3 "$SKILL_DIR/scripts/proxyctl.py" --help
```

Two providers are supported:

- `xray` (default): binary `xray` from `PATH` or `~/.local/bin/xray`, config `~/.config/xray/config.json`, state under `${XDG_STATE_HOME:-$HOME/.local/state}/manage-proxy/xray`.
- `sing-box`: binary `sing-box` from `PATH` or `~/.local/bin/sing-box`, config `~/.config/sing-box/config.json`, state under `.../manage-proxy/sing-box`. Node switching (`nodes`/`use`) applies to this provider only.

Select the provider with `--provider sing-box` on each command, or once via `export MANAGE_PROXY_PROVIDER=sing-box`.

## Workflow

1. Inspect before changing process state:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box doctor
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box status
   ```

2. If Xray is missing and installation is in scope, install the latest official XTLS release:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider xray install
   ```

   Use `install --upgrade` only when the user requests an update. Direct downloads use the official release URL. A user-supplied `--download-prefix` may accelerate the same asset, but installation must still match the SHA-256 returned by the official GitHub Releases API. `install` does not automate sing-box; install it manually from the official SagerNet release.

3. Start or restart the managed process, then prove the data path:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box start
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box check
   ```

   Treat `start` as local-process success only. Claim the proxy is usable only after `check` completes an HTTP request through the proxy.

4. Inspect failures with status and logs:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box status
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box logs --lines 100
   ```

5. Stop only the process recorded and verified by the skill:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box stop
   ```

### Taking over a manually started process

The skill refuses to adopt or stop a process it did not start. To take over a manually started sing-box/xray: stop the manual instance first (via its own pid file or process group), then `start` it through the CLI so the skill's pid file owns it.

## Sing-box Node Management

The sing-box provider can switch between subscription nodes recorded in a nodes file (default `<state>/nodes.json`, override `MANAGE_PROXY_NODES_FILE`). The file is an array of `{name, server, port, password, params}` objects, holds credentials, must be mode 0600, and is produced outside the skill by a subscription parser; never paste node credentials into the skill or conversation.

```bash
python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box nodes   # list index, protocol, name, port
python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box use 5   # rewrite config for node 5, restart if running
```

`use` validates the generated config with `sing-box check` before replacing the live config; a failed validation leaves the current config untouched. Generation currently covers `anytls` nodes only.

## Shell Environment

Print Bash exports derived from the selected inbound (works for both providers):

```bash
python3 "$SKILL_DIR/scripts/proxyctl.py" --provider sing-box env
```

The user may copy this output into `.bashrc`. Do not edit `.bashrc` automatically. Commenting exports affects only new shells; clear an existing shell with:

```bash
unset http_proxy https_proxy all_proxy
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
unset no_proxy NO_PROXY
```

Stopping the proxy does not clear proxy variables already exported in other processes or shells.

## Overrides

Use environment variables for machine-local differences; never commit user configurations or credentials into the skill:

- `MANAGE_PROXY_PROVIDER`
- `MANAGE_PROXY_STATE_DIR`
- `MANAGE_PROXY_HOST` and `MANAGE_PROXY_PORT`
- `MANAGE_PROXY_HEALTH_URL`
- `MANAGE_PROXY_NODES_FILE` (sing-box node list path)
- xray only: `MANAGE_PROXY_XRAY_BIN` or `XRAY_BIN`, `MANAGE_PROXY_XRAY_CONFIG` or `XRAY_CONFIG`, `MANAGE_PROXY_XRAY_ASSET_DIR` or `XRAY_LOCATION_ASSET`, `MANAGE_PROXY_INSTALL_ROOT`, `MANAGE_PROXY_BIN_DIR`, `MANAGE_PROXY_DOWNLOAD_PREFIX`
- sing-box only: `MANAGE_PROXY_SINGBOX_BIN` or `SINGBOX_BIN`, `MANAGE_PROXY_SINGBOX_CONFIG` or `SINGBOX_CONFIG`

Pass `--provider ...` explicitly when clarity helps. Reject unsupported providers rather than approximating one binary's behavior with another's commands.

## Guardrails

- Do not display outbound server credentials, UUIDs, passwords, tokens, node URIs, or the full config.
- Do not kill an unverified PID or a manually started process that is not owned by the skill state file.
- Do not infer end-to-end health from a process or open local port alone.
- Do not persist Git, pip, uv, apt, Docker, systemd, or application-specific proxy configuration.
- Do not describe environment-variable proxying as a TUN VPN or transparent system proxy.
- Do not add Clash, TUN, iptables, nftables, automatic restarts, or continuous monitoring in v1.
