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

## Install for multiple agents

`bootstrap.sh` installs into the Codex skills directory. To install the same
skills into other agents (ZCode, Claude Code, Cursor) or into the cross-tool
shared path `~/.agents/skills`, use `install-for-agent.sh`. It delegates to
`bootstrap.sh` for each selected agent, so all idempotency, backup, and
keep-vs-overwrite behavior is identical.

Interactive (shows a numbered menu):

```bash
bash ~/codex-skills/install-for-agent.sh
```

Non-interactive (repeat `--agent`):

```bash
bash ~/codex-skills/install-for-agent.sh --agent zcode --agent agents
```

List known agents and their resolved target paths without installing:

```bash
bash ~/codex-skills/install-for-agent.sh --list
```

Known agents and their default target directories (override each home via
`CODEX_HOME`, `ZCODE_HOME`, `AGENTS_HOME`, `CLAUDE_HOME`, `CURSOR_HOME`):

| Agent  | Default target            | Note                          |
|--------|---------------------------|-------------------------------|
| codex  | `~/.codex/skills`         | bootstrap.sh default          |
| zcode  | `~/.zcode/skills`         |                               |
| agents | `~/.agents/skills`        | Cross-tool shared path        |
| claude | `~/.claude/skills`        |                               |
| cursor | `~/.cursor/skills`        |                               |

All skills are installed unconditionally. Skills whose body hardcodes Codex
paths (currently `tencent-coscli`, `manage-proxy`, `manage-project-memory`, and
`codex-skills-sync`) may not work correctly under a non-Codex agent; review them
before relying on them outside Codex.

## Update on a machine

```bash
cd ~/codex-skills
git pull --ff-only
bash ./bootstrap.sh
```

Use `bash ./bootstrap.sh --overwrite` when the repo version should replace a
same-named local skill.

## Sync local Codex skills into this repo

If a skill was installed or created directly under `$CODEX_HOME/skills`, import
it into this repository:

```bash
cd ~/codex-skills
bash ./sync-from-codex.sh
git status --short
```

The default is to copy only new skills and keep repo skills when names collide.
To replace same-named repo skills with the local Codex version:

```bash
bash ./sync-from-codex.sh --overwrite
```

After importing a new skill, run this if the current machine should use the
repo-managed symlink instead of the original local directory:

```bash
bash ./bootstrap.sh --overwrite
```

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
- `codex-skills-sync`
- `manage-project-memory`
- `restore-vrdma`
- `tencent-coscli`
- `tikit-tione`

## Optional installers

The bootstrap script above is the canonical setup path for this repository. If a
machine already has one of these skill managers, these commands can also be used:

```bash
DISABLE_TELEMETRY=1 npx skills add yiming-cc/codex-skills -g -a codex --skill '*' -y
```

```bash
gh skill install yiming-cc/codex-skills codex-skills-sync --agent codex --scope user
gh skill install yiming-cc/codex-skills karpathy-guidelines --agent codex --scope user
gh skill install yiming-cc/codex-skills manage-project-memory --agent codex --scope user
gh skill install yiming-cc/codex-skills restore-vrdma --agent codex --scope user
gh skill install yiming-cc/codex-skills tencent-coscli --agent codex --scope user
gh skill install yiming-cc/codex-skills tikit-tione --agent codex --scope user
```
