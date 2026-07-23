---
name: codex-skills-sync
description: Manage the personal git@github.com:yiming-cc/codex-skills.git repository for Codex skill migration, installation, updates, reverse-sync from $CODEX_HOME/skills, keep-vs-overwrite choices, duplicate skill cleanup, and committing/pushing skill changes. Use when the user asks to clone or bootstrap Codex skills on a new machine, sync local ~/.codex skills into Git, update skills from GitHub, repair duplicate backup installs, or make Codex skills portable across machines.
---

# Codex Skills Sync

## Overview

Use `/home/ymc/codex-skills` or `${CODEX_SKILLS_REPO_DIR:-$HOME/codex-skills}` as the working repo for personal Codex skills. The canonical remote is:

```bash
git@github.com:yiming-cc/codex-skills.git
```

The repo root scripts are the source of truth:

```bash
bootstrap.sh          # repo -> $CODEX_HOME/skills
sync-from-codex.sh    # $CODEX_HOME/skills -> repo
```

## Guardrails

- Run `git status --short --branch` before writes. Do not overwrite unrelated user changes.
- Do not commit `.system`, `*.backup-*`, `__pycache__`, `*.pyc`, tokens, cloud credentials, cookies, registry passwords, or local private env files.
- Default to keeping existing skills. Use `--overwrite` only when the user wants the repo version or local version to replace an existing same-named skill.
- After changing installed skills, tell the user that Codex may need a new task or restart to load newly linked skills.

## Ensure Repo

```bash
repo="${CODEX_SKILLS_REPO_DIR:-$HOME/codex-skills}"
if [ -d "$repo/.git" ]; then
  git -C "$repo" status --short --branch
else
  git clone git@github.com:yiming-cc/codex-skills.git "$repo"
fi
```

Pull only when the repo is clean or after understanding dirty changes:

```bash
git -C "$repo" pull --ff-only
```

## Install Or Update Local Codex Skills

Install repo skills into `${CODEX_HOME:-$HOME/.codex}/skills`:

```bash
bash "$repo/bootstrap.sh"
```

This keeps existing same-named local skills. To replace same-named local skills with repo-managed symlinks:

```bash
bash "$repo/bootstrap.sh" --overwrite
```

Verify:

```bash
find "${CODEX_HOME:-$HOME/.codex}/skills" -maxdepth 1 -mindepth 1 \
  \( -type l -o -type d \) -printf '%f -> %l\n' | sort
```

### Other agents

To install the same skills into other agents (ZCode, Claude Code, Cursor) or
into the cross-tool shared path `~/.agents/skills`, use `install-for-agent.sh`.
It delegates to `bootstrap.sh` for each selected agent, so all idempotency,
backup, and keep-vs-overwrite behavior is identical.

Interactive menu:

```bash
bash "$repo/install-for-agent.sh"
```

Non-interactive:

```bash
bash "$repo/install-for-agent.sh" --agent zcode --agent agents
```

Known agents and default targets: `codex` (`~/.codex/skills`), `zcode`
(`~/.zcode/skills`), `agents` (`~/.agents/skills`, cross-tool shared), `claude`
(`~/.claude/skills`), `cursor` (`~/.cursor/skills`). Override each home via
`CODEX_HOME` / `ZCODE_HOME` / `AGENTS_HOME` / `CLAUDE_HOME` / `CURSOR_HOME`.

All skills are installed unconditionally. Skills whose body hardcodes Codex
paths (`tencent-coscli`, `manage-proxy`, `manage-project-memory`, and this
`codex-skills-sync` skill itself) may not work correctly under a non-Codex
agent; flag this to the user before relying on them outside Codex.

## Sync Local Skills Back To Git

When the user created or installed a skill directly in `$CODEX_HOME/skills`, import it:

```bash
bash "$repo/sync-from-codex.sh"
git -C "$repo" status --short
```

This copies only new skills and keeps repo versions on name collisions. To replace repo versions with the local Codex versions:

```bash
bash "$repo/sync-from-codex.sh" --overwrite
```

After importing a new skill, run this if the current machine should use the repo-managed symlink:

```bash
bash "$repo/bootstrap.sh" --overwrite
```

## Commit And Push

Before committing, inspect changes and scan for likely secrets:

```bash
git -C "$repo" diff --check
rg -n --hidden -i \
  '(ghp_|github_pat_|sk-[A-Za-z0-9]|AKIA[0-9A-Z]{16}|BEGIN (RSA|OPENSSH|PRIVATE) KEY|SECRET_(ID|KEY)=|TOKEN=|PASSWORD=)' \
  "$repo" --glob '!/.git/**'
```

Treat placeholder examples such as `<secret-id>` as okay, but do not print or commit real secrets.

If the user asked for the full sync to GitHub:

```bash
git -C "$repo" add README.md bootstrap.sh sync-from-codex.sh skills
git -C "$repo" commit -m "update codex skills"
git -C "$repo" push
```

Use a more specific commit message when the change is narrow.

## Duplicate Skill Cleanup

If old backups under `$CODEX_HOME/skills` are being discovered as duplicate skills, move them outside the scanned directory:

```bash
target="${CODEX_HOME:-$HOME/.codex}/skills"
backup_root="$(dirname "$target")/skill-backups/legacy-$(date +%Y%m%d%H%M%S)"
mkdir -p "$backup_root"
for path in "$target"/*.backup-*; do
  [ -e "$path" ] || [ -L "$path" ] || continue
  mv "$path" "$backup_root/"
done
```
