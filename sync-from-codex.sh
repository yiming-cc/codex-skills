#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_skills_dir="$repo_dir/skills"
source_dir="${SKILL_SOURCE:-${CODEX_HOME:-$HOME/.codex}/skills}"
sync_mode="${SKILL_SYNC_MODE:-keep}"

usage() {
  cat <<'USAGE'
Usage: sync-from-codex.sh [--keep-existing|--overwrite] [--source-dir DIR]

Options:
  --keep-existing  Keep a same-named skill that already exists in this repo.
                   This is the default.
  --overwrite      Replace a same-named repo skill with the Codex-local version.
  --source-dir DIR Read skills from DIR instead of $CODEX_HOME/skills.
  -h, --help       Show this help.

Environment:
  SKILL_SYNC_MODE=keep|overwrite
  SKILL_SOURCE=/path/to/codex/skills
USAGE
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --keep-existing|--keep)
      sync_mode="keep"
      ;;
    --overwrite)
      sync_mode="overwrite"
      ;;
    --source-dir)
      shift
      if [ "$#" -eq 0 ]; then
        echo "--source-dir requires a directory" >&2
        exit 1
      fi
      source_dir="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 1
      ;;
  esac

  shift
done

case "$sync_mode" in
  keep|overwrite)
    ;;
  *)
    echo "invalid sync mode: $sync_mode" >&2
    exit 1
    ;;
esac

abs_dir() {
  cd "$1" && pwd -P
}

copy_skill() {
  local source="$1"
  local dest="$2"

  rm -rf "$dest"
  cp -aL "$source" "$dest"
  find "$dest" -type d -name __pycache__ -prune -exec rm -rf {} +
  find "$dest" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
}

if [ ! -d "$source_dir" ]; then
  echo "missing Codex skills directory: $source_dir" >&2
  exit 1
fi

mkdir -p "$repo_skills_dir"

handled=0
copied=0
kept=0
unchanged=0
for skill_dir in "$source_dir"/*; do
  [ -d "$skill_dir" ] || continue

  skill_name="$(basename "$skill_dir")"
  repo_skill_dir="$repo_skills_dir/$skill_name"

  case "$skill_name" in
    .*|*.backup-*)
      continue
      ;;
  esac

  if [ ! -f "$skill_dir/SKILL.md" ]; then
    echo "skip $skill_name: missing SKILL.md"
    continue
  fi

  if [ -d "$repo_skill_dir" ] && [ "$(abs_dir "$skill_dir")" = "$(abs_dir "$repo_skill_dir")" ]; then
    echo "ok $skill_name already managed by this repo"
    unchanged=$((unchanged + 1))
    handled=$((handled + 1))
    continue
  fi

  if [ -e "$repo_skill_dir" ] || [ -L "$repo_skill_dir" ]; then
    if [ "$sync_mode" = "keep" ]; then
      echo "keep repo $skill_name at $repo_skill_dir"
      kept=$((kept + 1))
      handled=$((handled + 1))
      continue
    fi
  fi

  copy_skill "$skill_dir" "$repo_skill_dir"
  echo "copy $skill_name -> $repo_skill_dir"
  copied=$((copied + 1))
  handled=$((handled + 1))
done

if [ "$handled" -eq 0 ]; then
  echo "no skills synced from $source_dir" >&2
  exit 1
fi

echo "Handled $handled skill(s) from $source_dir: copied $copied, kept $kept, unchanged $unchanged."

