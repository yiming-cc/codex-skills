# COSCLI Notes

## Local Installation

- Wrapper: `/cfs/users/chenyiming/bin/coscli`
- Real binary: `/cfs/users/chenyiming/bin/coscli-bin`
- Config: `/cfs/users/chenyiming/.cos.yaml`
- Logs: `/cfs/users/chenyiming/coscli_output`
- User: `ymc`
- Default bucket: `phymi-cos-1438869198`
- Endpoint: `cos.ap-shanghai.myqcloud.com`

Do not run `coscli config show` in user-visible output because it decrypts and prints credentials.

## New User Installation

Use the installer when the pinned `/cfs/users/chenyiming/bin/coscli` wrapper is not available or the user needs an isolated config:

```bash
/cfs/users/chenyiming/.codex/skills/tencent-coscli/scripts/install_coscli.sh
export PATH="$HOME/bin:$PATH"
coscli -v
```

The installer detects Linux/macOS CPU architecture and downloads from Tencent's official COSCLI host:

```text
https://cosbrowser.cloud.tencent.com/software/coscli/
```

It installs:

- wrapper: `$HOME/bin/coscli`
- real binary: `$HOME/bin/coscli-bin`
- config: `$HOME/.cos.yaml`
- logs: `$HOME/coscli_output`

To initialize the default `phymi-cos-1438869198` bucket, pass credentials through environment variables or a private env file:

```bash
export COSCLI_SECRET_ID='<secret-id>'
export COSCLI_SECRET_KEY='<secret-key>'
/cfs/users/chenyiming/.codex/skills/tencent-coscli/scripts/install_coscli.sh --configure --verify
unset COSCLI_SECRET_ID COSCLI_SECRET_KEY
```

or:

```bash
install -m 600 /dev/null "$HOME/.coscli.env"
# Add COSCLI_SECRET_ID=... and COSCLI_SECRET_KEY=... locally; do not print the file.
/cfs/users/chenyiming/.codex/skills/tencent-coscli/scripts/install_coscli.sh --configure --credential-file "$HOME/.coscli.env" --verify
```

Never store shared default AK/SK values in this skill, scripts, committed files, shell history, or chat output. If site default credentials are required, inject them from a private source such as `COSCLI_SECRET_ID`/`COSCLI_SECRET_KEY` or `--credential-file`.

## Common Commands

List:

```bash
coscli ls cos://phymi-cos-1438869198/
coscli ls cos://phymi-cos-1438869198/system2-cache/
```

Download a prefix to `/cfs`:

```bash
coscli sync \
  cos://phymi-cos-1438869198/teleoperate_data_humanoid_nero_sharpa/ \
  /cfs/teleoperate_data_humanoid_nero_sharpa/ \
  -r --update
```

Upload a directory:

```bash
coscli sync \
  /cfs/path/to/local_dir/ \
  cos://phymi-cos-1438869198/users/chenyiming/transfer/local_dir/ \
  -r --update
```

Single-file copy:

```bash
coscli cp /cfs/path/to/file.pt cos://phymi-cos-1438869198/users/chenyiming/transfer/file.pt
coscli cp cos://phymi-cos-1438869198/users/chenyiming/transfer/file.pt /cfs/path/to/file.pt
```

## `/cfs` ACL Pitfall

`/cfs` may show mode `777`, but ACL can still restrict `ymc`:

```text
user:ymc:r-x
default:user:ymc:r-x
```

Symptoms:

- `mkdir <target>: permission denied`
- `Total num: ... Processed num: N(Error N objects), OK size: 0`
- `touch /cfs/<target>/.write_test` fails

Fix the target directory, not the whole `/cfs` tree:

```bash
sudo mkdir -p /cfs/<target>
sudo chown ymc:ymc /cfs/<target>
sudo setfacl -m u:ymc:rwx,d:u:ymc:rwx /cfs/<target>
touch /cfs/<target>/.write_test && rm /cfs/<target>/.write_test
```

If there are already root-owned partial files, add recursive repair only for that target:

```bash
sudo chown -R ymc:ymc /cfs/<target>
sudo setfacl -R -m u:ymc:rwx /cfs/<target>
sudo setfacl -R -d -m u:ymc:rwx /cfs/<target>
```

## Safety

- Never expose AK/SK or tokens.
- Do not run `sudo coscli`; repair filesystem permissions first.
- Avoid `sync --delete` unless the user explicitly asks to mirror-delete.
- Prefer `sync -r --update` for routine incremental transfers.
