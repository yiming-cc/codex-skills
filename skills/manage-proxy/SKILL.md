---
name: manage-proxy
description: Install, start, stop, restart, inspect, and troubleshoot user-owned proxy clients, including process state, local listeners, configuration validity, logs, shell proxy exports, and end-to-end connectivity. Use when Codex needs to manage a proxy service, diagnose whether a proxy is actually usable, generate shell proxy settings, or install Xray from official XTLS releases. Version 1 supports Xray on Linux; other providers such as Clash are future extensions.
---

# Manage Proxy

Use the bundled CLI as the single management entry point. Resolve it relative to this `SKILL.md` instead of assuming the current project directory:

```bash
SKILL_DIR="$HOME/.agents/skills/manage-proxy"
python3 "$SKILL_DIR/scripts/proxyctl.py" --help
```

The CLI defaults to provider `xray`, binary `xray` from `PATH` or `~/.local/bin/xray`, config `~/.config/xray/config.json`, and state under `${XDG_STATE_HOME:-$HOME/.local/state}/manage-proxy/xray`.

## Workflow

1. Inspect before changing process state:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" doctor
   python3 "$SKILL_DIR/scripts/proxyctl.py" status
   ```

2. If Xray is missing and installation is in scope, install the latest official XTLS release:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" install
   ```

   Use `install --upgrade` only when the user requests an update. Direct downloads use the official release URL. A user-supplied `--download-prefix` may accelerate the same asset, but installation must still match the SHA-256 returned by the official GitHub Releases API.

3. Start or restart the managed process, then prove the data path:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" start
   python3 "$SKILL_DIR/scripts/proxyctl.py" check
   ```

   Treat `start` as local-process success only. Claim the proxy is usable only after `check` completes an HTTP request through the proxy.

4. Inspect failures with status and logs:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" status
   python3 "$SKILL_DIR/scripts/proxyctl.py" logs --lines 100
   ```

5. Stop only the process recorded and verified by the skill:

   ```bash
   python3 "$SKILL_DIR/scripts/proxyctl.py" stop
   ```

## Shell Environment

Print Bash exports derived from the selected Xray inbound:

```bash
python3 "$SKILL_DIR/scripts/proxyctl.py" env
```

The user may copy this output into `.bashrc`. Do not edit `.bashrc` automatically. Commenting exports affects only new shells; clear an existing shell with:

```bash
unset http_proxy https_proxy all_proxy
unset HTTP_PROXY HTTPS_PROXY ALL_PROXY
unset no_proxy NO_PROXY
```

Stopping Xray does not clear proxy variables already exported in other processes or shells.

## Overrides

Use environment variables for machine-local differences; never commit user configurations or credentials into the skill:

- `MANAGE_PROXY_XRAY_BIN` or `XRAY_BIN`
- `MANAGE_PROXY_XRAY_CONFIG` or `XRAY_CONFIG`
- `MANAGE_PROXY_XRAY_ASSET_DIR` or `XRAY_LOCATION_ASSET`
- `MANAGE_PROXY_STATE_DIR`
- `MANAGE_PROXY_HOST` and `MANAGE_PROXY_PORT`
- `MANAGE_PROXY_HEALTH_URL`
- `MANAGE_PROXY_INSTALL_ROOT` and `MANAGE_PROXY_BIN_DIR`
- `MANAGE_PROXY_DOWNLOAD_PREFIX`

Pass `--provider xray` explicitly when clarity helps. Reject unsupported providers rather than approximating Clash behavior with Xray commands.

## Guardrails

- Do not display outbound server credentials, UUIDs, passwords, tokens, or the full config.
- Do not kill an unverified PID or a manually started process that is not owned by the skill state file.
- Do not infer end-to-end health from a process or open local port alone.
- Do not persist Git, pip, uv, apt, Docker, systemd, or application-specific proxy configuration.
- Do not describe environment-variable proxying as a TUN VPN or transparent system proxy.
- Do not add Clash, TUN, iptables, nftables, automatic restarts, or continuous monitoring in v1.
