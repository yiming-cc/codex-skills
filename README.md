# Codex Skills

Personal Codex skills managed with Git.

## One-command setup

```bash
git clone git@github.com:yiming-cc/codex-skills.git ~/codex-skills
bash ~/codex-skills/bootstrap.sh
```

`bootstrap.sh` links every directory under `skills/` into:

```bash
${CODEX_HOME:-$HOME/.codex}/skills
```

If a same-named local skill already exists, the default behavior is to keep the
existing skill and skip linking the repo version:

```bash
bash ~/codex-skills/bootstrap.sh --keep-existing
```

To replace same-named local skills with the repo version:

```bash
bash ~/codex-skills/bootstrap.sh --overwrite
```

Overwrite mode moves old skills outside the scanned skills directory, under
`${CODEX_HOME:-$HOME/.codex}/skill-backups/bootstrap-*`, before creating links.
This avoids duplicate skill discovery from in-place backup folders. Other skills
are left untouched.

## Update on a machine

```bash
cd ~/codex-skills
git pull --ff-only
bash ./bootstrap.sh
```

Use `bash ./bootstrap.sh --overwrite` when the repo version should replace a
same-named local skill.

## Add or edit a skill

Edit files under `skills/<skill-name>/`, then commit and push:

```bash
git add skills/<skill-name>
git commit -m "update <skill-name>"
git push
```

Keep secrets out of this repository. Use environment variables or local private
files for API keys, cloud credentials, tokens, cookies, and registry passwords.

## Current skills

- `karpathy-guidelines`
- `tencent-coscli`
- `tikit-tione`

## Optional installers

The bootstrap script above is the canonical setup path for this repository. If a
machine already has one of these skill managers, these commands can also be used:

```bash
DISABLE_TELEMETRY=1 npx skills add yiming-cc/codex-skills -g -a codex --skill '*' -y
```

```bash
gh skill install yiming-cc/codex-skills karpathy-guidelines --agent codex --scope user
gh skill install yiming-cc/codex-skills tencent-coscli --agent codex --scope user
gh skill install yiming-cc/codex-skills tikit-tione --agent codex --scope user
```
