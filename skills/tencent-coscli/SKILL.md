---
name: tencent-coscli
description: Tencent Cloud COS data transfer with coscli on the LogosVLA/TI-ONE CFS environment. Use when Codex needs to list, inspect, download, upload, or synchronize COS prefixes such as cos://phymi-cos-1438869198/...; move datasets/checkpoints between COS and /cfs; repair /cfs ACL issues before syncing; or diagnose coscli authentication, endpoint, logging, and permission errors.
---

# Tencent COSCLI

## Core Rules

- Use `/cfs/users/chenyiming/bin/coscli` by default. It wraps the real binary and pins:
  - config: `/cfs/users/chenyiming/.cos.yaml`
  - logs: `/cfs/users/chenyiming/coscli_output`
- Never print `SecretId`, `SecretKey`, session tokens, or `coscli config show` output. Validate credentials by `coscli ls`, not by displaying them.
- Do not hard-code shared AK/SK values into this skill, scripts, committed files, shell history, or chat output. For installation/configuration, pass credentials through `COSCLI_SECRET_ID` and `COSCLI_SECRET_KEY`, or through a private chmod `600` env file passed with `--credential-file`.
- Default bucket is `phymi-cos-1438869198`, endpoint `cos.ap-shanghai.myqcloud.com`.
- Prefer absolute local paths. If the user asks for `/cfs/...`, use exactly `/cfs/...`, not `/cfs/users/chenyiming/...`.
- Do not use `sudo coscli`. Use sudo only for local directory ownership/ACL repair, then run `coscli` as user `ymc`.
- Treat `sync --delete`, `rm`, and `cp --move` as destructive. Require explicit user intent; for the helper script, set `COSCLI_ALLOW_DELETE=1` before using `--delete`, `rm`, or `--move`.

## Install COSCLI For A New User

If `/cfs/users/chenyiming/bin/coscli` is unavailable or the user needs their own install, run the installer. It downloads the official Tencent COSCLI binary for Linux/macOS, installs a wrapper, and can initialize `~/.cos.yaml`.

```bash
$HOME/.agents/skills/tencent-coscli/scripts/install_coscli.sh
export PATH="$HOME/bin:$PATH"
coscli -v
```

To configure the default bucket without exposing credentials in output:

```bash
export COSCLI_SECRET_ID='<secret-id>'
export COSCLI_SECRET_KEY='<secret-key>'
$HOME/.agents/skills/tencent-coscli/scripts/install_coscli.sh --configure --verify
unset COSCLI_SECRET_ID COSCLI_SECRET_KEY
```

For a private credential file:

```bash
install -m 600 /dev/null "$HOME/.coscli.env"
# Edit the file locally so it contains COSCLI_SECRET_ID=... and COSCLI_SECRET_KEY=...
$HOME/.agents/skills/tencent-coscli/scripts/install_coscli.sh --configure --credential-file "$HOME/.coscli.env" --verify
```

The installer defaults to:

- wrapper: `$HOME/bin/coscli`
- real binary: `$HOME/bin/coscli-bin`
- config: `$HOME/.cos.yaml`
- logs: `$HOME/coscli_output`
- bucket: `phymi-cos-1438869198`
- endpoint: `cos.ap-shanghai.myqcloud.com`

Never paste or print the configured credentials. If a user asks to use site default credentials, use a private env file or environment variables supplied outside chat; if neither exists, ask for a secure credential source instead of inventing or displaying one.

## Helper Script

Use `scripts/cos_transfer.sh` for routine operations:

```bash
$HOME/.agents/skills/tencent-coscli/scripts/cos_transfer.sh ls teleoperate_data_humanoid_nero_sharpa/
$HOME/.agents/skills/tencent-coscli/scripts/cos_transfer.sh download teleoperate_data_humanoid_nero_sharpa/ /cfs/teleoperate_data_humanoid_nero_sharpa/
$HOME/.agents/skills/tencent-coscli/scripts/cos_transfer.sh upload /cfs/path/to/data/ users/chenyiming/transfer/data/
$HOME/.agents/skills/tencent-coscli/scripts/cos_transfer.sh sync cos://phymi-cos-1438869198/a/ /cfs/a/ -r --update
```

The script accepts either full `cos://...` URLs or bucket-relative prefixes. Bucket-relative prefixes are expanded under `cos://phymi-cos-1438869198/`.

## Workflow

1. Inspect first:
   ```bash
   coscli ls cos://phymi-cos-1438869198/<prefix>/
   coscli du cos://phymi-cos-1438869198/<prefix>/
   ```
2. Prepare the local target. For `/cfs/...`, check ACL:
   ```bash
   getfacl -p /cfs/<target> | sed -n '1,80p'
   touch /cfs/<target>/.write_test && rm /cfs/<target>/.write_test
   ```
   If `user:ymc:r-x` blocks writing, repair the target directory only:
   ```bash
   sudo mkdir -p /cfs/<target>
   sudo chown ymc:ymc /cfs/<target>
   sudo setfacl -m u:ymc:rwx,d:u:ymc:rwx /cfs/<target>
   ```
3. Download with incremental sync:
   ```bash
   coscli sync cos://phymi-cos-1438869198/<prefix>/ /cfs/<target>/ -r --update
   ```
4. Upload with incremental sync:
   ```bash
   coscli sync /cfs/<source>/ cos://phymi-cos-1438869198/<prefix>/ -r --update
   ```
5. After transfer, verify object/file counts and ownership:
   ```bash
   find /cfs/<target> -type f | wc -l
   du -sh /cfs/<target>
   find /cfs/<target> -maxdepth 2 -printf '%u %g %p\n' | sed -n '1,40p'
   ```

## Diagnostics

- `mkdir ... permission denied` under `/cfs`: inspect ACL; `ls -ld` can look writable while ACL denies `ymc`.
- `sudo: coscli: command not found`: expected; do not use `sudo coscli`.
- `Error N objects` with `OK size: 0`: usually local write permission, not COS authentication. Check process logs and local `touch`.
- Authentication problems usually appear as COS errors such as `AccessDenied` or signature mismatch. Confirm with `coscli ls cos://phymi-cos-1438869198/`.

Read `references/coscli-notes.md` for local paths, examples, and ACL details.
